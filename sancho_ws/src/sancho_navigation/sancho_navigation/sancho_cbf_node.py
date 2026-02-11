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
        self.declare_parameter('d_safe', 0.35)
        self.declare_parameter('gamma_cbf', 10.0)
        self.declare_parameter('gamma_adapt', 0.1)
        self.declare_parameter('hopfield_eta', 0.001)
        self.declare_parameter('hopfield_rho', 100.0)
        self.declare_parameter('lookahead', 0.1)
        # ROS 2 Parameters
        self.d_safe = self.get_parameter('d_safe').value
        self.gamma_cbf = self.get_parameter('gamma_cbf').value
        self.gamma_adapt = self.get_parameter('gamma_adapt').value
        self.eta = self.get_parameter('hopfield_eta').value
        self.rho = self.get_parameter('hopfield_rho').value
        self.lookahead = self.get_parameter('lookahead').value
        # State and Adaptation
        self.theta_hat = 0.0  # Estimated friction/drag parameter
        self.lidar_points = {"1st": None, "2nd": None}
        
        qos_profile = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT)
        
        # Subscriptions
        self.create_subscription(LaserScan, '/scan_1st', self.scan_cb_1, qos_profile)
        self.create_subscription(LaserScan, '/scan_2nd', self.scan_cb_2, qos_profile)
        self.create_subscription(Twist, '/cmd_vel_nav2', self.nav_cb, 10)
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        # Publisher
        self.pub = self.create_publisher(Twist, '/cmd_vel', 10)
        
        self.get_logger().info("Sancho CaCBF Node Initialized with Hopfield Solver")

    def scan_cb_1(self, msg): self.process_scans(msg, "1st")
    def scan_cb_2(self, msg): self.process_scans(msg, "2nd")

    def process_scans(self, msg, lidar_id):
        ranges = np.array(msg.ranges)
        angles = np.linspace(msg.angle_min, msg.angle_max, len(ranges))
        mask = (ranges > 0.1) & (ranges < 4.0)
        pts = np.column_stack((ranges[mask]*np.cos(angles), ranges[mask]*np.sin(angles)))
        self.lidar_points[lidar_id] = pts

    def nav_cb(self, msg_nav2):
        # Merge all available lidar points
        all_pts = [p for p in self.lidar_points.values() if p is not None]
        if not all_pts:
            self.pub.publish(msg_nav2)
            return
        
        combined_points = np.vstack(all_pts)
        # Reference points on the robot for safety checks
        check_points = [
            (0.0, 0.0),             # Center
            (self.lookahead, 0.0),  # Front prediction
            (0.25, 0.22), (0.25, -0.22), # Front corners
            (-0.25, 0.22), (-0.25, -0.22) # Back corners
        ]
        # Desired control input from Nav2
        u_nom = np.array([msg_nav2.linear.x, 0.0, msg_nav2.angular.z])
        # QP objective: minimize ||u - u_nom||^2
        # (Actually we use weighted norm for smoother control)
        Q_qp = np.diag([1.0, 1.2, 0.8])
        c_qp = -Q_qp @ u_nom
        G_list, h_list = [], []
        
        # Adaptation Law calculation: dot_theta_hat = Gamma * L_Delta_h
        dot_theta_hat_sum = 0.0
        for px, py in check_points:
            # Distance to the nearest obstacle point
            dx = combined_points[:, 0] - px
            dy = combined_points[:, 1] - py
            dist_sq = dx**2 + dy**2
            min_idx = np.argmin(dist_sq)
            d_min = np.sqrt(dist_sq[min_idx])
            
            # Simple distance-based CBF: h = d - d_safe
            h_val = d_min - self.d_safe
            
            # Normal vector from obstacle to robot point
            nx = -dx[min_idx] / d_min
            ny = -dy[min_idx] / d_min
            # Dynamics: x_dot = f(x) + g(x)u + Delta(x)theta
            # Ignoring rotational dynamics for simple safety filter:
            # dot_d = nx * vx + ny * vy + (uncertainty term)
            # We assume theta affects the velocity directly as a drag factor: dot_d += theta * vx
            
            Lg_h = np.array([nx, ny, 0.0]) # Control Lie derivative
            LDelta_h = nx * u_nom[0] # Uncertainty Lie derivative (simplified)
            
            # Adaptive constraint: Lg_h * u >= -gamma * h - LDelta_h * theta_hat
            rhs = -self.gamma_cbf * (h_val**3) - LDelta_h * self.theta_hat
            
            G_list.append(-Lg_h)
            h_list.append(-rhs)
            
            # Accumulate adaptation part
            dot_theta_hat_sum += self.gamma_adapt * LDelta_h * h_val
        # Update parameter estimate (Euler step)
        self.theta_hat += dot_theta_hat_sum * 0.05 # Assuming 20Hz loop
        
        # Solve using Hopfield Network
        solver = HopfieldQPSolver(Q_qp, c_qp, G=np.array(G_list), h=np.array(h_list))
        u_safe = solver.solve(x0=u_nom, eta=self.eta, rho=self.rho)
        # Publish safe command
        safe_msg = Twist()
        safe_msg.linear.x = float(u_safe[0])
        safe_msg.linear.y = float(u_safe[1])
        safe_msg.angular.z = float(u_safe[2])
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