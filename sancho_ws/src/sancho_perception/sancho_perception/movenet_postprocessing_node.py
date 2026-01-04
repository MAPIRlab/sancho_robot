#!/usr/bin/env python3

import copy
import random

import message_filters
import numpy as np
import rclpy
import tf_transformations
from cv_bridge import CvBridge, CvBridgeError
from geometry_msgs.msg import Pose, PoseArray, Quaternion
from people_msgs.msg import People, Person
from rclpy.duration import Duration
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from sensor_msgs.msg import CameraInfo, Image
from std_msgs.msg import Header
from tf2_ros import (
    Buffer,
    TransformListener,
)

from sancho_msgs.msg import PersonPose, PersonsPoses

random.seed(42)
# Opcional: semilla para reproducibilidad

from geometry_msgs.msg import Point
from visualization_msgs.msg import Marker, MarkerArray

from .movenet_utils import convert_2d_to_3d, get_depth_value


class MoveNetPostprocessingNode(LifecycleNode):
    """ROS 2 Lifecycle Node for post-processing MoveNet human pose estimations by adding 3D information.

    This node takes 2D keypoint detections from MoveNet along with depth images and converts them into
    3D skeleton representations. It handles coordinate transformation, depth filtering, 
    visualization markers generation, and publishes data in various formats for downstream components.

    Subscribed Topics:
        /movenet/raw_detections (PersonsPoses): 2D keypoint detections from MoveNet
        astra_camera/camera/depth/image_raw (Image): Depth image from camera
        astra_camera/camera/depth/camera_info (CameraInfo): Camera intrinsic parameters

    Published Topics:
        /human_pose/keypoints3d (PersonsPoses): 3D keypoints with depth information
        /human_pose/skeleton_markers (MarkerArray): RViz markers for skeleton visualization
        /people (People): Standard people tracking message format
        /human_pose/persons_poses (PoseArray): Person positions as pose array

    Parameters
    ----------
        depth_window_size (int, default=3): Window size for depth value averaging
        keypoint_score_threshold (float, default=0.4): Minimum confidence score to consider a keypoint
        target_frame (string, default="base_footprint"): Target frame for coordinate transformation
        depth_outlier_radius (float, default=0.5): Maximum allowed deviation from mean depth in meters

    Processing Pipeline:
        1. Synchronizes raw detections with depth image
        2. Projects 2D keypoints to 3D using depth information
        3. Filters outlier points based on depth consistency
        4. Transforms coordinates to target frame
        5. Generates visualization markers and standard message formats
        6. Publishes all outputs for downstream consumption

    Notes
    -----
        - The node requires at least 1/3 of the expected keypoints to be valid for a person to be published
        - Depth outlier filtering helps remove inconsistent depth readings
        - Skeleton connections follow the standard MoveNet/COCO 17-point skeleton format

    """

    def __init__(self):
        super().__init__("movenet_postprocessing_node")
        self.get_logger().info("Iniciando nodo de postprocesamiento MoveNet...")
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self)

        # Inicializa todo a None, se configurarán en on_configure
        self.bridge = None

        # Suscriptores
        self.detections_sub = None
        self.depth_sub = None
        self.camera_info_sub = None

        self.sync = None
        self.camera_info = None

        self.keypoints3d_pub = None
        self.skeleton_markers_pub = None
        self.people_pub = None
        self.pose_array_pub = None

        self.bridge = CvBridge()

        self.expected_kpts = 17
        self.min_valid_keypoints = self.expected_kpts // 3
        self.skel_conns = [
            (0, 1),
            (0, 2),
            (1, 3),
            (2, 4),
            (0, 5),
            (0, 6),
            (5, 7),
            (7, 9),
            (6, 8),
            (8, 10),
            (5, 11),
            (6, 12),
            (11, 13),
            (13, 15),
            (12, 14),
            (14, 16),
        ]

        self.declare_parameter("depth_window_size", 3)
        self.declare_parameter("keypoint_score_threshold", 0.4)
        self.declare_parameter("target_frame", "base_footprint")
        self.declare_parameter("depth_outlier_radius", 0.5)  # 0.5 m por defecto

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando MoveNetPostprocessingNode...")

        self.depth_window_size = self.get_parameter("depth_window_size").value
        self.keypoint_score_threshold = self.get_parameter(
            "keypoint_score_threshold"
        ).value

        # Publicadores para detecciones 3D y esqueletos en MarkerArray
        self.keypoints3d_pub = self.create_lifecycle_publisher(
            PersonsPoses, "/human_pose/keypoints3d", 10
        )
        self.skeleton_markers_pub = self.create_lifecycle_publisher(
            MarkerArray, "/human_pose/skeleton_markers", 10
        )
        self.people_pub = self.create_lifecycle_publisher(People, "/people", 10)
        self.pose_array_pub = self.create_lifecycle_publisher(
            PoseArray, "/human_pose/persons_poses", 10
        )
        self.target_frame = self.get_parameter("target_frame").value
        self.depth_outlier_radius = self.get_parameter("depth_outlier_radius").value

        return super().on_configure(state)

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Activando MoveNetPostprocessingNode...")

        # Crear los subscribers sincronizados
        self.detections_sub = message_filters.Subscriber(
            self, PersonsPoses, "/movenet/raw_detections"
        )
        self.depth_sub = message_filters.Subscriber(
            self, Image, "astra_camera/camera/depth/image_raw"
        )

        self.camera_info_sub = self.create_subscription(
            CameraInfo,
            "astra_camera/camera/depth/camera_info",
            self.camera_info_callback,
            10,
        )

        self.sync = message_filters.ApproximateTimeSynchronizer(
            [self.detections_sub, self.depth_sub], queue_size=10, slop=0.1
        )
        self.sync.registerCallback(self.sync_callback)
        return super().on_activate(state)

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando MoveNetPostprocessingNode...")

        if self.sync:
            self.sync.callbacks.clear()
            self.sync = None
        if self.detections_sub:
            self.destroy_subscription(self.detections_sub)
            self.detections_sub = None
        if self.depth_sub:
            self.destroy_subscription(self.depth_sub)
            self.depth_sub = None
        if self.camera_info_sub:
            self.destroy_subscription(self.camera_info_sub)
            self.camera_info_sub = None

        return super().on_deactivate(state)

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Limpiando MoveNetPostprocessingNode...")
        # Limpiar recursos
        self.bridge = None
        self.camera_info = None
        self.sync = None
        self.detections_sub = None
        self.depth_sub = None
        self.destroy_lifecycle_publisher(self.keypoints3d_pub)
        self.destroy_lifecycle_publisher(self.skeleton_markers_pub)
        self.destroy_lifecycle_publisher(self.people_pub)
        self.destroy_lifecycle_publisher(self.pose_array_pub)

        self.destroy_subscription(self.detections_sub)
        self.destroy_subscription(self.depth_sub)
        self.destroy_subscription(self.camera_info_sub)

        return super().on_cleanup(state)

    def on_error(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().error(
            "Error en MoveNetPostprocessingNode, limpiando recursos..."
        )

        # Aquí podrías limpiar todo lo necesario
        self.bridge = None
        self.camera_info = None
        self.sync = None
        self.detections_sub = None
        self.depth_sub = None

        return super().on_error(state)

    def on_shutdown(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Apagando MoveNetPostprocessingNode...")
        # Limpiar todo lo necesario
        self.bridge = None
        self.camera_info = None
        self.sync = None
        self.detections_sub = None
        self.depth_sub = None
        self.destroy_lifecycle_publisher(self.keypoints3d_pub)
        self.destroy_lifecycle_publisher(self.skeleton_markers_pub)
        self.destroy_lifecycle_publisher(self.people_pub)
        self.destroy_lifecycle_publisher(self.pose_array_pub)

        self.destroy_subscription(self.detections_sub)
        self.destroy_subscription(self.depth_sub)
        self.destroy_subscription(self.camera_info_sub)

        return super().on_shutdown(state)

    def camera_info_callback(self, msg):

        self.camera_info = msg

    def sync_callback(self, detections_msg, depth_msg):

        if self.camera_info is None:
            self.get_logger().warn(
                "camera_info aún no disponible, omitiendo procesamiento de este ciclo."
            )
            return

        try:
            depth_image = self.bridge.imgmsg_to_cv2(
                depth_msg, desired_encoding="passthrough"
            )
        except CvBridgeError as e:
            self.get_logger().error(f"Error al convertir imagen de profundidad: {e}")
            return
        if depth_image is None or depth_image.size == 0:
            self.get_logger().debug(
                "Imagen de profundidad vacía o inválida, omitiendo procesamiento de este ciclo."
            )
            return
        if detections_msg is None or len(detections_msg.persons) == 0:
            self.get_logger().debug(
                "No se detectaron personas, omitiendo procesamiento de este ciclo."
            )
            return

        full_detections_msg = self._procesar_detecciones_3d(detections_msg, depth_image)
        if full_detections_msg is None:
            self.get_logger().warn(
                "No se pudieron completar las detecciones 3D, omitiendo procesamiento de este ciclo."
            )
            return
        # Transformar detecciones al frame 'map'
        detections_msg = self._transform_detections_frame(full_detections_msg)

        if detections_msg is None:
            self.get_logger().warn(
                f"No se pudieron transformar las detecciones al frame {self.target_frame}, omitiendo procesamiento de este ciclo."
            )
            return

        self.keypoints3d_pub.publish(detections_msg)

        pose_array_msg = self._generar_pose_array(detections_msg)
        self.pose_array_pub.publish(pose_array_msg)

        people_msg = self._generar_people_msg(detections_msg)
        self.people_pub.publish(people_msg)

        skeleton_marker_array = self._generar_visualizaciones(detections_msg)
        self.skeleton_markers_pub.publish(skeleton_marker_array)

    def _transform_detections_frame(self, detections_msg):
        """Transforma un mensaje PersonsPoses (con array de PersonPose.persons)
        desde detections_msg.header.frame_id → 'map', modificando keypoints3d
        pero manteniendo siempre el mismo número de keypoints.
        """
        try:
            # 1) Pedir la transformación al frame 'map'
            t = self.tf_buffer.lookup_transform(
                self.target_frame,  # destino
                detections_msg.header.frame_id,  # origen
                rclpy.time.Time(),  # último disponible
                timeout=Duration(seconds=0.5),
            )

            # 2) Construir matriz homogénea 4×4
            tr = t.transform.translation
            rot = t.transform.rotation
            M = tf_transformations.quaternion_matrix([rot.x, rot.y, rot.z, rot.w])
            M[0:3, 3] = [tr.x, tr.y, tr.z]

            # 3) Copiar mensaje y actualizar header
            transformed_msg = copy.deepcopy(detections_msg)
            transformed_msg.header.frame_id = self.target_frame

            # 4) Batch-transform de cada persona
            for person in transformed_msg.persons:
                # a) Plano Nx3 desde la lista plana de 51 floats
                pts = np.array(person.keypoints3d, dtype=float).reshape(-1, 3)

                # b) Máscara de puntos válidos
                valid_mask = ~np.all(pts == 0.0, axis=1)
                if not valid_mask.any():
                    self.get_logger().warn(
                        f"Persona {person.id} no tiene puntos válidos; keypoints3d rellenados con ceros en '{self.target_frame}'."
                    )

                # c) Coordenadas homogéneas Nx4
                ones = np.ones((pts.shape[0], 1))
                pts_h = np.hstack([pts, ones])

                # d) Aplicar transformación
                pts_map_all = (M @ pts_h.T).T[:, :3]

                # e) Reconstruir array preservando longitud: solo reemplazar los válidos
                pts_transformed = np.zeros_like(pts)  # comienza en ceros
                pts_transformed[valid_mask] = pts_map_all[valid_mask]

                # f) Volver a lista plana
                person.keypoints3d = pts_transformed.flatten().tolist()

                # g) Actualizar frame_id interno si existe
                if hasattr(person, "header"):
                    person.header.frame_id = self.target_frame

            return transformed_msg

        except Exception as e:
            self.get_logger().error(f"Error al transformar detecciones: {e}")
            raise

    def _generar_pose_array(self, persons_3d_msg):
        pose_array_msg = PoseArray()
        pose_array_msg.header = persons_3d_msg.header

        for person in persons_3d_msg.persons:
            x, y, z = person.keypoints3d[0:3]
            if x == 0.0 and y == 0.0 and z == 0.0:
                continue  # skip invalid

            pose = Pose()
            pose.position = Point(x=float(x), y=float(y), z=float(z))
            pose.orientation = Quaternion(x=0.0, y=0.0, z=0.0, w=1.0)
            pose_array_msg.poses.append(pose)

        return pose_array_msg

    def _procesar_detecciones_3d(self, detections_msg, depth_image):
        persons_3d_msg = PersonsPoses()
        persons_3d_msg.header = detections_msg.header

        for person in detections_msg.persons:
            # Prepara listas “por índice” de longitud esperada
            pts_list = [None] * self.expected_kpts
            depth_list = [None] * self.expected_kpts

            # Extrae keypoints 2D y scores
            keypoints2d = [
                (int(person.keypoints[i]), int(person.keypoints[i + 1]))
                for i in range(0, len(person.keypoints), 2)
            ]

            # Recorre cada keypoint indexado
            for idx, ((x, y), score) in enumerate(
                zip(keypoints2d, person.scores, strict=False)
            ):
                if (
                    score > self.keypoint_score_threshold
                    and 0 <= x < depth_image.shape[1]
                    and 0 <= y < depth_image.shape[0]
                ):
                    depth_val = get_depth_value(
                        x, y, depth_image, self.depth_window_size
                    )
                    if depth_val and depth_val > 0:
                        pt3d = convert_2d_to_3d(x, y, depth_val, self.camera_info)
                        pts_list[idx] = (float(pt3d[0]), float(pt3d[1]), float(pt3d[2]))
                        depth_list[idx] = depth_val
                # else deja pts_list[idx]=None y depth_list[idx]=None

            # Filtrado de outliers por radio alrededor de la media
            valid_depths = [d for d in depth_list if d is not None]
            if valid_depths:
                mean_depth = float(np.mean(valid_depths))
                for i, d in enumerate(depth_list):
                    if (
                        d is not None
                        and abs(d - mean_depth) > self.depth_outlier_radius
                    ):
                        # descartamos este punto
                        pts_list[i] = None
                        depth_list[i] = None

            # Reconstruye keypoints3d plano (ceros donde no haya pt)
            flat_kpts3d = []
            for pt in pts_list:
                if pt is not None:
                    flat_kpts3d.extend([pt[0], pt[1], pt[2]])
                else:
                    flat_kpts3d.extend([0.0, 0.0, 0.0])

            # Comprueba ahora cuántos puntos quedan
            valid_count = sum(1 for pt in pts_list if pt is not None)
            if valid_count < self.min_valid_keypoints:
                continue  # muy pocos puntos válidos

            # Construye PersonPose
            new_person = PersonPose()
            new_person.header = person.header
            new_person.id = person.id
            new_person.scores = person.scores
            new_person.keypoints = person.keypoints
            new_person.keypoints3d = flat_kpts3d
            # Promedia sólo las profundidades no descartadas
            new_person.avg_depth = float(
                np.mean([d for d in depth_list if d is not None])
            )

            persons_3d_msg.persons.append(new_person)

        self.get_logger().info(f"Personas 3D procesadas: {len(persons_3d_msg.persons)}")
        return persons_3d_msg

    def _generar_visualizaciones(self, persons_3d_msg):
        skeleton_marker_array = MarkerArray()

        for person in persons_3d_msg.persons:
            keypoints_3d = person.keypoints3d
            if len(keypoints_3d) != self.expected_kpts * 3:
                self.get_logger().debug(
                    f"Persona {person.id}: número de keypoints 3D inesperado."
                )
                continue

            points_3d = {
                idx: (float(x), float(y), float(z))
                for idx, (x, y, z) in enumerate(
                    zip(*[iter(keypoints_3d)] * 3, strict=False)
                )
                if (float(x), float(y), float(z)) != (0.0, 0.0, 0.0)
            }
            # self.get_logger().info(f"Profundidad de cada punto de la persona {person.id}: {[points_3d[idx][2] for idx in points_3d]}")

            skeleton_marker_array.markers.append(
                self._crear_marker_puntos(persons_3d_msg.header, person.id, points_3d)
            )
            skeleton_marker_array.markers.append(
                self._crear_marker_lineas(persons_3d_msg.header, person.id, points_3d)
            )
            skeleton_marker_array.markers.append(
                self._crear_marker_texto(persons_3d_msg.header, person.id, points_3d)
            )
        return skeleton_marker_array

    def _crear_marker_puntos(self, header, person_id, points_3d):
        marker = Marker()
        marker.header = header
        marker.ns = f"skeleton_points_{person_id}"
        marker.id = person_id * 2
        marker.type = Marker.SPHERE_LIST
        marker.action = Marker.ADD
        marker.scale.x = marker.scale.y = marker.scale.z = 0.05
        marker.color.r = 1.0
        marker.color.a = 1.0
        marker.lifetime.sec = 1

        for pt in points_3d.values():
            marker.points.append(Point(x=(pt[0]), y=(pt[1]), z=(pt[2])))
        return marker

    def _crear_marker_lineas(self, header, person_id, points_3d):
        marker = Marker()
        marker.header = header
        marker.ns = f"skeleton_lines_{person_id}"
        marker.id = person_id * 2 + 1
        marker.type = Marker.LINE_LIST
        marker.action = Marker.ADD
        marker.scale.x = 0.02
        marker.color.r = random.random()
        marker.color.g = random.random()
        marker.color.b = random.random()
        marker.color.a = 1.0
        marker.lifetime.sec = 1

        for idx1, idx2 in self.skel_conns:
            if idx1 in points_3d and idx2 in points_3d:
                p1 = points_3d[idx1]
                p2 = points_3d[idx2]
                marker.points.extend(
                    [Point(x=p1[0], y=p1[1], z=p1[2]), Point(x=p2[0], y=p2[1], z=p2[2])]
                )
        return marker

    def _crear_marker_texto(self, header, person_id, points_3d):
        marker = Marker()
        marker.header = header
        marker.ns = "skeleton_text"
        marker.id = 1000 + person_id
        marker.type = Marker.TEXT_VIEW_FACING
        marker.action = Marker.ADD
        marker.scale.z = 0.2
        marker.color.r = marker.color.g = marker.color.b = marker.color.a = 1.0
        first_point = next(iter(points_3d.values()))
        marker.pose.position.x = (first_point)[0]
        marker.pose.position.y = (first_point)[1]
        marker.pose.position.z = (first_point)[2] + 0.3
        marker.text = f"ID{person_id}"
        marker.lifetime.sec = 1
        return marker

    def _generar_people_msg(self, persons_3d_msg):
        people_msg = People()
        people_msg.header = Header()
        people_msg.header.stamp = self.get_clock().now().to_msg()
        people_msg.header.frame_id = persons_3d_msg.header.frame_id

        for person in persons_3d_msg.persons:
            if person.avg_depth > 1.0:
                p = Person()
                p.name = f"person_{person.id}"
                coords = np.array(person.keypoints3d).reshape(-1, 3)
                valid = coords[(coords != 0.0).all(axis=1)]
                if len(valid):
                    x, y, z = valid.mean(axis=0)
                else:
                    continue
                if x == 0.0 and y == 0.0 and z == 0.0:
                    continue
                p.position = Point(
                    x=float(person.keypoints3d[0]),
                    y=float(person.keypoints3d[1]),
                    z=float(person.keypoints3d[2]),
                )
                if (
                    len(coords) > 6
                    and not np.all(coords[5] == 0.0)
                    and not np.all(coords[6] == 0.0)
                ):
                    left_shoulder = coords[5]
                    right_shoulder = coords[6]
                    shoulder_vec = left_shoulder - right_shoulder
                    angle = float(np.arctan2(shoulder_vec[1], shoulder_vec[0]))
                else:
                    angle = 0.0
                # Guardar el ángulo en velocity.z (por ejemplo)
                p.velocity = Point(x=0.0, y=0.0, z=angle)
                people_msg.people.append(p)
        return people_msg


def main(args=None):
    rclpy.init(args=args)

    # Creamos el nodo de ciclo de vida
    node = MoveNetPostprocessingNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # Limpieza
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
