#!/usr/bin/env python3

import rclpy
from rclpy.node import Node
from std_msgs.msg import String

class FaceTester(Node):
    def __init__(self):
        super().__init__('face_tester')
        self.pub = self.create_publisher(String, 'face/mode', 10)
        self.get_logger().info('Face tester initialized. Ready to publish to face/mode.')

    def publish_command(self, cmd):
        msg = String()
        msg.data = cmd
        self.pub.publish(msg)
        self.get_logger().info(f'Published: "{cmd}"')

def main(args=None):
    rclpy.init(args=args)
    node = FaceTester()
    
    valid_modes = ["idle", "listening", "thinking", "speaking"]
    valid_emotions = ["happy", "surprised", "sad", "angry", "bored", "suspicious", "neutral"]
    
    print("\n" + "="*40)
    print("🤖 Face Node Tester 🤖")
    print("="*40)
    print("\nAvailable Modes:")
    print("  " + ", ".join(valid_modes))
    print("\nAvailable Emotions:")
    print("  " + ", ".join(valid_emotions))
    print("\nType 'quit', 'q' or 'exit' to stop.")
    
    try:
        while rclpy.ok():
            user_input = input("\n> Enter mode or emotion: ").strip().lower()
            if user_input in ['quit', 'exit', 'q']:
                break
            if user_input in valid_modes or user_input in valid_emotions:
                node.publish_command(user_input)
            elif user_input:
                print(f"⚠️ Warning: '{user_input}' is not a recognized mode or emotion.")
                print("It will still be published, but face_node might ignore it.")
                node.publish_command(user_input)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
