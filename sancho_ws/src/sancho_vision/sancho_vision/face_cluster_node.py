import rclpy
from rclpy.node import Node
from std_msgs.msg import Header
from geometry_msgs.msg import PointStamped
from sensor_msgs.msg import CameraInfo
from sancho_msgs.msg import FaceDetection, FaceRecognition, FaceRecognitionArray
# from sancho_msgs.srv import ComputeCluster  # Custom srv: uint32[] member_ids; float32 centroid_x; float32 centroid_y; float32 centroid_z
from std_srvs.srv import Empty as ComputeCluster  # Placeholder, replace with actual custom service
from visualization_msgs.msg import Marker, MarkerArray
import tf2_ros
import tf2_geometry_msgs
from rclpy.duration import Duration

import numpy as np
from sklearn.cluster import DBSCAN
from scipy.optimize import linear_sum_assignment
from filterpy.kalman import KalmanFilter
from filterpy.common import Q_discrete_white_noise
from typing import cast


def euclidean(a, b):
    return np.linalg.norm(a - b)

class Track3D:
    def __init__(self, track_id, init_pos, person_id=0, max_misses=60, dt=0.1):
        # Using FilterPy KalmanFilter for state [x, y, z, vx, vy, vz]
        self.id = track_id
        self.person_id = person_id
        self.dt = dt
        self.kf = KalmanFilter(dim_x=6, dim_z=3)
        # State transition
        self.kf.F = np.array([[1,0,0,dt,0,0],
                              [0,1,0,0,dt,0],
                              [0,0,1,0,0,dt],
                              [0,0,0,1,0,0],
                              [0,0,0,0,1,0],
                              [0,0,0,0,0,1]])
        # Measurement function
        self.kf.H = np.array([[1,0,0,0,0,0],
                              [0,1,0,0,0,0],
                              [0,0,1,0,0,0]])
        # Covariances
        self.kf.P *= 1.0
        self.kf.Q = Q_discrete_white_noise(dim=3, dt=dt, var=0.1, block_size=2)
        self.kf.R = np.eye(3) * 0.5
        # Initialize state
        self.kf.x[:3] = np.array(init_pos).reshape((3,1))
        self.kf.x[3:] = 0.0
        # Miss handling
        self.misses = 0
        self.max_misses = max_misses

    def predict(self):
        self.kf.predict()
        return self.pos

    def update(self, meas_pos, person_id=0):
        z = np.array(meas_pos).reshape((3,))
        self.kf.update(z)
        self.misses = 0
        # Update identity only if new id known
        if person_id > 0:
            self.person_id = person_id

    def miss(self):
        self.misses += 1
        return self.misses > self.max_misses

    @property
    def pos(self):
        return self.kf.x[:3].reshape((3,))

class SORT3D:
    def __init__(self, max_misses=60, dist_threshold=2.5, dt=0.1, identity_penalty=1.0):
        self.tracks = []
        self.next_id = 1
        self.max_misses = max_misses
        self.dist_threshold = dist_threshold
        self.dt = dt
        self.identity_penalty = identity_penalty

    def update(self, detections):
        # detections: list of (pos, person_id)
        # Predict all tracks
        for tr in self.tracks:
            tr.predict()
        # First assign by known person_id (choose nearest track with same pid)
        assigned_det = set()
        assigned_tr = set()
        for j, (det_pos, pid) in enumerate(detections):
            if pid > 0:
                best_i = None
                best_dist = float('inf')
                for i, tr in enumerate(self.tracks):
                    if tr.person_id == pid:
                        d = euclidean(tr.pos, det_pos)
                        if d < best_dist:
                            best_dist = d
                            best_i = i
                if best_i is not None and best_dist < self.dist_threshold:
                    self.tracks[best_i].update(det_pos, pid)
                    assigned_tr.add(best_i)
                    assigned_det.add(j)
                # Prepare unmatched for Hungarian
        unmatched_tracks = [i for i in range(len(self.tracks)) if i not in assigned_tr]
        unmatched_dets = [j for j in range(len(detections)) if j not in assigned_det]
        N = len(unmatched_tracks)
        M = len(unmatched_dets)
        # Hungarian on unmatched
        if N > 0 and M > 0:
            cost = np.zeros((N, M), dtype=float)
            for idx_i, i in enumerate(unmatched_tracks):
                tr = self.tracks[i]
                for idx_j, j in enumerate(unmatched_dets):
                    det_pos, pid = detections[j]
                    base_cost = euclidean(tr.pos, det_pos)
                    # add penalty if both identities known and mismatch
                    penalty = self.identity_penalty if (tr.person_id > 0 and pid > 0 and tr.person_id != pid) else 0.0
                    cost[idx_i, idx_j] = base_cost + penalty
            row_ind, col_ind = linear_sum_assignment(cost)
            for idx_i, idx_j in zip(row_ind, col_ind):
                if cost[idx_i, idx_j] < self.dist_threshold + self.identity_penalty:
                    tr_idx = unmatched_tracks[idx_i]
                    det_idx = unmatched_dets[idx_j]
                    det_pos, pid = detections[det_idx]
                    self.tracks[tr_idx].update(det_pos, pid)
                    assigned_tr.add(tr_idx)
                    assigned_det.add(det_idx)
        # Handle misses and remove stale
        survivors = []
        for i, tr in enumerate(self.tracks):
            if i in assigned_tr or not tr.miss():
                survivors.append(tr)
            else:
            # Logging when a track is lost
                print(f"[SORT3D] Track lost: id={tr.id}, person_id={tr.person_id}, last_pos={tr.pos}")
        self.tracks = survivors
        # Create new for unassigned detections
        for j, (det_pos, pid) in enumerate(detections):
            if j not in assigned_det:
                self.tracks.append(Track3D(self.next_id, det_pos, pid, self.max_misses, self.dt))
                self.next_id += 1

class FaceClusterServiceNode(Node):
    def __init__(self):
        super().__init__('face_cluster_service_node')
        # Parameters
        self.declare_parameter('input_topic', '/face_recognitions')
        self.declare_parameter('camera_frame', 'camera_link')
        self.declare_parameter('head_frame', 'base_link')
        self.declare_parameter('camera_info_topic', '/sancho_camera/camera_info')
        self.declare_parameter('depth_scale.k', 8400.0)
        self.declare_parameter('dbscan.eps', 0.35)
        self.declare_parameter('dbscan.min_samples', 2)
        self.declare_parameter('track.max_misses', 60)
        self.declare_parameter('track.dist_threshold', 0.5)
        self.declare_parameter('track.dt', 0.1)
        self.declare_parameter('track.identity_penalty', 1.0)

        topic = self.get_parameter('input_topic').value
        self.camera_frame = self.get_parameter('camera_frame').value
        self.head_frame = self.get_parameter('head_frame').value
        self.camera_info_topic = self.get_parameter('camera_info_topic').value
        self.k = self.get_parameter('depth_scale.k').value
        self.dbscan_eps = self.get_parameter('dbscan.eps').value
        self.dbscan_min = self.get_parameter('dbscan.min_samples').value
        max_misses = self.get_parameter('track.max_misses').value
        dist_thr = self.get_parameter('track.dist_threshold').value
        dt = self.get_parameter('track.dt').value
        identity_penalty = self.get_parameter('track.identity_penalty').value

        self.intrinsics = None
        self.tracker = SORT3D(max_misses=max_misses,
                              dist_threshold=dist_thr,
                              dt=dt,
                              identity_penalty=identity_penalty)

        self.face_sub = self.create_subscription(FaceRecognitionArray, topic, self.face_cb, 10)
        self.info_sub = self.create_subscription(CameraInfo, self.camera_info_topic, self.info_cb, 10)
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer, self)

        self.marker_pub = self.create_publisher(MarkerArray, 'face_markers', 10)
        self.srv = self.create_service(ComputeCluster, 'compute_cluster', self.compute_cluster_cb)
        self.get_logger().info(f"Node ready: sub to {topic} & {self.camera_info_topic}")

    def info_cb(self, msg: CameraInfo):
        fx, fy = msg.k[0], msg.k[4]
        cx, cy = msg.k[2], msg.k[5]
        self.intrinsics = {'fx': fx, 'fy': fy, 'cx': cx, 'cy': cy}
        self.get_logger().info(f"Camera intrinsics set: {self.intrinsics}")
        self.destroy_subscription(self.info_sub)

    def face_cb(self, msg: FaceRecognitionArray):
        if self.intrinsics is None or len(msg.recognitions) == 0:
            return
        self.get_logger().info(f"\n----------- Han llegado unas {len(msg.recognitions)} caras ------------------------\n")
        detections = []  # list of (pos, person_id)
        for det, recog in zip(msg.detections, msg.recognitions):
            det = cast(FaceDetection, det)
            recog = cast(FaceRecognition, recog)

            if det.height <= 0:
                continue
            # Use recognition info if available
            pid = int(recog.classified_id) if recog.classified_id and recog.distance > 0.5 else -1
            
            # Calculate 3D position from detection
            if det.height <= 0:
                continue
            Z = self.k / det.height
            # if not (0.3 <= Z <= 6.0): 
            #     continue
            u, v = det.corner.x - det.width/2, det.corner.y - det.height/2  # center point
            X = (u - self.intrinsics['cx']) * Z / self.intrinsics['fx']
            Y = (v - self.intrinsics['cy']) * Z / self.intrinsics['fy']
            pt_cam = PointStamped()
            pt_cam.header.stamp = msg.header.stamp
            pt_cam.header.frame_id = self.camera_frame
            pt_cam.point.x, pt_cam.point.y, pt_cam.point.z = X, Y, Z

            try:
                pt_head = self.tf_buffer.transform(pt_cam, self.head_frame, timeout=rclpy.duration.Duration(seconds=0.1))
                p = pt_head.point
                detections.append(([p.x, p.y, p.z], pid))

                # Log recognized faces
                if pid > 0:
                    self.get_logger().info(f"Face detected: ID={pid}, Distance={recog.distance:.3f} position : {round(X,2) ,round(Y, 2),round(Z, 2)}")
            except Exception as e:
                self.get_logger().warning(f"Transform failed: {str(e)}")
                continue
        self.get_logger().info(f"\n-------Actualizando tracks -----------------------------\n")
        self.tracker.update(detections)
        self.get_logger().info(f"Lista de (track_id, person_id) en los tracks: {[(tr.id, tr.person_id) for tr in self.tracker.tracks]}")
        # Publish tracks
        ma = MarkerArray()
        for tr in self.tracker.tracks:
            # Sphere marker
            m = Marker(header=Header(frame_id=self.head_frame, stamp=msg.header.stamp), ns='face_sphere', type=Marker.SPHERE, action=Marker.ADD)
            m.lifetime = Duration(seconds=(0.1)).to_msg()
            m.id = tr.id
            m.pose.position.x, m.pose.position.y, m.pose.position.z = tr.pos.tolist()
            m.pose.position.z = float(1.0) #Debug
            m.scale.x = m.scale.y = m.scale.z = 0.5
            m.color.a = 1.0; m.color.r = 0.0; m.color.g = 1.0; m.color.b = 0.0
            ma.markers.append(m)

            # Text marker above the sphere showing the track id
            text_m = Marker(header=Header(frame_id=self.head_frame, stamp=msg.header.stamp), ns='face_text', type=Marker.TEXT_VIEW_FACING, action=Marker.ADD)
            text_m.lifetime = Duration(seconds=(2)).to_msg()
            text_m.id = tr.id
            text_m.pose.position.x = tr.pos[0]
            text_m.pose.position.y = tr.pos[1]
            # place text slightly above the sphere
            text_m.pose.position.z = m.pose.position.z + 0.3
            # Text uses scale.z for height
            text_m.scale.z = 0.2
            text_m.color.a = 1.0; text_m.color.r = 1.0; text_m.color.g = 1.0; text_m.color.b = 1.0
            text_m.text = f"trk:{tr.id} pid:{tr.person_id if tr.person_id>0 else 'unk'}"
            ma.markers.append(text_m)
        self.marker_pub.publish(ma)

    def compute_cluster_cb(self, request, response):
        pts = np.array([tr.pos for tr in self.tracker.tracks])
        ids = [tr.id for tr in self.tracker.tracks]
        if pts.size == 0:
            response.member_ids = []
            return response
        labels = DBSCAN(eps=self.dbscan_eps, min_samples=self.dbscan_min).fit_predict(pts)
        best_lbl, best_dist, best_centroid = None, float('inf'), None
        for lbl in set(labels):
            if lbl < 0:
                continue
            cluster_pts = pts[labels == lbl]
            centroid = cluster_pts.mean(axis=0)
            dist = np.linalg.norm(centroid[:2])
            if dist < best_dist:
                best_dist, best_lbl, best_centroid = dist, lbl, centroid
        if best_lbl is not None:
            response.member_ids = [int(ids[i]) for i, l in enumerate(labels) if l == best_lbl]
            response.centroid_x, response.centroid_y, response.centroid_z = map(float, best_centroid)
        else:
            response.member_ids = []
        return response


def main(args=None):
    rclpy.init(args=args)
    node = FaceClusterServiceNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()
