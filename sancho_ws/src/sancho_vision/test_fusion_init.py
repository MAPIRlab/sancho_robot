import rclpy
from sancho_vision.body_face_fusion_node import BodyFaceFusionNode
import sys

def test_init():
    rclpy.init()
    try:
        node = BodyFaceFusionNode()
        print("BodyFaceFusionNode initialized successfully.")
        node.destroy_node()
        return True
    except Exception as e:
        print(f"Failed to initialize BodyFaceFusionNode: {e}")
        return False
    finally:
        rclpy.shutdown()

if __name__ == "__main__":
    if test_init():
        sys.exit(0)
    else:
        sys.exit(1)
