import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2

from sancho_msgs.msg import FaceRecognitionArray
from .api.gui_utils import mark_face

class FaceVisualizerNode(Node):
    def __init__(self):
        super().__init__('face_visualizer_node')
        self.bridge = CvBridge()

        # Parameters
        self.declare_parameters(namespace='', parameters=[
            ('face_recognitions_topic', '/face_recognitions'),
            ('output_image_topic', '/face_recognitions/visual'),
            ('middle_bound', 0.80),
            ('upper_bound', 0.90),
            ('show_distance', True),
            ('show_score', True),
            ('draw_rectangle', True)
        ])

        input_topic = self.get_parameter('face_recognitions_topic').value
        output_topic = self.get_parameter('output_image_topic').value

        # Subscriptions and Publishers
        self.sub_recog = self.create_subscription(FaceRecognitionArray, input_topic, self.callback, 10)
        self.pub_viz = self.create_publisher(Image, output_topic, 10)

        self.get_logger().info(f"Face Visualizer Node started. Subscribed to {input_topic}, publishing to {output_topic}")

    def callback(self, msg: FaceRecognitionArray):
        # 1. Handle "No Detections" Case
        if not msg.detections:
            # If we have an image but no people, just publish the clean image
            if msg.image.data:
                # FIX: Use pub_viz, not the non-existent pub_recog
                self.pub_viz.publish(msg.image) 
            return

        # 2. Convert to OpenCV
        try:
            frame = self.bridge.imgmsg_to_cv2(msg.image, desired_encoding="bgr8")
        except Exception as e:
            self.get_logger().error(f"Error converting image: {e}")
            return

        # 3. Get Drawing Parameters
        middle_bound = self.get_parameter('middle_bound').value
        upper_bound = self.get_parameter('upper_bound').value
        show_distance = self.get_parameter('show_distance').value
        show_score = self.get_parameter('show_score').value
        draw_rectangle = self.get_parameter('draw_rectangle').value

        # 4. Iterate and Draw
        # We can safely zip because the Fusion node guarantees lists are same length
        for det, recog in zip(msg.detections, msg.recognitions):
            x = int(det.corner.x)
            y = int(det.corner.y)
            w = int(det.width)
            h = int(det.height)
            position = [x, y, w, h]
            
            # Now safely populated by the Fusion node
            distance = recog.distance 
            confidence = det.confidence
            
            # Logic for display name
            cid = recog.classified_id
            cname = recog.classified_name
            
            # If we have a name, use it; otherwise check if we have a temporary ID
            if cname:
                display_name = cname
            elif cid:
                display_name = f"ID: {cid}"
            else:
                display_name = "Unknown"
            
            # Draw using your GUI util
            mark_face(
                frame, 
                position, 
                distance, 
                middle_bound, 
                upper_bound, 
                display_name, 
                drawRectangle=draw_rectangle, 
                score=confidence, 
                showDistance=show_distance, 
                showScore=show_score,
                tracker_id=det.tid if det.tid > 0 else None
            )

        # 5. Publish Final Image
        out_msg = self.bridge.cv2_to_imgmsg(frame, "bgr8")
        out_msg.header = msg.header
        self.pub_viz.publish(out_msg)

def main(args=None):
    rclpy.init(args=args)
    node = FaceVisualizerNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()