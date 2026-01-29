import rclpy
from rclpy.node import Node
from sensor_msgs.msg import LaserScan
from rcl_interfaces.srv import SetParameters
from rcl_interfaces.msg import Parameter, ParameterType, ParameterValue
import numpy as np

class NarrowSpaceManager(Node):
    def __init__(self):
        super().__init__('narrow_space_manager_node')

        self.narrow_threshold = 1.1  # Ancho total (izq + der) para activar modo estrecho
        self.hysteresis = 0.2        # Margen para salir del modo estrecho
        self.base_desired_vel = 0.35 # Tu parámetro actual
        self.base_inflation = 0.35   # Tu parámetro actual

        self.is_narrow = False
        
        self.create_subscription(LaserScan, '/scan_1st', self.front_callback, 10)
        self.create_subscription(LaserScan, '/scan_2nd', self.back_callback, 10)

        self.latest_front = None
        self.latest_back = None

        self.controller_client = self.create_client(SetParameters, '/controller_server/ros__parameters')
        self.costmap_client = self.create_client(SetParameters, '/local_costmap/local_costmap/ros__parameters')


    def front_callback(self, msg): self.latest_front = msg; self.process_scans()
    def back_callback(self, msg): self.latest_back = msg

    def process_scans(self):
        if self.latest_front is None or self.latest_back is None:
            return

        front_ranges = np.array(self.latest_front.ranges)
        back_ranges = np.array(self.latest_back.ranges)

        # Detectar distancias laterales (Ventanas de 20º a 90º y 270º)
        # Asumiendo 360 puntos, 90º es el índice 90
        def get_side_dist(ranges):
            mid = len(ranges) // 4 # Aproximación para 90 grados
            left = np.nanmedian(ranges[mid-10 : mid+10])
            right = np.nanmedian(ranges[3*mid-10 : 3*mid+10])
            return left, right

        f_left, f_right = get_side_dist(front_ranges)
        b_left, b_right = get_side_dist(back_ranges)

        # La seguridad manda: tomamos la distancia más corta de cualquiera de los dos LIDARs
        # Esto asegura que si la "cola" sigue en el pasillo, mantenemos el modo estrecho
        min_left = np.nanmin([f_left, b_left])
        min_right = np.nanmin([f_right, b_right])
        total_width = min_left + min_right

        # --- MÁQUINA DE ESTADOS ---
        if total_width < self.narrow_threshold and not self.is_narrow:
            self.apply_context("NARROW", total_width)
        elif total_width > (self.narrow_threshold + self.hysteresis) and self.is_narrow:
            self.apply_context("NORMAL", total_width)

    def apply_context(self, mode, width):
        mppi_params = []
        costmap_params = []

        if mode == "NARROW":
            self.get_logger().warn(f"PASILLO DETECTADO ({width:.2f}).")
            self.is_narrow = True
            mppi_params.append(self.make_param('FollowPath.desired_linear_vel', 0.18))
            mppi_params.append(self.make_param('FollowPath.PathAlignCritic.weight', 50.0))

            costmap_params.append(self.make_param('inflation_layer.inflation_radius', 0.28))
        else:
            self.get_logger().info("SALIENDO A ESPACIO ABIERTO.")
            self.is_narrow = False
            mppi_params.append(self.make_param('FollowPath.desired_linear_vel', self.base_desired_vel))
            mppi_params.append(self.make_param('FollowPath.PathAlignCritic.weight', 10.0))
            costmap_params.append(self.make_param('inflation_layer.inflation_radius', self.base_inflation))

        self.send_params(self.controller_client, mppi_params)
        self.send_params(self.costmap_client, costmap_params)

    def make_param(self, name, value):
        return Parameter(name=name, value=ParameterValue(type=ParameterType.PARAMETER_DOUBLE, double_value=value))

    def send_params(self, client, params):
        if not client.service_is_ready():
            return
        req = SetParameters.Request()
        req.parameters = params
        client.call_async(req)

def main():
    rclpy.init()
    node = NarrowSpaceManager()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()