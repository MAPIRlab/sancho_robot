import math
import time
import json
import threading
from enum import Enum
from queue import Queue
from typing import Tuple, List

import numpy as np

import rclpy
from rclpy.qos import QoSProfile
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor
from rclpy.lifecycle import LifecycleNode, TransitionCallbackReturn

from std_msgs.msg import String, Float32, Int16
from hri_msgs.msg import ChunkMono
from sancho_msgs.msg import QuestionTTS, FaceRecognitionArray, UserTranscription
from sancho_msgs.srv import AskUser
from speech_msgs.srv import STT

# ---- Utils (se mantienen igual que en tu código original) ----
from .utils.sound import play
from .utils.sounds import ACTIVATION_SOUND, TIME_OUT_SOUND
from .utils.silero_vad_attach_criterion import SileroVADAttachCriterion
from .utils.intensity_attach_criterion import IntensityAttachCriterion


# ---------- Helper sincrono para llamadas a servicios (mismo estilo) ----------
def _call_service_sync(node, client, request, timeout=5.0):
    if not client.service_is_ready():
        raise RuntimeError(f"Service {client.srv_name} is not ready")

    fut = client.call_async(request)
    done = threading.Event()

    def _on_done(_):
        try:
            _ = fut.result()
        except Exception:
            pass
        finally:
            done.set()

    fut.add_done_callback(_on_done)

    deadline = time.monotonic() + timeout if timeout else None
    while True:
        if done.wait(timeout=0.01):
            return fut.result()
        if deadline is not None and time.monotonic() > deadline:
            raise TimeoutError(f"Timeout waiting for service {client.srv_name} response")


# ---------------------------- Enums ----------------------------
class AUDIO_STATE(int, Enum):
    NO_AUDIO = -1
    SOME_AUDIO = 0
    END_AUDIO = 1


class HELPER_STATE(int, Enum):
    NAME = 0
    SPEAKING = 1
    COMMAND = 2
    ASKING = 3


# --------------------- Lifecycle Node principal ---------------------
class AssistantHelperLifecycleNode(LifecycleNode):
    def __init__(self):
        super().__init__("assistant_helper")

        # Declaración de parámetros (con valores por defecto)
        self.declare_parameters(namespace="", parameters=[
            ("name", "Sancho"),
            ("microphone_topic", "sancho_audio/microphone/mono"),
            ("mode_topic", "sancho_audio/assistant_helper/mode"),
            ("face_recognitions_topic", "face_recognitions"),
            ("audio_doa_topic", "sancho_audio/doa"),
            ("face_mode_topic", "face/mode"),
            ("assistant_transcription_topic", "sancho_audio/assistant_helper/transcription"),
            ("question_tts_topic", "question_tts"),
            ("stt_service", "speech_tools/stt"),
            ("ask_user_service", "sancho_audio/ask_user"),
            ("processing_rate", 100.0),  # Hz del timer de procesamiento
            ("helper_chunk_size", 0.5),
            ("intensity_threshold", 1400),
            ("timeout_seconds", 5.0),
            ("hotword", "openwakeword"),       # "stt" | "pvporcupine" | "openwakeword"
            ("attach_criterion", "intensity"), # "intensity" | "silero_vad"
        ])

        # Estructuras de colas compartidas
        self.chunk_queue: Queue = Queue()
        self.question_queue: Queue = Queue()

        # Callback group reentrante para concurrencia
        self.cb_group = ReentrantCallbackGroup()

        # Pubs/subs/timers/servicios (se inicializan en on_configure / on_activate)
        self.pub_face_mode = None
        self.pub_assistant_text = None
        self.pub_question_tts = None

        self.sub_micro = None
        self.sub_mode = None
        self.sub_face_recog = None
        self.sub_audio_doa = None

        self.ask_user_server = None
        self.stt_client = None

        self.spin_timer = None

        # Listas temporales para DOA y reconocimiento facial
        self.face_recog_list: List[FaceRecognitionArray] = []
        self.audio_doa_list: List[Float32] = []

        # Estado y helper (lógica)
        self.helper = None

    # ---------------- Lifecycle: configure ----------------
    def on_configure(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Configurando AssistantHelper lifecycle node...")

        # Leer parámetros
        self.name = self.get_parameter("name").value
        self.microphone_topic = self.get_parameter("microphone_topic").value
        self.mode_topic = self.get_parameter("mode_topic").value
        self.face_recognitions_topic = self.get_parameter("face_recognitions_topic").value
        self.audio_doa_topic = self.get_parameter("audio_doa_topic").value
        self.face_mode_topic = self.get_parameter("face_mode_topic").value
        self.assistant_transcription_topic = self.get_parameter("assistant_transcription_topic").value
        self.question_tts_topic = self.get_parameter("question_tts_topic").value
        self.stt_service_name = self.get_parameter("stt_service").value
        self.ask_user_service_name = self.get_parameter("ask_user_service").value
        self.processing_rate = float(self.get_parameter("processing_rate").value)
        self.helper_chunk_size = float(self.get_parameter("helper_chunk_size").value)
        self.intensity_threshold = int(self.get_parameter("intensity_threshold").value)
        self.timeout_seconds = float(self.get_parameter("timeout_seconds").value)
        self.hotword = self.get_parameter("hotword").value
        self.attach_criterion = self.get_parameter("attach_criterion").value

        qos10 = QoSProfile(depth=10)
        self.pub_face_mode = self.create_lifecycle_publisher(String, self.face_mode_topic, qos10)
        self.pub_assistant_text = self.create_lifecycle_publisher(UserTranscription, self.assistant_transcription_topic, qos10)
        self.pub_question_tts = self.create_lifecycle_publisher(QuestionTTS, self.question_tts_topic, qos10)

        # Cliente STT
        self.stt_client = self.create_client(STT, self.stt_service_name, callback_group=self.cb_group)
        attempts = 0
        while not self.stt_client.wait_for_service(timeout_sec=1.0):
            attempts += 1
            self.get_logger().info('STT service not available, waiting again...')
            # Opcionalmente romper si excede un número de intentos

        # Instanciar la lógica del helper
        self.helper = AssistantHelper(self, name=self.name,
                                      helper_chunk_size=self.helper_chunk_size,
                                      intensity_threshold=self.intensity_threshold,
                                      timeout_seconds=self.timeout_seconds,
                                      hotword=self.hotword,
                                      attach_criterion=self.attach_criterion)

        return super().on_configure(state)

    # ---------------- Lifecycle: activate ----------------
    def on_activate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Activando AssistantHelper lifecycle node...")

        qos10 = QoSProfile(depth=10)

        # Subscripciones
        self.sub_micro = self.create_subscription(
            ChunkMono,
            self.microphone_topic,
            self.microphone_callback,
            qos10,
            callback_group=self.cb_group
        )
        self.sub_mode = self.create_subscription(
            Int16,
            self.mode_topic,
            self.mode_callback,
            qos10,
            callback_group=self.cb_group
        )
        self.sub_face_recog = self.create_subscription(
            FaceRecognitionArray,
            self.face_recognitions_topic,
            self.face_recog_callback,
            qos10,
            callback_group=self.cb_group
        )
        self.sub_audio_doa = self.create_subscription(
            Float32,
            self.audio_doa_topic,
            self.audio_doa_callback,
            qos10,
            callback_group=self.cb_group
        )

        # Servidor de servicio AskUser (igual que en tu nodo original)
        self.ask_user_server = self.create_service(
            AskUser,
            self.ask_user_service_name,
            self.ask_user_service_callback,
            callback_group=self.cb_group
        )

        # Timer de procesamiento al estilo del otro nodo
        self.spin_timer = self.create_timer(1.0 / self.processing_rate, self.helper.spin_step, callback_group=self.cb_group)

        return super().on_activate(state)

    # ---------------- Lifecycle: deactivate ----------------
    def on_deactivate(self, state) -> TransitionCallbackReturn:
        self.get_logger().info("Desactivando AssistantHelper lifecycle node...")

        if self.spin_timer:
            self.spin_timer.cancel()
            self.spin_timer = None

        if self.sub_micro:
            self.destroy_subscription(self.sub_micro)
            self.sub_micro = None

        if self.sub_mode:
            self.destroy_subscription(self.sub_mode)
            self.sub_mode = None

        if self.sub_face_recog:
            self.destroy_subscription(self.sub_face_recog)
            self.sub_face_recog = None

        if self.sub_audio_doa:
            self.destroy_subscription(self.sub_audio_doa)
            self.sub_audio_doa = None

        if self.ask_user_server:
            self.destroy_service(self.ask_user_server)
            self.ask_user_server = None

        return super().on_deactivate(state)

    # ---------------- Callbacks de I/O ----------------
    def microphone_callback(self, msg: ChunkMono):
        new_audio = list([np.int16(x) for x in msg.chunk_mono])
        sample_rate = msg.sample_rate
        self.chunk_queue.put([new_audio, sample_rate])

    def mode_callback(self, msg: Int16):
        new_helper_state = msg.data
        if new_helper_state in [e.value for e in HELPER_STATE]:
            self.helper.helper_state = HELPER_STATE(new_helper_state)
            self.helper.transcription_sent = False
            self.get_logger().info(f"Helper state changed to: {self.helper.helper_state.name}")
        else:
            self.get_logger().info(f"Invalid helper state mode: {new_helper_state}")

    def face_recog_callback(self, msg: FaceRecognitionArray):
        if self.helper.audio_state != AUDIO_STATE.NO_AUDIO:
            self.face_recog_list.append(msg)

    def audio_doa_callback(self, msg: Float32):
        if self.helper.audio_state != AUDIO_STATE.NO_AUDIO:
            self.audio_doa_list.append(msg)

    def ask_user_service_callback(self, request: AskUser.Request, response: AskUser.Response):
        # Igual que tu nodo original: mete en cola y responde accepted=True
        self.question_queue.put([request.question_id, request.args_json])
        response.accepted = True
        return response


# ------------------------- Lógica (igual que tu clase original, adaptada) -------------------------
class AssistantHelper:

    def __init__(self, node: AssistantHelperLifecycleNode, name="Sancho",
                 helper_chunk_size=0.5, intensity_threshold=1400, timeout_seconds=5.0,
                 hotword="openwakeword", attach_criterion="intensity"):
        self.node = node
        self.name = name

        self.audio_state = AUDIO_STATE.NO_AUDIO
        self.helper_state = HELPER_STATE.NAME
        self.transcription_sent = False

        self.sample_rate = -1  # se establece al llegar audio
        self.helper_chunk_size = float(helper_chunk_size)
        self.intensity_threshold = int(intensity_threshold)
        self.timeout_seconds = float(timeout_seconds)

        self.hotword_detection_time = 0.0

        self.audio: List[int] = []
        self.check_audio: List[int] = []
        self.previous_chunk: List[int] = []

        self.hotword_detector = self._init_hotword_detector(hotword)
        self.chunk_attach_criterion = self._init_chunk_attach_criterion(attach_criterion)

    # Llamado en cada tick del timer (estilo lifecycle)
    def spin_step(self):
        while not self.node.chunk_queue.empty(): # While para que si entran dos chunks antes del siguiente spin pues se procesen los dos
            [new_audio, self.sample_rate] = self.node.chunk_queue.get()

            if self.transcription_sent:
                # No hacemos nada hasta que nos cambien de estado desde fuera
                pass

            elif self.helper_state == HELPER_STATE.NAME:
                if not self.node.question_queue.empty():
                    [question_id, args] = self.node.question_queue.get()
                    self.process_question(question_id, args)
                else:
                    self.detect_hotword(new_audio)

            elif self.helper_state in [HELPER_STATE.COMMAND, HELPER_STATE.ASKING]:
                self.build_audio_command(new_audio)

    # ---------- Métricas/lógica iguales a tu código ----------
    def process_question(self, question_id, args_json):
        self.node.pub_question_tts.publish(QuestionTTS(question_id=question_id, args_json=args_json))
        self.helper_state = HELPER_STATE.SPEAKING

    def detect_hotword(self, new_audio: List[int]):
        self.node.get_logger().info(f"Listening for hotword: {len(new_audio)}")
        if self.hotword_detector.detect(new_audio, self.sample_rate):
            self.node.pub_face_mode.publish(String(data="listening"))
            self.helper_state = HELPER_STATE.COMMAND

            self.hotword_detection_time = time.time()
            self.node.get_logger().info(f"✅✅✅ '{self.name.upper()}' DETECTED")

            play(ACTIVATION_SOUND, wait_for_end=True)

            # Limpiar buffers y colas como en el original
            self._reset_audio_buffers(clear_chunk_queue=True)

    def build_audio_command(self, new_audio: List[int]):
        self.check_audio = self.check_audio + new_audio

        # Timeout cuando todavía no hemos empezado a adjuntar audio
        if self.helper_state != HELPER_STATE.ASKING and len(self.audio) == 0 and time.time() - self.hotword_detection_time > self.timeout_seconds:
            self.node.pub_face_mode.publish(String(data="idle"))
            self.helper_state = HELPER_STATE.NAME
            
            play(TIME_OUT_SOUND, wait_for_end=True)
            self.node.get_logger().info(f"No audio command detected for {self.timeout_seconds} seconds, timeout.")

        elif self.is_audio_length(self.check_audio, self.helper_chunk_size):
            if self.chunk_attach_criterion.should_attach_chunk(self.check_audio, self.sample_rate):
                if self.audio_state == AUDIO_STATE.NO_AUDIO:
                    self.audio_state = AUDIO_STATE.SOME_AUDIO
                if len(self.audio) == 0:
                    # Adjuntar chunk previo la primera vez para no cortar inicio
                    self.audio = self.previous_chunk
                self.audio = self.audio + self.check_audio
                self.node.get_logger().info(f"Chunk attached ({len(self.audio) / self.sample_rate}s)")
            elif self.audio_state != AUDIO_STATE.NO_AUDIO:
                # Cierre de ventana de audio
                self.audio_state = AUDIO_STATE.END_AUDIO
                self.audio = self.audio + self.check_audio
                self.node.get_logger().info("No more audio detected. Closing chunk window")
            else:
                self.node.get_logger().info("Listening for command but no audio detected yet")

            self.previous_chunk = self.check_audio
            self.check_audio = []

        if self.audio_state == AUDIO_STATE.END_AUDIO:
            self.process_audio_command(self.audio)

            self.audio = []
            self.check_audio = []
            self.audio_state = AUDIO_STATE.NO_AUDIO

            # Limpiar cola mientras hacemos STT, como en tu código
            self._reset_audio_buffers(clear_chunk_queue=True)

    def process_audio_command(self, audio: List[int]):
        self.node.get_logger().info(f"Transcribing {len(audio) / self.sample_rate}s chunk...")

        rec = self.stt_request(list(map(int, audio)), self.sample_rate)
        if rec:
            if rec.lower().strip() == self.name.lower():
                self.hotword_detection_time = time.time()
                play(ACTIVATION_SOUND)
                self.node.get_logger().info(f"✅✅✅ '{self.name.upper()}' DETECTED AGAIN")
            else:
                id_, name_ = self.determine_user(self.node.face_recog_list, self.node.audio_doa_list)
                self.node.get_logger().info(f"📖📖📖 USUARIO IDENTIFICADO: {id_}-{name_}")

                self.node.pub_assistant_text.publish(UserTranscription(text=rec, id=id_, name=name_))
                self.node.get_logger().info(f"✅✅✅ Text transcribed ({len(audio) / self.sample_rate}s): {rec}")

                self.transcription_sent = True
                self.node.face_recog_list = []
                self.node.audio_doa_list = []
        else:
            self.node.get_logger().info("Transcription result is empty.")

    # --------- Utilidades de lógica (igual que original) ----------
    def determine_user(self, face_recog_list, audio_doa_list) -> Tuple[str, str]:
        DEFAULT = ("", "")
        if len(face_recog_list) <= 0:
            return DEFAULT

        last_face_recog: FaceRecognitionArray = face_recog_list[-1]
        recognitions = last_face_recog.recognitions
        detections = last_face_recog.detections

        if len(recognitions) <= 0:
            return DEFAULT

        if len(recognitions) == 1:
            return recognitions[0].classified_id, recognitions[0].classified_name

        if not audio_doa_list:
            return DEFAULT

        last_audio_doa: Float32 = audio_doa_list[-1]
        angle = last_audio_doa.data

        if angle is None or angle != angle:  # NaN check
            return DEFAULT

        angle_x = self.calc_x_from_azimut(angle)

        best_recog, best_diff = None, float('inf')
        for recog, det in zip(recognitions, detections):
            det_center_x = det.corner.x + (det.width / 2)
            diff = abs(det_center_x - angle_x)
            if diff < best_diff:
                best_diff = diff
                best_recog = recog

        return (best_recog.classified_id, best_recog.classified_name) if best_recog else DEFAULT

    def calc_x_from_azimut(self, azimut_deg, yaw_off=0.0, cx=939.37064, fx=1075.42921):
        theta = max(-89.9, min(89.9, float(azimut_deg) + yaw_off))
        return int(round(cx + fx * math.tan(math.radians(theta))))

    # --------- Llamada STT con helper sincrono (mismo estilo) ----------
    def stt_request(self, audio: List[int], sample_rate: int) -> str:
        if not self.node.stt_client or not self.node.stt_client.service_is_ready():
            self.node.get_logger().error("STT client not ready")
            return ""

        req = STT.Request()
        req.audio = audio
        req.sample_rate = sample_rate

        try:
            result = _call_service_sync(self.node, self.node.stt_client, req, timeout=20.0)
            return result.text
        except Exception as e:
            self.node.get_logger().error(f"Error calling STT service: {e}")
            return ""

    # --------- Inicialización de detectores/criterios (igual que original) ----------
    def _init_hotword_detector(self, hotword="openwakeword"):
        if hotword == "stt":
            from .utils.stt_hotword import STTHotword
            return STTHotword(self.stt_request, name=self.name)
        elif hotword == "pvporcupine":
            from .utils.pvporcupine_hotword import PVPorcupineHotword
            return PVPorcupineHotword()
        else:  # openwakeword
            from .utils.openwakeword_hotword import OpenWakeWordHotword
            return OpenWakeWordHotword()

    def _init_chunk_attach_criterion(self, criterion="intensity"):
        if criterion == "intensity":
            return IntensityAttachCriterion(self.intensity_threshold)
        else:  # silero_vad
            return SileroVADAttachCriterion()

    def is_audio_length(self, audio: List[int], seconds: float) -> bool:
        return len(audio) >= seconds * self.sample_rate

    def _reset_audio_buffers(self, clear_chunk_queue=False):
        if clear_chunk_queue:
            self.node.chunk_queue = Queue()
        self.audio = []
        self.check_audio = []
        self.previous_chunk = []


# ------------------------------ main ------------------------------
def main(args=None):
    rclpy.init(args=args)
    node = AssistantHelperLifecycleNode()

    executor = MultiThreadedExecutor(num_threads=4)
    executor.add_node(node)
    try:
        executor.spin()
    finally:
        executor.shutdown()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()
