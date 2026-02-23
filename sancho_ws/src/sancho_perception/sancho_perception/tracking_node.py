import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from cv_bridge import CvBridge
import cv2
import torch
import numpy as np
import sys
import os
from sancho_msgs.msg import FaceDetectionArray, FaceDetection
from geometry_msgs.msg import Point

from ament_index_python.packages import get_package_share_directory

# 1. Rutas del sistema
pkg_share = get_package_share_directory('sancho_perception')

from yolox.exp import get_exp
from yolox.data.data_augment import preproc
from yolox.utils import fuse_model, postprocess
from yolox.utils.visualize import plot_tracking
from yolox.tracker.byte_tracker import BYTETracker

class SanchoTrackingNode(Node):
    def __init__(self):
        super().__init__('sancho_tracking_node')
        self.bridge = CvBridge()
        
        self.exp_file = os.path.join(pkg_share, "exps/yolox_tiny_mix_det.py")
        self.ckpt_file = os.path.join(pkg_share, "models/bytetrack_tiny_mot17.pth.tar")
        
        # 2. Setup del Modelo YOLOX
        self.exp = get_exp(self.exp_file, None)
        self.exp.test_conf = 0.3 
        self.exp.nmsthre = 0.45 
        
        self.get_logger().info("Cargando modelo PyTorch en CPU...")
        self.model = self.exp.get_model()
        self.model.eval()
        
        ckpt = torch.load(self.ckpt_file, map_location="cpu")
        self.model.load_state_dict(ckpt["model"])
        self.model = fuse_model(self.model)
        
        # 3. Setup del Tracker
        class ByteTrackArgs:
            track_thresh = 0.5
            track_buffer = 30
            match_thresh = 0.8
            mot20 = False
            min_box_area = 10
            aspect_ratio_thresh = 1.6
        
        self.tracker_args = ByteTrackArgs()
        self.tracker = BYTETracker(self.tracker_args, frame_rate=30)
        self.test_size = (416, 416) 
        
        self.rgb_means = (0.485, 0.456, 0.406)
        self.std = (0.229, 0.224, 0.225)

        # 4. Suscriptores y Publicadores
        self.subscription = self.create_subscription(
            Image, '/sancho_camera/image_rect', self.image_callback, 10)
        self.publisher_ = self.create_publisher(Image, '/sancho_perception/tracking_viz', 10)
        self.human_tracking_pub = self.create_publisher(FaceDetectionArray, '/sancho_perception/human_tracking', 10)
        
        self.get_logger().info("Nodo Sancho Tracking (PyTorch CPU) Activo.")

    def image_callback(self, msg):
        try:
            # Convert incoming ROS message to OpenCV
            frame = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            self.get_logger().error(f"Error reading image: {e}")
            return
            
        # Create a deep copy of the original frame to send to the Fusion node
        # This prevents the tracking boxes from being drawn onto the face recognition input
        original_frame = frame.copy()
        
        # A. Preprocesamiento oficial
        img, ratio = preproc(frame, self.test_size, self.rgb_means, self.std)
        img = torch.from_numpy(img).unsqueeze(0).float()
        
        # B. Inferencia
        with torch.no_grad():
            outputs = self.model(img)
            outputs = postprocess(outputs, self.exp.num_classes, self.exp.test_conf, self.exp.nmsthre)
        
        # Initialize lists at the top of the logic block to prevent UnboundLocalError
        online_tlwhs = []
        online_ids = []
        
        if outputs[0] is not None:
            # C. Filtrar para clase 0 (Persona)
            output = outputs[0].cpu().numpy()
            person_mask = (output[:, 6] == 0)
            filtered_output = output[person_mask]

            if len(filtered_output) > 0:
                # D. Actualizar Tracker
                online_targets = self.tracker.update(
                    torch.from_numpy(filtered_output), 
                    frame.shape[:2], 
                    self.test_size
                )
                
                for t in online_targets:
                    tlwh = t.tlwh
                    # Filtros de área y aspecto para evitar falsos positivos
                    vertical = tlwh[2] / tlwh[3] > self.tracker_args.aspect_ratio_thresh
                    if tlwh[2] * tlwh[3] > self.tracker_args.min_box_area and not vertical:
                        online_tlwhs.append(tlwh)
                        online_ids.append(t.track_id)
                
                # Pintar los resultados en el frame modificado para visualización
                frame = plot_tracking(frame, online_tlwhs, online_ids, frame_id=0, fps=0.0)

            # E. Publicar tracking de humanos como FaceDetectionArray
            tracking_msg = FaceDetectionArray()
            tracking_msg.header = msg.header
            
            # ROOT CAUSE FIX: Re-encode the image to detach it from the incoming msg reference
            tracking_msg.image = self.bridge.cv2_to_imgmsg(original_frame, "bgr8")
            tracking_msg.image.header = msg.header
            
            for i in range(len(online_tlwhs)):
                det = FaceDetection()
                tlwh = online_tlwhs[i]
                det.corner = Point(x=float(tlwh[0]), y=float(tlwh[1]), z=0.0)
                det.width = float(tlwh[2])
                det.height = float(tlwh[3])
                det.tid = int(online_ids[i])
                det.confidence = 1.0 
                tracking_msg.detections.append(det)
                
            self.human_tracking_pub.publish(tracking_msg)

        # Publicar el resultado visual
        out_msg = self.bridge.cv2_to_imgmsg(frame, "bgr8")
        out_msg.header = msg.header
        self.publisher_.publish(out_msg)

def main():
    rclpy.init()
    node = SanchoTrackingNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()