import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
import numpy as np
from cvxopt import matrix, solvers
from scipy.ndimage import distance_transform_edt

solvers.options['show_progress'] = False

class SanchoSafetyFilter(Node):
    def __init__(self):
        super().__init__('sancho_safety_filter')
        
        # --- PARÁMETROS ---
        self.d_safe = 0.29      # Radio del robot + margen mínimo (2-3 cm)
        self.gamma = 10.0       # Aumentado para que no frene tan pronto (Ames alpha)
        self.lookahead = 0.05   # Punto de mira muy cercano para no ser conservador
        self.R_min = 0.45       # Radio de giro mínimo
        
        self.create_subscription(OccupancyGrid, '/local_costmap/costmap', self.costmap_callback, 10)
        self.create_subscription(Twist, '/cmd_vel_nav2', self.nav_callback, 10)
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        self.edf = None
        self.resolution = 0.05

    def costmap_callback(self, msg):
        self.resolution = msg.info.resolution
        grid = np.array(msg.data).reshape((msg.info.height, msg.info.width))
        # Binarización: 1 libre, 0 obstáculo
        binary_map = np.where(grid < 50, 1, 0)
        self.edf = distance_transform_edt(binary_map) * self.resolution

    def get_barrier_constraints(self, v_deseada):
        h, w = self.edf.shape
        cy, cx = h // 2, w // 2
        
        look_idx = int(self.lookahead / self.resolution)
        target_y = np.clip(cy + look_idx, 1, h-2)
        target_x = cx
        
        h_x = self.edf[target_y, target_x] - self.d_safe
        
        # Gradiente
        nx = (self.edf[target_y + 1, target_x] - self.edf[target_y - 1, target_x]) / (2 * self.resolution)
        
        return h_x, nx

    def nav_callback(self, msg_nav2):
        if self.edf is None:
            self.pub.publish(msg_nav2)
            return

        h_x, nx = self.get_barrier_constraints(msg_nav2.linear.x)

        # --- QP SOLVER ---
        P = matrix(np.eye(2, dtype=float))
        q = matrix(-np.array([msg_nav2.linear.x, msg_nav2.angular.z], dtype=float))

        # Restricción CBF
        G_list = [[-nx, 0.0]]
        h_list = [self.gamma * (h_x**3)]

        if abs(msg_nav2.linear.x) > 0.02:
            G_list.append([-1.0/self.R_min, 1.0])
            G_list.append([-1.0/self.R_min, -1.0])
            h_list.extend([0.0, 0.0])

        G = matrix(np.array(G_list, dtype=float))
        h_val = matrix(np.array(h_list, dtype=float))

        try:
            sol = solvers.qp(P, q, G, h_val)
            
            safe_msg = Twist()
            safe_msg.linear.x = float(sol['x'][0])
            safe_msg.angular.z = float(sol['x'][1])
            
            self.get_logger().info(f"h_x: {h_x:.2f} | V_in: {msg_nav2.linear.x:.2f} | V_out: {safe_msg.linear.x:.2f}")
            
            self.pub.publish(safe_msg)

        except:
            self.pub.publish(Twist())

def main():
    rclpy.init()
    rclpy.spin(SanchoSafetyFilter())
    rclpy.shutdown()