import cv2
import rclpy
import time
import threading
import numpy as np
from rclpy.node import Node
from concurrent.futures import ThreadPoolExecutor
from sensor_msgs.msg import Image
from cv_bridge import CvBridge

from sancho_msgs.msg import FaceDetectionArray, FaceDetection, FaceRecognitionArray, FaceRecognition
from geometry_msgs.msg import Point

from .detectors import load_detector
from .encoders import load_encoder
from .classifiers.complex_classifier import ComplexClassifier
from .aligners.aligner_dlib import align_face


# ──────────────────────────────────────────────────────────
#  Threshold tiers (mirrors HumanFaceRecognizerLifecycleNode)
# ──────────────────────────────────────────────────────────
LOWER_BOUND  = 0.65   # below  → Unknown
MIDDLE_BOUND = 0.75   # 0.75–0.80 → probable
UPPER_BOUND  = 0.85   # ≥ 0.90  → very confident → refine online


class BodyFaceFusionNode(Node):
    """
    Pipeline B: anchors face identities to stable body-track IDs (ByteTrack/YOLOX).

    For each body track received from sancho_perception, it:
      1. Crops the head region (top 40 % of the body bounding box).
      2. Applies preprocess_frame() preprocessing (from pipeline A's detector node).
      3. Runs a configurable face detector on the crop.
      4. Aligns the best detected face with dlib 68-point landmarks.
      5. Encodes it with FaceNet (or any configured encoder).
      6. Classifies via cosine similarity against faceprints_db.json.
      7. Stores the result in a TTL/LRU recognition cache keyed by body TID.

    Because identification is cached by body TID, it persists through face
    occlusions as long as the body track is alive.
    """

    def __init__(self):
        super().__init__('body_face_fusion_node')
        self.bridge = CvBridge()

        # ── Parameters ─────────────────────────────────────────────────────
        self.declare_parameters(namespace='', parameters=[
            ('human_tracking_topic',    '/sancho_perception/human_tracking'),
            ('face_recognitions_topic', '/face_recognitions'),
            ('detector_name',           'mtcnn'),   # same options as pipeline A
            ('encoder_name',            'facenet'),
            ('head_fraction',           0.40),   # top N% of body box → face region
            ('cache_ttl',               10.0),   # seconds before a cached entry expires
            ('cache_max_size',          20),      # LRU eviction limit
            ('cleanup_timeout',         30.0),   # seconds before a body TID is forgotten
        ])

        detector_name  = self.get_parameter('detector_name').value
        encoder_name   = self.get_parameter('encoder_name').value
        self.cache_ttl      = float(self.get_parameter('cache_ttl').value)
        self.cache_max_size = int(self.get_parameter('cache_max_size').value)
        self.head_fraction  = float(self.get_parameter('head_fraction').value)

        # ── ML components (same as pipeline A) ─────────────────────────────
        try:
            self.detector   = load_detector(detector_name)
            self.get_logger().info(f"Detector loaded: {detector_name}")
        except Exception as e:
            self.get_logger().error(f"Failed to load detector '{detector_name}': {e}")
            raise

        try:
            self.encoder    = load_encoder(encoder_name)
            self.get_logger().info(f"Encoder loaded: {encoder_name}")
        except Exception as e:
            self.get_logger().error(f"Failed to load encoder '{encoder_name}': {e}")
            raise

        self.classifier = ComplexClassifier('save')

        # ── Recognition cache (mirrors HumanFaceRecognizerLifecycleNode) ───
        #
        # Key  : body tracker TID (int)
        # Value: {face_aligned, features, faceprint, distance, pos,
        #         face_updated, last_seen}
        self.recognition_cache: dict = {}

        # ── Body-lifetime tracking (for cleanup) ────────────────────────────
        self.last_seen: dict = {}    # tid → wall-clock timestamp

        # ── Retry counters (to rate-limit inference per TID) ────────────────
        self.retry_count: dict = {}  # tid → int

        # ── Thread safety ───────────────────────────────────────────────────
        self.state_lock = threading.Lock()

        # One worker thread for non-blocking ML inference
        self.inference_pool = ThreadPoolExecutor(max_workers=1)

        # ── ROS I/O ─────────────────────────────────────────────────────────
        human_topic   = self.get_parameter('human_tracking_topic').value
        recog_topic   = self.get_parameter('face_recognitions_topic').value
        self.sub_human = self.create_subscription(
            FaceDetectionArray, human_topic, self.human_callback, 10)
        self.pub_recog = self.create_publisher(
            FaceRecognitionArray, recog_topic, 10)

        # ── Timers ───────────────────────────────────────────────────────────
        self.cache_prune_timer  = self.create_timer(5.0,  self.prune_cache)
        self.cleanup_timer      = self.create_timer(10.0, self.cleanup_body_tracks)

        self.get_logger().info(
            f"BodyFaceFusionNode ready | "
            f"detector={detector_name} | encoder={encoder_name} | "
            f"head_fraction={self.head_fraction:.0%}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    #  Preprocessing  (exact copy of pipeline A's HumanFaceDetectorLifecycleNode)
    # ─────────────────────────────────────────────────────────────────────────
    def preprocess_frame(self, frame):
        """Bilateral filter + histogram equalization on the Y channel of YCrCb."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        image_bilateral = cv2.bilateralFilter(gray, d=5, sigmaColor=50, sigmaSpace=50)
        gray_equalized  = cv2.equalizeHist(image_bilateral)
        frame_ycrcb     = cv2.cvtColor(frame, cv2.COLOR_BGR2YCrCb)
        frame_ycrcb[:, :, 0] = gray_equalized
        return cv2.cvtColor(frame_ycrcb, cv2.COLOR_YCrCb2BGR)

    # ─────────────────────────────────────────────────────────────────────────
    #  Main callback
    # ─────────────────────────────────────────────────────────────────────────
    def human_callback(self, msg: FaceDetectionArray):
        if not msg.detections:
            return

        try:
            frame = self.bridge.imgmsg_to_cv2(msg.image, "bgr8")
        except Exception as e:
            self.get_logger().error(f"CV Bridge error: {e}")
            return

        now = time.monotonic()

        out_msg           = FaceRecognitionArray()
        out_msg.header    = msg.header
        out_msg.image     = self.bridge.cv2_to_imgmsg(frame, "bgr8")
        out_msg.image.header = msg.header

        # FIX: Preprocess the FULL frame globally, exactly like Pipeline A
        frame_preprocessed = self.preprocess_frame(frame.copy())

        with self.state_lock:
            for body in msg.detections:
                tid = body.tid
                self.last_seen[tid] = now

                if tid in self.recognition_cache:
                    entry = self.recognition_cache[tid]
                    entry['last_seen'] = now
                    recog = self._entry_to_recognition(entry)
                    out_msg.recognitions.append(recog)
                    out_msg.detections.append(body)
                    continue

                if tid not in self.retry_count:
                    self.retry_count[tid] = 0

                if self.retry_count[tid] % 10 == 0:
                    # FIX: Pass BOTH the raw frame and the preprocessed frame
                    self.inference_pool.submit(
                        self.process_identification,
                        tid, frame.copy(), frame_preprocessed.copy(), body
                    )

                self.retry_count[tid] = (self.retry_count[tid] + 1) % 10001

                # Publish "Unknown" placeholder while we wait for inference
                recog = FaceRecognition()
                recog.classified_id   = ''
                recog.classified_name = 'Unknown'
                recog.distance        = 0.0
                out_msg.recognitions.append(recog)
                out_msg.detections.append(body)

        self.pub_recog.publish(out_msg)

    # ─────────────────────────────────────────────────────────────────────────
    #  Identification pipeline (runs in thread pool)
    # ─────────────────────────────────────────────────────────────────────────
    def process_identification(self, tid: int, frame_raw: np.ndarray, frame_preproc: np.ndarray, body_det):
        try:
            x = int(body_det.corner.x)
            y = int(body_det.corner.y)
            w = int(body_det.width)
            h = int(body_det.height)

            # ── 1. Context Padding ───────────────────────────────────────────
            y_margin = int(h * 0.20)
            x_margin = int(w * 0.20)
            head_h = int(h * 0.50) 
            
            y1 = max(0, y - y_margin) 
            y2 = min(frame_raw.shape[0], y + head_h)
            x1 = max(0, x - x_margin) 
            x2 = min(frame_raw.shape[1], x + w + x_margin) 

            # ── 2. Detection (Using the Globally Preprocessed Frame) ─────────
            # We take the crop from the image that was already globally equalized
            crop_prep = frame_preproc[y1:y2, x1:x2]

            if crop_prep.shape[0] < 40 or crop_prep.shape[1] < 40:
                self.get_logger().info(f"[TID {tid}] SILENT EXIT: Head crop too small {crop_prep.shape}")
                return

            positions, confidences = self.detector.get_faces(crop_prep)

            # Fallback to full body if head crop misses
            if len(positions) == 0:
                fy1, fy2 = max(0, y), min(frame_raw.shape[0], y + h)
                fx1, fx2 = max(0, x), min(frame_raw.shape[1], x + w)
                
                full_crop_prep = frame_preproc[fy1:fy2, fx1:fx2]
                
                if full_crop_prep.shape[0] >= 40 and full_crop_prep.shape[1] >= 40:
                    positions, confidences = self.detector.get_faces(full_crop_prep)
                    if len(positions) > 0:
                        y1, x1 = fy1, fx1 # Update offset references for mapping

            if len(positions) == 0:
                self.get_logger().info(f"[TID {tid}] SILENT EXIT: No face found by Dlib in any crop.")
                return

            # ── 3. Coordinate Mapping ─────────────────────────────────────────
            best_idx  = int(np.argmax(confidences))
            best_face = positions[best_idx]
            best_conf = confidences[best_idx]

            if best_conf < 0.60: 
                self.get_logger().info(f"[TID {tid}] SILENT EXIT: Ignored false positive (conf={best_conf:.3f})")
                return

            # Safely extract coordinates whether it's a Dlib rectangle or a list
            if hasattr(best_face, 'left'):
                face_x = best_face.left() + x1
                face_y = best_face.top() + y1
                face_w = best_face.width()
                face_h = best_face.height()
            else:
                face_x = best_face[0] + x1
                face_y = best_face[1] + y1
                face_w = best_face[2]
                face_h = best_face[3]

            absolute_position = [face_x, face_y, face_w, face_h]
            self.get_logger().info(f"[TID {tid}] Face detected | conf={best_conf:.3f}")

            # ── 4. Align & Encode (Using the RAW Frame) ───────────────────────
            # FaceNet needs raw pixels, not equalized pixels
            face_aligned = align_face(frame_raw, absolute_position)

            features = self.encoder.encode_face(face_aligned)
            faceprint, distance, pos = self.classifier.classify_face(features)

            self.get_logger().info(
                f"[TID {tid}] Classification → '{faceprint.get('name', 'Unknown')}' | "
                f"distance={distance:.4f} | conf={best_conf:.3f}"
            )

            # ... Keep your existing threshold (Step 5) and caching (Step 6) logic ...
            # ── 5. Apply Thresholds ───────────────────────────────────────────
            face_updated = False
            if distance >= UPPER_BOUND and best_conf >= 1.0:
                self.classifier.refine_class(faceprint['id'], features, pos)
                face_updated = self.classifier.save_face(faceprint['id'], face_aligned, best_conf)

            if distance < LOWER_BOUND:
                self.get_logger().info(f"[TID {tid}] REJECTED (distance {distance:.4f} < {LOWER_BOUND})")
                return

            # ── 6. Cache ──────────────────────────────────────────────────────
            display_name = (
                "Unknown"         if not faceprint.get("id") else
                faceprint["name"] if faceprint.get("name")   else
                f"User-{faceprint['id']}"
            )
            self.get_logger().info(f"[TID {tid}] CACHED as '{display_name}' (distance={distance:.4f})")

            entry = {
                'face_aligned': face_aligned,
                'features':     features,
                'faceprint':    faceprint,
                'distance':     distance,
                'pos':          pos,
                'face_updated': face_updated,
                'last_seen':    time.monotonic(),
            }

            with self.state_lock:
                self.recognition_cache[tid] = entry
                self.retry_count.pop(tid, None)

        except Exception as e:
            import traceback
            self.get_logger().error(f"[TID {tid}] HIDDEN THREAD CRASH: {e}\n{traceback.format_exc()}")

    # ─────────────────────────────────────────────────────────────────────────
    #  Cache maintenance  (mirrors HumanFaceRecognizerLifecycleNode)
    # ─────────────────────────────────────────────────────────────────────────
    def prune_cache(self):
        """Evict stale entries from the recognition cache (TTL + LRU)."""
        now = time.monotonic()
        with self.state_lock:
            # TTL eviction
            expired = [
                tid for tid, e in self.recognition_cache.items()
                if (now - e.get('last_seen', 0)) > self.cache_ttl
            ]
            for tid in expired:
                del self.recognition_cache[tid]
                self.get_logger().info(f"[cache] Evicted TID {tid} (TTL expired)")

            # LRU eviction if over max size
            if len(self.recognition_cache) > self.cache_max_size:
                sorted_ids = sorted(
                    self.recognition_cache.items(),
                    key=lambda kv: kv[1].get('last_seen', 0)
                )
                for tid, _ in sorted_ids[:len(self.recognition_cache) - self.cache_max_size]:
                    if tid in self.recognition_cache:
                        del self.recognition_cache[tid]
                        self.get_logger().info(f"[cache] Evicted TID {tid} (LRU)")

    def cleanup_body_tracks(self):
        """Remove tracking state for body TIDs that have disappeared."""
        now = time.monotonic()
        timeout = float(self.get_parameter('cleanup_timeout').value)
        with self.state_lock:
            to_remove = [
                tid for tid, last in self.last_seen.items()
                if (now - last) > timeout
            ]
            for tid in to_remove:
                self.last_seen.pop(tid, None)
                self.retry_count.pop(tid, None)
                self.recognition_cache.pop(tid, None)
                self.get_logger().info(f"[body] Cleaned up TID {tid} (body track gone)")

    # ─────────────────────────────────────────────────────────────────────────
    #  Helpers
    # ─────────────────────────────────────────────────────────────────────────
    @staticmethod
    def _entry_to_recognition(entry: dict) -> FaceRecognition:
        faceprint = entry['faceprint']
        recog = FaceRecognition()
        recog.classified_id   = faceprint.get('id', '')
        recog.classified_name = faceprint.get('name', '')
        recog.distance        = float(entry.get('distance', 0.0))
        recog.face_updated    = bool(entry.get('face_updated', False))
        return recog


def main(args=None):
    rclpy.init(args=args)
    node = BodyFaceFusionNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.inference_pool.shutdown(wait=False)
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()