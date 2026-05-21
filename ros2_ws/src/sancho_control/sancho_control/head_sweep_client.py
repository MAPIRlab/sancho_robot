import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
import time

# Importa el tipo de acción personalizado que usas en tu servidor
from sancho_interfaces.action import RotateHead

class HeadSweepClient(Node):
    def __init__(self):
        super().__init__('head_sweep_client')
        
        # Crea el cliente de acción apuntando al mismo topic que el servidor
        self._action_client = ActionClient(self, RotateHead, '/head_controller/rotate')
        
        # Parámetros del barrido
        self.angles = [-45.0, 45.0]  # Ángulos en grados a alternar
        self.current_target_idx = 0
        self.timeout_sec = 5.0       # Tiempo máximo para alcanzar la meta
        
        self.get_logger().info("Esperando al servidor de acción /head_controller/rotate ...")
        self._action_client.wait_for_server()
        self.get_logger().info("Servidor de acción encontrado. Iniciando secuencia de barrido.")

        # Inicia el primer movimiento
        self.send_goal()

    def send_goal(self):
        target_angle = self.angles[self.current_target_idx]
        
        goal_msg = RotateHead.Goal()
        goal_msg.target_angle_deg = target_angle
        goal_msg.timeout_sec = self.timeout_sec

        self.get_logger().info(f"Enviando comando para girar la cabeza a: {target_angle}º")

        # Envía la meta de forma asíncrona
        self._send_goal_future = self._action_client.send_goal_async(
            goal_msg, 
            feedback_callback=self.feedback_callback
        )
        self._send_goal_future.add_done_callback(self.goal_response_callback)

    def feedback_callback(self, feedback_msg):
        # Puedes descomentar esto si quieres ver el progreso en tiempo real
        # feedback = feedback_msg.feedback
        # self.get_logger().debug(f"Progreso: ángulo actual {feedback.current_angle_deg:.1f}º, falta {feedback.distance_remaining:.1f}º")
        pass

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().error("¡La meta fue rechazada por el servidor!")
            return

        self.get_logger().info("Meta aceptada. Esperando a que termine el giro...")
        self._get_result_future = goal_handle.get_result_async()
        self._get_result_future.add_done_callback(self.get_result_callback)

    def get_result_callback(self, future):
        result = future.result().result
        status = future.result().status

        if result.success:
            self.get_logger().info(f"Giro completado con éxito. Ángulo final: {result.final_angle_deg:.2f}º")
        else:
            self.get_logger().warn(f"Giro fallido o interrumpido. Motivo: {result.message}. Ángulo final: {result.final_angle_deg:.2f}º")

        # Cambiar al siguiente objetivo
        self.current_target_idx = (self.current_target_idx + 1) % len(self.angles)
        
        # Pequeña pausa de 1 segundo antes de volver a girar hacia el otro lado
        # Esto te da tiempo a comprobar si el TID se mantiene estable al parar
        self.get_logger().info("Pausa antes del siguiente giro...")
        time.sleep(2.0) 
        
        # Enviar el siguiente comando
        self.send_goal()

def main(args=None):
    rclpy.init(args=args)
    node = HeadSweepClient()

    try:
        # spin() mantiene el nodo vivo y procesando los callbacks asíncronos
        rclpy.spin(node)
    except KeyboardInterrupt:
        node.get_logger().info("Secuencia de barrido detenida por el usuario.")
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == '__main__':
    main()