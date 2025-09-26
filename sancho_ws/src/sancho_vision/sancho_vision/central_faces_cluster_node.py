#!/usr/bin/env python3
import math
import threading
from typing import List, Tuple

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
from rclpy.duration import Duration  # <<< necesario para lifetime

from geometry_msgs.msg import Point
from visualization_msgs.msg import Marker, MarkerArray

from sancho_msgs.msg import FaceRecognitionArray, FaceDetection, FaceRecognition
from sancho_msgs.srv import GetCentralFaceCluster

try:
    from sklearn.cluster import DBSCAN
    import numpy as np
except Exception:
    DBSCAN = None
    np = None


class CentralFacesClusterNode(Node):
    def __init__(self):
        super().__init__('central_faces_cluster_node')

        # Parámetros
        self.declare_parameter('input_topic', '/face_recognitions')
        self.declare_parameter('eps_default', 60.0)             # píxeles (para DBSCAN)
        self.declare_parameter('min_samples_default', 2)
        self.declare_parameter('marker_ns', 'faces')
        self.declare_parameter('marker_lifetime', 0.3)          # seg
        self.declare_parameter('head_frame', 'camera_link')
        self.declare_parameter('pixel_to_meter', 0.002)         # <<< 1 px = 2 mm (ajústalo a tu gusto)
        self.declare_parameter('sphere_diameter', 0.3)         # <<< 3 cm por esfera
        self.declare_parameter('text_height', 0.6)             # <<< 6 cm de alto del texto

        input_topic = self.get_parameter('input_topic').get_parameter_value().string_value
        qos = QoSProfile(depth=10, reliability=ReliabilityPolicy.BEST_EFFORT, history=HistoryPolicy.KEEP_LAST)

        self._lock = threading.Lock()
        self._last_msg: FaceRecognitionArray | None = None
        self._last_centers: List[Tuple[float, float]] = []  # en píxeles (x,y, origen arriba-izq)
        self._last_ids: List[str] = []
        self._last_names: List[str] = []

        self._sub = self.create_subscription(FaceRecognitionArray, input_topic, self._on_faces, qos)
        self._marker_pub = self.create_publisher(MarkerArray, '~/markers', 10)
        self._srv = self.create_service(GetCentralFaceCluster, '~/get_central_cluster', self._on_srv)

        if DBSCAN is None or np is None:
            self.get_logger().error('Falta scikit-learn y/o numpy. Instala con: pip install scikit-learn numpy')

        self.get_logger().info(f'central_faces_cluster_node listo. Suscrito a {input_topic}')

    # -------------------------------------
    # Callback de suscripción
    # -------------------------------------
    def _on_faces(self, msg: FaceRecognitionArray):
        centers: List[Tuple[float, float]] = []
        ids: List[str] = []
        names: List[str] = []

        n = min(len(msg.detections), len(msg.recognitions))
        for i in range(n):
            det: FaceDetection = msg.detections[i]
            rec: FaceRecognition = msg.recognitions[i]

            # Centro en PIXELES (origen arriba-izq, corner = left-down):
            # x_c = x + w/2 ; y_c = y - h/2
            x_c = det.corner.x + det.width * 0.5
            y_c = det.corner.y - det.height * 0.5

            centers.append((x_c, y_c))
            ids.append(rec.classified_id)
            names.append(rec.classified_name)

        with self._lock:
            self._last_msg = msg
            self._last_centers = centers
            self._last_ids = ids
            self._last_names = names

        try:
            self._publish_markers(msg, centers, ids)  # visualización
        except Exception as e:
            self.get_logger().warn(f'Error publicando markers: {e}')

    # -------------------------------------
    # Servicio: calcula clúster central (en píxeles)
    # -------------------------------------
    def _on_srv(self, request: GetCentralFaceCluster.Request, response: GetCentralFaceCluster.Response):
        with self._lock:
            msg = self._last_msg
            centers = list(self._last_centers)
            ids = list(self._last_ids)
            names = list(self._last_names)

        if msg is None or len(centers) == 0:
            response.cluster_center = Point(x=float('nan'), y=float('nan'), z=0.0)
            response.ids = []
            response.names = []
            response.indices = []
            return response

        if DBSCAN is None or np is None:
            self.get_logger().error('No está disponible scikit-learn/numpy para DBSCAN')
            response.cluster_center = Point(x=float('nan'), y=float('nan'), z=0.0)
            return response

        eps = request.eps if request.eps > 0.0 else float(self.get_parameter('eps_default').value)
        min_samples = request.min_samples if request.min_samples > 0 else int(self.get_parameter('min_samples_default').value)

        X = np.array(centers, dtype=float)  # en píxeles
        labels = DBSCAN(eps=eps, min_samples=min_samples).fit_predict(X)

        # Agrupa por etiqueta (ignora -1 = ruido)
        clusters = {}
        for idx, lbl in enumerate(labels):
            if lbl == -1:
                continue
            clusters.setdefault(lbl, []).append(idx)

        if not clusters:
            response.cluster_center = Point(x=float('nan'), y=float('nan'), z=0.0)
            response.ids = []
            response.names = []
            response.indices = []
            return response

        img_w = float(msg.image.width)
        img_h = float(msg.image.height)
        img_cx = img_w * 0.5
        img_cy = img_h * 0.5

        best_lbl = None
        best_dist = float('inf')
        best_center = (float('nan'), float('nan'))

        for lbl, idxs in clusters.items():
            pts = X[idxs, :]
            mean_x = float(np.mean(pts[:, 0]))
            mean_y = float(np.mean(pts[:, 1]))
            # Distancia al centro de la imagen (en píxeles)
            d = math.hypot(mean_x - img_cx, mean_y - img_cy)
            if d < best_dist:
                best_dist = d
                best_lbl = lbl
                best_center = (mean_x, mean_y)

        chosen_indices = clusters[best_lbl]
        # La respuesta queda en PIXELES (z=0)
        response.cluster_center = Point(x=best_center[0], y=best_center[1], z=0.0)
        response.ids = [ids[i] for i in chosen_indices]
        response.names = [names[i] for i in chosen_indices]
        response.indices = [int(i) for i in chosen_indices]
        return response

    # -------------------------------------
    # Markers para RViz (visualización en METROS, centrados en el centro de la imagen)
    # -------------------------------------
    def _publish_markers(self, msg: FaceRecognitionArray, centers_px: List[Tuple[float, float]], ids: List[str]):
        ma = MarkerArray()
        header = msg.header
        head_frame = self.get_parameter('head_frame').get_parameter_value().string_value
        if head_frame:
            header.frame_id = head_frame

        px2m = float(self.get_parameter('pixel_to_meter').value)     # <<< conversión para RViz
        sphere_d = float(self.get_parameter('sphere_diameter').value)
        text_h = float(self.get_parameter('text_height').value)

        # Centro de imagen en píxeles
        img_w = float(msg.image.width)
        img_h = float(msg.image.height)
        cx = img_w * 0.5
        cy = img_h * 0.5

        # ----- Esferas (SPHERE_LIST) -----
        spheres = Marker()
        spheres.header = header
        spheres.ns = self.get_parameter('marker_ns').value
        spheres.id = 0
        spheres.type = Marker.SPHERE_LIST        # <<< para listas de esferas
        spheres.action = Marker.ADD
        spheres.scale.x = sphere_d               # diámetro común
        spheres.scale.y = sphere_d
        spheres.scale.z = sphere_d
        spheres.color.a = 1.0
        spheres.color.r = 0.0
        spheres.color.g = 1.0
        spheres.color.b = 0.0
        spheres.lifetime = Duration(seconds=float(self.get_parameter('marker_lifetime').value)).to_msg()

        for (x_px, y_px) in centers_px:
            # Centrar en (0,0) y pasar a metros. También invertimos Y para que arriba sea +Y en RViz.
            x_m = (x_px - cx) * px2m
            y_m = (cy - y_px) * px2m
            spheres.points.append(Point(x=x_m, y=y_m, z=0.0))

        ma.markers.append(spheres)

        # ----- Textos por ID -----
        mid = 1
        for i, (x_px, y_px) in enumerate(centers_px):
            text = ids[i] if ids[i] else '(?)'
            t = Marker()
            t.header = header
            t.ns = self.get_parameter('marker_ns').value
            t.id = mid
            mid += 1
            t.type = Marker.TEXT_VIEW_FACING
            t.action = Marker.ADD
            t.pose.position.x = (x_px - cx) * px2m
            t.pose.position.y = (cy - y_px) * px2m
            t.pose.position.z = sphere_d * 0.7               # un poco por encima
            t.scale.z = text_h *0.5                                # <<< en TEXT_VIEW_FACING sólo cuenta Z
            t.color.a = 1.0
            t.color.r = 1.0
            t.color.g = 1.0
            t.color.b = 1.0
            t.text = text
            t.lifetime = spheres.lifetime
            ma.markers.append(t)

        self._marker_pub.publish(ma)


def main():
    rclpy.init()
    node = CentralFacesClusterNode()
    try:
            rclpy.spin(node)
    except KeyboardInterrupt:
            pass
    finally:
            node.destroy_node()
            rclpy.shutdown()


if __name__ == '__main__':
    main()
