import threading
from rclpy.node import Node
from lifecycle_msgs.srv import ChangeState, GetState
from lifecycle_msgs.msg import Transition, State

class ManagedLifecycleClient:
    """
    Clase de utilidad para interactuar de forma segura y asíncrona 
    con nodos Lifecycle en ROS 2. Utiliza hilos en segundo plano para 
    evitar deadlocks en el Executor.
    """
    def __init__(self, parent_node: Node, target_node_name: str, callback_group=None):
        self.node = parent_node
        self.name = target_node_name
        
        # Creamos los clientes internamente
        self.change_client = self.node.create_client(
            ChangeState, f'/{target_node_name}/change_state', callback_group=callback_group)
        self.state_client = self.node.create_client(
            GetState, f'/{target_node_name}/get_state', callback_group=callback_group)

    def set_state(self, activate: bool):
        """
        Lanza la petición en un hilo en segundo plano (fire-and-forget).
        Esto es CRUCIAL para evitar congelar la máquina de estados de ROS 2.
        """
        threading.Thread(target=self._set_state_task, args=(activate,), daemon=True).start()

    def _set_state_task(self, activate: bool):
        """Tarea interna que realiza las comprobaciones bloqueantes de forma segura."""
        if not self.state_client.wait_for_service(timeout_sec=2.0) or not self.change_client.wait_for_service(timeout_sec=2.0):
            self.node.get_logger().warn(f"Servicios Lifecycle de {self.name} no disponibles.")
            return

        try:
            # 1. Preguntar el estado actual
            req_get = GetState.Request()
            future_get = self.state_client.call_async(req_get)
            event_get = threading.Event()
            future_get.add_done_callback(lambda _: event_get.set())
            
            # Usamos timeout para evitar hilos zombis si el otro nodo muere
            if not event_get.wait(timeout=3.0):
                self.node.get_logger().warn(f"Timeout al preguntar el estado de {self.name}.")
                return

            current_state_id = future_get.result().current_state.id

            # 2. Comprobar si la transición es válida y necesaria
            if activate and current_state_id == State.PRIMARY_STATE_ACTIVE:
                return  # Ya está activo
            if not activate and current_state_id == State.PRIMARY_STATE_INACTIVE:
                return  # Ya está inactivo
            if current_state_id == State.PRIMARY_STATE_UNCONFIGURED:
                self.node.get_logger().warn(f"No se puede cambiar {self.name}: Aún está UNCONFIGURED.")
                return

            # 3. Enviar la orden de cambio de estado
            req_change = ChangeState.Request()
            req_change.transition.id = Transition.TRANSITION_ACTIVATE if activate else Transition.TRANSITION_DEACTIVATE
            self.node.get_logger().info(f"Cambiando estado de {self.name} a {'ACTIVO' if activate else 'INACTIVO'}...")
            
            future_change = self.change_client.call_async(req_change)
            event_change = threading.Event()
            future_change.add_done_callback(lambda _: event_change.set())
            
            if not event_change.wait(timeout=3.0):
                self.node.get_logger().warn(f"Timeout al intentar cambiar el estado de {self.name}.")
                return
            
            response = future_change.result()
            if not response.success:
                self.node.get_logger().warn(f"El nodo {self.name} rechazó el cambio de estado.")
                
        except Exception as e:
            self.node.get_logger().error(f"Error interno cambiando estado de {self.name}: {e}")