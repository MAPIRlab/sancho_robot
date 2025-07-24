import math
import os
import threading

import rclpy
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from lifecycle_msgs.msg import Transition
from lifecycle_msgs.srv import ChangeState
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sancho_msgs.action import PlayAudio
from sancho_msgs.msg import FaceArray
from sancho_msgs.srv import SocialState
from std_msgs.msg import Float32
from tf_transformations import (
    quaternion_from_euler,  # Asegúrate de que este paquete está instalado
)


class IMState:
    """Interface for InteractionManager states."""

    def __init__(self, manager: "InteractionManager") -> None:
        self.manager = manager

    def enter(self) -> None:
        """Hook executed when the state is entered."""

    def execute(self) -> None:
        """Main logic executed periodically by the manager."""

    def exit(self) -> None:
        """Cleanup executed when leaving the state."""


class InteractionManager(LifecycleNode):
    """Manages the interaction flow of a robot with a user by coordinating various modules
    such as face detection, face tracking, audio processing, and head movement.

    This class implements a ROS 2 LifecycleNode, allowing it to be managed (configured,
    activated, deactivated, cleaned up) by a lifecycle manager. It operates as a state
    machine, transitioning through different states to achieve a complete interaction
    sequence: detecting a user, orienting towards them, playing an audio message,
    and then returning to an idle state.

    Key functionalities:
    -   **State Machine:** Controls the interaction logic through a series of defined states.
    -   **Module Management:** Manages the lifecycle (activation/deactivation) of external
        ROS 2 nodes (e.g., face detector, face tracker, audio player).
    -   **Face Detection & Selection:** Subscribes to face detection messages and selects
        the "best" face based on confidence and size thresholds.
    -   **Sound Source Localization (TDOA):** Subscribes to TDOA (Time Difference of Arrival)
        angle data to orient the robot's head towards a sound source as a fallback mechanism.
    -   **Head Movement:** Publishes `PoseStamped` messages to control the robot's head
        orientation.
    -   **Audio Playback:** Uses a ROS 2 action client to request playback of pre-recorded
        audio messages.
    -   **Social State Reporting:** Communicates the status of the social interaction (ready,
        finished, error) via a ROS 2 service client.

    Parameters
    ----------
        -   `face_size_threshold`: Minimum relative width of a face to be considered valid.
        -   `face_confidence_threshold`: Minimum confidence score for a face detection.
        -   `max_face_attempts`: Number of attempts to find a face before fallback.
        -   `tdoa_angle_limit`: Maximum absolute TDOA angle to consider for head rotation.
        -   `rotation_speed`: (Not directly used in this snippet, but declared) Speed for head rotation.
        -   `rotation_duration`: (Not directly used in this snippet, but declared) Duration for head rotation.
        -   `head_movement_topic`: Topic for publishing head movement commands.
        -   `audio_angle_topic`: Topic for TDOA angle subscription.
        -   `lifecycle_timeout`: Default timeout for lifecycle service calls.
        -   `tdoa_timeout`: Timeout for waiting for a TDOA message.
        -   `fallback_max_attempts`: Maximum attempts for fallback mechanisms.
        -   `fallback_retry_backoff`: Exponential backoff factor for retries.
        -   `face_detection_topic`: Topic for face detection messages.

    Subscriptions:
        -   `face_detection_topic` (sensor_interfaces/msg/FaceArray): Receives face detections.
        -   `audio_angle_topic` (std_msgs/msg/Float32): Receives TDOA angle.

    Publishers:
        -   `head_movement_topic` (geometry_msgs/msg/PoseStamped): Publishes head orientation goals.

    Action Clients:
        -   `/play_audio` (sancho_interfaces/action/PlayAudio): To request audio playback.

    Service Clients:
        -   `{module_name}/change_state` (lifecycle_msgs/srv/ChangeState): To manage lifecycle of modules.
        -   `/social_state` (sancho_interfaces/srv/SocialState): To report social interaction status.

    The interaction flow typically involves:
    1.  Activating the face detector.
    2.  Searching for a face.
    3.  If no face is found, falling back to TDOA to locate a sound source.
    4.  Tracking the face (or orienting via TDOA) and playing an audio message.
    5.  Deactivating all modules and returning to an idle state.

    """

    # Estados de la state machine
    (STATE_SOCIAL_READY, STATE_SOCIAL_FINISHED, STATE_SOCIAL_ERROR) = range(3)

    def __init__(self):

        super().__init__("interaction_manager")
        # Callback groups para separar lifecycle / IO
        self.life_cb = ReentrantCallbackGroup()
        self.io_cb = ReentrantCallbackGroup()

        package_name = "sancho_interaction"
        package_path = get_package_share_directory(package_name)
        relative_speach_file_path = "audios/audio_tts_xtts.wav"
        self.speech_file_path = os.path.join(package_path, relative_speach_file_path)

        # Parámetros
        self.declare_parameter("face_size_threshold", 0.1)
        self.declare_parameter("face_confidence_threshold", 0.7)
        self.declare_parameter("max_face_attempts", 3)
        self.declare_parameter("tdoa_angle_limit", 90.0)
        self.declare_parameter("rotation_speed", 0.3)
        self.declare_parameter("rotation_duration", 2.0)
        self.declare_parameter("head_movement_topic", "/head_goal")
        self.declare_parameter("audio_angle_topic", "/audio/angle")
        self.declare_parameter("lifecycle_timeout", 5.0)
        self.declare_parameter("tdoa_timeout", 5.0)
        self.declare_parameter("fallback_max_attempts", 3)
        self.declare_parameter(
            "fallback_retry_backoff", 1.5
        )  # factor de exponenciación
        self.declare_parameter("face_detection_topic", "/face_detections")
        # Módulos a gestionar
        self.modules = ["/face_detector", "/face_tracker", "/audio_player"]
        self.module_clients = {}
        self.active_modules = set()

        # QoS
        self.sensor_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.control_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

        # Subscriptions y publishers (inactivas al principio)
        self.face_sub = None
        self.tdoa_sub = None
        self.cmd_vel = None

        # Action client
        self.audio_action = None

        # Variables de runtime
        self.face_msgs = []
        self.tdoa_angle = None
        self.attempt = 0
        self.best_face = None

        # Máquina de estados
        self.current_state: IMState | None = None
        self.wait_timer = None
        self.main_timer = None
        self.transition_to(IdleState)

        self.get_logger().info("InteractionManager (sync) creado")

    def transition_to(self, state_cls: type[IMState]) -> None:
        """Change current state."""
        if self.current_state:
            self.current_state.exit()
        self.current_state = state_cls(self)
        self.current_state.enter()

    # ------------------------------------------------------------
    # Lifecycle callbacks
    # ------------------------------------------------------------
    def on_configure(self, state):
        self.get_logger().info("Configuring InteractionManager")

        # Leer parámetros
        self.max_attempts = self.get_parameter("max_face_attempts").value
        self.face_size_threshold = self.get_parameter("face_size_threshold").value
        self.face_confidence_threshold = self.get_parameter(
            "face_confidence_threshold"
        ).value
        self.tdoa_angle_limit = self.get_parameter("tdoa_angle_limit").value
        self.rotation_speed = self.get_parameter("rotation_speed").value
        self.rotation_duration = self.get_parameter("rotation_duration").value
        self.head_movement_topic = self.get_parameter("head_movement_topic").value
        self.audio_angle_topic = self.get_parameter("audio_angle_topic").value
        self.face_detection_topic = self.get_parameter("face_detection_topic").value
        self.lifecycle_timeout = self.get_parameter("lifecycle_timeout").value
        self.tdoa_timeout = self.get_parameter("tdoa_timeout").value
        self.fallback_max_attempts = self.get_parameter("fallback_max_attempts").value
        self.backoff_factor = self.get_parameter("fallback_retry_backoff").value

        self.get_logger().info("Parámetros configurados: ")
        # Crear clients de ciclo de vida para cada módulo
        for m in self.modules:
            cli = self.create_client(
                ChangeState, f"{m}/change_state", callback_group=self.life_cb
            )
            if not cli.wait_for_service(timeout_sec=5.0):
                self.get_logger().error(f"No se encontró el servicio {m}/change_state")
                return TransitionCallbackReturn.FAILURE
            self.module_clients[m] = cli
            self.get_logger().info(f"Cliente de lifecycle para {m} listo")
        self.get_logger().info("Todos los clientes de lifecycle creados")
        # Publisher de head_movement_pub (lifecycle)
        self.head_movement_pub = self.create_lifecycle_publisher(
            PoseStamped, self.head_movement_topic, 10, callback_group=self.life_cb
        )
        self.get_logger().info(
            f"Publisher de head_movement en {self.head_movement_topic} listo"
        )
        # Action client para audio
        self.audio_action = ActionClient(
            self, PlayAudio, "/play_audio", callback_group=self.life_cb
        )

        self.social_state_client = self.create_client(
            SocialState, "/social_state", callback_group=self.life_cb
        )

        self.get_logger().info("InteractionManager configurado")
        return super().on_configure(state)

    def on_activate(self, state):
        self.get_logger().info("Activando interacción (sync)")
        # Subscriptions de sensores
        self.face_sub = self.create_subscription(
            FaceArray,
            self.face_detection_topic,
            callback=self._face_cb,
            qos_profile=self.sensor_qos,
            callback_group=self.io_cb,
        )

        self.audio_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)

        # SUSCRIPCIÓN CORRECTA PARA /audio/angle
        self.tdoa_sub = self.create_subscription(
            Float32,
            self.audio_angle_topic,
            callback=self._tdoa_cb,
            qos_profile=self.audio_qos,
            callback_group=self.io_cb,
        )

        # Iniciar máquina de estados en primer estado útil
        self.transition_to(ActivateFaceDetectorState)
        self.main_timer = self.create_timer(0.1, self._run_state)
        return super().on_activate(state)

    def on_deactivate(self, state):
        self.get_logger().info("Desactivando interacción (sync)")
        if self.main_timer:
            self.main_timer.cancel()
            self.main_timer = None
        # Destruir subscriptions
        if self.face_sub:
            self.destroy_subscription(self.face_sub)
            self.face_sub = None
        if self.tdoa_sub:
            self.destroy_subscription(self.tdoa_sub)
            self.tdoa_sub = None
        self.face_msgs = None
        self.tdoa_angle = None

        return super().on_deactivate(state)

    def on_cleanup(self, state):
        self.get_logger().info("Desactivando interacción (sync)")
        if self.main_timer:
            self.main_timer.cancel()
            self.main_timer = None
        # Destruir subscriptions
        if self.face_sub:
            self.destroy_subscription(self.face_sub)
            self.face_sub = None
        if self.tdoa_sub:
            self.destroy_subscription(self.tdoa_sub)
            self.tdoa_sub = None
        # Publisher y clients
        if self.head_movement_pub:
            self.destroy_lifecycle_publisher(self.head_movement_pub)
            self.head_movement_pub = None
        for cli in self.module_clients.values():
            self.destroy_client(cli)
        self.module_clients.clear()
        return super().on_cleanup(state)

    # ------------------------------------------------------------
    # Callbacks de sensores
    # ------------------------------------------------------------
    def _face_cb(self, msg: FaceArray):
        self.face_msgs = msg.faces

    def _tdoa_cb(self, msg: Float32):
        self.tdoa_angle = msg.data

    # ------------------------------------------------------------
    # Utils sync: llamar servicio de lifecycle
    # ------------------------------------------------------------
    def call_lifecycle(
        self, module: str, transition_id: int, timeout_sec: float = 5.0
    ) -> bool:
        self.get_logger().info(f"Llamando a {module} transición {transition_id}")
        cli = self.module_clients.get(module)
        if cli is None:
            self.get_logger().error(f"Cliente inexistente: {module}")
            return False
        req = ChangeState.Request()
        req.transition.id = transition_id
        future = cli.call_async(req)
        # Evento para señalizar que el Future ha terminado
        done_evt = threading.Event()

        def _on_done(fut):
            done_evt.set()

        future.add_done_callback(_on_done)  # no bloquea el executor

        # Esperamos hasta que self o el executor procesen la respuesta
        timeout = timeout_sec or self.lifecycle_timeout
        if not done_evt.wait(timeout):
            self.get_logger().error(
                f"Timeout al esperar {module} transición {transition_id}"
            )
            return False

        # Comprobamos resultado
        result = future.result()
        if result is None or not result.success:
            self.get_logger().error(f"{module} transición {transition_id} fallida")
            return False

        if transition_id == Transition.TRANSITION_ACTIVATE:
            self.active_modules.add(module)
            self.get_logger().info(f"{module} añadido a active_modules")
        elif transition_id == Transition.TRANSITION_DEACTIVATE:
            self.active_modules.discard(module)
            self.get_logger().info(f"{module} eliminado de active_modules")

        self.get_logger().info(f"{module} transición {transition_id} completada")
        return True

    # ------------------------------------------------------------
    # State machine
    # ------------------------------------------------------------
    def _run_state(self):
        """Execute the current state."""
        if self.current_state:
            self.current_state.execute()

    def _get_latest_tdoa(self, timeout_sec: float) -> float | None:
        """Usa la suscripción permanente self.tdoa_sub. Espera hasta que self.tdoa_angle
        sea distinto de None o se cumpla el timeout.
        """
        # Limpiamos cualquier dato previo
        self.tdoa_angle = None
        start_time = self.get_clock().now().nanoseconds

        # Mientras no haya dato y no se exceda el timeout
        while rclpy.ok():
            # Si la callback _tdoa_cb ya escribió algo, lo devolvemos
            if self.tdoa_angle is not None:
                return self.tdoa_angle

            # Comprobamos si se ha excedido el timeout
            elapsed = (self.get_clock().now().nanoseconds - start_time) / 1e9
            if elapsed >= timeout_sec:
                self.get_logger().warn(f"No llegó TDOA en {timeout_sec:.2f}s")
                return None

            # Permitimos que otros callbacks (incluyendo _tdoa_cb) se procesen
            rclpy.spin_once(self, timeout_sec=0.01)

        return None

    def _on_tdoa_wait_complete(self):
        # cancelamos el temporizador y volvemos a STATE_FALLBACK_TDOA
        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None
        self.main_timer = self.create_timer(0.1, self._run_state)
        self.transition_to(FallbackTdoaState)

    def _on_audio_goal_response(self, future):
        """Callback cuando el action server acepta (o no) el goal."""
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("Audio goal rechazado :(")
            # decides si vuelves a un estado de error o directamente deactivas
            self.fail_social_service_call()  # Llamada al servicio social_state con error

            self.transition_to(DeactivateAllState)
            return

        # si lo acepta, esperamos el resultado:
        result_fut = goal_handle.get_result_async()
        result_fut.add_done_callback(self._on_audio_result)

    def _on_audio_result(self, future):
        """Callback cuando termina la reproducción de audio."""
        result = future.result().result  # .result() es del ActionResult
        if result.success:
            self.get_logger().info("Audio reproducido OK")
            req = SocialState.Request()
            req.state = self.STATE_SOCIAL_FINISHED
            self.social_state_client.call_async(req)  # Llamada al servicio social_state
        else:
            self.get_logger().error("Falló reproducción de audio")
            self.fail_social_service_call()  # Llamada al servicio social_state con error
        # ahora continuamos: desactivamos módulos y terminamos
        self.transition_to(DeactivateAllState)

    def fail_social_service_call(self):
        """Llamada al servicio social_state con estado de error."""
        req = SocialState.Request()
        req.state = self.STATE_SOCIAL_ERROR
        self.social_state_client.call_async(req)

    def _on_wait_complete(self):
        # reactivar el main_timer
        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None
        self.main_timer = self.create_timer(0.1, self._run_state)
        self.transition_to(SearchFaceState)

    # Funciion para apagar todos los modulos comprobando si estan activos
    def _deactivate_all_modules(self):
        self.get_logger().info("Desactivando módulos activos...")
        for m in list(self.active_modules):
            if self.call_lifecycle(m, Transition.TRANSITION_DEACTIVATE):
                self.get_logger().info(f"{m} desactivado correctamente")
                # Eliminar el módulo de module_clients tras desactivarlo correctamente
                self.active_modules.discard(m)
            else:
                self.get_logger().error(f"Error al desactivar {m}")
        if not self.active_modules:
            self.get_logger().info("Todos los módulos desactivados")
        else:
            self.get_logger().warn(
                "No se pudieron desactivar todos los módulos. Módulos activos: "
                + ", ".join(self.active_modules)
            )
        self.get_logger().info("Desactivando este nodo...")
        self.trigger_deactivate()

    # ------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------
    def _select_best_face(self):
        best = None
        if not self.face_msgs:
            self.get_logger().warn("No hay mensajes de cara disponibles")
            return None
        for f in self.face_msgs:
            if (
                f.confidence >= self.face_confidence_threshold
                and f.width >= self.face_size_threshold
            ):
                if best is None or f.confidence > best.confidence:
                    best = f
        return best

    def _rotate_head(self, angle: float):
        # Convertir ángulo de grados a radianes
        angle_pan = math.radians(angle)
        angle_tilt = math.radians(30.0)  # Cabeza no inclina hacia arriba/abajo
        # Convertir a quaternion para rotación en Z
        q = quaternion_from_euler(0.0, -angle_tilt, angle_pan)

        # Crear mensaje PoseStamped
        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"  # Cambia según tu sistema
        msg.pose.position.x = 0.0
        msg.pose.position.y = 0.0
        msg.pose.position.z = 0.0
        msg.pose.orientation.x = q[0]
        msg.pose.orientation.y = q[1]
        msg.pose.orientation.z = q[2]
        msg.pose.orientation.w = q[3]

        self.get_logger().info(
            f"Publicando rotación de cabeza: {angle:.1f}° ({angle_pan:.2f} rad)"
        )
        self.head_movement_pub.publish(msg)


class IdleState(IMState):
    def enter(self) -> None:
        self.manager.get_logger().info("Estado IDLE")


class ActivateFaceDetectorState(IMState):
    def execute(self) -> None:
        mgr = self.manager
        if mgr.call_lifecycle("/face_detector", Transition.TRANSITION_ACTIVATE):
            mgr.get_logger().info("Face detector activado")
            mgr.attempt = 0
            mgr.transition_to(SearchFaceState)
            mgr.get_logger().info("Esperando detecciones de cara")
        else:
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)


class SearchFaceState(IMState):
    def execute(self) -> None:
        mgr = self.manager
        mgr.get_logger().info("Buscando cara")
        mgr.best_face = mgr._select_best_face()
        if mgr.best_face:
            mgr.get_logger().info("Cara encontrada!")
            mgr.transition_to(TrackAndAudioState)
        elif mgr.attempt < mgr.max_attempts:
            angle = (
                0.0
                if mgr.attempt == mgr.max_attempts - 1
                else (45.0 if mgr.attempt % 2 == 0 else -45.0)
            )
            mgr._rotate_head(angle)
            mgr.attempt += 1
            if mgr.main_timer:
                mgr.main_timer.cancel()
            mgr.wait_timer = mgr.create_timer(
                mgr.rotation_duration, mgr._on_wait_complete, callback_group=mgr.io_cb
            )
        else:
            mgr.get_logger().warn("No se encontró cara, fallback TDOA")
            mgr.transition_to(FallbackTdoaState)
            mgr.tdoa_angle = None
            mgr.tdoa_attempts = 0


class FallbackTdoaState(IMState):
    def execute(self) -> None:
        mgr = self.manager
        if mgr.tdoa_attempts < mgr.fallback_max_attempts:
            mgr.best_face = mgr._select_best_face()
            if mgr.best_face:
                mgr.transition_to(TrackAndAudioState)
                return
            angle = mgr.tdoa_angle
            if angle is None:
                mgr.get_logger().warn("Timeout esperando TDOA; reintentando fallback")
                mgr.tdoa_attempts += 1
                if mgr.main_timer:
                    mgr.main_timer.cancel()
                mgr.wait_timer = mgr.create_timer(
                    mgr.tdoa_timeout,
                    mgr._on_tdoa_wait_complete,
                    callback_group=mgr.io_cb,
                )
                return
            if abs(angle) <= mgr.tdoa_angle_limit:
                mgr.get_logger().info(f"Girando por TDOA: {angle:.1f}°")
                mgr._rotate_head(angle)
                mgr.tdoa_attempts += 1
                if mgr.main_timer:
                    mgr.main_timer.cancel()
                mgr.wait_timer = mgr.create_timer(
                    mgr.tdoa_timeout,
                    mgr._on_tdoa_wait_complete,
                    callback_group=mgr.io_cb,
                )
                return
            mgr.get_logger().warn(f"[TDOA] ángulo {angle:.1f}° fuera de límite")
        mgr.get_logger().warn("No se detectó persona tras TDOA, desactivando")
        mgr.fail_social_service_call()
        mgr.transition_to(DeactivateAllState)


class TrackAndAudioState(IMState):
    def execute(self) -> None:
        mgr = self.manager
        mgr.call_lifecycle("/face_tracker", Transition.TRANSITION_ACTIVATE)
        mgr.call_lifecycle("/audio_player", Transition.TRANSITION_ACTIVATE)
        goal = PlayAudio.Goal()
        goal.filename = mgr.speech_file_path
        send_goal_fut = mgr.audio_action.send_goal_async(goal)
        send_goal_fut.add_done_callback(mgr._on_audio_goal_response)
        mgr.transition_to(WaitAudioState)


class WaitAudioState(IMState):
    def execute(self) -> None:  # wait until callbacks complete
        pass


class DeactivateAllState(IMState):
    def execute(self) -> None:
        mgr = self.manager
        if mgr.main_timer:
            mgr.main_timer.cancel()
            mgr.main_timer = None
        mgr._deactivate_all_modules()
        mgr.transition_to(DoneState)


class DoneState(IMState):
    def execute(self) -> None:
        pass


def main(args=None):
    rclpy.init(args=args)
    node = InteractionManager()
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        node.destroy_node()
        rclpy.shutdown()
