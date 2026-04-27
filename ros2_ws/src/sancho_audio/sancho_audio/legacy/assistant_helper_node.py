import math
import time
import numpy as np
from queue import Queue
from enum import Enum

import rclpy
from rclpy.node import Node

from std_msgs.msg import String, Float32, Int16
from std_srvs.srv import SetBool
from sancho_interfaces.msg import ChunkMono
from sancho_interfaces.msg import QuestionTTS, FaceRecognitionArray, UserTranscription
from sancho_interfaces.srv import AskUser
from sancho_interfaces.srv import STT

from .utils.sound import play
from .utils.sounds import ACTIVATION_SOUND, TIME_OUT_SOUND

from .utils.silero_vad_attach_criterion import SileroVADAttachCriterion
from .utils.intensity_attach_criterion import IntensityAttachCriterion

class AUDIO_STATE(int, Enum):
    NO_AUDIO = -1
    SOME_AUDIO = 0
    END_AUDIO = 1

class HELPER_STATE(int, Enum):
    NAME = 0
    SPEAKING = 1
    COMMAND = 2
    ASKING = 3


class AssistantHelperNode(Node): # Poner una variable para esperar X chunks antes de decidir que ya ha terminado de hablar

    def __init__(self, assistant_helper: "AssistantHelper"):
        super().__init__("assistant_helper")

        self.assistant_helper = assistant_helper

        self.declare_parameter("active", True)
        self.is_active = bool(self.get_parameter("active").value)

        self.face_recog_list = []
        self.audio_doa_list = []
        
        self.chunk_queue = Queue()
        self.question_queue = Queue()

        self.face_mode_pub = self.create_publisher(String, "face/mode", 10)
        self.assistant_text_pub = self.create_publisher(UserTranscription, 'sancho_audio/assistant_helper/transcription', 10)
        self.question_tts_pub = self.create_publisher(QuestionTTS, 'question_tts', 10)

        self.micro_sub = self.create_subscription(ChunkMono, 'sancho_audio/microphone/mono', self.microphone_callback, 10)
        self.mode_sub = self.create_subscription(Int16, 'sancho_audio/assistant_helper/mode', self.mode_callback, 10)
        self.face_recog_sub = self.create_subscription(FaceRecognitionArray, 'face_recognitions', self.face_recog_callback, 10)
        self.audio_doa_sub = self.create_subscription(Float32, 'sancho_audio/doa', self.audio_doa_callback, 10)

        self.stt_client = self.create_client(STT, 'sancho_hri/speech/stt')
        while not self.stt_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('STT service not available, waiting again...')
        
        self.ask_user_srv = self.create_service(AskUser, 'sancho_audio/ask_user', self.ask_user_service)
        self.set_active_srv = self.create_service(SetBool, 'sancho_audio/assistant_helper/set_active', self.set_active_service)

        self.get_logger().info("Assistant Helper Node initializated succesfully.")

    def microphone_callback(self, msg):
        if not self.is_active:
            return
        
        new_audio = list([np.int16(x) for x in msg.chunk_mono])
        sample_rate = msg.sample_rate
        
        self.chunk_queue.put([new_audio, sample_rate])
    
    def mode_callback(self, msg):
        if not self.is_active:
            return
        
        new_helper_state = msg.data

        if new_helper_state in [e.value for e in HELPER_STATE]:
            self.assistant_helper.helper_state = HELPER_STATE(new_helper_state)
            self.assistant_helper.transcription_sent = False

            self.get_logger().info(f"Helper state changed to: {self.assistant_helper.helper_state.name}")
        else:
            self.get_logger().info(f"Invalid helper state mode: {new_helper_state}")

    def face_recog_callback(self, msg):
        if not self.is_active:
            return
        
        if self.assistant_helper.audio_state != AUDIO_STATE.NO_AUDIO:
            self.face_recog_list.append(msg) # Timestamp en header

    def audio_doa_callback(self, msg):
        if not self.is_active:
            return
        
        if self.assistant_helper.audio_state != AUDIO_STATE.NO_AUDIO:
            self.audio_doa_list.append(msg) # Habria que poner el timestamp de cuando se recibio el chunk

    def ask_user_service(self, request, response):
        if not self.is_active:
            response.accepted = False
            return response
        
        self.question_queue.put([request.question_id, request.args_json])

        response.accepted = True

        return response
    
    def set_active_service(self, request, response):
        self.is_active = request.data
        self.get_logger().info(f">>> ESTADO DE ASSISTANT HELPER CAMBIADO A {self.is_active}")

        response.success = True

        return response


class AssistantHelper:

    def __init__(self, name="Sancho"):
        self.name = name

        self.audio_state = AUDIO_STATE.NO_AUDIO
        self.helper_state = HELPER_STATE.NAME
        self.transcription_sent = False

        self.sample_rate = -1 # Will set on mic callbacks
        self.helper_chunk_size = 0.5
        self.intensity_threshold = 900
        self.timeout_seconds = 5

        self.hotword_detection_time = 0

        self.audio = []
        self.check_audio = []
        self.previous_chunk = []

        self.hotword_detector = self._init_hotword_detector()
        self.chunk_attach_criterion = self._init_chunk_attach_criterion()
        
        self.node = AssistantHelperNode(self)

    def spin(self):
        while True:
            self.node.get_logger().debug(f"Helper State: {self.helper_state.name}, Audio State: {self.audio_state.name}")
            if not self.node.is_active:
                pass

            while not self.node.chunk_queue.empty(): # Combine audio chunks
                [new_audio, self.sample_rate] = self.node.chunk_queue.get()

                if self.transcription_sent:
                    pass

                elif self.helper_state == HELPER_STATE.NAME: # Si NAME mode
                    if not self.node.question_queue.empty():
                        [question_id, args] = self.node.question_queue.get()
                        self.process_question(question_id, args)
                    else:
                        self.detect_hotword(new_audio)

                elif self.helper_state in [HELPER_STATE.COMMAND, HELPER_STATE.ASKING]: # Si COMMAND o ASKING mode
                    self.build_audio_command(new_audio)

            rclpy.spin_once(self.node)

    def process_question(self, question_id, args_json):
        self.node.question_tts_pub.publish(QuestionTTS(question_id=question_id, args_json=args_json))
        self.helper_state = HELPER_STATE.SPEAKING

    def detect_hotword(self, new_audio): 
        if self.hotword_detector.detect(new_audio, self.sample_rate):
            self.node.face_mode_pub.publish(String(data="listening"))
            self.helper_state = HELPER_STATE.COMMAND

            self.hotword_detection_time = time.time()

            self.node.get_logger().info(f"✅✅✅ '{self.name.upper()}' DETECTED")

            play(ACTIVATION_SOUND, wait_for_end=True)

            self.node.chunk_queue = Queue()
            self.audio = []
            self.audio_chunk = []
            self.previous_chunk = []

    def build_audio_command(self, new_audio):
        self.check_audio = self.check_audio + new_audio
        
        if self.helper_state != HELPER_STATE.ASKING and len(self.audio) == 0 and time.time() - self.hotword_detection_time > self.timeout_seconds: # Si timeout, vuelve a idle
            self.node.face_mode_pub.publish(String(data="idle"))
            self.helper_state = HELPER_STATE.NAME
            
            play(TIME_OUT_SOUND, wait_for_end=True)
            self.node.get_logger().info(f"No audio command detected for {self.timeout_seconds} seconds, timeout.")

        elif self.is_audio_length(self.check_audio, self.helper_chunk_size):
            if self.chunk_attach_criterion.should_attach_chunk(self.check_audio, self.sample_rate):
                if self.audio_state == AUDIO_STATE.NO_AUDIO: # Por si es en END, no pase a SOME
                    self.audio_state = AUDIO_STATE.SOME_AUDIO

                if len(self.audio) == 0: # Si intensidad por primera vez, metemos chunk previo
                    self.audio = self.previous_chunk 

                self.audio = self.audio + self.check_audio # Luego el trozo nuevo
                self.node.get_logger().info(f"Chunk attached ({len(self.audio) / self.sample_rate}s)")
            elif self.audio_state != AUDIO_STATE.NO_AUDIO: # Si no hay intensidad y hay audio, terminamos trozo
                self.audio_state = AUDIO_STATE.END_AUDIO

                self.audio = self.audio + self.check_audio # Para que no se corte el audio, metemos tmb este ultimo
                self.node.get_logger().info("No more audio detected. Closing chunk window")
            else: # Si no hay intensidad ni audio, pues aun no hay audio
                self.node.get_logger().info("Listening for command but no audio detected yet")

            self.previous_chunk = self.check_audio
            self.check_audio = []

        if self.audio_state == AUDIO_STATE.END_AUDIO:
            self.process_audio_command(self.audio)
            
            self.audio = []
            self.check_audio = []
            self.audio_state = AUDIO_STATE.NO_AUDIO

            self.node.chunk_queue = Queue() # Limpiar lo que se ha acumulado mientras hace STT, mejor que que procese lo acumulado

    def process_audio_command(self, audio):
        self.node.get_logger().info(f"Transcribing {len(self.audio) / self.sample_rate}s chunk...")
        rec = self.stt_request(list(map(int, audio)), self.sample_rate)   
                     
        if rec:
            if rec.lower().strip() == self.name.lower(): # Si escucha Sancho otra vez, reinicia el timer y eso
                self.hotword_detection_time = time.time()

                play(ACTIVATION_SOUND)
                self.node.get_logger().info(f"✅✅✅ '{self.name.upper()}' DETECTED AGAIN")
            else: # Enviar transcripción al nodo assistant
                id, name = self.determine_user(self.node.face_recog_list, self.node.audio_doa_list)
                self.node.get_logger().info(f"📖📖📖 USUARIO IDENTIFICADO: {id}-{name}")

                self.node.assistant_text_pub.publish(UserTranscription(text=rec, id=id, name=name))
                self.node.get_logger().info(f"✅✅✅ Text transcribed ({len(audio) / self.sample_rate}s): {rec}")

                self.transcription_sent = True
                self.node.face_recog_list = []
                self.node.audio_doa_list = []                
        else:
            self.node.get_logger().info("Transcription result is empty.")

    def determine_user(self, face_recog_list, audio_doa_list): # Hacer trackeando la evolucion en el tiempo y todo eso, de momento esta a lo simple
        """Version simple que solo mira el ultmo, no tiene en cuenta que el hablante puede estar fuera de pantalla..."""
        
        DEFAULT = ("", "")
        if len(face_recog_list) <= 0:
            return DEFAULT

        last_face_recog = face_recog_list[-1]
        recognitions = last_face_recog.recognitions
        detections = last_face_recog.detections

        if len(recognitions) <= 0:
            return DEFAULT
        
        if len(recognitions) == 1:
            return recognitions[0].classified_id, recognitions[0].classified_name
    
        if not audio_doa_list:
            return DEFAULT

        last_audio_doa = audio_doa_list[-1]
        angle = last_audio_doa.data

        if angle is None or angle == float("nan"):
            return DEFAULT
        
        angle_x = self.calc_x_from_azimut(angle)
        
        best_recog, best_diff = None, float('inf')
        for recog, det in zip(recognitions, detections):
            det_center_x = det.corner.x + (det.width / 2)
           
            diff = abs(det_center_x - angle_x)
            if diff < best_diff:
                best_diff = diff
                best_recog = recog
        
        return best_recog.classified_id, best_recog.classified_name if best_recog else DEFAULT
        
    def calc_x_from_azimut(self, azimut_deg,  yaw_off=0.0, cx=939.37064, fx=1075.42921):
        theta = max(-89.9, min(89.9, float(azimut_deg) + yaw_off))
        return int(round(cx + fx * math.tan(math.radians(theta))))

    def stt_request(self, audio, sample_rate):
        stt_request = STT.Request()
        stt_request.audio = audio
        stt_request.sample_rate = sample_rate

        future_stt = self.node.stt_client.call_async(stt_request)
        rclpy.spin_until_future_complete(self.node, future_stt)
        result_stt = future_stt.result()

        return result_stt.text

    def _init_hotword_detector(self, hotword="openwakeword"):
        if hotword == "stt":
            from .utils.stt_hotword import STTHotword
            return STTHotword(self.stt_request, name=self.name)
        elif hotword == "pvporcupine":
            from .utils.pvporcupine_hotword import PVPorcupineHotword
            return PVPorcupineHotword()
        else: # openwakeword
            from .utils.openwakeword_hotword import OpenWakeWordHotword
            return OpenWakeWordHotword()
        
    def _init_chunk_attach_criterion(self, criterion="intensity"):
        if criterion == "intensity":
            return IntensityAttachCriterion(self.intensity_threshold)
        else: # silero_vad
            return SileroVADAttachCriterion()

    def is_audio_length(self, audio, seconds):
        return len(audio) >= seconds * self.sample_rate


def main(args=None):
    rclpy.init(args=args)

    assistant_helper = AssistantHelper()

    assistant_helper.spin()
    rclpy.shutdown()

if __name__ == '__main__':
    main()