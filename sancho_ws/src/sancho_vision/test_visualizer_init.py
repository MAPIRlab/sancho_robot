import rclpy
from sancho_vision.face_visualizer_node import FaceVisualizerNode
import sys

def test_init():
    rclpy.init()
    try:
        node = FaceVisualizerNode()
        print("FaceVisualizerNode initialized successfully.")
        node.destroy_node()
        return True
    except Exception as e:
        print(f"Failed to initialize FaceVisualizerNode: {e}")
        return False
    finally:
        rclpy.shutdown()

if __name__ == "__main__":
    if test_init():
        sys.exit(0)
    else:
        sys.exit(1)
