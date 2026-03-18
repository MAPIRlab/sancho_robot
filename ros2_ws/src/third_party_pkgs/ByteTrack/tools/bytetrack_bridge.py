import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import torch
import numpy as np

# ByteTrack/YOLOX imports
from yolox.exp import get_exp
from yolox.data.data_augment import preproc # Use the official normalization
from yolox.utils import fuse_model, postprocess
from yolox.utils.visualize import plot_tracking
from yolox.tracker.byte_tracker import BYTETracker

class ByteTrackCPUBridge(Node):
    def __init__(self):
        super().__init__('bytetrack_cpu_node')
        self.bridge = CvBridge()
        
        # 1. Setup Model
        exp_file = "exps/example/mot/yolox_tiny_mix_det.py"
        ckpt_file = "pretrained/bytetrack_tiny_mot17.pth.tar"
        
        self.exp = get_exp(exp_file, None)
        # SETTINGS MATCHING YOUR WORKING DEMO
        self.exp.test_conf = 0.3  # Restore to 0.3 as in your command line
        self.exp.nmsthre = 0.45 
        # Note: Do NOT manually change num_classes unless you know your weights are 1-class
        
        self.model = self.exp.get_model()
        self.model.eval()
        
        ckpt = torch.load(ckpt_file, map_location="cpu")
        self.model.load_state_dict(ckpt["model"])
        self.model = fuse_model(self.model)
        
        # 2. Tracker Setup
        class ByteTrackArgs:
            track_thresh = 0.5
            track_buffer = 30
            match_thresh = 0.8
            mot20 = False
            # Matching the demo's filter
            min_box_area = 10
            aspect_ratio_thresh = 1.6
        
        self.tracker_args = ByteTrackArgs()
        self.tracker = BYTETracker(self.tracker_args, frame_rate=5)
        self.test_size = (416, 416) 
        
        # Normalization values from Predictor class
        self.rgb_means = (0.485, 0.456, 0.406)
        self.std = (0.229, 0.224, 0.225)

        # 3. ROS Sub/Pub
        self.latest_image = None
        self.subscription = self.create_subscription(
            Image, '/sancho_camera/image_rect', self.image_callback, 10)
        self.publisher_ = self.create_publisher(Image, '/tracking_result', 10)
        self.timer = self.create_timer(1/5, self.process_frame) # 5.0 FPS

        self.get_logger().info("CPU Bridge Active. Properly Normalized for People Tracking.")

    def image_callback(self, msg):
        self.latest_image = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        
    def process_frame(self):
        frame = self.latest_image
        if frame is None:
            return
        
        # A. USE THE OFFICIAL PREPROC (Normalization + Resize)
        img, ratio = preproc(frame, self.test_size, self.rgb_means, self.std)
        img = torch.from_numpy(img).unsqueeze(0).float()
        
        # B. Inference
        with torch.no_grad():
            outputs = self.model(img)
            outputs = postprocess(outputs, self.exp.num_classes, self.exp.test_conf, self.exp.nmsthre)
        
        if outputs[0] is not None:
            # C. FILTER FOR CLASS 0 (Person)
            # This kills the "everything is an object" chaos
            output = outputs[0].cpu().numpy()
            person_mask = (output[:, 6] == 0)
            filtered_output = output[person_mask]

            if len(filtered_output) > 0:
                online_targets = self.tracker.update(
                    torch.from_numpy(filtered_output), 
                    frame.shape[:2], 
                    self.test_size
                )
                
                online_tlwhs, online_ids = [], []
                for t in online_targets:
                    # Apply final demo filters (area and aspect ratio)
                    tlwh = t.tlwh
                    vertical = tlwh[2] / tlwh[3] > self.tracker_args.aspect_ratio_thresh
                    if tlwh[2] * tlwh[3] > self.tracker_args.min_box_area and not vertical:
                        online_tlwhs.append(tlwh)
                        online_ids.append(t.track_id)
                
                frame = plot_tracking(frame, online_tlwhs, online_ids, frame_id=0, fps=0.0)

        out_msg = self.bridge.cv2_to_imgmsg(frame, "bgr8")
        self.publisher_.publish(out_msg)

def main():
    rclpy.init()
    node = ByteTrackCPUBridge()
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()