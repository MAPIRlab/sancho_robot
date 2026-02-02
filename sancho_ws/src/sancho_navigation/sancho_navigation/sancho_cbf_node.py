import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy
from geometry_msgs.msg import Twist
from sensor_msgs.msg import LaserScan
import numpy as np
import os
import sys

# Ensure local imports work
sys.path.append(os.path.dirname(__file__))
from hopfield_solver_lib import HopfieldQPSolver
class SanchoCBF(Node):
    def __init__(self):
        super().__init__('sancho_cbf')
        
        # Declare Parameters
        self.declare_parameter('d_safe', 0.20)  # Reduced for closer following
        self.declare_parameter('gamma_cbf', 5.0)  # Linear gain for smoother response
        self.declare_parameter('gamma_adapt', 0.05)
        self.declare_parameter('hopfield_eta', 0.005) # Increased learning rate for solver
        self.declare_parameter('hopfield_rho', 150.0)
        self.declare_parameter('min_turning_radius', 0.4764)
        
        # ROS 2 Parameters
        self.d_safe = self.get_parameter('d_safe').value
        self.gamma_cbf = self.get_parameter('gamma_cbf').value
        self.gamma_adapt = self.get_parameter('gamma_adapt').value
        self.eta = self.get_parameter('hopfield_eta').value
        self.rho = self.get_parameter('hopfield_rho').value
        self.r_min = self.get_parameter('min_turning_radius').value
        
        # State and Adaptation
        self.theta_hat = 0.0  
        self.lidar_points = {"1st": None, "2nd": None}
        
        qos_profile = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        
        # Subscriptions
        self.create_subscription(LaserScan, '/scan_1st', self.scan_cb_1, qos_profile)
        self.create_subscription(LaserScan, '/scan_2nd', self.scan_cb_2, qos_profile)
        self.create_subscription(Twist, '/cmd_vel_nav2', self.nav_cb, 10)
        
        # Publisher
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        self.get_logger().info("Sancho CBF Node: Ackermann Model Initialized")

    def scan_cb_1(self, msg): self.process_scans(msg, "1st")
    def scan_cb_2(self, msg): self.process_scans(msg, "2nd")

    def process_scans(self, msg, lidar_id):
        ranges = np.array(msg.ranges)
        angles = np.linspace(msg.angle_min, msg.angle_max, len(ranges))
        mask = (ranges > 0.05) & (ranges < 3.5)
        pts = np.column_stack((ranges[mask]*np.cos(angles), ranges[mask]*np.sin(angles)))
        self.lidar_points[lidar_id] = pts

    def nav_cb(self, msg_nav2):
        # Merge all available lidar points
        all_pts = [p for p in self.lidar_points.values() if p is not None]
        if not all_pts or (msg_nav2.linear.x == 0 and msg_nav2.angular.z == 0):
            # Pass through if no obstacles or no motion
            self.pub.publish(msg_nav2)
            return
        
        combined_points = np.vstack(all_pts)
        
        # Footprint corners and safety points
        # Robot dimension: Length 0.75m, Width 0.55m
        check_points = [
            (0.375, 0.275), (0.375, -0.275),   # Front corners
            (0.0, 0.275),   (0.0, -0.275),     # Sides
            (-0.375, 0.275), (-0.375, -0.275), # Back corners
            (0.45, 0.0)                        # Virtual Front bumper
        ]
        
        # ACKERMANN MODEL: u = [v, omega]
        u_nom = np.array([msg_nav2.linear.x, msg_nav2.angular.z])
        
        # QP objective: minimize ||u - u_nom||^2
        # We weigh rotational changes less to keep orientation stable
        Q_qp = np.diag([1.0, 0.5])
        c_qp = -Q_qp @ u_nom
        G_list, h_list = [], []
        
        # 1. ACKERMANN STEERING CONSTRAINTS: |omega| <= |v|/R_min
        # Linearized around v_nom to keep it a standard QP
        v_abs_base = max(abs(u_nom[0]), 0.1) 
        k_max = 1.0 / self.r_min
        
        # G @ u <= h  =>  [ -k_max,  1 ] * [v, w] <= 0
        #                 [ -k_max, -1 ] * [v, w] <= 0
        if u_nom[0] >= 0:
            G_list.append(np.array([-k_max, 1.0]))
            h_list.append(0.0)
            G_list.append(np.array([-k_max, -1.0]))
            h_list.append(0.0)
        else:
            G_list.append(np.array([k_max, 1.0]))
            h_list.append(0.0)
            G_list.append(np.array([k_max, -1.0]))
            h_list.append(0.0)

        # 2. CBF SAFETY CONSTRAINTS
        dot_theta_hat_sum = 0.0
        for px, py in check_points:
            dx = combined_points[:, 0] - px
            dy = combined_points[:, 1] - py
            dist_sq = dx**2 + dy**2
            min_idx = np.argmin(dist_sq)
            d_min = np.sqrt(dist_sq[min_idx])
            
            # Normal vector from obstacle to point on robot (in robot frame)
            nx = -dx[min_idx] / d_min
            ny = -dy[min_idx] / d_min
            
            # Control Lie derivative Lg_h for Ackermann:
            # point velocity: [v - omega*py, omega*px]
            # dot_d = nx * (v - omega*py) + ny * (omega*px)
            # dot_d = [nx] * v + [ny*px - nx*py] * omega
            Lg_h = np.array([nx, ny*px - nx*py])
            
            # Adaptive CBF: h_val = d - d_safe
            h_val = d_min - self.d_safe
            
            # Adaptive constraint: Lg_h * u >= -gamma * h - LDelta_h * theta_hat
            # We assume uncertainty affects linear velocity
            LDelta_h = nx * u_nom[0]
            rhs = -self.gamma_cbf * h_val - LDelta_h * self.theta_hat
            
            G_list.append(-Lg_h)
            h_list.append(-rhs)
            
            dot_theta_hat_sum += self.gamma_adapt * LDelta_h * h_val

        # Update parameter estimate
        self.theta_hat += dot_theta_hat_sum * 0.05 
        
        # Solve with Hopfield Solver
        solver = HopfieldQPSolver(Q_qp, c_qp, G=np.array(G_list), h=np.array(h_list))
        u_safe = solver.solve(x0=u_nom, eta=self.eta, rho=self.rho)
        
        # Publish
        safe_msg = Twist()
        safe_msg.linear.x = float(u_safe[0])
        safe_msg.angular.z = float(u_safe[1])
        self.pub.publish(safe_msg)
def main():
    rclpy.init()
    node = SanchoCBF()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()
if __name__ == '__main__':
    main()