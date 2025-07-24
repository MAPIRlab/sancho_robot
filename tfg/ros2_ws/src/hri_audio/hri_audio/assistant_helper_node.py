import time
import json
import numpy as np
from queue import Queue
from enum import Enum

import rclpy
from rclpy.node import Node

from std_msgs.msg import String
from hri_msgs.msg import ChunkMono
from speech_msgs.srv import STT

from .utils.sound import play
from .utils.sounds import ACTIVATION_SOUND, TIME_OUT_SOUND

from .utils import STTHotword, PVPorcupineHotword, IntensityAttachCriterion, SileroVADAttachCriterion


class AUDIO_STATE(int, Enum):
    NO_AUDIO = -1
    SOME_AUDIO = 0
    END_AUDIO = 1

class HELPER_STATE(int, Enum):
    NAME = 0
    SPEAKING = 1
    COMMAND = 2
    ASKING = 3


class AssistantHelperNode(Node):

    def __init__(self, assistant_helper: "AssistantHelper"):
        super().__init__("assistant_helper")

        self.assistant_helper = assistant_helper

        self.face_mode_pub = self.create_publisher(String, "face/mode", 10)
        self.assistant_text_pub = self.create_publisher(String, 'hri_audio/assistant_helper/transcription', 10)
        self.micro_sub = self.create_subscription(ChunkMono, 'hri_audio/microphone/mono', self.microphone_callback, 10)
        self.mode_sub = self.create_subscription(String, 'hri_audio/assistant_helper/mode', self.mode_callback, 10)

        self.stt_client = self.create_client(STT, 'speech_tools/stt')
        while not self.stt_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('STT service not available, waiting again...')
            
        self.chunk_queue = Queue()

        self.get_logger().info("Assistant Helper Node initializated succesfully.")

    def microphone_callback(self, msg):
        new_audio = list([np.int16(x) for x in msg.chunk_mono])
        sample_rate = msg.sample_rate
        
        self.chunk_queue.put([new_audio, sample_rate])
    
    def mode_callback(self, msg):
        for i in range(10):
            self.get_logger().info(f"RECIBIDO EN EL CAMBIAR MODO: {msg.data}")
        data = json.loads(msg.data)
        helper_state = data["helper_state"]

        if helper_state in [e.value for e in HELPER_STATE]:
            self.assistant_helper.transcription_sent = False
            self.assistant_helper.helper_state = HELPER_STATE(helper_state)
            state_name = HELPER_STATE(helper_state).name
            self.get_logger().info(f"Helper state changed to: {state_name}")

            if self.assistant_helper.helper_state == HELPER_STATE.ASKING:
                asking_mode = data["asking_mode"]

                self.assistant_helper.asking_mode = asking_mode
                self.get_logger().info(f"With asking mode: {asking_mode}")
            else:
                self.assistant_helper.asking_mode = None
        else:
            self.get_logger().info(f"Invalid helper state mode: {helper_state}")
            self.assistant_helper.asking_mode = None


class AssistantHelper:

    def __init__(self, name="Sancho"):
        self.name = name

        self.audio_state = AUDIO_STATE.NO_AUDIO
        self.helper_state = HELPER_STATE.NAME
        self.asking_mode = None
        self.transcription_sent = False

        self.sample_rate = -1 # Will set on mic callbacks
        self.helper_chunk_size = 0.5
        self.intensity_threshold = 1400
        self.timeout_seconds = 5

        self.hotword_detection_time = 0

        self.audio = []
        self.check_audio = []
        self.previous_chunk = []

        #self.hotword_detector = STTHotword(self.stt_request, name=name)
        self.hotword_detector = PVPorcupineHotword()
        self.chunk_attach_criterion = IntensityAttachCriterion(self.intensity_threshold)
        #self.chunk_attach_criterion = SileroVADAttachCriterion()
        
        self.node = AssistantHelperNode(self)

    def spin(self):
        while rclpy.ok():
            if not self.node.chunk_queue.empty(): # Combine audio chunks
                [new_audio, self.sample_rate] = self.node.chunk_queue.get()

                if self.transcription_sent:
                    pass

                elif self.helper_state == HELPER_STATE.NAME: # Si NAME mode
                    self.process_name_mode(new_audio)

                elif self.helper_state in [HELPER_STATE.COMMAND, HELPER_STATE.ASKING]: # Si COMMAND mode
                    self.process_command_mode(new_audio)

            rclpy.spin_once(self.node)

    def process_name_mode(self, new_audio): 
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

    def process_command_mode(self, new_audio):
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
            else:
                self.node.assistant_text_pub.publish(String(data=json.dumps({
                    "text": rec,
                    **({"asking_mode": self.asking_mode} if self.asking_mode else {})
                })))
                self.transcription_sent = True
                
                self.node.get_logger().info(f"✅✅✅ Text transcribed ({len(audio) / self.sample_rate}s): {rec}")
        else:
            self.node.get_logger().info("Transcription result is empty.")

    def stt_request(self, audio, sample_rate):
        stt_request = STT.Request()
        stt_request.audio = audio
        stt_request.sample_rate = sample_rate

        future_stt = self.node.stt_client.call_async(stt_request)
        rclpy.spin_until_future_complete(self.node, future_stt)
        result_stt = future_stt.result()

        return result_stt.text
    
    def is_audio_length(self, audio, seconds):
        return len(audio) >= seconds * self.sample_rate


def main(args=None):
    rclpy.init(args=args)

    assistant_helper = AssistantHelper()

    assistant_helper.spin()
    rclpy.shutdown()