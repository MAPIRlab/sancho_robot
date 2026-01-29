import rclpy
from rclpy.node import Node
from geometry_msgs.msg import Twist
from nav_msgs.msg import OccupancyGrid
import numpy as np
from cvxopt import matrix, solvers
from scipy.ndimage import distance_transform_edt

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
        
        #self.costmap = None
        self.resolution = 0.05
        self.edf = None


#    def costmap_callback(self, msg):
#        grid = np.array(msg.data).reshape((msg.info.height, msg.info.width))
#        self.costmap = grid
#        self.resolution = msg.info.resolution
    

    def costmap_callback(self, msg):
        self.resolution = msg.info.resolution
        
        # Convertir a binario: 1 si es libre, 0 si es obstáculo
        shape = np.array(msg.data).reshape((msg.info.height, msg.info.width))
        binary_map = np.where(shape < 50, 1, 0)

        # Transformada de Distancia Euclídea
        self.edf = distance_transform_edt(binary_map) * self.resolution

    
    def get_edf_cbf(self):
        h, w = self.edf.shape
        cy, cx = h // 2, w // 2 # Posición del robot (centro del mapa local)
        
        # h(x) es la distancia leída directamente del EDF en la posición del robot
        dist_actual = self.edf[cy, cx]
        h_x = dist_actual - self.d_safe
        
        # Gradiente: miramos la pendiente de la distancia alrededor del robot
        gx = (self.edf[cy, cx+1] - self.edf[cy, cx-1]) / (2 * self.res)
        gy = (self.edf[cy+1, cx] - self.edf[cy-1, cx]) / (2 * self.res)

#    def get_barrier_data(self):
#        h, w = self.costmap.shape
#        cy, cx = h // 2, w // 2
#        
#        window = self.costmap[cy-10:cy+10, cx-10:cx+10]
        
#        # h(x) aproximado
#        max_cost = np.max(window)
#        dist_to_obs = (100 - max_cost) / 100.0 * 0.5
        
#        h_x = dist_to_obs - 0.05 # Margen crítico
        
#        # Gradiente
#        gy, gx = np.gradient(window)
#        nx = -np.mean(gx)
#        ny = -np.mean(gy)
        
#        return h_x, nx, ny

    def nav2_callback(self, msg_nav2):
#        if self.costmap is None:
#            self.pub.publish(msg_nav2)
#            return

#        h_x, nx, ny = self.get_barrier_data()

        if self.edf is None:
            self.pub.publish(msg_nav2)
            return

        h_x, nx, ny = self.get_edf_cbf()

        # --- OPTIMIZACIÓN CUADRÁTICA (QP) ---
        # Queremos min 1/2 * |v - v_nav2|^2
        # P = Identidad, q = -v_nav2
        P = matrix(np.eye(2, dtype=float))
        q = matrix(-np.array([msg_nav2.linear.x, msg_nav2.angular.z], dtype=float))

        # Restricción: dot(v, n) >= -gamma * h(x)^3
        # Que es lo mismo que: -nx*vx - ny*vy <= gamma * h(x)^3
        G = matrix(-np.array([[nx, 0.0]], dtype=float))
        h = matrix(np.array([self.gamma * (h_x**3)], dtype=float))

        try:
            sol = solvers.qp(P, q, G, h)
            v_optimal = sol['x']
            
            safe_msg = Twist()
            safe_msg.linear.x = float(v_optimal[0])
            safe_msg.angular.z = float(v_optimal[1])
            
            self.pub.publish(safe_msg)
        except:
            self.pub.publish(Twist())

def main():
    rclpy.init()
    rclpy.spin(SanchoCBFNode())
    rclpy.shutdown()