import time
import json
import requests
import threading
import sounddevice as sd
from enum import Enum

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String, Empty
from std_srvs.srv import SetBool
from sancho_msgs.msg import ConversationTurn
from sancho_msgs.srv import StartInteraction, EndInteraction, ForceAttention
from speech_msgs.srv import TTS

try:
    from .utils.sound import play
    from .utils.sounds import ACTIVATION_SOUND
except ImportError:
    pass

class QuestionState(int, Enum):
    NO_QUESTION = 0
    GET_NAME = 1
    CONFIRM_NAME = 2

class DialogManagerNode(Node):
    """
    Core brain of the Sancho robot. 
    Orchestrates the audio nodes, processes text via the LLM (Mapirbot),
    manages the conversation state, and executes Text-to-Speech (TTS) actions.
    """
    def __init__(self):
        super().__init__("dialog_manager")

        self.declare_parameter("mapirbot_url", "https://experiments-suspension-predictions-mid.trycloudflare.com/ask")
        self.declare_parameter("hotword_node", "hotword_detector")
        self.declare_parameter("transcriptor_node", "vad_transcriptor")

        self.hotword_node = self.get_parameter("hotword_node").get_parameter_value().string_value
        self.transcriptor_node = self.get_parameter("transcriptor_node").get_parameter_value().string_value
        self.mapirbot_url = self.get_parameter("mapirbot_url").get_parameter_value().string_value

        self.question_state = QuestionState.NO_QUESTION
        self.current_speaker_id = "0"
        self.current_speaker_name = "Unknown"
        self.latest_doa_angle = 0.0
        self._waiting_for_attention = False

        self.cb_group = ReentrantCallbackGroup()

        # Publishers
        self.face_mode_pub = self.create_publisher(String, "face/mode", 10)
        self.log_pub = self.create_publisher(ConversationTurn, "conversation_log/add", 10)
        
        # Subscribers
        self.hotword_sub = self.create_subscription(Empty, "/voice_events/hotword_detected", self.on_hotword_detected, 10)
        self.transcription_sub = self.create_subscription(String, "/voice_events/user_transcription", self.on_transcription_received, 10)
        self.speaker_sub = self.create_subscription(String, "/active_speaker_info", self.on_speaker_update, 10)

        # Service Clients
        self.tts_client = self.create_client(TTS, 'speech_tools/tts', callback_group=self.cb_group)
        self.hotword_enable_client = self.create_client(SetBool, f'/{self.hotword_node}/enable_listening', callback_group=self.cb_group)
        self.transcriptor_enable_client = self.create_client(SetBool, f'/{self.transcriptor_node}/enable_recording', callback_group=self.cb_group)

        self.start_interaction_srv = self.create_service(StartInteraction, '~/start_interaction', self.start_interaction_cb, callback_group=self.cb_group)
        self.end_interaction_client = self.create_client(EndInteraction, '/attention_manager/interaction_finished', callback_group=self.cb_group)
        self.force_attention_client = self.create_client(ForceAttention, '/attention_manager/force_attention', callback_group=self.cb_group)

        self.get_logger().info(f"{self.get_name()} initialized. Setting up the auditory system...")
        threading.Thread(target=self.initial_setup, daemon=True).start()

    def initial_setup(self):
        """Sets the initial state: Transcription off, Hotword on."""
        self.set_node_state(self.transcriptor_enable_client, False, self.transcriptor_node)
        self.set_node_state(self.hotword_enable_client, True, self.hotword_node)
        
        self.face_mode_pub.publish(String(data="idle"))
        self.get_logger().info("System ready. Sancho is passively listening for the wake word.")

    def set_node_state(self, client, state: bool, node_name: str):
        """Helper to call the SetBool service synchronously inside threads."""
        if not client.wait_for_service(timeout_sec=3.0):
            self.get_logger().error(f"SetBool service for '{node_name}' is unavailable.")
            return False
            
        req = SetBool.Request()
        req.data = state
        future = client.call_async(req)
        
        event = threading.Event()
        future.add_done_callback(lambda _: event.set())
        event.wait()

        response = future.result()
        return response.success if response else False

    # ------- Communication with Attention Manager -----------
    def start_interaction_cb(self, request, response):
        self._waiting_for_attention = False # Cancelamos el watchdog si existía
        
        names_list = request.user_names
        user_name = names_list[0] if names_list else "Desconocido"

        threading.Thread(target=self.play_tts, args=(f"¡Hola {user_name}! Dime algo", "happy", True), daemon=True).start()

        response.success = True
        response.message = "Interacción aceptada."
        return response
    
    def end_interaction(self, reason="unknown"):
        self.get_logger().info(f"Terminando interacción. Motivo: {reason}")
        self._waiting_for_attention = False

        # 1. Apagamos el micro (por si acaso) y encendemos escucha pasiva
        self.set_node_state(self.transcriptor_enable_client, False, self.transcriptor_node)
        self.set_node_state(self.hotword_enable_client, True, self.hotword_node)
        self.face_mode_pub.publish(String(data="idle"))

        # 2. Devolvemos el control al cuerpo
        req = EndInteraction.Request()
        req.reason = reason
        self.end_interaction_client.call_async(req)
    # ------------------------------------------------------------------

    def on_speaker_update(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.current_speaker_id = data.get("id", "0")
            self.current_speaker_name = data.get("name", "Unknown")
        except json.JSONDecodeError:
            self.get_logger().debug("Failed to decode speaker info JSON.")

    def on_hotword_detected(self, msg: Empty):
        self.get_logger().info("Wake word detected! Activating attention...")
        self.face_mode_pub.publish(String(data="listening"))
        
        threading.Thread(target=self.play_sound_and_listen, daemon=True).start()

    def play_sound_and_listen(self):
        # Deactivate hotword detection
        self.set_node_state(self.hotword_enable_client, False, self.hotword_node)
        
        # Play sound and wait until it has finished
        try: 
            play(ACTIVATION_SOUND, wait_for_end=True) 
        except Exception as e: 
            self.get_logger().warn(f"Error reproduciendo sonido: {e}")
        
        # Activate transcription
        self.set_node_state(self.transcriptor_enable_client, True, self.transcriptor_node)

    def on_transcription_received(self, msg: String):
        text = msg.data.strip()
        # Nota: El nodo ASR ya se ha auto-apagado al enviar la transcripción.
        
        if not text:
            self.get_logger().info("No speech detected or timeout reached. Returning to idle state.")
            self.play_tts("Lo siento, no te he entendido")
            self.reset_to_idle()
            return

        self.get_logger().info(f"[USER -> SANCHO] {self.current_speaker_name}: {text}")
        self.face_mode_pub.publish(String(data="thinking"))

        threading.Thread(target=self.echo, args=(text,), daemon=True).start()

    def process_user_transcription(self, user_text):
        ai_response, emotion = self.call_mapirbot(user_text)
        self.log_conversation(user_text, ai_response, emotion)

        keep_asking = False
        if self.question_state == QuestionState.GET_NAME:
            keep_asking = False
            self.question_state = QuestionState.NO_QUESTION

        self.play_tts(ai_response, emotion, keep_asking)

    def echo(self, user_text):
        self.get_logger().info("Modo echo...")
        
        texto_minusculas = user_text.lower()
        
        # 1. Comprobamos si el usuario se quiere despedir
        if "adiós" in texto_minusculas or "hasta luego" in texto_minusculas or "terminar" in texto_minusculas:
            ai_response = f"¡Ayps!"
            emotion = "happy"
            end_conversation = True
            
        # 2. Si no se despide, hacemos de loro
        else:
            ai_response = user_text
            emotion = "neutral"
            end_conversation = False
            
        # Reproducimos la respuesta generada localmente
        self.play_tts(ai_response, emotion, keep_asking=(not end_conversation))

    def call_mapirbot(self, text):
        payload = {"query": text, "thread_id": self.current_speaker_id}
        headers = {"Content-Type": "application/json"}
        try:
            res = requests.post(self.mapirbot_url, data=json.dumps(payload), headers=headers, timeout=10)
            if res.status_code == 200:
                data = res.json()
                return data.get("response", str(data)), data.get("emotion", "happy")
            self.get_logger().error(f"Mapirbot returned status code: {res.status_code}")
        except requests.exceptions.RequestException as e:
            self.get_logger().error(f"Mapirbot connection error: {e}")
            
        return "Lo siento, ha habido un error al conectar con mi agente.", "sad"

    def play_tts(self, text, emotion="neutral", keep_asking=False):
        self.get_logger().info(f"[SANCHO -> USER] {text}")
        
        self.face_mode_pub.publish(String(data="speaking"))
        self.face_mode_pub.publish(String(data=emotion.lower())) 

        req = TTS.Request()
        req.text = text
        future = self.tts_client.call_async(req)
        
        event = threading.Event()
        future.add_done_callback(lambda _: event.set())
        event.wait()
        
        if future.result():
            audio = future.result().audio
            sample_rate = future.result().sample_rate
            sd.play(audio, samplerate=sample_rate)
            sd.wait() 

        if keep_asking:
            self.face_mode_pub.publish(String(data="listening"))
            self.set_node_state(self.transcriptor_enable_client, True, self.transcriptor_node)
        else:
            self.end_interaction()
            self.reset_to_idle()

    def reset_to_idle(self):
        self.face_mode_pub.publish(String(data="idle"))
        self.question_state = QuestionState.NO_QUESTION
        self.set_node_state(self.hotword_enable_client, True, self.hotword_node)

    def log_conversation(self, user_text, assistant_text, emotion):
        turn = ConversationTurn()
        turn.chat_id = "0"
        turn.user_timestamp = time.time()
        turn.user_id = self.current_speaker_id
        turn.user_name = self.current_speaker_name
        turn.user_text = user_text
        turn.assistant_timestamp = time.time()
        turn.assistant_text = assistant_text
        turn.assistant_provider = "mapirbot"
        turn.assistant_model = "mapirbot"
        turn.assistant_value_json = json.dumps({"emotion": emotion})
        
        self.log_pub.publish(turn)

def main(args=None):
    rclpy.init(args=args)
    node = DialogManagerNode()
    try:
        executor = MultiThreadedExecutor()
        executor.add_node(node)
        executor.spin()
    except KeyboardInterrupt:
        node.get_logger().info(f"{node.get_name()} shutting down manually...")
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()