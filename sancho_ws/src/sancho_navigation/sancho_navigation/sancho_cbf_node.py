import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
import numpy as np
from cvxopt import matrix, solvers

solvers.options['show_progress'] = False

class SanchoCBF(Node):
    def __init__(self):
        super().__init__('sancho_cbf')
        
        # Parámetros 
        self.d_safe = 0.30      # Distancia de seguridad crítica
        self.gamma = 15.0       # Agresividad de la barrera de Ames
        self.lookahead = 0.45   # Horizonte de predicción frontal

        qos_profile = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        
        # Suscripciones
        self.create_subscription(LaserScan, '/scan_1st', self.scan_cb_1, qos_profile)
        self.create_subscription(LaserScan, '/scan_2nd', self.scan_cb_2, qos_profile)
        self.create_subscription(Twist, '/cmd_vel_nav2', self.nav_cb, qos_profile)
        self.pub = self.create_publisher(Twist, '/cmd_vel', qos_profile)
        
        self.lidar_points = {'1st': None, '2nd': None} # Nube de puntos local

    def process_scan(self, msg):
        """ Convierte LaserScan a coordenadas cartesianas locales """
        ranges = np.array(msg.ranges)
        angles = np.linspace(msg.angle_min, msg.angle_max, len(ranges))
        
        # Filtro de seguridad: descartar ceros e infinitos
        mask = (ranges > msg.range_min) & (ranges < 4.0) # Miramos hasta 4m
        r = ranges[mask]
        a = angles[mask]
        
        # Convertir a XY (Asumiendo que los frames laser_front/back están bien en el TF)
        # Si no tienes transformadas activas, aquí proyectamos relativo al sensor
        return np.column_stack((r * np.cos(a), r * np.sin(a)))

    def scan_cb_1(self, msg):
        self.lidar_points['1st'] = self.process_scan(msg)

    def scan_cb_2(self, msg):
        self.lidar_points['2nd'] = self.process_scan(msg)

    def nav_cb(self, msg_nav2):
        # Unimos todos los puntos disponibles
        all_pts = [p for p in self.lidar_points.values() if p is not None]
        if not all_pts:
            self.pub.publish(msg_nav2)
            return
        
        combined_points = np.vstack(all_pts)

        # Puntos de control del robot
        check_points = [
            (0.0, 0.0),             # Centro
            (self.lookahead, 0.0),  # Predicción frontal
            (0.25, 0.22), (0.25, -0.22), # Esquinas delanteras
            (-0.25, 0.22), (-0.25, -0.22) # Esquinas traseras
        ]

        # QP: [vx, vy, w]
        P = matrix(np.diag([1.0, 1.2, 0.8]))
        q = matrix(-np.array([msg_nav2.linear.x, 0.0, msg_nav2.angular.z], dtype=float))

        G_list, h_list = [], []

        for px, py in check_points:
            # Distancia de este punto del robot a TODOS los puntos de AMBOS lidars
            dx = combined_points[:, 0] - px
            dy = combined_points[:, 1] - py
            dist_sq = dx**2 + dy**2
            min_idx = np.argmin(dist_sq)
            d_min = np.sqrt(dist_sq[min_idx])
            
            h_val = d_min - self.d_safe
            nx = -dx[min_idx] / d_min
            ny = -dy[min_idx] / d_min

            G_list.append([-nx, -ny, 0.0])
            h_list.append(self.gamma * (h_val**3))

        G = matrix(np.array(G_list, dtype=float))
        h_vec = matrix(np.array(h_list, dtype=float))

        try:
            sol = solvers.qp(P, q, G, h_vec)
            u = sol['x']
            safe_msg = Twist()
            safe_msg.linear.x, safe_msg.linear.y, safe_msg.angular.z = float(u[0]), float(u[1]), float(u[2])
            self.pub.publish(safe_msg)
        except:
            self.pub.publish(Twist())

def main():
    rclpy.init()
    rclpy.spin(SanchoCBF())
    rclpy.shutdown()