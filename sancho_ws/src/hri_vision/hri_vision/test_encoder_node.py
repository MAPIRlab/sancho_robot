import os
import cv2
import time
import json
import signal
import random
import subprocess
import numpy as np
from queue import Queue
from scipy.spatial.distance import cdist
from tqdm import tqdm
from sklearn.metrics import silhouette_score, calinski_harabasz_score

import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from std_msgs.msg import String
from hri_msgs.srv import Detection, Recognition, Training, GetString
from ros2web_msgs.srv import R2WSubscribe

from .api.gui_utils import mark_face
from .hri_bridge import HRIBridge

from hri_vision.human_face_recognizer import EncoderType


class TestEncoderNode(Node):
    def __init__(self, test_encoder: "TestEncoder"):
        super().__init__('test_encoder_node')
        self.test_encoder = test_encoder
        self.data_queue = Queue(maxsize=1)

        self.publisher_recognition = self.create_publisher(Image, 'camera/color/recognition', 1)

        self.detection_client = self.create_client(Detection, 'detection')
        while not self.detection_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('Detection service not available, waiting again...')

        self.recognition_client = self.create_client(Recognition, 'recognition')
        self.training_client = self.create_client(Training, 'recognition/training')
        self.get_faceprints_client = self.create_client(GetString, 'recognition/get_faceprint')
        self.ros2web_client = self.create_client(R2WSubscribe, "ros2web/subscribe")

        self.br = HRIBridge()
        self.get_logger().info("Test Encoder Node initialized successfully")


class TestEncoder:
    LOWER_BOUND = 0.75
    MIDDLE_BOUND = 0.80
    UPPER_BOUND = 0.90

    def __init__(self):
        self.node = TestEncoderNode(self)
        self.dataset_path = "/home/ubuntu/tfg/sandbox/vision/mapir_dataset"
        self.subscribed = False
        self.current_index = 0

        results_dir = os.path.join(os.path.dirname(__file__), "results")
        os.makedirs(results_dir, exist_ok=True)
        self.results_path = os.path.join(results_dir, f"test_encoder_results.json")

        self.samples = self.load_dataset()
        self.results = self.load_results()

        random.seed(42)

    def load_results(self):
        if os.path.exists(self.results_path):
            with open(self.results_path, 'r') as f:
                return json.load(f)
        return {}

    def save_results(self):
        with open(self.results_path, 'w') as f:
            json.dump(self.results, f, indent=4)

    def spin(self):
        for encoder in EncoderType:
            if encoder.value in self.results:
                self.node.get_logger().info(f"Encoder '{encoder.value}' ya evaluado. Saltando...")
                continue

            self.node.get_logger().info(f"\n==== Probando encoder: {encoder.value} ====")

            process = subprocess.Popen(
                "bash -c 'cd /home/ubuntu/tfg/ros2_ws && source install/setup.bash && ros2 run hri_vision recognizer --ros-args -p db_mode:=no_save -p encoder_name:=" + encoder.value + "'",
                shell=True,
                preexec_fn=os.setsid  # inicia nuevo process group
            )
            if not self.subscribed:
                self.ros2web_request('/camera/color/recognition', 'IMAGE')

            self.node.get_logger().info("Esperando 10s...")
            time.sleep(10)  # Esperar a que arranque el recognizer y los servicios

            try:
                result = self.run_test_for_encoder(encoder)
                self.results[encoder.value] = result
                self.save_results()
            finally:
                self.node.get_logger().info("Terminando proceso...")
                os.killpg(os.getpgid(process.pid), signal.SIGKILL)
                self.node.get_logger().info(f"\n==== Finalizado {encoder.value} ====")

                i = 0
                while True:
                    try:
                        out = subprocess.check_output(["ros2", "node", "list"]).decode()
                        if "/human_face_recognizer" not in out:
                            break
                        self.node.get_logger().info(f"{i}.- Esperando a que el nodo /human_face_recognizer desaparezca...")
                    except Exception as e:
                        self.node.get_logger().warn(f"Error consultando nodos: {e}")
                    
                    i += 1
                    time.sleep(1)

                self.node.get_logger().info(f"\n==== Finalizado {encoder.value} ====")

    def run_test_for_encoder(self, encoder):
        total = 0
        correct = 0
        class_wise = {}
        not_detected = 0
        recognition_times = []
        true_positives = 0
        false_positives = 0
        false_negatives = 0
        name_questions = 0
        confirm_questions = 0
        embedding_size = 0

        for client, name in [
            (self.node.detection_client, 'Detection'),
            (self.node.recognition_client, 'Recognition'),
            (self.node.training_client, 'Training'),
            (self.node.get_faceprints_client, 'GetFaceprint')
        ]:
            while not client.wait_for_service(timeout_sec=1.0):
                self.node.get_logger().info(f'{name} service not available, waiting again...')

        for idx in tqdm(range(len(self.samples)), desc=f"Evaluando {encoder.value}"):
            path, label = self.samples[idx]
            img = cv2.imread(path)

            if img is None:
                self.node.get_logger().warn(f"No se pudo cargar la imagen: {path}")
                continue

            predicted, recog_time, name_q, confirm_q, emb_size = self.process_frame(img, label)
            name_questions += name_q
            confirm_questions += confirm_q
            if embedding_size == 0:
                embedding_size = emb_size
            elif emb_size > 0 and embedding_size != emb_size:
                self.node.get_logger().info(f"PROBLEMON: {embedding_size}, {emb_size}")

            if recog_time > 0:
                recognition_times.append(recog_time)

            if predicted is None:
                not_detected += 1
                false_negatives += 1
                continue

            total += 1
            if predicted == label:
                correct += 1
                true_positives += 1
                class_wise.setdefault(label, {"correct": 0, "total": 0})["correct"] += 1
            else:
                false_positives += 1
            class_wise.setdefault(label, {"correct": 0, "total": 0})["total"] += 1

            acc = 100 * correct / total if total else 0.0
            #self.node.get_logger().info(f"[{idx + 1}/{len(self.samples)}] ACC: {acc:.2f}%")

            rclpy.spin_once(self.node)

        avg_time = float(np.mean(recognition_times)) if recognition_times else 0.0
        precision = true_positives / (true_positives + false_positives + 1e-8)
        recall = true_positives / (true_positives + false_negatives + 1e-8)
        f1_score = 2 * precision * recall / (precision + recall + 1e-8)

        self.node.get_logger().info(f"\n--- RESULTADOS PARA {encoder.value} ---")
        self.node.get_logger().info(f"Imágenes sin detección de cara: {not_detected}")
        self.node.get_logger().info(f"Accuracy global: {100 * correct / total:.2f}%")
        self.node.get_logger().info(f"Tiempo medio de codificación: {avg_time:.4f} s")
        self.node.get_logger().info(f"Precision: {precision:.4f}, Recall: {recall:.4f}, F1: {f1_score:.4f}")

        for cls, stats in class_wise.items():
            acc = 100 * stats["correct"] / stats["total"]
            self.node.get_logger().info(f"Clase {cls}: {acc:.2f}% ({stats['correct']}/{stats['total']})")

        embedding_metrics = self.get_faceprint_metrics()
        return {
            "embedding_size": embedding_size,
            "true_positives": true_positives,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1_score, 4),
            "avg_recognition_time": round(avg_time, 4),
            "global_accuracy": round(100 * correct / total, 2) if total else 0.0,
            "class_accuracy": {cls: round(100 * stats["correct"] / stats["total"], 2) for cls, stats in class_wise.items()},
            "undetected_samples": not_detected,
            "total_samples": len(self.samples),
            "name_questions": name_questions,
            "confirm_questions": confirm_questions,
            **embedding_metrics
        }

    def load_dataset(self):
        samples = []
        for class_name in sorted(os.listdir(self.dataset_path)):
            class_dir = os.path.join(self.dataset_path, class_name)
            if not os.path.isdir(class_dir):
                continue
            for fname in os.listdir(class_dir):
                if "rgb" in fname:
                    path = os.path.join(class_dir, fname)
                    samples.append((path, class_name))
        random.shuffle(samples)
        self.node.get_logger().info(f"{samples[0]} {samples[1]} {samples[2]}")
        return samples

    def process_frame(self, frame, real_class):
        frame_msg = self.node.br.cv2_to_imgmsg(frame, "bgr8")
        positions_msg, scores_msg = self.detection_request(frame_msg)
        positions, scores = self.node.br.msg_to_detector(positions_msg, scores_msg)

        classified_name = None
        recog_time = 0.0
        name_questions = 0
        confirm_questions = 0
        emb_size = 0
        for i in range(len(positions)):
            result = self.recognition_request(frame_msg, positions_msg[i], scores_msg[i])
            face_aligned_msg, features_msg, classified_id, classified_name_msg, distance_msg, pos_msg, face_updated, recog_time = result
            face_aligned, features, classified_name, distance, pos = self.node.br.msg_to_recognizer(
                face_aligned_msg, features_msg, classified_name_msg, distance_msg, pos_msg
            )
            emb_size = len(features)
            self.node.get_logger().info(f"emb_size: {emb_size}")

            if distance < self.LOWER_BOUND and scores[i] > 0.25:
                face_aligned_base64 = self.node.br.cv2_to_base64(face_aligned)
                classified_name = self.process_face_name_response(real_class, face_aligned_base64, features, scores[i])
                name_questions += 1
            elif distance < self.MIDDLE_BOUND and scores[i] > 0.25:
                face_aligned_base64 = self.node.br.cv2_to_base64(face_aligned)
                classified_name, asked_name = self.process_face_question_response(real_class, classified_id, classified_name, face_aligned_base64, features, scores[i])
                confirm_questions += 1
                if asked_name:
                    name_questions += 1
            elif distance >= self.UPPER_BOUND:
                self.training_request(String(data="refine_class"), String(data=json.dumps({
                    "class_id": classified_id,
                    "features": features,
                    "position": pos
                })))

            mark_face(frame, positions[i], distance, self.MIDDLE_BOUND, self.UPPER_BOUND, classified=classified_name,
                      drawRectangle=True, score=scores[i], showDistance=True, showScore=True)

        self.node.publisher_recognition.publish(self.node.br.cv2_to_imgmsg(frame, "bgr8"))
        return classified_name, recog_time, name_questions, confirm_questions, emb_size

    def process_face_name_response(self, real_class, face_base64, features, score):
        self.node.get_logger().info(f"RESPUESTA: {real_class}")
        self.training_request(String(data="add_class"), String(data=json.dumps({
            "class_name": real_class,
            "features": features,
            "face": face_base64,
            "score": score
        })))
        return real_class

    def process_face_question_response(self, real_class, classified_id, classified_name, face_base64, features, score):
        self.node.get_logger().info(f"PREGUNTANDIO SI {real_class} ES {classified_name}")
        if real_class == classified_name:
            self.node.get_logger().info(f"RESPUESTA: SI")
            self.training_request(String(data="add_features"), String(data=json.dumps({
                "class_id": classified_id,
                "features": features,
            })))
            return real_class, False
        else:
            self.node.get_logger().info(f"RESPUESTA: NO")
            return self.process_face_name_response(real_class, face_base64, features, score), True

    def detection_request(self, frame_msg):
        req = Detection.Request()
        req.frame = frame_msg
        future = self.node.detection_client.call_async(req)
        rclpy.spin_until_future_complete(self.node, future)
        return future.result().positions, future.result().scores

    def recognition_request(self, frame_msg, position_msg, score_msg):
        req = Recognition.Request()
        req.frame = frame_msg
        req.position = position_msg
        req.score = score_msg
        future = self.node.recognition_client.call_async(req)
        rclpy.spin_until_future_complete(self.node, future)
        return (future.result().face_aligned, future.result().features, future.result().classified_id,
                future.result().classified_name, future.result().distance, future.result().pos,
                future.result().face_updated, future.result().recognition_time)

    def training_request(self, cmd_type_msg, args_msg):
        req = Training.Request()
        req.cmd_type = cmd_type_msg
        req.args = args_msg
        future = self.node.training_client.call_async(req)
        rclpy.spin_until_future_complete(self.node, future)
        return future.result().result, future.result().message.data

    def ros2web_request(self, topic, name):
        if not self.node.ros2web_client.service_is_ready():
            return 0

        req = R2WSubscribe.Request()
        req.topic = topic
        req.name = name
        future = self.node.ros2web_client.call_async(req)
        rclpy.spin_until_future_complete(self.node, future)
        return future.result().value

    def get_faceprint_metrics(self):
        req = GetString.Request()
        req.args = json.dumps({})
        future = self.node.get_faceprints_client.call_async(req)
        rclpy.spin_until_future_complete(self.node, future)
        data = json.loads(future.result().text)

        return self.compute_faceprint_metrics(data)

    def compute_faceprint_metrics(self, faceprints):
        class_centroids = {}
        intra_variances = []
        total_embeddings = 0
        all_embeddings = []
        all_labels = []

        for fp in faceprints:
            features_list = fp["features"]
            features = np.array(features_list, dtype=np.float32)
            if len(features) == 0:
                continue

            centroid = np.mean(features, axis=0)
            class_centroids[fp["name"]] = centroid

            diffs = features - centroid
            sq_diffs = np.sum(diffs ** 2, axis=1)
            variance = np.mean(sq_diffs)
            intra_variances.append(variance)

            total_embeddings += len(features)
            all_embeddings.append(features)
            all_labels.extend([fp["name"]] * len(features))

        if len(class_centroids) < 2:
            return {
                "num_classes": len(class_centroids),
                "mean_class_size": total_embeddings / len(class_centroids) if class_centroids else 0,
                "mean_intra_variance": float(np.mean(intra_variances)) if intra_variances else 0.0,
                "mean_inter_class_distance": 0.0,
                "min_inter_class_distance": 0.0,
                "max_inter_class_distance": 0.0,
                "separability": 0.0,
                "silhouette_score": -1,
                "calinski_harabasz_score": -1
            }

        centroids = np.array(list(class_centroids.values()))
        centroid_distances = cdist(centroids, centroids, metric="euclidean")
        np.fill_diagonal(centroid_distances, np.nan)

        mean_inter = float(np.nanmean(centroid_distances))
        min_inter = float(np.nanmin(centroid_distances))
        max_inter = float(np.nanmax(centroid_distances))
        mean_intra = float(np.mean(intra_variances)) if intra_variances else 0.0

        separability = mean_inter / (mean_intra + 1e-8) if mean_intra > 0 else 0.0

        all_embeddings = np.vstack(all_embeddings)
        label_set = list(sorted(set(all_labels)))
        label_to_int = {label: idx for idx, label in enumerate(label_set)}
        label_indices = [label_to_int[label] for label in all_labels]

        try:
            sil_score = float(silhouette_score(all_embeddings, label_indices))
        except Exception:
            sil_score = -1.0
        try:
            ch_score = float(calinski_harabasz_score(all_embeddings, label_indices))
        except Exception:
            ch_score = -1.0

        return {
            "num_classes": len(class_centroids),
            "mean_class_size": total_embeddings / len(class_centroids),
            "mean_intra_variance": mean_intra,
            "mean_inter_class_distance": mean_inter,
            "min_inter_class_distance": min_inter,
            "max_inter_class_distance": max_inter,
            "separability": round(separability, 4),
            "silhouette_score": round(sil_score, 4),
            "calinski_harabasz_score": round(ch_score, 2)
        }

def main(args=None):
    rclpy.init(args=args)

    test_encoder = TestEncoder()
    test_encoder.spin()

    rclpy.shutdown()