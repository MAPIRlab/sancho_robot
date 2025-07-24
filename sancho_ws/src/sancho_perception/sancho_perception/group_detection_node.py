#!/usr/bin/env python3
"""Nodo de detección de grupos robusto con múltiples filtros temporales y espaciales (versión lifecycle corregida).
"""
import numpy as np
import rclpy
from geometry_msgs.msg import Point, PoseArray, Quaternion
from rclpy.duration import Duration
from rclpy.lifecycle import LifecycleNode, LifecycleState, TransitionCallbackReturn
from rclpy.qos import QoSProfile
from sklearn.cluster import DBSCAN
from sklearn.metrics import silhouette_score
from visualization_msgs.msg import Marker, MarkerArray

from sancho_msgs.msg import GroupInfo


def bounding_box_area(points: np.ndarray) -> float:
    """Área del rectángulo mínimo que engloba los puntos (solo XY)."""
    min_xy = points.min(axis=0)
    max_xy = points.max(axis=0)
    return float(np.prod(max_xy - min_xy))


class GroupDetectionNode(LifecycleNode):
    """A ROS2 lifecycle node that detects groups of people based on spatial clustering.

    This node subscribes to pose arrays containing detected persons, applies DBSCAN clustering
    to identify groups, and publishes information about detected stable groups. The node
    implements the ROS2 managed lifecycle pattern (configure, activate, deactivate, cleanup).

    The group detection algorithm works by:
    1. Receiving person positions via PoseArray messages
    2. Running DBSCAN clustering to identify potential groups 
    3. Selecting the largest cluster and calculating its centroid and radius
    4. Tracking cluster stability over time (position and membership)
    5. Validating clusters using silhouette score when multiple clusters are present
    6. Publishing group information when a stable group has been detected for a minimum duration
    7. Visualizing the group with a marker in RViz

    Parameters
    ----------
        group_distance_threshold (float, default: 1.0): Maximum distance between points in a cluster
        min_group_duration (float, default: 3.0): Time in seconds a group must be stable before detection
        group_centroid_tolerance (float, default: 0.5): Maximum allowed movement of cluster centroid
        check_period (float, default: 0.5): Timer period for checking timeouts
        dbscan_min_samples (int, default: 2): Minimum samples for DBSCAN clustering
        detection_timeout (float, default: 2.0): Time after which detection is reset if no updates
        message_timeout (float, default: 2.0): Time after which state is reset if no messages
        silhouette_threshold (float, default: 0.3): Minimum silhouette score to consider cluster valid
        grace_period (float, default: 1.0): Time to maintain group detection during brief absences
        min_group_radius (float, default: 0.1): Minimum radius of a valid group
        cluster_history_size (int, default: 10): Size of cluster history buffer
        cluster_history_required (int, default: 5): Required consecutive stable clusters

    Subscribes:
        /human_pose/persons_poses (PoseArray): Positions of detected persons

    Publishes:
        /detected_group (GroupInfo): Information about detected groups
        /group_marker_array (MarkerArray): Visualization markers for detected groups

    Lifecycle:
        on_configure: Sets up parameters and publishers
        on_activate: Creates subscriptions and timers
        on_deactivate: Cancels timers and destroys subscriptions
        on_cleanup: Cleans up all resources

    """

    def __init__(self):
        super().__init__("group_detection_lifecycle")
        self.get_logger().info(
            "Inicializando nodo de detección de grupos (lifecycle)..."
        )

        # Declarar parámetros con valores por defecto
        self.declare_parameter("group_distance_threshold", 1.0)
        self.declare_parameter("min_group_duration", 3.0)
        self.declare_parameter("group_centroid_tolerance", 0.5)
        self.declare_parameter("check_period", 0.5)
        self.declare_parameter("dbscan_min_samples", 2)
        self.declare_parameter("detection_timeout", 2.0)
        self.declare_parameter("message_timeout", 2.0)
        self.declare_parameter("silhouette_threshold", 0.3)
        self.declare_parameter("grace_period", 1.0)
        self.declare_parameter("min_group_radius", 0.1)
        self.declare_parameter("cluster_history_size", 10)
        self.declare_parameter("cluster_history_required", 5)

        # Publishers y subscriptores (se crearán en on_configure/on_activate)
        self.group_pub = None
        self.marker_pub = None
        self.persons_sub = None
        self.timer = None

        # Estado interno
        self.cluster_history = []  # lista de tuplas (centroid, set(ids))
        self.consecutive_stable = 0
        self.current_detected = False
        self.group_start_time = None
        self.last_detection_time = None
        self.last_msg_ts = None
        self.absence_start = None
        self.last_marker_id = None

    def on_configure(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando nodo...")

        # Leer y validar parámetros
        raw = self.get_parameter("group_distance_threshold").value
        self.group_distance_threshold = max(0.001, raw)

        raw = self.get_parameter("min_group_duration").value
        self.min_group_duration = max(0.1, raw)

        raw = self.get_parameter("group_centroid_tolerance").value
        self.group_centroid_tolerance = max(0.0, raw)

        raw = self.get_parameter("check_period").value
        self.check_period = max(0.01, raw)

        raw = self.get_parameter("dbscan_min_samples").value
        self.dbscan_min_samples = max(1, int(raw))

        raw = self.get_parameter("detection_timeout").value
        self.detection_timeout = max(0.0, raw)

        raw = self.get_parameter("message_timeout").value
        self.message_timeout = max(0.0, raw)

        raw = self.get_parameter("silhouette_threshold").value
        if raw < -1.0 or raw > 1.0:
            self.get_logger().warn(
                "silhouette_threshold fuera de rango [-1,1], usando 0.3"
            )
            self.silhouette_threshold = 0.3
        else:
            self.silhouette_threshold = raw

        raw = self.get_parameter("grace_period").value
        self.grace_period = max(0.0, raw)

        raw = self.get_parameter("min_group_radius").value
        self.min_group_radius = max(0.0, raw)

        raw = self.get_parameter("cluster_history_size").value
        self.cluster_history_size = max(1, int(raw))

        raw = self.get_parameter("cluster_history_required").value
        self.cluster_history_required = max(1, int(raw))

        if self.cluster_history_required > self.cluster_history_size:
            self.get_logger().warn(
                "cluster_history_required > cluster_history_size, igualando ambos"
            )
            self.cluster_history_required = self.cluster_history_size

        # Crear publishers lifecycle
        qos = QoSProfile(depth=10)
        self.group_pub = self.create_lifecycle_publisher(
            GroupInfo, "/detected_group", qos
        )
        self.marker_pub = self.create_lifecycle_publisher(
            MarkerArray, "/group_marker_array", qos
        )

        self.get_logger().info("Nodo configurado.")
        return super().on_configure(state)

    def on_activate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Activando nodo...")

        qos = QoSProfile(depth=10)
        # Suscripción solo mientras está activo
        self.persons_sub = self.create_subscription(
            PoseArray, "/human_pose/persons_poses", self.poses_callback, qos
        )
        # Timer para revisar timeouts
        self.timer = self.create_timer(self.check_period, self.timer_callback)

        self.get_logger().info("Nodo activo.")
        return super().on_activate(state)

    def on_deactivate(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando nodo...")

        # Cancelar timer y destruir suscripción
        if self.timer:
            self.timer.cancel()
        if self.persons_sub:
            self.destroy_subscription(self.persons_sub)

        self.get_logger().info("Nodo desactivado.")
        return super().on_deactivate(state)

    def on_cleanup(self, state: LifecycleState) -> TransitionCallbackReturn:
        self.get_logger().info("Limpiando recursos...")

        if self.timer:
            self.destroy_timer(self.timer)
        if self.group_pub:
            self.destroy_lifecycle_publisher(self.group_pub)
        if self.marker_pub:
            self.destroy_lifecycle_publisher(self.marker_pub)
        if self.persons_sub:
            self.destroy_subscription(self.persons_sub)

        self.get_logger().info("Recursos limpiados.")
        return super().on_cleanup(state)

    def _check_message_gap(self, now: rclpy.time.Time) -> None:
        if self.last_msg_ts is None or not self.current_detected:
            return
        gap = (now - self.last_msg_ts).nanoseconds / 1e9
        if gap > self.message_timeout:
            self.get_logger().warn(
                f"No llegan mensajes desde hace {gap:.2f}s. Reiniciando estado."
            )
            self.reset(keep_last_detection=True)

    def poses_callback(self, msg: PoseArray) -> None:
        now = rclpy.time.Time.from_msg(msg.header.stamp)
        # Verificar retraso de mensajes solo si estábamos detectando
        self._check_message_gap(now)
        self.last_msg_ts = now

        poses = msg.poses
        if len(poses) < 2:
            # No hay suficientes personas para agrupar
            self.get_logger().debug("Menos de dos personas en el frame, reset.")
            self.reset()
            return

        # Extraer coordenadas XY
        points = np.array([[p.position.x, p.position.y] for p in poses])
        # IDs de trackeo: si no existen, usar índices temporales
        try:
            ids = list(msg.track_ids)
            if len(ids) != len(poses):
                raise AttributeError
        except AttributeError:
            ids = list(range(len(poses)))
            self.get_logger().debug(
                "msg.track_ids no definido o incoherente, usando índices."
            )

        # Filtrar posiciones inválidas (NaN/Inf)
        mask = np.isfinite(points).all(axis=1)
        if not mask.any():
            self.get_logger().debug("Todas las posiciones inválidas, reset.")
            self.reset()
            return
        points = points[mask]
        ids = [ids[i] for i, m in enumerate(mask) if m]

        if len(points) < 2:
            self.get_logger().debug("Tras filtrar inválidos, menos de dos, reset.")
            self.reset()
            return

        # Calcular eps acotado según densidad
        area = bounding_box_area(points)
        density = len(points) / max(area, 1e-3)
        base_eps = self.group_distance_threshold
        factor = 1 + 0.5 * (density - 1)
        eps = float(np.clip(base_eps * factor, base_eps * 0.5, base_eps * 2.0))

        # Ejecutar DBSCAN
        try:
            labels = DBSCAN(eps=eps, min_samples=self.dbscan_min_samples).fit_predict(
                points
            )
        except ValueError as e:
            self.get_logger().error(f"DBSCAN ValueError: {e}. Reset.")
            self.reset()
            return
        except MemoryError as e:
            self.get_logger().error(f"DBSCAN MemoryError: {e}. Reset.")
            self.reset()
            return

        unique_labels = set(labels) - {-1}
        if not unique_labels:
            # No hay clúster válido
            if self.absence_start is None:
                self.absence_start = now
                self.cluster_history.clear()
                self.consecutive_stable = 0
                self.get_logger().debug("Primera ausencia de clúster, vacío historial.")
            elif (now - self.absence_start).nanoseconds / 1e9 > self.grace_period:
                self.get_logger().info("Sin grupos detectados por grace_period, reset.")
                self.reset()
            return

        # Hay al menos un clúster: reiniciar ausencia
        self.absence_start = None

        # Seleccionar clúster más grande
        best_label = max(unique_labels, key=lambda lbl: np.sum(labels == lbl))
        member_idx = np.where(labels == best_label)[0]
        member_ids = {ids[i] for i in member_idx}
        pts = points[labels == best_label]
        cen = pts.mean(axis=0)
        rad = float(np.linalg.norm(pts - cen, axis=1).max())

        # Validar radio mínimo
        if rad < self.min_group_radius:
            self.get_logger().debug("Radio de cluster muy pequeño, reset.")
            self.reset()
            return

        # Evaluar silueta solo si hay ≥ 2 clústeres y suficientes puntos
        if len(points) >= 3 and len(unique_labels) > 1:
            try:
                score = silhouette_score(points, labels)
            except ValueError as e:
                self.get_logger().warn(f"Silhouette error: {e}. Ignorando este filtro.")
            else:
                if score < self.silhouette_threshold:
                    self.get_logger().debug(f"Silhouette bajo ({score:.2f}), reset.")
                    self.reset()
                    return

        # Control de estabilidad consecutiva de centroides
        if self.cluster_history:
            prev_cen, _ = self.cluster_history[-1]
            dist = np.linalg.norm(prev_cen - cen)
            if dist < self.group_centroid_tolerance:
                self.consecutive_stable += 1
            else:
                # Cambio brusco: limpiar historial y reiniciar contador
                self.cluster_history.clear()
                self.consecutive_stable = 1
                self.get_logger().debug(
                    "Centro cambió demasiado, limpio historial de clusters."
                )
        else:
            self.consecutive_stable = 1

        # Añadir al historial
        self.cluster_history.append((cen, member_ids))
        if len(self.cluster_history) > self.cluster_history_size:
            self.cluster_history.pop(0)

        if self.consecutive_stable < self.cluster_history_required:
            self.get_logger().debug(
                f"Cluster no suficientemente estable: {self.consecutive_stable}/"
                f"{self.cluster_history_required}"
            )
            # Si habíamos marcado detección parcial, desactivarla
            if self.current_detected:
                self.current_detected = False
                self.group_start_time = None
                self.get_logger().debug(
                    "Estabilidad perdida antes del tiempo mínimo, reset parcial."
                )
            return

        # A partir de aquí, el clúster es estable en suficientes iteraciones
        if not self.current_detected:
            self.group_start_time = now
            self.current_detected = True
            self.get_logger().info("Inicia conteo para detección de grupo.")
            return

        elapsed = (now - self.group_start_time).nanoseconds / 1e9
        if elapsed >= self.min_group_duration:
            # Solo publicar si hace > detection_timeout desde la última vez (o si nunca)
            if (not self.last_detection_time) or (
                (now - self.last_detection_time).nanoseconds / 1e9
                > self.detection_timeout
            ):
                self.publish_group(cen, rad, now, frame_id=msg.header.frame_id)
                self.last_detection_time = now

    def timer_callback(self) -> None:
        now = self.get_clock().now()
        if self.last_detection_time:
            elapsed = (now - self.last_detection_time).nanoseconds / 1e9
            if elapsed > self.detection_timeout:
                self.get_logger().debug("Detection_timeout excedido, reset.")
                self.reset()

    def publish_group(
        self,
        centroid: np.ndarray,
        radius: float,
        timestamp: rclpy.time.Time,
        frame_id: str = "map",
    ) -> None:
        # Preparar y publicar GroupInfo
        gm = GroupInfo()
        gm.header.stamp = timestamp.to_msg()
        gm.header.frame_id = frame_id
        gm.pose.position = Point(x=float(centroid[0]), y=float(centroid[1]), z=0.0)
        gm.pose.orientation = Quaternion(w=1.0)
        gm.radius = radius
        self.group_pub.publish(gm)

        # Antes de publicar nuevo marcador, borrar el antiguo (si existe)
        ma = MarkerArray()
        if self.last_marker_id is not None:
            m_del = Marker()
            m_del.header.stamp = timestamp.to_msg()
            m_del.header.frame_id = frame_id
            m_del.ns = "group"
            m_del.id = self.last_marker_id
            m_del.action = Marker.DELETE
            ma.markers.append(m_del)

        # Crear nuevo marcador
        m = Marker()
        m.header.stamp = timestamp.to_msg()
        m.header.frame_id = frame_id
        m.ns = "group"
        # asignar un nuevo ID (puede ser siempre 0 si cerramos el anterior)
        new_id = 0
        m.id = new_id
        m.type = Marker.SPHERE
        m.action = Marker.ADD
        m.pose.position = gm.pose.position
        m.pose.orientation = gm.pose.orientation
        m.scale.x = radius * 2.0
        m.scale.y = radius * 2.0
        m.scale.z = radius * 2.0
        m.color.r = 0.0
        m.color.g = 1.0
        m.color.b = 0.0
        m.color.a = 0.5
        # Mostrar el marcador hasta detection_timeout + un pequeño margen
        lifetime = Duration(seconds=(self.detection_timeout + 0.1)).to_msg()
        m.lifetime = lifetime
        ma.markers.append(m)

        self.marker_pub.publish(ma)
        self.last_marker_id = new_id

        self.get_logger().info(
            f"Publicado grupo: centro=({centroid[0]:.2f}, {centroid[1]:.2f}), radio={radius:.2f}"
        )

    def reset(self, keep_last_detection: bool = False) -> None:
        """Restablece el estado interno de detección.
        Si keep_last_detection=True, no borra last_detection_time.
        """
        self.get_logger().debug("Reset estado de detección.")
        self.cluster_history.clear()
        self.consecutive_stable = 0
        self.current_detected = False
        self.group_start_time = None
        if not keep_last_detection:
            self.last_detection_time = None
        self.absence_start = None
        # No modificamos last_msg_ts aquí para no interferir con checks posteriores


def main(args=None) -> None:
    rclpy.init(args=args)
    node = GroupDetectionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
