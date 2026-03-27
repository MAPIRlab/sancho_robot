import os
import math
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.action import ActionClient
from ament_index_python import get_package_share_directory

from std_msgs.msg import Empty, Float32
from geometry_msgs.msg import PoseStamped
from tf_transformations import quaternion_from_euler

from sancho_lifecycle_utils.lifecycle_client import ManagedLifecycleClient
from sancho_interfaces.msg import FaceRecognitionArray
from sancho_interfaces.srv import GetCentralFaceCluster, StartInteraction, EndInteraction
from sancho_interfaces.action import PlayAudio

# ============================================================================
# MÁQUINA DE ESTADOS (BASE)
# ============================================================================
class AttentionState:
    def __init__(self, manager: "AttentionManagerNode"):
        self.manager = manager

    def enter(self) -> None:
        """Se ejecuta una vez al entrar en el estado."""
        pass

    def execute(self) -> None:
        """Se ejecuta en bucle (a 10Hz) mientras el estado esté activo."""
        pass

    def exit(self) -> None:
        """Se ejecuta justo antes de cambiar a otro estado."""
        pass


# ============================================================================
# ESTADOS ESPECÍFICOS
# ============================================================================
class IdleState(AttentionState):
    def enter(self):
        self.manager.get_logger().info("[ESTADO] IDLE: Esperando estímulos...")
        self.manager.hotword_lc.set_state(True)
        self.idle_time = 0.0
        
        # NUEVO: Pequeño tiempo de gracia para no re-evaluar caras inmediatamente
        # y evitar el micro-bucle si la persona enfrente está en cooldown.
        self.ignore_faces_until = self.manager.get_clock().now().nanoseconds / 1e9 + 2.0

    def execute(self):
        now = self.manager.get_clock().now().nanoseconds / 1e9
        
        # 1. ¿Vemos una cara por casualidad? (Respetando el tiempo de gracia)
        if now > self.ignore_faces_until and self.manager.has_valid_faces():
            self.manager.get_logger().info("Cara detectada pasivamente. Investigando...")
            self.manager.transition_to(IdentifyUserState)
            return

        # 2. ¿Llevamos mucho tiempo aburridos? (ej. 30 segundos)
        self.idle_time += 0.1 # execute corre a 10Hz
        if self.idle_time > 30.0:
            self.manager.transition_to(ScanningState)


class ScanningState(AttentionState):
    def enter(self):
        self.manager.get_logger().info("[ESTADO] SCANNING: Buscando personas...")
        self.scan_angles = [0.0, 45.0, -45.0, 0.0]
        self.current_scan_idx = 0
        self.waiting_for_rotation = False
        self.timer = None

    def execute(self):
        if self.waiting_for_rotation:
            # Si vemos a alguien mientras giramos, paramos de escanear
            if self.manager.has_valid_faces():
                self._cancel_timer()
                self.manager.transition_to(IdentifyUserState)
            return

        # Si ya hemos escaneado todos los ángulos y no hay nadie
        if self.current_scan_idx >= len(self.scan_angles):
            self.manager.get_logger().info("Escaneo terminado. No se encontró a nadie.")
            self.manager.transition_to(IdleState)
            return

        # Girar al siguiente ángulo
        angle = self.scan_angles[self.current_scan_idx]
        self.manager.rotate_head(angle)
        self.current_scan_idx += 1
        
        # Esperar 2 segundos a que el cuello termine de girar
        self.waiting_for_rotation = True
        self.timer = self.manager.create_timer(2.0, self._on_rotation_done, callback_group=self.manager.cb_group)

    def _on_rotation_done(self):
        self._cancel_timer()
        self.waiting_for_rotation = False

    def _cancel_timer(self):
        # NUEVO: Prevenir memory leaks destruyendo el timer
        if hasattr(self, 'timer') and self.timer:
            self.timer.cancel()
            self.manager.destroy_timer(self.timer)
            self.timer = None

    def exit(self):
        self._cancel_timer()


class OrientingState(AttentionState):
    def enter(self):
        self.manager.get_logger().info(f"[ESTADO] ORIENTING: Girando hacia el sonido ({self.manager.target_angle}°)...")
        self.manager.rotate_head(self.manager.target_angle)
        
        # Esperamos a que gire y miramos si hay alguien
        self.timer = self.manager.create_timer(3.0, self._on_rotation_done, callback_group=self.manager.cb_group)

    def _on_rotation_done(self):
        self._cancel_timer()
        
        if self.manager.has_valid_faces():
            self.manager.transition_to(IdentifyUserState)
        else:
            self.manager.get_logger().info("Falsa alarma. No hay nadie en esa dirección.")
            self.manager.transition_to(IdleState)

    def _cancel_timer(self):
        # NUEVO: Prevenir memory leaks destruyendo el timer
        if hasattr(self, 'timer') and self.timer:
            self.timer.cancel()
            self.manager.destroy_timer(self.timer)
            self.timer = None

    def exit(self):
        self._cancel_timer()


class IdentifyUserState(AttentionState):
    def enter(self):
        self.manager.get_logger().info("[ESTADO] IDENTIFY_USER: Analizando clúster de caras...")
        self.request_sent = False

    def execute(self):
        if self.request_sent:
            return

        # Llamada ASÍNCRONA para no bloquear el nodo
        if not self.manager.central_cluster_client.wait_for_service(timeout_sec=1.0):
            self.manager.get_logger().warn("Servicio de clúster no disponible. Abortando...")
            self.manager.transition_to(IdleState)
            return

        req = GetCentralFaceCluster.Request()
        future = self.manager.central_cluster_client.call_async(req)
        future.add_done_callback(self._on_cluster_response)
        self.request_sent = True

    def filter_cluster_by_confidence(self, cluster_response, confidence_threshold):
        filtered_ids = []
        filtered_names = []

        for uid, name, idx in zip(cluster_response.ids, cluster_response.names, cluster_response.indices):
            if idx < len(self.manager.recognitions):
                conf = self.manager.recognitions[idx].distance
                
                if conf >= confidence_threshold:
                    filtered_ids.append(uid)
                    filtered_names.append(name)
                else:
                    self.manager.get_logger().debug(
                        f"Descartando a '{name}' del grupo por baja confianza ({conf:.2f} < {confidence_threshold})"
                    )

        return filtered_ids, filtered_names

    def _on_cluster_response(self, future):
        try:
            response = future.result()
            
            # Check that we have a valid response
            if response and response.ids and hasattr(response, 'indices') and len(response.indices) > 0:
                
                filtered_ids, filtered_names = self.filter_cluster_by_confidence(response, confidence_threshold=0.7)
                
                # Check if we have anyone after filtering
                if not filtered_ids:
                    self.manager.get_logger().info("Nadie en el grupo superó el umbral de confianza. Ignorando.")
                    self.manager.transition_to(IdleState)
                    return
                
                # If hotword is triggered, we ignore the cooldown
                if not self.manager.hotword_triggered:
                    # Check cooldown
                    now = self.manager.get_clock().now().nanoseconds / 1e9
                    all_in_cooldown = True
                    
                    for uid in filtered_ids:
                        last_interaction_time = self.manager.user_cooldowns.get(uid, 0.0)
                        if (now - last_interaction_time) >= self.manager.cooldown_seconds:
                            all_in_cooldown = False
                            break # There is at least one person without cooldown
                    
                    if all_in_cooldown:
                        self.manager.get_logger().info(f"El grupo filtrado {filtered_names} está en cooldown. Ignorando.")
                        self.manager.transition_to(IdleState)
                        return
                    
                # Update targets
                self.manager.target_ids = filtered_ids
                self.manager.target_names = filtered_names
                
                # CORRECCIÓN: Hacemos referencia al manager, no a la clase local
                self.manager.hotword_triggered = False 
                
                self.manager.get_logger().info(f"Objetivo fijado: {self.manager.target_names}")
                self.manager.transition_to(EngagedState)
                return  
                
            # No valid response
            self.manager.get_logger().info("El clúster no contenía caras reconocibles.")
            self.manager.transition_to(IdleState)
            
        except Exception as e:
            self.manager.get_logger().error(f"Error procesando clúster: {e}")
            self.manager.transition_to(IdleState)


class EngagedState(AttentionState):
    def enter(self):
        self.manager.get_logger().info("[ESTADO] ENGAGED: Cediendo control al Dialog Manager...")
        self.request_sent = False

    def execute(self):
        if self.request_sent:
            return # Nos quedamos en este estado esperando a que el Dialog Manager nos libere

        # Pasamos la pelota al Dialog Manager de forma asíncrona
        if not self.manager.start_interaction_client.wait_for_service(timeout_sec=2.0):
            self.manager.get_logger().error("Dialog Manager no responde. Abortando interacción.")
            self.manager.transition_to(IdleState)
            return

        req = StartInteraction.Request()
        req.user_ids = self.manager.target_ids
        req.user_names = self.manager.target_names
        req.context = "proactive_greeting"

        future = self.manager.start_interaction_client.call_async(req)
        future.add_done_callback(self._on_interaction_started)
        self.request_sent = True
    
    def exit(self):
        self.manager.tracker_lc.set_state(False)

    def _on_interaction_started(self, future):
        response = future.result()
        if response.success:
            self.manager.get_logger().info("¡Dialog Manager tomó el control! Manteniendo contacto visual y rearmando oídos...")
            self.manager.tracker_lc.set_state(True)
            
            # NUEVO: Rearmamos el hotword para que el robot sea interrumpible
            self.manager.hotword_lc.set_state(True)
        else:
            self.manager.get_logger().warn("Dialog Manager rechazó la interacción.")
            self.manager.transition_to(IdleState)


# ============================================================================
# NODO PRINCIPAL (ORQUESTADOR DE ATENCIÓN)
# ============================================================================
class AttentionManagerNode(Node):
    def __init__(self):
        super().__init__("attention_manager")

        try:
            audio_pkg_path = get_package_share_directory('sancho_audio')
            default_sound_path = os.path.join(audio_pkg_path, 'sounds', 'activation_sound.wav')
        except Exception as e:
            self.get_logger().warn(f"No se pudo encontrar sancho_audio: {e}")
            default_sound_path = ""

        # Parameters
        self.declare_parameter("activation_sound_path", default_sound_path)
        self.declare_parameter("cooldown_seconds", 60.0)

        self.cb_group = ReentrantCallbackGroup()

        # State variables
        self.current_state: AttentionState = None

        self.recognitions = []
        self.last_face_time = 0.0

        self.latest_doa_angle = 0.0
        
        self.target_angle = 0.0
        self.target_ids = []
        self.target_names = []
        
        self.activation_sound_path = self.get_parameter("activation_sound_path").value
        
        self.cooldown_seconds = self.get_parameter("cooldown_seconds").value
        self.user_cooldowns = {}
        self.hotword_triggered = False

        # Publishers / Subscribers
        self.face_sub = self.create_subscription(FaceRecognitionArray, "/face_recognitions", self._face_cb, 10, callback_group=self.cb_group)
        self.hotword_sub = self.create_subscription(Empty, "/voice_events/hotword_detected", self._hotword_cb, 10, callback_group=self.cb_group)
        self.doa_sub = self.create_subscription(Float32, "/sancho_audio/doa", self._doa_cb, 10, callback_group=self.cb_group)
        self.head_pub = self.create_publisher(PoseStamped, "/head_goal", 10)

        # Clients
        self.central_cluster_client = self.create_client(GetCentralFaceCluster, "/central_faces_cluster_node/get_central_cluster", callback_group=self.cb_group)
        self.start_interaction_client = self.create_client(StartInteraction, "/dialog_manager/start_interaction", callback_group=self.cb_group)
        self.audio_client = ActionClient(self, PlayAudio, 'play_audio', callback_group=self.cb_group)
        
        # Lifecycle clients
        self.hotword_lc = ManagedLifecycleClient(self, "hotword_detector", self.cb_group)
        self.tracker_lc = ManagedLifecycleClient(self, "face_tracker_lifecycle", self.cb_group)

        # Services
        self.end_interaction_srv = self.create_service(EndInteraction, "~/interaction_finished", self._interaction_finished_cb, callback_group=self.cb_group)

        # State Machine main loop (10 Hz)
        self.transition_to(IdleState)
        self.main_timer = self.create_timer(0.1, self._run_state, callback_group=self.cb_group)

        self.get_logger().info("Attention Manager inicializado y listo.")

    def _face_cb(self, msg: FaceRecognitionArray):
        """Keeps last recognition message updated"""
        self.recognitions = msg.recognitions
        self.last_face_time = self.get_clock().now().nanoseconds / 1e9

    def _doa_cb(self, msg: Float32):
        """Keeps DoA angle updated"""
        self.latest_doa_angle = msg.data

    def _hotword_cb(self, msg: Empty):
        """Called when someone says the hotword"""
        self.get_logger().info("¡Hotword detectado! Interrumpiendo rutina...")

        # Deactivate hotword node
        self.hotword_lc.set_state(False)
        
        # Reproducir el sonido de activación usando la Acción (No bloqueante)
        self._play_activation_sound()

        # Girar la cabeza hacia el origen del sonido
        self.target_angle = self.latest_doa_angle
        self.hotword_triggered = True # Ignora cooldowns en IdentifyUserState
        
        # Transitar al estado Orienting para buscar a la persona
        self.transition_to(OrientingState)

    def _play_activation_sound(self):
        """Sends a goal to the audio player action server"""
        if not self.audio_client.wait_for_server(timeout_sec=1.0):
            self.get_logger().warn("El Action Server de audio no está disponible.")
            return

        goal_msg = PlayAudio.Goal()
        goal_msg.filename = self.activation_sound_path

        self.get_logger().info(f"Pidiendo reproducción de {goal_msg.filename}...")
        self.audio_client.send_goal_async(goal_msg)

    def has_valid_faces(self):
        now = self.get_clock().now().nanoseconds / 1e9
        if (now - self.last_face_time) > 1.0:
            self.face_msgs = []
            return False

        return self.recognitions and len(self.recognitions) > 0

    def rotate_head(self, angle_deg: float):
        angle_rad = max(min(math.radians(angle_deg), math.radians(100.0)), math.radians(-100.0))
        q = quaternion_from_euler(0.0, math.radians(-30.0), angle_rad) # Asume tilt -30

        msg = PoseStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = "base_link"
        msg.pose.orientation.x = q[0]
        msg.pose.orientation.y = q[1]
        msg.pose.orientation.z = q[2]
        msg.pose.orientation.w = q[3]

        self.head_pub.publish(msg)

    # --- Communication Callback with Dialog Manager ---
    def _interaction_finished_cb(self, request, response):
        """Called when conversation is over"""
        self.get_logger().info(f"El Dialog Manager ha terminado la interacción. Motivo: {request.reason}")

        now = self.get_clock().now().nanoseconds / 1e9
        for uid in self.target_ids:
            self.user_cooldowns[uid] = now

        if isinstance(self.current_state, EngagedState):
            self.transition_to(IdleState)
        
        response.success = True
        return response

    # --- State Machine Motor ---
    def transition_to(self, state_class):
        if self.current_state:
            self.current_state.exit()
        self.current_state = state_class(self)
        self.current_state.enter()

    def _run_state(self):
        if self.current_state:
            self.current_state.execute()


def main(args=None):
    rclpy.init(args=args)
    node = AttentionManagerNode()
    
    # Fundamental: Usar MultiThreadedExecutor para permitir la asincronía real
    executor = MultiThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info("Apagando Attention Manager...")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()