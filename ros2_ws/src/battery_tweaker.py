import rclpy
from rclpy.node import Node
from sensor_msgs.msg import BatteryState

class BatteryTweaker(Node):
    def __init__(self):
        super().__init__('battery_tweaker')
        
        # 1. Subscribe to the topic where the hardware is currently publishing
        self.subscription = self.create_subscription(
            BatteryState,
            '/fake_battery',
            self.listener_callback,
            10
        )
            
        # 2. Publish to the standard topic that the Behavior Tree expects
        self.publisher = self.create_publisher(
            BatteryState, 
            '/battery_state', 
            10
        )
        
        # 3. Parameter for dynamic percentage injection
        self.declare_parameter('spoofed_percentage', 50.0)
        self.get_logger().info("Reverse Tweaker active. Reading from /fake_battery, writing tweaked data to /battery_state.")

    def listener_callback(self, msg):
        # Retrieve the current parameter value
        fake_percentage = self.get_parameter('spoofed_percentage').value
        
        # Overwrite the percentage field
        msg.percentage = float(fake_percentage)
        
        # Publish the modified message down the pipeline
        self.publisher.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = BatteryTweaker()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()