import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
import numpy as np
from cvxopt import matrix, solvers

# Desactivar output innecesario del solver
solvers.options['show_progress'] = False

class SanchoCBFNode(Node):
    def __init__(self):
        super().__init__('sancho_cbf_node')
        
        # Parámetros de la Barrera
        self.d_safe = 0.30  # Distancia mínima (radio robot + margen)
        self.gamma = 1.5    # Agresividad de la barrera
        
        self.create_subscription(OccupancyGrid, '/local_costmap/costmap', self.costmap_callback, 10)
        self.create_subscription(Twist, '/cmd_vel_nav2', self.nav2_callback, 10)
        
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        self.costmap = None
        self.resolution = 0.05

    def costmap_callback(self, msg):
        grid = np.array(msg.data).reshape((msg.info.height, msg.info.width))
        self.costmap = grid
        self.resolution = msg.info.resolution

    def get_barrier_data(self):
        h, w = self.costmap.shape
        cy, cx = h // 2, w // 2
        
        window = self.costmap[cy-10:cy+10, cx-10:cx+10]
        
        # h(x) aproximado
        max_cost = np.max(window)
        dist_to_obs = (100 - max_cost) / 100.0 * 0.5
        
        h_x = dist_to_obs - 0.05 # Margen crítico
        
        # Gradiente
        gy, gx = np.gradient(window)
        nx = -np.mean(gx)
        ny = -np.mean(gy)
        
        return h_x, nx, ny

    def nav2_callback(self, msg_nav2):
        if self.costmap is None:
            self.pub.publish(msg_nav2)
            return

        h_x, nx, ny = self.get_barrier_data()

        # --- OPTIMIZACIÓN CUADRÁTICA (QP) ---
        # Queremos min 1/2 * |v - v_nav2|^2
        # P = Identidad, q = -v_nav2
        P = matrix(np.eye(2, dtype=float))
        q = matrix(-np.array([msg_nav2.linear.x, msg_nav2.linear.y], dtype=float))

        # Restricción: dot(v, n) >= -gamma * h(x)^3
        # Que es lo mismo que: -nx*vx - ny*vy <= gamma * h(x)^3
        G = matrix(-np.array([[nx, ny]], dtype=float))
        h = matrix(np.array([self.gamma * (h_x**3)], dtype=float))

        try:
            sol = solvers.qp(P, q, G, h)
            v_optimal = sol['x']
            
            safe_msg = Twist()
            safe_msg.linear.x = float(v_optimal[0])
            safe_msg.linear.y = float(v_optimal[1])
            safe_msg.angular.z = msg_nav2.angular.z
            
            self.pub.publish(safe_msg)
        except:
            self.pub.publish(Twist())

def main():
    rclpy.init()
    rclpy.spin(SanchoCBFNode())
    rclpy.shutdown()