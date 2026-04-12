import rclpy
from rclpy.node import Node
from geometry_msgs.msg import PoseStamped
from std_msgs.msg import String
from sancho_navigation.topology_manager import TopologyManager

class TopologyLocalizer(Node):
    def __init__(self):
        super().__init__('topology_localizer')
        self.declare_parameter('topology_file', 'topology.yaml')
        self.declare_parameter('pose_topic', '/amcl_pose')
        self.declare_parameter('publish_topic', '/current_room')
        self.declare_parameter('tolerance', 0.5)

        topology_path = self.get_parameter('topology_file').get_parameter_value().string_value
        self.tolerance = self.get_parameter('tolerance').get_parameter_value().double_value
        self.manager = TopologyManager()
        if not self.manager.load_graph(topology_path):
            self.get_logger().error(f'Failed to load topology from {topology_path}')

        self.pose_sub = self.create_subscription(
            PoseStamped,
            self.get_parameter('pose_topic').get_parameter_value().string_value,
            self.pose_callback,
            10)
        self.room_pub = self.create_publisher(String, self.get_parameter('publish_topic').get_parameter_value().string_value, 10)
        self.last_room = ''

    def pose_callback(self, msg: PoseStamped):
        room = self.manager.nearest_node(msg, self.tolerance)
        if room and room != self.last_room:
            self.last_room = room
            out = String()
            out.data = room
            self.room_pub.publish(out)
            self.get_logger().info(f'Current room: {room}')

def main(args=None):
    rclpy.init(args=args)
    node = TopologyLocalizer()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
