import rclpy
from rclpy.node import Node
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
        
        # Suscripciones
        self.create_subscription(LaserScan, '/scan_merged', self.scan_cb, 10)
        self.create_subscription(Twist, '/cmd_vel_nav2', self.nav_cb, 10)
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        self.points_xyz = None # Nube de puntos local

    def scan_cb(self, msg):
        # Convertimos el scan (polares) a puntos Cartesianos locales [x, y]
        ranges = np.array(msg.ranges)
        angles = np.linspace(msg.angle_min, msg.angle_max, len(ranges))
        
        # Filtramos lecturas válidas
        mask = (ranges > 0.05) & (ranges < 3.0)
        r = ranges[mask]
        a = angles[mask]
        
        # Transformación a coordenadas del robot (x adelante, y izquierda)
        self.points_xyz = np.column_stack((r * np.cos(a), r * np.sin(a)))

    def nav_cb(self, msg_nav2):
        if self.points_xyz is None:
            self.pub.publish(msg_nav2)
            return

        # Puntos críticos del footprint de Sancho
        check_points = [
            (0.0, 0.0),             # Centro
            (self.lookahead, 0.0),  # Frente
            (0.25, 0.22),           # Esquina Delantera Izq
            (0.25, -0.22)           # Esquina Delantera Der
        ]

        # QP: u = [vx, vy, w]
        P = matrix(np.diag([1.0, 1.2, 0.8])) 
        q = matrix(-np.array([msg_nav2.linear.x, 0.0, msg_nav2.angular.z], dtype=float))

        G_list = []
        h_list = []

        # Para cada punto del robot, buscamos el obstáculo más cercano en el scan
        for px, py in check_points:
            # Calculamos distancias de este punto de control a TODOS los puntos del LiDAR
            # dist = sqrt((x_obs - px)^2 + (y_obs - py)^2)
            dx = self.points_xyz[:, 0] - px
            dy = self.points_xyz[:, 1] - py
            distances = np.sqrt(dx**2 + dy**2)
            
            min_idx = np.argmin(distances)
            d_min = distances[min_idx]
            
            # h(x) para este punto específico
            h_val = d_min - self.d_safe
            
            # Gradiente
            nx = -dx[min_idx] / d_min
            ny = -dy[min_idx] / d_min

            # Restricción de Ames: dot(h) >= -gamma * h^3
            # nx*vx + ny*vy >= -gamma * h^3  =>  -nx*vx - ny*vy <= gamma * h^3
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