import math
import os
import threading
from enum import IntEnum
from typing import Optional

import rclpy
from ament_index_python.packages import get_package_share_directory
from geometry_msgs.msg import PoseStamped
from lifecycle_msgs.msg import Transition, State
from lifecycle_msgs.srv import ChangeState, GetState
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sancho_msgs.msg import FaceDetectionArray, FaceRecognitionArray
from sancho_msgs.srv import GetCentralFaceCluster, SocialState, GreetPeople
from std_msgs.msg import Float32, Int16
from std_srvs.srv import Trigger
from tf_transformations import quaternion_from_euler

def clip(value: float, min_value: float, max_value: float) -> float:
    """Clamp value to the inclusive range [min_value, max_value]."""
    return max(min_value, min(value, max_value))


# ============================================================================
# CONSTANTS
# ============================================================================

class SocialStateEnum(IntEnum):
    """Social interaction states."""
    READY = 0
    FINISHED = 1
    ERROR = 2


class ModuleNames:
    """Names of managed modules."""
    FACE_DETECTOR = "/face_detector"
    FACE_RECOGNIZER = "/face_recognizer"
    FACE_MANAGER = "/face_manager"
    CENTRAL_FACE_CLUSTER = "/central_faces_cluster_node"
    # FACE_TRACKER = "/human_face_tracker"
    ASSISTANT_HELPER = "/assistant_helper"  # Placeholder for future lifecycle integration


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
        self.declare_parameter("audio_angle_topic", "/sancho_audio/doa")
        self.declare_parameter("lifecycle_timeout", 5.0)
        self.declare_parameter("tdoa_timeout", 5.0)
        self.declare_parameter("fallback_max_attempts", 3)
        self.declare_parameter("fallback_retry_backoff", 1.5)
        self.declare_parameter("face_detection_topic", "/face_detections")
        self.declare_parameter("face_recognition_topic", "/face_recognitions")
        self.declare_parameter(
            "central_face_cluster_service",
            "/central_faces_cluster_node/get_central_cluster",
        )
        self.declare_parameter("assistant_helper_greet_service_name", "assistant/greet_people")
        self.declare_parameter("assistant_finished_service_name", "assistant_finished")
        self.declare_parameter("assistant_helper_mode_topic", "sancho_audio/assistant_helper/mode")
        self.declare_parameter("assistant_helper_question_id", 1)
        self.declare_parameter("assistant_helper_timeout", 60.0)
        self.declare_parameter("assistant_helper_service_timeout", 10.0)
        self.declare_parameter("scan_angles", [0.0, 45.0, -45.0, 0.0])  # Scan pattern
        self.declare_parameter("min_faces_for_direct_interaction", 1)  # Min faces needed to skip TDOA
        self.declare_parameter("max_fallback_search_cycles", 3)  # Max fallback->search cycles before giving up
        self.declare_parameter("max_tdoa_wait_attempts", 3)  # Max attempts to wait for TDOA angle before giving up
        
        # Módulos gestionados directamente por este nodo
        self.modules = [
            # ModuleNames.FACE_TRACKER,
            ModuleNames.FACE_MANAGER,

        ]
        # Módulos externos que deben estar activos antes de continuar (no se activan aquí)
        self.required_external_modules = [
            ModuleNames.FACE_DETECTOR,
            ModuleNames.FACE_RECOGNIZER,
        ]
        self.module_clients = {}
        self.required_module_state_clients = {}
        self.active_modules = set()
        self.central_cluster_client = None
        self.assistant_helper_client = None
        self.assistant_finished_service = None
        self.assistant_helper_interaction_started = False
        self.assistant_helper_interaction_finished = False
        self.assistant_helper_start_time: Optional[float] = None
        self.assistant_helper_deadline: Optional[float] = None
        self.assistant_helper_target_ids: list[str] = []
        self.assistant_helper_target_names: list[str] = []
        self.assistant_helper_cluster_center = None
        self.assistant_helper_service_timeout = None

        # QoS
        self.sensor_qos = QoSProfile(depth=1, reliability=ReliabilityPolicy.BEST_EFFORT)
        self.control_qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.RELIABLE)

        # Subscriptions y publishers (inactivas al principio)
        self.face_sub = None
        self.tdoa_sub = None
        self.cmd_vel = None


        # Variables de runtime
        self.face_msgs = []
        self.tdoa_angle = None
        self.attempt = 0
        self.best_face = None
        self.faces_detected_during_scan = False  # Track if we saw any valid faces during scanning
        self.scan_positions = []  # Positions to scan: [0, 45, -45, 0] for example
        self.fallback_search_attempts = 0  # Track number of fallback->search cycles
        self.tdoa_wait_attempts = 0  # Track TDOA angle wait attempts within a fallback cycle

        # Máquina de estados
        self.current_state: IMState | None = None
        self.wait_timer = None
        self.main_timer = None
        self.transition_to(IdleState)

        self.get_logger().info("InteractionManager (sync) creado")

    def _assistant_finished_cb(self, request, response):
        """Callback for the service that assistant_helper calls when it's done."""
        self.get_logger().info("Assistant helper ha notificado su finalización.")
        self.assistant_helper_interaction_finished = True
        response.success = True
        response.message = "Notificación de finalización recibida."
        return response

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
        self.central_cluster_service_name = self.get_parameter("central_face_cluster_service").value
        self.assistant_helper_greet_service_name = self.get_parameter("assistant_helper_greet_service_name").value
        self.assistant_finished_service_name = self.get_parameter("assistant_finished_service_name").value
        self.assistant_helper_mode_topic = self.get_parameter("assistant_helper_mode_topic").value
        self.assistant_helper_question_id = int(self.get_parameter("assistant_helper_question_id").value)
        self.assistant_helper_timeout = float(self.get_parameter("assistant_helper_timeout").value)
        self.assistant_helper_service_timeout = float(self.get_parameter("assistant_helper_service_timeout").value)
        self.scan_angles = self.get_parameter("scan_angles").value
        self.min_faces_for_direct_interaction = int(self.get_parameter("min_faces_for_direct_interaction").value)
        self.max_fallback_search_cycles = int(self.get_parameter("max_fallback_search_cycles").value)
        self.max_tdoa_wait_attempts = int(self.get_parameter("max_tdoa_wait_attempts").value)

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

        # Clientes get_state para los módulos gestionados externamente
        for module in self.required_external_modules:
            state_cli = self.create_client(
                GetState, f"{module}/get_state", callback_group=self.life_cb
            )
            self.required_module_state_clients[module] = state_cli
            if state_cli.wait_for_service(timeout_sec=2.0):
                self.get_logger().info(f"Cliente de get_state para {module} listo")
            else:
                self.get_logger().warn(
                    f"Servicio {module}/get_state no disponible durante configure; se comprobará más adelante."
                )

        # Gestionar el lifecycle de módulos adicionales (face cluster y assistant helper)
       
        timeout_sec = 10.0
        for module in self.modules:
            cli = self.create_client(
                ChangeState,
                f"{module}/change_state",
                callback_group=self.life_cb,
            )
            
            if not cli.wait_for_service(timeout_sec=timeout_sec):
                self.get_logger().error(
                    f"No se pudo conectar con el servicio {module} "
                    f"en {timeout_sec} segundos. Abortando."
                )
                return TransitionCallbackReturn.FAILURE
            else:
                self.module_clients[module] = cli
                self.get_logger().info(
                    f"Cliente de lifecycle para {module} listo"
                )

        # Publisher de head_movement_pub (lifecycle)
        self.head_movement_pub = self.create_lifecycle_publisher(
            PoseStamped, self.head_movement_topic, 10, callback_group=self.life_cb
        )
        self.get_logger().info(
            f"Publisher de head_movement en {self.head_movement_topic} listo"
        )

        self.social_state_client = self.create_client(
            SocialState, "/social_state", callback_group=self.life_cb
        )
        
        # Cliente central_face_cluster =================
        self.central_cluster_client = self.create_client(
            GetCentralFaceCluster,
            self.central_cluster_service_name,
            callback_group=self.io_cb,
        )
        if not self.central_cluster_client.wait_for_service(timeout_sec=5.0):
            self.get_logger().warn(
                f"Servicio {self.central_cluster_service_name} no disponible durante configure; reintentaremos más tarde."
            )
        else:
            self.get_logger().info("Cliente de GetCentralFaceCluster listo")


        # Cliente greet_people del assistant helper =================
        self.assistant_helper_greet_client = self.create_client(
            GreetPeople,
            self.assistant_helper_greet_service_name,
            callback_group=self.io_cb,
        )
        if not self.assistant_helper_greet_client.wait_for_service(timeout_sec=2.0):
            self.get_logger().warn(
                f"Servicio {self.assistant_helper_greet_service_name} no disponible durante configure; "
                "se reintentará antes de lanzar la interacción. "
                "TODO: sincronizar con el servicio real del assistant helper."
            )
        
        # Servicio para que el assistant helper notifique que ha terminado
        self.assistant_finished_service = self.create_service(
            Trigger,
            self.assistant_finished_service_name,
            self._assistant_finished_cb,
            callback_group=self.io_cb,
        )
        self.get_logger().info(f"Servicio {self.assistant_finished_service_name} listo.")

        self.get_logger().info("InteractionManager configurado")
        return super().on_configure(state)

    def on_activate(self, state):
        self.get_logger().info("Activando interacción (sync)")
        # Subscriptions de sensores
        self.face_sub = self.create_subscription(
            FaceDetectionArray,
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

        self.deactivate_all_modules()

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
        for cli in self.required_module_state_clients.values():
            self.destroy_client(cli)
        self.required_module_state_clients.clear()
        if self.central_cluster_client:
            self.destroy_client(self.central_cluster_client)
            self.central_cluster_client = None
        if self.assistant_helper_client:
            self.destroy_client(self.assistant_helper_client)
            self.assistant_helper_client = None
        if self.assistant_finished_service:
            self.destroy_service(self.assistant_finished_service)
            self.assistant_finished_service = None

        return super().on_cleanup(state)

    # ------------------------------------------------------------
    # Callbacks de sensores
    # ------------------------------------------------------------
    def _face_cb(self, msg: FaceDetectionArray):
        """Callback for face detection messages."""
        self.face_msgs = msg.detections

    def _tdoa_cb(self, msg: Float32):
        """Callback for TDOA angle messages."""
        self.tdoa_angle = None if math.isnan(msg.data) else msg.data

    # ------------------------------------------------------------
    # Lifecycle management utilities
    # ------------------------------------------------------------
    def call_lifecycle(
        self, module: str, transition_id: int, timeout_sec: Optional[float] = None
    ) -> bool:
        """Call lifecycle transition on a managed module.
        
        Args:
            module: Module name (e.g., ModuleNames.FACE_TRACKER)
            transition_id: Transition ID from lifecycle_msgs
            timeout_sec: Timeout in seconds (uses default if None)
            
        Returns:
            True if transition succeeded, False otherwise
        """
        self.get_logger().info(f"Calling lifecycle transition {transition_id} on {module}")
        
        cli = self.module_clients.get(module)
        if cli is None:
            self.get_logger().error(f"Lifecycle client does not exist: {module}")
            return False
            
        req = ChangeState.Request()
        req.transition.id = transition_id
        future = cli.call_async(req)
        
        # Event to signal completion
        done_evt = threading.Event()
        future.add_done_callback(lambda _: done_evt.set())

        # Wait for response
        timeout = timeout_sec if timeout_sec is not None else self.lifecycle_timeout
        if not done_evt.wait(timeout):
            self.get_logger().error(
                f"Timeout waiting for {module} transition {transition_id}"
            )
            return False

        # Check result
        result = future.result()
        if result is None or not result.success:
            self.get_logger().error(f"{module} transition {transition_id} failed")
            return False

        # Update active modules tracking
        if transition_id == Transition.TRANSITION_ACTIVATE:
            self.active_modules.add(module)
            self.get_logger().info(f"{module} activated")
        elif transition_id == Transition.TRANSITION_DEACTIVATE:
            self.active_modules.discard(module)
            self.get_logger().info(f"{module} deactivated")

        self.get_logger().info(f"{module} transition {transition_id} completed")
        return True

    def activate_module(self, module: str) -> bool:
        """Activate a specific module."""
        return self.call_lifecycle(module, Transition.TRANSITION_ACTIVATE)

    def deactivate_module(self, module: str) -> bool:
        """Deactivate a specific module."""
        return self.call_lifecycle(module, Transition.TRANSITION_DEACTIVATE)

    def is_module_active(self, module: str) -> bool:
        """Check if the given lifecycle module is currently active."""
        client = self.required_module_state_clients.get(module)
        if client is None:
            self.get_logger().warn(
                f"No existe cliente get_state para {module}; asumiendo activo (placeholder). "
                "TODO: revisar configuración de lifecycle superior."
            )
            return True

        if not client.wait_for_service(timeout_sec=2.0):
            self.get_logger().error(
                f"No se pudo contactar con {module}/get_state para verificar su estado."
            )
            return False

        req = GetState.Request()
        future = client.call_async(req)
        done_evt = threading.Event()
        future.add_done_callback(lambda _: done_evt.set())

        timeout = self.lifecycle_timeout
        if not done_evt.wait(timeout):
            self.get_logger().error(
                f"Timeout consultando el estado actual de {module}"
            )
            return False

        response = future.result()
        if response is None:
            self.get_logger().error(f"Respuesta vacía de {module}/get_state")
            return False

        if response.current_state.id != State.PRIMARY_STATE_ACTIVE:
            self.get_logger().warn(
                f"{module} no está ACTIVE (estado actual: {response.current_state.label})"
            )
            return False

        return True

    def check_active_face_detection_pipeline(self) -> bool:
        """Verify detector, recognizer, and manager are already active (no activation here)."""
        all_active = True
        for module in self.required_external_modules:
            if not self.is_module_active(module):
                self.get_logger().error(
                    f"El módulo requerido {module} no está activo; abortando pipeline."
                )
                all_active = False
        if all_active:
            self.get_logger().debug("Face detection pipeline verificada como activa.")
        return all_active

    # def activate_face_tracking(self) -> bool:
    #     """Activate face tracker module."""
    #     return self.activate_module(ModuleNames.FACE_TRACKER)

    def deactivate_all_modules(self) -> bool:
        """Deactivate all active modules."""
        self.get_logger().info("Deactivating all active modules...")
        success = True
        for module in list(self.active_modules):
            if not self.deactivate_module(module):
                self.get_logger().error(f"Failed to deactivate {module}")
                success = False
        return success

    def reset_assistant_helper_context(self) -> None:
        """Reset assistant helper tracking state."""
        self.assistant_helper_interaction_started = False
        self.assistant_helper_interaction_finished = False
        self.assistant_helper_start_time = None
        self.assistant_helper_deadline = None
        self.assistant_helper_target_ids.clear()
        self.assistant_helper_target_names.clear()
        self.assistant_helper_cluster_center = None

    def ensure_central_face_cluster_ready(self) -> bool:
        """Ensure the central face cluster node is active before requesting data."""
        module = ModuleNames.CENTRAL_FACE_CLUSTER
        if module in self.module_clients:
            self.get_logger().info(
                "Activando central_face_cluster vía lifecycle antes de consultar el servicio..."
            )
            if not self.activate_module(module):
                self.get_logger().error(
                    "Fallo al activar central_face_cluster mediante lifecycle."
                )
                return False
        else:
            self.get_logger().info(
                "central_face_cluster se asume activo (placeholder). "
                "TODO: eliminar esta asunción cuando exista lifecycle."
            )
        return True

    def fetch_central_face_cluster(self) -> bool:
        """Fetch central face cluster to determine user IDs for the assistant helper."""
        if self.central_cluster_client is None:
            self.get_logger().error("Cliente de GetCentralFaceCluster no inicializado")
            return False

        if not self.central_cluster_client.wait_for_service(
            timeout_sec=self.assistant_helper_service_timeout
        ):
            self.get_logger().error(
                f"Servicio {self.central_cluster_service_name} no disponible"
            )
            return False

        req = GetCentralFaceCluster.Request()
        future = self.central_cluster_client.call_async(req)
        done_evt = threading.Event()
        future.add_done_callback(lambda _: done_evt.set())

        if not done_evt.wait(self.assistant_helper_service_timeout):
            self.get_logger().error(
                f"Timeout esperando respuesta de {self.central_cluster_service_name}"
            )
            return False

        response = future.result()
        if response is None:
            self.get_logger().error(
                f"Respuesta vacía al llamar {self.central_cluster_service_name}"
            )
            return False

        ids = list(response.ids)
        names = list(response.names)
        if not ids:
            self.get_logger().warn(
                "GetCentralFaceCluster no retornó IDs válidos para iniciar assistant helper"
            )
            return False

        self.assistant_helper_target_ids = ids
        self.assistant_helper_target_names = names
        self.assistant_helper_cluster_center = response.cluster_center

        self.get_logger().info(
            f"Cluster central obtenido. IDs: {ids} Names: {names} "
            f"Centro: ({response.cluster_center.x:.1f}, {response.cluster_center.y:.1f})"
        )
        return True

    def start_assistant_interaction(self) -> bool:
        """Trigger the assistant helper service with the detected user information."""
        if not self.assistant_helper_target_names:
            self.get_logger().error(
                "No hay nombres para enviar al assistant helper; abortando la interacción."
            )
            return False

        if self.assistant_helper_greet_client is None:
            self.get_logger().warn(
                "Cliente de servicio del assistant helper no inicializado. "
            )
            return False

        if not self.assistant_helper_greet_client.wait_for_service(
            timeout_sec=self.assistant_helper_service_timeout
        ):
            self.get_logger().error(
                f"Servicio {self.assistant_helper_greet_service_name} no disponible al iniciar la interacción."
            )
            return False

        req = GreetPeople.Request()
        req.ids = self.assistant_helper_target_ids
        req.names = self.assistant_helper_target_names

        future = self.assistant_helper_greet_client.call_async(req)
        done_evt = threading.Event()
        future.add_done_callback(lambda _: done_evt.set())

        if not done_evt.wait(self.assistant_helper_service_timeout):
            self.get_logger().error(
                f"Timeout esperando respuesta del servicio {self.assistant_helper_greet_service_name}"
            )
            return False
        
        response = future.result()
        if response is None:
            self.get_logger().error(
                f"Respuesta vacía al llamar {self.assistant_helper_greet_service_name}"
            )
            return False

        if not response.accepted:
            self.get_logger().error(
                "Assistant helper rechazó la interacción solicitada."
            )
            return False

        now_sec = self.get_clock().now().nanoseconds / 1e9
        self.assistant_helper_interaction_started = True
        self.assistant_helper_start_time = now_sec
        self.assistant_helper_deadline = now_sec + self.assistant_helper_timeout
        self.get_logger().info(
            f"Assistant helper aceptó la interacción para: {self.assistant_helper_target_names}"
        )
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
        """Callback when audio playback completes."""
        result = future.result().result
        if result.success:
            self.get_logger().info("Audio playback completed successfully")
            self.success_social_service_call()
        else:
            self.get_logger().error("Audio playback failed")
            self.fail_social_service_call()
        
        # Continue to deactivate modules and finish
        self.transition_to(DeactivateAllState)

    def fail_social_service_call(self):
        """Call social_state service with error state."""
        req = SocialState.Request()
        req.state = SocialStateEnum.ERROR
        self.social_state_client.call_async(req)
        self.get_logger().error("Social state set to ERROR")

    def success_social_service_call(self):
        """Call social_state service with finished state."""
        req = SocialState.Request()
        req.state = SocialStateEnum.FINISHED
        self.social_state_client.call_async(req)
        self.get_logger().info("Social state set to FINISHED")

    def _on_wait_complete(self):
        # reactivar el main_timer
        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None
        self.main_timer = self.create_timer(0.1, self._run_state)
        # Stay in SearchFaceState to continue scanning

    def _on_tdoa_oriented_complete(self):
        """Callback when TDOA orientation is complete, return to SearchFaceState for full scan."""
        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None
        self.main_timer = self.create_timer(0.1, self._run_state)
        self.transition_to(SearchFaceState)

    def _on_tdoa_scan_ready(self):
        """Callback when TDOA orientation is complete and ready to start scanning."""
        if self.wait_timer:
            self.wait_timer.cancel()
            self.wait_timer = None
        self.main_timer = self.create_timer(0.1, self._run_state)
        # Stay in FallbackTdoaState, now in scanning phase

    

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

    def _has_valid_faces(self):
        """Check if there are any valid faces in current detection messages."""
        if not self.face_msgs:
            return False
        
        self.get_logger().info(f"Se han recibido este numero de caras: {len(self.face_msgs)}")
        for f in self.face_msgs:
            if (
                f.confidence >= self.face_confidence_threshold
                and f.width >= self.face_size_threshold
            ):
                return True
        return False

    def _rotate_head(self, angle: float):
        # Convertir ángulo de grados a radianes
        angle_pan = math.radians(angle)
        # Clipping angle to limit -100 to 100 degrees
        angle_pan = max(min(angle_pan, math.radians(100.0)), math.radians(-100.0))
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
    """State to verify the face detection pipeline is already active."""
    
    def enter(self) -> None:
        self.manager.get_logger().info("Verificando que el pipeline de detección facial esté activo...")
    
    def execute(self) -> None:
        mgr = self.manager
        if mgr.check_active_face_detection_pipeline():
            mgr.get_logger().info("Pipeline de detección facial listo")
            # Reset scan variables
            mgr.attempt = 0
            mgr.tdoa_attempts = 0
            mgr.faces_detected_during_scan = False
            mgr.scan_positions = []
            mgr.fallback_search_attempts = 0
            mgr.tdoa_wait_attempts = 0
            mgr.transition_to(SearchFaceState)
        else:
            mgr.get_logger().error("El pipeline de detección facial no está listo")
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)


class SearchFaceState(IMState):
    """State to search for faces by scanning multiple positions."""
    
    def enter(self) -> None:
        mgr = self.manager
        if mgr.fallback_search_attempts > 0:
            mgr.get_logger().info(
                f"Iniciando escaneo de caras (intento post-fallback {mgr.fallback_search_attempts}/{mgr.max_fallback_search_cycles})..."
            )
        else:
            mgr.get_logger().info("Iniciando escaneo inicial de caras...")
        
        mgr.scan_positions = list(mgr.scan_angles)
        mgr.faces_detected_during_scan = False
        mgr.attempt = 0
    
    def execute(self) -> None:
        mgr = self.manager
        
        # Check if we found valid faces at current position
        if mgr._has_valid_faces():
            mgr.faces_detected_during_scan = True
            mgr.get_logger().info(f"Caras válidas detectadas en posición {mgr.attempt}")
        
        # Check if scan is complete
        if mgr.attempt >= len(mgr.scan_positions):
            if mgr.faces_detected_during_scan:
                mgr.get_logger().info(
                    f"Escaneo completo. Se detectaron caras válidas. "
                    "Procediendo a iniciar assistant helper..."
                )
                mgr.transition_to(StartAssistantHelperState)
            else:
                mgr.get_logger().warn(
                    "Escaneo completo sin detectar caras válidas. "
                    "Cambiando a fallback TDOA..."
                )
                mgr.transition_to(FallbackTdoaState)
            return
        
        # Move to next scan position
        angle = mgr.scan_positions[mgr.attempt]
        mgr._rotate_head(angle)
        mgr.get_logger().info(
            f"Escaneando posición {mgr.attempt + 1}/{len(mgr.scan_positions)}: {angle}°"
        )
        mgr.attempt += 1
        
        # Wait for rotation to complete and detection to update
        if mgr.main_timer:
            mgr.main_timer.cancel()
            mgr.main_timer = None
        mgr.wait_timer = mgr.create_timer(
            mgr.rotation_duration, mgr._on_wait_complete, callback_group=mgr.io_cb
        )


class FallbackTdoaState(IMState):
    """State to use TDOA (Time Difference of Arrival) as fallback for face detection.
    Orients head towards sound source, then returns to SearchFaceState for full scan."""
    
    def enter(self) -> None:
        mgr = self.manager
        mgr.get_logger().info(
            f"Entrando en modo fallback TDOA (ciclo {mgr.fallback_search_attempts + 1}/{mgr.max_fallback_search_cycles})..."
        )
        mgr.tdoa_angle = None  # Reset TDOA angle for fresh reading
        mgr.tdoa_wait_attempts = 0  # Reset wait attempts counter
        self._tdoa_oriented = False
    
    def execute(self) -> None:
        mgr = self.manager
        
        # Check if we've exhausted fallback cycles
        if mgr.fallback_search_attempts >= mgr.max_fallback_search_cycles:
            mgr.get_logger().error(
                f"Se agotaron todos los ciclos de fallback ({mgr.max_fallback_search_cycles}). "
                "Finalizando interacción."
            )
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)
            return
        
        # If already oriented, shouldn't happen but safeguard
        if self._tdoa_oriented:
            return
        
        # Try to get TDOA angle
        angle = mgr.tdoa_angle
        if angle is None:
            # Check if we've exceeded max wait attempts
            if mgr.tdoa_wait_attempts >= mgr.max_tdoa_wait_attempts:
                mgr.get_logger().error(
                    f"No se recibió ángulo TDOA válido después de {mgr.max_tdoa_wait_attempts} intentos. "
                    "Finalizando interacción."
                )
                mgr.fail_social_service_call()
                mgr.transition_to(DeactivateAllState)
                return
            
            mgr.tdoa_wait_attempts += 1
            mgr.get_logger().info(
                f"Esperando datos de TDOA (ángulo de voz)... "
                f"Intento {mgr.tdoa_wait_attempts}/{mgr.max_tdoa_wait_attempts}"
            )
            # Wait for TDOA data with timeout
            if mgr.main_timer:
                mgr.main_timer.cancel()
                mgr.main_timer = None
            mgr.wait_timer = mgr.create_timer(
                mgr.tdoa_timeout,
                mgr._on_tdoa_wait_complete,
                callback_group=mgr.io_cb,
            )
            return
        
        # Check angle validity
        if abs(angle) > mgr.tdoa_angle_limit:
            mgr.get_logger().warn(
                f"TDOA angle {angle:.1f}° excede el límite de {mgr.tdoa_angle_limit}°. "
                "Reintentando..."
            )
            mgr.tdoa_angle = None  # Reset for next attempt
            
            # Check if we've exceeded max wait attempts for invalid angles
            if mgr.tdoa_wait_attempts >= mgr.max_tdoa_wait_attempts:
                mgr.get_logger().error(
                    f"No se recibió ángulo TDOA válido después de {mgr.max_tdoa_wait_attempts} intentos. "
                    "Finalizando interacción."
                )
                mgr.fail_social_service_call()
                mgr.transition_to(DeactivateAllState)
                return
            
            mgr.tdoa_wait_attempts += 1
            if mgr.main_timer:
                mgr.main_timer.cancel()
                mgr.main_timer = None
            mgr.wait_timer = mgr.create_timer(
                mgr.tdoa_timeout,
                mgr._on_tdoa_wait_complete,
                callback_group=mgr.io_cb,
            )
            return
        
        # Valid TDOA angle - orient head and then go back to SearchFaceState
        mgr.get_logger().info(
            f"Orientando cabeza hacia TDOA angle: {angle:.1f}°. "
            f"Luego se realizará escaneo completo (ciclo {mgr.fallback_search_attempts + 1})."
        )
        mgr._rotate_head(angle)
        self._tdoa_oriented = True
        mgr.fallback_search_attempts += 1
        
        # Wait for rotation, then return to SearchFaceState
        if mgr.main_timer:
            mgr.main_timer.cancel()
            mgr.main_timer = None
        mgr.wait_timer = mgr.create_timer(
            mgr.rotation_duration,
            mgr._on_tdoa_oriented_complete,
            callback_group=mgr.io_cb,
        )


class StartAssistantHelperState(IMState):
    """State to prepare tracking data and trigger the assistant helper service."""

    def enter(self) -> None:
        self.manager.get_logger().info(
            "Preparando interacción con assistant helper..."
        )
        self._started = False
        self.manager.reset_assistant_helper_context()

    def execute(self) -> None:
        mgr = self.manager

        if self._started:
            mgr.transition_to(WaitAssistantHelperState)
            return

        # if not mgr.ensure_central_face_cluster_ready():
        #     mgr.fail_social_service_call()
        #     mgr.transition_to(DeactivateAllState)
        #     return

        # if not mgr.activate_face_tracking():
        #     mgr.get_logger().error("Failed to activate face tracker")
        #     mgr.fail_social_service_call()
        #     mgr.transition_to(DeactivateAllState)
        #     return

        if not mgr.fetch_central_face_cluster():
            mgr.get_logger().error(
                "No se pudo obtener el cluster central para preparar assistant helper"
            )
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)
            return

        if not mgr.start_assistant_interaction():
            mgr.get_logger().error(
                "Assistant helper no aceptó la interacción solicitada"
            )
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)
            return

        self._started = True
        mgr.transition_to(WaitAssistantHelperState)


class WaitAssistantHelperState(IMState):
    """State to wait for the assistant helper interaction to finish."""

    def enter(self) -> None:
        self.manager.get_logger().info(
            "Esperando a que assistant helper finalice la interacción..."
        )

    def execute(self) -> None:
        mgr = self.manager
        now_sec = mgr.get_clock().now().nanoseconds / 1e9

        # Si el asistente ya ha llamado al servicio de finalización
        if mgr.assistant_helper_interaction_finished:
            mgr.get_logger().info("Assistant helper completó la interacción (notificado por servicio).")
            mgr.success_social_service_call()
            mgr.transition_to(DeactivateAllState)
            return

        # Comprobar si se ha superado el tiempo de espera
        if (
            mgr.assistant_helper_deadline is not None
            and now_sec >= mgr.assistant_helper_deadline
        ):
            mgr.get_logger().error("Timeout: Assistant helper no finalizó a tiempo.")
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)
            return


class DeactivateAllState(IMState):
    """State to deactivate all modules and clean up."""
    
    def enter(self) -> None:
        self.manager.get_logger().info("Deactivating all modules...")
    
    def execute(self) -> None:
        mgr = self.manager
        
        # Cancel main timer
        mgr.trigger_deactivate()
        
        # Transition to done state
        mgr.transition_to(DoneState)


class DoneState(IMState):
    """Final state indicating interaction is complete."""
    
    def enter(self) -> None:
        self.manager.get_logger().info("Interaction complete. Returning to idle...")
    
    def execute(self) -> None:
        # Interaction complete, waiting for deactivation
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
