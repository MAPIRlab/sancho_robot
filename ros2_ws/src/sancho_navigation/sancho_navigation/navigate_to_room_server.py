import os
import rclpy
from rclpy.node import Node
from rclpy.action import ActionServer, ActionClient
from geometry_msgs.msg import PoseStamped
from nav2_msgs.action import NavigateToPose
from sancho_navigation.action import NavigateToRoom
from sancho_navigation.topology_manager import TopologyManager

class NavigateToRoomServer(Node):
    def __init__(self):
        super().__init__('navigate_to_room_server')
        # Parameters
        self.declare_parameter('topology_file', 'topology.yaml')
        self.declare_parameter('use_sim_time', False)
        topology_path = self.get_parameter('topology_file').get_parameter_value().string_value
        # Load topology
        self.manager = TopologyManager()
        if not self.manager.load_graph(topology_path):
            self.get_logger().error(f'Failed to load topology from {topology_path}')
        # Action server for custom NavigateToRoom
        self._as = ActionServer(
            self,
            NavigateToRoom,
            'navigate_to_room',
            execute_callback=self.execute_callback)
        # Action client to Nav2 NavigateToPose
        self._nav_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.get_logger().info('NavigateToRoom action server ready')

    def execute_callback(self, goal_handle):
        room_label = goal_handle.request.room_label
        self.get_logger().info(f'Received request to navigate to room: {room_label}')
        node_id = self.manager.get_node_by_label(room_label)
        if node_id is None:
            self.get_logger().error(f'Room label {room_label} not found in topology')
            goal_handle.abort()
            result = NavigateToRoom.Result()
            result.success = False
            result.message = f'Room {room_label} not found'
            return result
        # Retrieve node data from graph
        data = self.manager.graph.nodes[node_id]
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = data.get('x', 0.0)
        pose.pose.position.y = data.get('y', 0.0)
        pose.pose.position.z = 0.0
        # Simple yaw to quaternion (no roll/pitch)
        import tf_transformations
        q = tf_transformations.quaternion_from_euler(0, 0, data.get('yaw', 0.0))
        pose.pose.orientation.x = q[0]
        pose.pose.orientation.y = q[1]
        pose.pose.orientation.z = q[2]
        pose.pose.orientation.w = q[3]
        # Send goal to Nav2
        if not self._nav_client.wait_for_server(timeout_sec=5.0):
            self.get_logger().error('NavigateToPose action server not available')
            goal_handle.abort()
            result = NavigateToRoom.Result()
            result.success = False
            result.message = 'Nav2 action server unavailable'
            return result
        nav_goal = NavigateToPose.Goal()
        nav_goal.pose = pose
        send_future = self._nav_client.send_goal_async(nav_goal)
        rclpy.spin_until_future_complete(self, send_future)
        nav_handle = send_future.result()
        if not nav_handle.accepted:
            self.get_logger().error('Nav2 goal rejected')
            goal_handle.abort()
            result = NavigateToRoom.Result()
            result.success = False
            result.message = 'Nav2 goal rejected'
            return result
        # Wait for result
        result_future = nav_handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future)
        nav_result = result_future.result().result
        # Populate custom result
        result = NavigateToRoom.Result()
        result.success = True
        result.message = f'Arrived at room {room_label}'
        goal_handle.succeed()
        return result

def main(args=None):
    rclpy.init(args=args)
    node = NavigateToRoomServer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
