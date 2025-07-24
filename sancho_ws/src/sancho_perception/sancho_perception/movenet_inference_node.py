#!/usr/bin/env python3
"""Nodo de inferencia con MoveNet que procesa imágenes, detecta poses humanas,
publica detecciones, Tiempo de inferencia y marcadores en CV y RViz.
"""
import time

import cv2
import numpy as np
import rclpy
import tf2_ros
from cv_bridge import CvBridge, CvBridgeError
from rcl_interfaces.msg import SetParametersResult
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import QoSProfile
from sensor_msgs.msg import Image
from std_msgs.msg import Float32
from visualization_msgs.msg import MarkerArray

from sancho_msgs.msg import PersonPose, PersonsPoses

from .movenet_utils import load_model, process_detections, run_inference_on_image


class MoveNetInferenceNode(LifecycleNode):
    """MoveNetInferenceNode - ROS2 Lifecycle Node for person pose detection using MoveNet.

    This node performs human pose detection on incoming camera images using Google's MoveNet model.
    It processes images from a subscribed topic, runs pose detection inference, and publishes pose
    data for detected persons. Multiple visualization options are available including OpenCV markers
    and RViz markers.

    Parameters
    ----------
        inference.mirror (bool, default=False): Whether to mirror input images horizontally
        inference.input_size (int, default=256): Input resolution for the neural network
        inference.model_url (str): URL to the TensorFlow Hub MoveNet model
        inference.keypoint_score_threshold (float, default=0.4): Confidence threshold for keypoints
        inference.min_keypoints (int, default=9): Minimum number of keypoints for valid detection
        performance.frame_skip (int, default=1): Process every Nth frame to control performance
        viz.visualize_markers (bool, default=True): Whether to publish visualization markers
        viz.image_topic (str, default="astra_camera/camera/color/image_raw"): Input image topic
        viz.cv_color (list, default=[0,255,0]): BGR color for keypoint markers
        viz.text_color (list, default=[255,0,0]): BGR color for keypoint labels
        debug.enable_video (bool, default=False): Whether to save debug video
        debug.video_path (str, default="/tmp/movenet_debug.avi"): Path to save debug video

    Published Topics:
        /movenet/raw_detections (PersonsPoses): Detected person poses
        <image_topic>/markers (Image): Visualization image with pose markers
        /movenet/markers_rviz (MarkerArray): Markers for RViz visualization
        /movenet/inference_time (Float32): Inference duration in milliseconds

    Subscribed Topics:
        <image_topic> (Image): Input camera images

    Lifecycle States:
        configure: Loads model and initializes publishers
        activate: Subscribes to image topic and starts processing
        deactivate: Unsubscribes from image topic
        cleanup: Releases resources
        shutdown: Cleans up resources before shutdown

    """

    def __init__(self):
        super().__init__("movenet_inference_node")
        self.get_logger().info("Iniciando nodo de inferencia MoveNet...")
        self.bridge = CvBridge()

        # Parámetros de inferencia
        self.declare_parameter("inference.mirror", False)
        self.declare_parameter("inference.input_size", 256)
        self.declare_parameter(
            "inference.model_url",
            "https://tfhub.dev/google/movenet/multipose/lightning/1",
        )
        self.declare_parameter("inference.keypoint_score_threshold", 0.4)
        self.declare_parameter("inference.min_keypoints", 9)
        # Rendimiento
        self.declare_parameter("performance.frame_skip", 1)
        # Visualización en CV
        self.declare_parameter("viz.visualize_markers", True)
        self.declare_parameter("viz.image_topic", "astra_camera/camera/color/image_raw")
        self.declare_parameter("viz.cv_color", [0, 255, 0])
        self.declare_parameter("viz.text_color", [255, 0, 0])

        # Debug avanzado
        self.declare_parameter("debug.enable_video", False)
        self.declare_parameter("debug.video_path", "/tmp/movenet_debug.avi")

        # Recursos
        self.image_sub = None
        self.detections_pub = None
        self.cv_marker_pub = None
        self.rviz_marker_pub = None
        self.inf_time_pub = None
        self.model = None
        self.debug_writer = None
        self.frame_count = 0

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo...")

        # Obtener parámetros
        self.inference: dict[str, any] = {
            "mirror": self.get_parameter("inference.mirror").value,
            "input_size": int(self.get_parameter("inference.input_size").value),
            "model_url": self.get_parameter("inference.model_url").value,
            "keypoint_score_threshold": float(
                self.get_parameter("inference.keypoint_score_threshold").value
            ),
            "min_keypoints": int(self.get_parameter("inference.min_keypoints").value),
        }
        self.frame_skip = int(self.get_parameter("performance.frame_skip").value)
        self.viz_cv: dict[str, any] = {
            "visualize_markers": self.get_parameter("viz.visualize_markers").value,
            "image_topic": self.get_parameter("viz.image_topic").value,
            "cv_color": tuple(self.get_parameter("viz.cv_color").value),
            "text_color": tuple(self.get_parameter("viz.text_color").value),
        }

        self.debug_opts: dict[str, any] = {
            "enable_video": self.get_parameter("debug.enable_video").value,
            "video_path": self.get_parameter("debug.video_path").value,
        }

        # Cargar modelo
        try:
            self.model = load_model(self.inference["model_url"])
            self.get_logger().info("Modelo MoveNet cargado.")
        except (OSError, RuntimeError) as e:
            self.get_logger().error(f"Error al cargar modelo: {e}")
            return TransitionCallbackReturn.FAILURE

        # Publicadores
        self.detections_pub = self.create_lifecycle_publisher(
            PersonsPoses, "/movenet/raw_detections", 10
        )
        if self.viz_cv["visualize_markers"]:
            self.cv_marker_pub = self.create_lifecycle_publisher(
                Image, self.viz_cv["image_topic"] + "/markers", 10
            )
        self.rviz_marker_pub = self.create_lifecycle_publisher(
            MarkerArray, "/movenet/markers_rviz", 10
        )
        self.inf_time_pub = self.create_lifecycle_publisher(
            Float32, "/movenet/inference_time", 10
        )

        # Debug: VideoWriter
        if self.debug_opts["enable_video"]:
            width = height = self.inference["input_size"]
            fourcc = cv2.VideoWriter_fourcc(*"XVID")
            self.debug_writer = cv2.VideoWriter(
                self.debug_opts["video_path"], fourcc, 20.0, (width, height)
            )

        # TF2 listener
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        # Callback de parámetros dinámicos
        self.add_on_set_parameters_callback(self.parameter_update_callback)

        return super().on_configure(state)

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo: suscribiendo a imágenes...")
        qos = QoSProfile(depth=1)
        self.image_sub = self.create_subscription(
            Image, self.viz_cv["image_topic"], self.image_callback, qos
        )
        return super().on_activate(state)

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info(
            "Desactivando nodo: cancelando suscripción de imágenes..."
        )
        if self.image_sub:
            self.destroy_subscription(self.image_sub)
            self.image_sub = None
        return super().on_deactivate(state)

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Limpiando nodo: destruyendo pubs y recursos...")
        if self.detections_pub:
            self.destroy_lifecycle_publisher(self.detections_pub)
            self.detections_pub = None
        if self.cv_marker_pub:
            self.destroy_lifecycle_publisher(self.cv_marker_pub)
            self.cv_marker_pub = None
        if self.rviz_marker_pub:
            self.destroy_lifecycle_publisher(self.rviz_marker_pub)
            self.rviz_marker_pub = None
        if self.inf_time_pub:
            self.destroy_lifecycle_publisher(self.inf_time_pub)
            self.inf_time_pub = None
        if self.debug_writer:
            self.debug_writer.release()
            self.debug_writer = None
        return super().on_cleanup(state)

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        # Mismos recursos que cleanup
        return self.on_cleanup(state)

    def parameter_update_callback(self, params):  # -> SetParametersResult
        successful = True
        for p in params:
            name = p.name
            if name.startswith("inference.") and name in [
                "inference.mirror",
                "inference.keypoint_score_threshold",
                "inference.min_keypoints",
            ]:
                self.inference[name.split(".", 1)[1]] = p.value
                self.get_logger().info(f"Parametro {name} actualizado: {p.value}")
            elif name == "inference.model_url":
                # recarga de modelo en caliente
                new_url = p.value
                try:
                    model = load_model(new_url)
                    self.model = model
                    self.inference["model_url"] = new_url
                    self.get_logger().info("Modelo recargado.")
                except Exception as e:
                    self.get_logger().error(f"Fallo recarga modelo: {e}")
                    successful = False
            elif name.startswith("viz.") and name in ["viz.visualize_markers"]:
                self.viz_cv["visualize_markers"] = p.value
                self.get_logger().info(f"Parametro {name} actualizado: {p.value}")
            else:
                # Parámetros que requieren reinicio
                self.get_logger().warn(
                    f"Parametro {name} requiere reinicio para aplicar."
                )
                successful = False
        return SetParametersResult(successful=successful)

    def preprocess_image(self, msg: Image) -> np.ndarray | None:
        try:
            cv_img = self.bridge.imgmsg_to_cv2(msg, "bgr8")
        except CvBridgeError as e:
            self.get_logger().error(f"CvBridge error: {e}")
            return None
        if self.inference["mirror"]:
            cv_img = cv2.flip(cv_img, 1)
        return cv_img

    def infer(self, image: np.ndarray) -> list:
        # Ejecuta inferencia y devuelve lista de (keypoints, scores)
        keypoints_list, scores_list = run_inference_on_image(
            image, self.inference["input_size"], self.model
        )
        return process_detections(
            keypoints_list,
            scores_list,
            self.inference["keypoint_score_threshold"],
            self.inference["min_keypoints"],
        )

    def draw_markers(self, image: np.ndarray, detections: list) -> np.ndarray:
        # Dibuja círculos y textos en la imagen
        for i, (kpts, scores) in enumerate(detections):
            for idx, (x, y) in enumerate(kpts):
                if scores[idx] >= self.inference["keypoint_score_threshold"]:
                    cv2.circle(image, (int(x), int(y)), 4, self.viz_cv["cv_color"], -1)
                    cv2.putText(
                        image,
                        str(idx),
                        (int(x) + 5, int(y) - 5),
                        cv2.FONT_HERSHEY_SIMPLEX,
                        0.4,
                        self.viz_cv["text_color"],
                        1,
                    )
        return image

    def image_callback(self, msg: Image) -> None:
        # Control de tasa de procesamiento
        self.frame_count = (self.frame_count + 1) % self.frame_skip
        if self.frame_count != 0:
            return
        # Preprocesado
        img = self.preprocess_image(msg)
        if img is None:
            return
        # Inferencia y tiempo
        start = time.perf_counter()
        try:
            detections = self.infer(img)
        except Exception as e:
            self.get_logger().error(f"Error en inferencia: {e}")
            return
        duration = (time.perf_counter() - start) * 1000.0
        # Publicar tiempo de inferencia
        self.inf_time_pub.publish(Float32(data=duration))
        # Construir mensaje de PersonsPoses
        pp_msg = PersonsPoses()
        pp_msg.header = msg.header
        for pid, (kpts, scores) in enumerate(detections):
            person = PersonPose()
            person.header = msg.header
            person.id = pid
            person.keypoints = [float(c) for p in kpts for c in p]
            person.scores = [float(s) for s in scores]
            person.keypoints3d = [0.0] * (len(kpts) * 3)
            person.avg_depth = 0.0
            pp_msg.persons.append(person)
        self.detections_pub.publish(pp_msg)
        # Debug: histograma
        if self.get_parameter("debug.enable_video").value:
            self.debug_writer.write(img)
        # Visualización CV
        if self.viz_cv["visualize_markers"] and self.cv_marker_pub:
            vis = img.copy()
            vis = self.draw_markers(vis, detections)
            try:
                out_msg = self.bridge.cv2_to_imgmsg(vis, "bgr8")
                out_msg.header = msg.header
                self.cv_marker_pub.publish(out_msg)
            except CvBridgeError as e:
                self.get_logger().error(f"CvBridge salida error: {e}")


def main(args=None) -> None:
    rclpy.init(args=args)
    node = MoveNetInferenceNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
