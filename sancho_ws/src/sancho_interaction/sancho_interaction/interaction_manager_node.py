"""Interaction Manager Node.

This module manages the interaction flow of a robot with users by coordinating
various modules such as face detection, recognition, tracking, and audio playback.
"""

import json
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
from rclpy.action import ActionClient
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile, ReliabilityPolicy
from sancho_msgs.action import PlayAudio
from sancho_msgs.msg import FaceDetectionArray, FaceRecognitionArray
from sancho_msgs.srv import GetCentralFaceCluster, SocialState, GreetPeople
from std_msgs.msg import Float32, Int16
from tf_transformations import quaternion_from_euler


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
    FACE_DETECTOR = "/human_face_detector"
    FACE_RECOGNIZER = "/human_face_recognizer"
    FACE_TRACKER = "/human_face_tracker"
    FACE_MANAGER = "/human_face_manager"
    AUDIO_PLAYER = "/audio_player"
    CENTRAL_FACE_CLUSTER = "/central_faces_cluster_node"
    ASSISTANT_HELPER = "/assistant_helper"  # Placeholder for future lifecycle integration


class AssistantHelperState(IntEnum):
    """Assistant helper internal state replicated from assistant helper node."""

    NAME = 0
    SPEAKING = 1
    COMMAND = 2
    ASKING = 3


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
        self.declare_parameter("fallback_retry_backoff", 1.5)
        self.declare_parameter("face_detection_topic", "/face_detections")
        self.declare_parameter("face_recognition_topic", "/face_recognitions")
        self.declare_parameter(
            "central_face_cluster_service",
            "/central_faces_cluster_node/get_central_cluster",
        )
        self.declare_parameter("assistant_helper_service", "assistant/greet_people")
        self.declare_parameter("assistant_helper_mode_topic", "sancho_audio/assistant_helper/mode")
        self.declare_parameter("assistant_helper_question_id", 1)
        self.declare_parameter("assistant_helper_timeout", 60.0)
        self.declare_parameter("assistant_helper_service_timeout", 10.0)
        
        # Módulos gestionados directamente por este nodo
        self.modules = [
            ModuleNames.FACE_TRACKER,
            ModuleNames.AUDIO_PLAYER,
        ]
        # Módulos externos que deben estar activos antes de continuar (no se activan aquí)
        self.required_external_modules = [
            ModuleNames.FACE_DETECTOR,
            ModuleNames.FACE_RECOGNIZER,
            ModuleNames.FACE_MANAGER,
        ]
        self.module_clients = {}
        self.required_module_state_clients = {}
        self.active_modules = set()
        self.central_cluster_client = None
        self.assistant_helper_client = None
        self.assistant_mode_sub = None
        self.assistant_helper_state = AssistantHelperState.NAME
        self.assistant_helper_last_state_change = None
        self.assistant_helper_interaction_started = False
        self.assistant_helper_detected_activity = False
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
        self.central_cluster_service_name = self.get_parameter("central_face_cluster_service").value
        self.assistant_helper_service_name = self.get_parameter("assistant_helper_service").value
        self.assistant_helper_mode_topic = self.get_parameter("assistant_helper_mode_topic").value
        self.assistant_helper_question_id = int(self.get_parameter("assistant_helper_question_id").value)
        self.assistant_helper_timeout = float(self.get_parameter("assistant_helper_timeout").value)
        self.assistant_helper_service_timeout = float(self.get_parameter("assistant_helper_service_timeout").value)

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

        # Gestionar el lifecycle del face cluster (ya no opcional)
        cluster_client = self.create_client(
            ChangeState,
            f"{ModuleNames.CENTRAL_FACE_CLUSTER}/change_state",
            callback_group=self.life_cb,
        )

        timeout_sec = 10.0  # o el valor que tú quieras

        if not cluster_client.wait_for_service(timeout_sec=timeout_sec):
            self.get_logger().error(
                f"No se pudo conectar con el servicio {ModuleNames.CENTRAL_FACE_CLUSTER} "
                f"en {timeout_sec} segundos. Abortando."
            )
            return TransitionCallbackReturn.FAILURE
        else:
            self.module_clients[ModuleNames.CENTRAL_FACE_CLUSTER] = cluster_client
            self.get_logger().info(
                "Cliente de lifecycle para central_face_cluster listo"
            )


        assistant_helper_client = self.create_client(
            ChangeState,
            f"{ModuleNames.ASSISTANT_HELPER}/change_state",
            callback_group=self.life_cb,
        )

        # Tiempo máximo de espera (puedes parametrizarlo)
        timeout_sec = 10.0  # Ejemplo: 10 segundos

        if not assistant_helper_client.wait_for_service(timeout_sec=timeout_sec):
            # Fallar explícitamente
            self.get_logger().error(
                f"No se pudo conectar con el servicio {ModuleNames.ASSISTANT_HELPER} "
                f"en {timeout_sec} segundos. Abortando."
            )
            return TransitionCallbackReturn.FAILURE
        else:
            self.module_clients[ModuleNames.ASSISTANT_HELPER] = assistant_helper_client
            self.get_logger().info(
                "Cliente de lifecycle para assistant_helper listo"
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

        self.assistant_helper_client = self.create_client(
            GreetPeople,
            self.assistant_helper_service_name,
            callback_group=self.io_cb,
        )
        if not self.assistant_helper_client.wait_for_service(timeout_sec=2.0):
            self.get_logger().warn(
                f"Servicio {self.assistant_helper_service_name} no disponible durante configure; "
                "se reintentará antes de lanzar la interacción. "
                "TODO: sincronizar con el servicio real del assistant helper."
            )

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

        self.assistant_mode_sub = self.create_subscription(
            Int16,
            self.assistant_helper_mode_topic,
            callback=self._assistant_mode_cb,
            qos_profile=self.control_qos,
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
        if self.assistant_mode_sub:
            self.destroy_subscription(self.assistant_mode_sub)
            self.assistant_mode_sub = None
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
        if self.assistant_mode_sub:
            self.destroy_subscription(self.assistant_mode_sub)
            self.assistant_mode_sub = None
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

        return super().on_cleanup(state)

    # ------------------------------------------------------------
    # Callbacks de sensores
    # ------------------------------------------------------------
    def _face_cb(self, msg: FaceDetectionArray):
        """Callback for face detection messages."""
        self.face_msgs = msg.detections

    def _tdoa_cb(self, msg: Float32):
        """Callback for TDOA angle messages."""
        self.tdoa_angle = msg.data

    def _assistant_mode_cb(self, msg: Int16):
        """Track assistant helper state transitions."""
        value = msg.data
        try:
            state = AssistantHelperState(value)
        except ValueError:
            self.get_logger().warn(
                f"Estado de assistant helper desconocido recibido: {value}"
            )
            return

        if self.assistant_helper_state != state:
            self.get_logger().debug(f"Assistant helper state -> {state.name}")
        self.assistant_helper_state = state
        self.assistant_helper_last_state_change = (
            self.get_clock().now().nanoseconds / 1e9
        )
        if state != AssistantHelperState.NAME:
            self.assistant_helper_detected_activity = True

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

    def activate_face_detection_pipeline(self) -> bool:
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

    def activate_face_tracking(self) -> bool:
        """Activate face tracker module."""
        return self.activate_module(ModuleNames.FACE_TRACKER)

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
        self.assistant_helper_detected_activity = False
        self.assistant_helper_start_time = None
        self.assistant_helper_deadline = None
        self.assistant_helper_last_state_change = None
        self.assistant_helper_state = AssistantHelperState.NAME
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

    def ensure_assistant_helper_ready(self) -> bool:
        """Ensure the assistant helper node is running before we interact with it."""
        if ModuleNames.ASSISTANT_HELPER in self.module_clients:
            self.get_logger().info("Activando assistant helper vía lifecycle...")
            if not self.activate_module(ModuleNames.ASSISTANT_HELPER):
                self.get_logger().error(
                    "Fallo al activar el assistant helper mediante lifecycle."
                )
                return False
        else:
            self.get_logger().info(
                "Assistant helper sin lifecycle; se asume que el orquestador ya lo lanzó (placeholder)."
            )

        if self.assistant_helper_last_state_change is None:
            self.get_logger().info(
                "Esperando una actualización del estado del assistant helper..."
            )
            start_time = self.get_clock().now().nanoseconds / 1e9
            timeout = self.assistant_helper_service_timeout
            while (
                self.assistant_helper_last_state_change is None
                and (self.get_clock().now().nanoseconds / 1e9 - start_time) < timeout
                and rclpy.ok()
            ):
                rclpy.spin_once(self, timeout_sec=0.1)

            if self.assistant_helper_last_state_change is None:
                self.get_logger().warn(
                    "No se recibió confirmación de estado del assistant helper; continuando de todos modos."
                )

        return True

    def start_assistant_helper_interaction(self) -> bool:
        """Trigger the assistant helper service with the detected user information."""
        if not self.assistant_helper_target_names:
            self.get_logger().error(
                "No hay nombres para enviar al assistant helper; abortando la interacción."
            )
            return False

        if self.assistant_helper_client is None:
            self.get_logger().warn(
                "Cliente de servicio del assistant helper no inicializado. "
                "TODO: conectar con el servicio real cuando esté disponible."
            )
            return False

        if not self.assistant_helper_client.wait_for_service(
            timeout_sec=self.assistant_helper_service_timeout
        ):
            self.get_logger().error(
                f"Servicio {self.assistant_helper_service_name} no disponible al iniciar la interacción."
            )
            return False

        req = GreetPeople.Request()
        req.ids = self.assistant_helper_target_ids
        req.names = self.assistant_helper_target_names

        future = self.assistant_helper_client.call_async(req)
        done_evt = threading.Event()
        future.add_done_callback(lambda _: done_evt.set())

        if not done_evt.wait(self.assistant_helper_service_timeout):
            self.get_logger().error(
                f"Timeout esperando respuesta del servicio {self.assistant_helper_service_name}"
            )
            return False
        
        response = future.result()
        if response is None:
            self.get_logger().error(
                f"Respuesta vacía al llamar {self.assistant_helper_service_name}"
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
        self.transition_to(SearchFaceState)

    

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
    """State to verify the face detection pipeline is already active."""
    
    def enter(self) -> None:
        self.manager.get_logger().info("Verificando que el pipeline de detección facial esté activo...")
    
    def execute(self) -> None:
        mgr = self.manager
        if mgr.activate_face_detection_pipeline():
            mgr.get_logger().info("Pipeline de detección facial listo")
            mgr.attempt = 0
            mgr.tdoa_attempts = 0
            mgr.transition_to(SearchFaceState)
        else:
            mgr.get_logger().error("El pipeline de detección facial no está listo")
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)


class SearchFaceState(IMState):
    """State to search for a face in detection messages."""
    
    def enter(self) -> None:
        self.manager.get_logger().info("Searching for face...")
    
    def execute(self) -> None:
        mgr = self.manager
        mgr.best_face = mgr._select_best_face()
        
        if mgr.best_face:
            mgr.get_logger().info("Face found! Proceeding to tracking...")
            mgr.transition_to(StartAssistantHelperState)
        elif mgr.attempt < mgr.max_attempts:
            # Calculate rotation angle for scanning
            angle = (
                0.0
                if mgr.attempt == mgr.max_attempts - 1
                else (45.0 if mgr.attempt % 2 == 0 else -45.0)
            )
            mgr._rotate_head(angle)
            mgr.attempt += 1
            mgr.get_logger().info(
                f"No valid face detected. Attempt {mgr.attempt}/{mgr.max_attempts}, "
                f"rotating head to {angle}°"
            )
            # Wait for rotation to complete
            if mgr.main_timer:
                mgr.main_timer.cancel()
                mgr.main_timer = None
            mgr.wait_timer = mgr.create_timer(
                mgr.rotation_duration, mgr._on_wait_complete, callback_group=mgr.io_cb
            )
        else:
            mgr.get_logger().warn(
                f"Max attempts ({mgr.max_attempts}) reached without detecting face. "
                "Falling back to TDOA..."
            )
            mgr.transition_to(FallbackTdoaState)
            mgr.tdoa_angle = None
            mgr.tdoa_attempts = 0


class FallbackTdoaState(IMState):
    """State to use TDOA (Time Difference of Arrival) as fallback for face detection."""
    
    def enter(self) -> None:
        self.manager.get_logger().info("Entering TDOA fallback mode...")
    
    def execute(self) -> None:
        mgr = self.manager
        
        if mgr.tdoa_attempts < mgr.fallback_max_attempts:
            # First check if we found a face
            mgr.best_face = mgr._select_best_face()
            if mgr.best_face:
                mgr.get_logger().info("Face found during TDOA fallback!")
                mgr.transition_to(StartAssistantHelperState)
                return
            
            # Try TDOA
            angle = mgr.tdoa_angle
            if angle is None:
                mgr.get_logger().warn(
                    f"No TDOA data received. Attempt {mgr.tdoa_attempts + 1}/"
                    f"{mgr.fallback_max_attempts}"
                )
                mgr.tdoa_attempts += 1
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
            if abs(angle) <= mgr.tdoa_angle_limit:
                mgr.get_logger().info(f"Rotating head to TDOA angle: {angle:.1f}°")
                mgr._rotate_head(angle)
                mgr.tdoa_attempts += 1
                if mgr.main_timer:
                    mgr.main_timer.cancel()
                    mgr.main_timer = None
                mgr.wait_timer = mgr.create_timer(
                    mgr.tdoa_timeout,
                    mgr._on_tdoa_wait_complete,
                    callback_group=mgr.io_cb,
                )
                return
            else:
                mgr.get_logger().warn(
                    f"TDOA angle {angle:.1f}° exceeds limit of {mgr.tdoa_angle_limit}°"
                )
        
        # All attempts exhausted
        mgr.get_logger().error(
            "Failed to detect person after all TDOA attempts. Ending interaction."
        )
        mgr.fail_social_service_call()
        mgr.transition_to(DeactivateAllState)


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

        if not mgr.ensure_central_face_cluster_ready():
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)
            return

        if not mgr.activate_face_tracking():
            mgr.get_logger().error("Failed to activate face tracker")
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)
            return

        if not mgr.fetch_central_face_cluster():
            mgr.get_logger().error(
                "No se pudo obtener el cluster central para preparar assistant helper"
            )
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)
            return

        if not mgr.ensure_assistant_helper_ready():
            mgr.get_logger().error("Assistant helper no pudo iniciarse")
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)
            return

        if not mgr.start_assistant_helper_interaction():
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
        self._warned_no_activity = False

    def execute(self) -> None:
        mgr = self.manager
        now_sec = mgr.get_clock().now().nanoseconds / 1e9

        if not mgr.assistant_helper_interaction_started:
            return

        if (
            mgr.assistant_helper_deadline is not None
            and now_sec >= mgr.assistant_helper_deadline
        ):
            mgr.get_logger().error("Assistant helper no respondió a tiempo")
            mgr.fail_social_service_call()
            mgr.transition_to(DeactivateAllState)
            return

        if mgr.assistant_helper_detected_activity:
            if mgr.assistant_helper_state == AssistantHelperState.NAME:
                mgr.get_logger().info("Assistant helper completó la interacción")
                mgr.success_social_service_call()
                mgr.transition_to(DeactivateAllState)
                return
        else:
            if (
                mgr.assistant_helper_start_time is not None
                and now_sec - mgr.assistant_helper_start_time > 5.0
                and not self._warned_no_activity
            ):
                mgr.get_logger().warn(
                    "Aún no se detecta actividad de assistant helper tras 5s"
                )
                self._warned_no_activity = True


class DeactivateAllState(IMState):
    """State to deactivate all modules and clean up."""
    
    def enter(self) -> None:
        self.manager.get_logger().info("Deactivating all modules...")
    
    def execute(self) -> None:
        mgr = self.manager
        
        # Cancel main timer
        if mgr.main_timer:
            mgr.main_timer.cancel()
            mgr.main_timer = None
        
        # Deactivate all modules
        mgr.deactivate_all_modules()
        
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
