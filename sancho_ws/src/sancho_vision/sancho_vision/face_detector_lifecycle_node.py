#!/usr/bin/env python3
"""Nodo ROS2 Lifecycle para detección facial (ROS2 Humble)
- Uso de LifecycleNode
- Procesamiento asíncrono con ThreadPoolExecutor
- Suavizado EMA de bounding boxes
- Umbral de confianza y NMS configurable
- Visualización opcional
"""
import os

import cv2
import dlib
import numpy as np
import rclpy
from ament_index_python.packages import get_package_share_directory
from cv_bridge import CvBridge, CvBridgeError
from geometry_msgs.msg import Point
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn
from rclpy.qos import QoSProfile
from sancho_msgs.msg import Face, FaceArray
from sensor_msgs.msg import Image

package_path = get_package_share_directory("sancho_vision")


class FaceDetectorLifecycleNode(LifecycleNode):
    """FaceDetectorLifecycleNode: A ROS 2 managed lifecycle node for real-time face detection.

    This node subscribes to camera images and publishes detected faces as FaceArray messages.
    It implements the lifecycle node state machine (configure, activate, deactivate, cleanup)
    to ensure proper resource management and predictable behavior.

    Features:
    - Configurable face detection using either dlib's HOG-based detector (fast) or CNN-based detector (more accurate)
    - Non-maximum suppression for merging overlapping detections
    - Optional visualization of face detections on images
    - Configurable downscaling for performance optimization
    - Rate-limited processing to manage computational load

    Parameters
    ----------
        image_topic (str): Topic name for input camera images
        detections_topic (str): Topic name for publishing face detections
        use_cnn (bool): Whether to use CNN-based detector (True) or HOG-based detector (False)
        cnn_model_path (str): Path to CNN model file (if empty, uses default path)
        confidence_threshold (float): Minimum confidence threshold for face detections
        nms_iou_threshold (float): IoU threshold for non-maximum suppression
        ema_alpha (float): Exponential moving average factor for smoothing detections
        downscale_factor (float): Factor to downscale images for faster processing
        visualization (bool): Whether to publish visualization images
        processing_rate (float): Rate in Hz at which to process images
        visualization_topic (str): Topic name for publishing visualization images

    Publishers:
        detections_topic (FaceArray): Publishes detected faces with confidence scores
        visualization_topic (Image): Publishes images with face detection visualizations (if enabled)

    Subscribers:
        image_topic (Image): Subscribes to camera images for processing

    Lifecycle Transitions:
        on_configure: Initializes detector and publishers
        on_activate: Creates subscribers and starts processing timer
        on_deactivate: Stops processing and removes subscribers
        on_cleanup: Cleans up all resources

    """

    def __init__(self):
        super().__init__("face_detector_lifecycle")

        self.declare_parameters(
            namespace="",
            parameters=[
                ("image_topic", "/sancho_camera/image_rect"),
                ("detections_topic", "/face_detections"),
                ("use_cnn", False),
                ("cnn_model_path", ""),
                ("confidence_threshold", 0.5),
                ("nms_iou_threshold", 0.3),
                ("ema_alpha", 0.3),
                ("downscale_factor", 0.5),
                ("visualization", True),
                ("processing_rate", 10.0),
                ("visualization_topic", "/face_detections/vis"),
            ],
        )

        self.bridge = CvBridge()

    def on_configure(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo...")

        self.use_cnn = self.get_parameter("use_cnn").value
        cnn_override = self.get_parameter("cnn_model_path").value
        cnn_default = os.path.join(
            package_path, "models", "mmod_human_face_detector.dat"
        )
        self.cnn_model_path = cnn_override if cnn_override else cnn_default
        self.conf_thresh = self.get_parameter("confidence_threshold").value
        self.nms_iou = self.get_parameter("nms_iou_threshold").value
        self.ema_alpha = self.get_parameter("ema_alpha").value
        self.ds_factor = self.get_parameter("downscale_factor").value
        self.visualization = self.get_parameter("visualization").value
        self.processing_rate = self.get_parameter("processing_rate").value

        if self.use_cnn:
            if not os.path.exists(self.cnn_model_path):
                self.get_logger().error(
                    f"Modelo CNN no encontrado: {self.cnn_model_path}"
                )
                return TransitionCallbackReturn.FAILURE
            self.detector = dlib.cnn_face_detection_model_v1(self.cnn_model_path)
            self.get_logger().info("Detector CNN de Dlib activado")
        else:
            self.detector = dlib.get_frontal_face_detector()
            self.get_logger().info("Detector Dlib activado")

        qos = QoSProfile(depth=10)
        self.pub = self.create_lifecycle_publisher(
            FaceArray, self.get_parameter("detections_topic").value, qos
        )
        if self.visualization:
            self.vis_pub = self.create_lifecycle_publisher(
                Image, self.get_parameter("visualization_topic").value, qos
            )

        return super().on_configure(state)

    def on_activate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo...")
        qos = QoSProfile(depth=10)
        self.sub = self.create_subscription(
            Image, self.get_parameter("image_topic").value, self.image_callback, qos
        )
        self.latest_img = None
        self.smoothed_boxes = []

        self.timer = self.create_timer(1.0 / self.processing_rate, self.process_image)
        self.get_logger().info(
            f"Nodo activado, subscrito a {self.get_parameter('image_topic').value}"
        )
        return super().on_activate(state)

    def on_deactivate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo...")
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.sub:
            self.destroy_subscription(self.sub)
            self.sub = None
        return super().on_deactivate(state)

    def on_cleanup(self, state) -> TransitionCallbackReturn:
        if self.timer:
            self.timer.cancel()
            self.timer = None
        if self.sub:
            self.destroy_subscription(self.sub)
            self.sub = None
        if self.pub:
            self.destroy_publisher(self.pub)
            self.pub = None
        if self.vis_pub:
            self.destroy_publisher(self.vis_pub)
            self.vis_pub = None
        return super().on_cleanup(state)

    def image_callback(self, msg):
        self.latest_img = msg

    def process_image(self):
        if self.latest_img is None:
            return
        try:
            cv_img = self.bridge.imgmsg_to_cv2(self.latest_img, "bgr8")
        except CvBridgeError as e:
            self.get_logger().error(f"CvBridge error: {e}")
            return

        small = cv2.resize(cv_img, None, fx=self.ds_factor, fy=self.ds_factor)
        scale = cv_img.shape[1] / small.shape[1]

        boxes, scores = [], []
        # Detección con CNN o HOG
        if self.use_cnn:
            dets = self.detector(small, 1)
            for d in dets:
                rect = d.rect
                conf = d.confidence
                boxes.append(
                    [
                        rect.left() * scale,
                        rect.top() * scale,
                        rect.right() * scale,
                        rect.bottom() * scale,
                    ]
                )
                scores.append(conf)
        else:
            dets, confidences, _ = self.detector.run(small, 0)
            for rect, conf in zip(dets, confidences, strict=False):
                boxes.append(
                    [
                        rect.left() * scale,
                        rect.top() * scale,
                        rect.right() * scale,
                        rect.bottom() * scale,
                    ]
                )
                scores.append(conf)

        idxs = cv2.dnn.NMSBoxes(boxes, scores, self.conf_thresh, self.nms_iou)
        filtered, filtered_scores = [], []
        if idxs is not None and len(idxs) > 0:
            if isinstance(idxs, tuple):
                idxs = np.array(idxs)
            for i in idxs.flatten():
                filtered.append(boxes[i])
                filtered_scores.append(scores[i])

        fa = FaceArray(header=self.latest_img.header)
        for box, sc in zip(filtered, filtered_scores, strict=False):
            cx, cy = (box[0] + box[2]) / 2, (box[1] + box[3]) / 2
            face = Face(
                header=self.latest_img.header,
                center=Point(x=cx, y=cy, z=0.0),
                width=box[2] - box[0],
                height=box[3] - box[1],
                confidence=sc,
            )
            fa.faces.append(face)

        self.pub.publish(fa)
        self.get_logger().info(f"Publicadas {len(fa.faces)} detecciones")

        if self.visualization:
            vis_img = cv_img.copy()
            for box in filtered:
                cv2.rectangle(
                    vis_img,
                    (int(box[0]), int(box[1])),
                    (int(box[2]), int(box[3])),
                    (0, 255, 0),
                    2,
                )
            vis_msg = self.bridge.cv2_to_imgmsg(vis_img, "bgr8")
            vis_msg.header = self.latest_img.header
            self.vis_pub.publish(vis_msg)


def main(args=None):
    rclpy.init(args=args)
    node = FaceDetectorLifecycleNode()
    rclpy.spin(node)
    rclpy.shutdown()


if __name__ == "__main__":
    main()
