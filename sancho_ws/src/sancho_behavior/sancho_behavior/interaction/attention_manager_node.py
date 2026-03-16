import math
import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import Float32
from geometry_msgs.msg import PoseStamped
from lifecycle_msgs.srv import ChangeState
from lifecycle_msgs.msg import Transition
from tf_transformations import quaternion_from_euler

# Mensajes de visión
from sancho_msgs.msg import FaceRecognitionArray
from sancho_msgs.srv import GetCentralFaceCluster

# (NUEVO) Servicios de comunicación con el Dialog Manager
# Asegúrate de haber definido estos .srv en tu paquete sancho_msgs
from sancho_msgs.srv import StartInteraction, EndInteraction, ForceAttention

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
        self.idle_time = 0.0

    def execute(self):
        # 1. ¿Vemos una cara por casualidad?
        if self.manager.has_valid_faces():
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
        
        # Esperar 2 segundos a que el cuello termine de girar (sin bloquear el hilo)
        self.waiting_for_rotation = True
        self.timer = self.manager.create_timer(2.0, self._on_rotation_done, callback_group=self.manager.cb_group)

    def _on_rotation_done(self):
        self._cancel_timer()
        self.waiting_for_rotation = False

    def _cancel_timer(self):
        if self.timer:
            self.timer.cancel()
            self.timer = None

    def exit(self):
        self._cancel_timer()


class OrientingState(AttentionState):
    def enter(self):
        self.manager.get_logger().info(f"[ESTADO] ORIENTING: Girando hacia el sonido ({self.manager.target_angle}°)...")
        self.manager.rotate_head(self.manager.target_angle)
        
        # Esperamos a que gire y miramos si hay alguien
        self.timer = self.manager.create_timer(1.5, self._on_rotation_done, callback_group=self.manager.cb_group)

    def _on_rotation_done(self):
        if self.timer:
            self.timer.cancel()
        
        if self.manager.has_valid_faces():
            self.manager.transition_to(IdentifyUserState)
        else:
            self.manager.get_logger().info("Falsa alarma. No hay nadie en esa dirección.")
            self.manager.transition_to(IdleState)

    def exit(self):
        if hasattr(self, 'timer') and self.timer:
            self.timer.cancel()


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

    def _on_cluster_response(self, future):
        try:
            response = future.result()
            
            # 1. Comprobamos que el servicio haya devuelto datos y que sepamos sus índices
            if response and response.ids and hasattr(response, 'indices') and len(response.indices) > 0:
                
                # 2. Cogemos el índice de la primera cara del clúster (la más central)
                main_face_idx = response.indices[0]
                
                # 3. Verificamos por seguridad que el índice exista en nuestra lista de caras
                if main_face_idx < len(self.manager.recognitions):
                    confidence = self.manager.recognitions[main_face_idx].distance
                    
                    # 4. Validamos la confianza
                    if confidence >= 0.7:
                        self.manager.target_ids = list(response.ids)
                        self.manager.target_names = list(response.names)
                        self.manager.get_logger().info(
                            f"Objetivo fijado: {self.manager.target_names} (Confianza: {confidence:.2f})"
                        )
                        self.manager.transition_to(EngagedState)
                        return
                    
                    else:
                        self.manager.get_logger().info(
                            f"Identidad dudosa (Confianza: {confidence:.2f}). Ignorando."
                        )
                else:
                    self.manager.get_logger().warn("Fallo de sincronización: El clúster devolvió un índice antiguo.")
            
            # 5. Si algo de lo anterior falla o la confianza es baja, cancelamos todo y volvemos a Idle
            self.manager.get_logger().info("No se pudo identificar a nadie con suficiente claridad.")
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
        self.manager.set_face_tracker(False)

    def _on_interaction_started(self, future):
        response = future.result()
        if response.success:
            self.manager.get_logger().info("¡Dialog Manager tomó el control! Manteniendo contacto visual...")
            self.manager.set_face_tracker(True)
        else:
            self.manager.get_logger().warn("Dialog Manager rechazó la interacción.")
            self.manager.transition_to(IdleState)


# ============================================================================
# NODO PRINCIPAL (ORQUESTADOR DE ATENCIÓN)
# ============================================================================
class AttentionManagerNode(Node):
    def __init__(self):
        super().__init__("attention_manager")

        self.cb_group = ReentrantCallbackGroup()

        # Variables de estado y contexto
        self.current_state: AttentionState = None
        self.recognitions = []
        self.last_face_time = 0.0
        self.target_angle = 0.0
        self.target_ids = []
        self.target_names = []

        # Publishers / Subscribers Sensoriales
        self.head_pub = self.create_publisher(PoseStamped, "/head_goal", 10)
        self.face_sub = self.create_subscription(FaceRecognitionArray, "/face_recognitions", self._face_cb, 10, callback_group=self.cb_group)

        # Clientes de Servicio (Hacia otros nodos)
        self.central_cluster_client = self.create_client(GetCentralFaceCluster, "/central_faces_cluster_node/get_central_cluster", callback_group=self.cb_group)
        self.start_interaction_client = self.create_client(StartInteraction, "/dialog_manager/start_interaction", callback_group=self.cb_group)
        self.tracker_client = self.create_client(ChangeState, "/face_tracker_lifecycle/change_state", callback_group=self.cb_group)

        # Servidores de Servicio (Para que el Dialog Manager nos llame a nosotros)
        self.end_interaction_srv = self.create_service(EndInteraction, "~/interaction_finished", self._interaction_finished_cb, callback_group=self.cb_group)
        self.force_attention_srv = self.create_service(ForceAttention, "~/force_attention", self._force_attention_cb, callback_group=self.cb_group)

        # Bucle principal de la Máquina de Estados (10 Hz)
        self.transition_to(IdleState)
        self.main_timer = self.create_timer(0.1, self._run_state, callback_group=self.cb_group)

        self.get_logger().info("Attention Manager inicializado y listo.")

    # --- Callbacks de Sensores ---
    def _face_cb(self, msg: FaceRecognitionArray):
        self.recognitions = msg.recognitions
        self.last_face_time = self.get_clock().now().nanoseconds / 1e9

    def has_valid_faces(self):
        now = self.get_clock().now().nanoseconds / 1e9
        if (now - self.last_face_time) > 1.0:
            self.face_msgs = []
            return False

        return self.recognitions and len(self.recognitions) > 0

    def set_face_tracker(self, enable: bool):
        """Activa o desactiva el nodo de seguimiento facial mediante Lifecycle."""
        if not self.tracker_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warn("Servicio Lifecycle del Face Tracker no disponible.")
            return

        req = ChangeState.Request()
        if enable:
            self.get_logger().info("Activando Face Tracker...")
            req.transition.id = Transition.TRANSITION_ACTIVATE
        else:
            self.get_logger().info("Desactivando Face Tracker...")
            req.transition.id = Transition.TRANSITION_DEACTIVATE

        self.tracker_client.call_async(req)

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

    # --- Callbacks de Comunicación con Dialog Manager ---
    def _force_attention_cb(self, request, response):
        """Llamado cuando el humano grita '¡Sancho!' (Inicia interacción Reactiva)."""
        self.get_logger().warn(f"¡Reclamo de atención! Girando de urgencia a {request.tdoa_angle}°")
        self.target_angle = request.tdoa_angle
        self.transition_to(OrientingState)
        
        response.success = True
        return response

    def _interaction_finished_cb(self, request, response):
        """Llamado cuando el humano se despide o el LLM corta la charla."""
        self.get_logger().info(f"El Dialog Manager ha terminado la interacción. Motivo: {request.reason}")
        if isinstance(self.current_state, EngagedState):
            self.transition_to(IdleState)
        
        response.success = True
        return response

    # --- Motor de la Máquina de Estados ---
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