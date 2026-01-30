import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
import numpy as np
from cvxopt import matrix, solvers
from scipy.ndimage import distance_transform_edt

solvers.options['show_progress'] = False

class SanchoCBF(Node):
    def __init__(self):
        super().__init__('sancho_cbf')
        
        # --- PARÁMETROS DE DISEÑO ---
        self.d_safe = 0.30      # Margen de seguridad
        self.gamma = 15.0       # Agresividad de la barrera de control
        self.lookahead = 0.45   # Horizonte de "visión" para abrirse
        
        self.create_subscription(OccupancyGrid, '/local_costmap/costmap', self.map_cb, 10)
        self.create_subscription(Twist, '/cmd_vel_nav2', self.nav_cb, 10)
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        self.edf = None
        self.res = 0.05

    def map_cb(self, msg):
        self.res = msg.info.resolution
        grid = np.array(msg.data).reshape((msg.info.height, msg.info.width))
        binary_map = np.where(grid < 50, 1, 0)
        self.edf = distance_transform_edt(binary_map) * self.res

    def get_constraints(self, x_m, y_m):
        """ Obtiene h(x) y gradiente en coordenadas relativas al robot """
        h_map, w_map = self.edf.shape
        idx_x = int(w_map // 2 + x_m / self.res)
        idx_y = int(h_map // 2 + y_m / self.res)
        
        idx_x = np.clip(idx_x, 1, w_map - 2)
        idx_y = np.clip(idx_y, 1, h_map - 2)
        
        h_x = self.edf[idx_y, idx_x] - self.d_safe
        nx = (self.edf[idx_y + 1, idx_x] - self.edf[idx_y - 1, idx_x]) / (2 * self.res)
        ny = (self.edf[idx_y, idx_x + 1] - self.edf[idx_y, idx_x - 1]) / (2 * self.res)
        
        return h_x, nx, ny

    def nav_cb(self, msg_nav2):
        if self.edf is None:
            self.pub.publish(msg_nav2)
            return

        # Puntos de control: Centro, Frente y Esquinas
        check_points = [
            (0.0, 0.0),             # Centro del robot
            (self.lookahead, 0.0),  # Punto de anticipación frontal
            (0.25, 0.20),           # Esquina delantera izq
            (0.25, -0.20)           # Esquina delantera der
        ]

        # Matriz de costes
        P = matrix(np.diag([1.0, 1.5, 0.8])) 
        q = matrix(-np.array([msg_nav2.linear.x, 0.0, msg_nav2.angular.z], dtype=float))

        G_list = []
        h_list = []

        for px, py in check_points:
            h_val, nx, ny = self.get_constraints(px, py)
            
            # Condición de Ames: nx*vx + ny*vy >= -gamma * h^3
            # Invertimos para el solver G*u <= h:
            G_list.append([-nx, -ny, 0.0]) 
            h_list.append(self.gamma * (h_val**3))

        G = matrix(np.array(G_list, dtype=float))
        h_vec = matrix(np.array(h_list, dtype=float))

        try:
            sol = solvers.qp(P, q, G, h_vec)
            u = sol['x']
            
            safe_msg = Twist()
            safe_msg.linear.x = float(u[0])
            safe_msg.linear.y = float(u[1])
            safe_msg.angular.z = float(u[2])
            
            self.pub.publish(safe_msg)
        except:
            self.pub.publish(Twist())

def main():
    rclpy.init()
    rclpy.spin(SanchoCBF())
    rclpy.shutdown()