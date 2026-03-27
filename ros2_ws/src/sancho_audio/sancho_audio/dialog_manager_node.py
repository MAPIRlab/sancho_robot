import time
import json
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
import requests
import threading
import sounddevice as sd
from enum import Enum
=======
import threading
import asyncio
import websockets
import sounddevice as sd
from concurrent.futures import ThreadPoolExecutor
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
from std_msgs.msg import String, Empty
from std_srvs.srv import SetBool
from sancho_interfaces.msg import ConversationTurn
from sancho_interfaces.srv import StartInteraction, EndInteraction, ForceAttention
from sancho_interfaces.srv import TTS

try:
    from .utils.sound import play
    from .utils.sounds import ACTIVATION_SOUND
except ImportError:
    pass

=======
from std_msgs.msg import String
from sancho_lifecycle_utils.lifecycle_client import ManagedLifecycleClient
from sancho_interfaces.msg import ConversationTurn
from sancho_interfaces.srv import StartInteraction, EndInteraction
from sancho_interfaces.srv import TTS

>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
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

        self.current_speaker_id = "0"
        self.current_speaker_name = "Unknown"
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        self.latest_doa_angle = 0.0
        self._waiting_for_attention = False

        self.cb_group = ReentrantCallbackGroup()
=======

        self.cb_group = ReentrantCallbackGroup()
        
        # --- NUEVO: Control de Concurrencia e Interrupciones ---
        # Un solo worker garantiza que Sancho piense y hable secuencialmente
        self.dialog_worker = ThreadPoolExecutor(max_workers=1)
        self._interrupt_flag = False
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py

        # Publishers
        self.face_mode_pub = self.create_publisher(String, "face/mode", 10)
        self.log_pub = self.create_publisher(ConversationTurn, "conversation_log/add", 10)
        
        # Subscribers
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        self.hotword_sub = self.create_subscription(Empty, "/voice_events/hotword_detected", self.on_hotword_detected, 10)
        self.transcription_sub = self.create_subscription(String, "/voice_events/user_transcription", self.on_transcription_received, 10)
        self.speaker_sub = self.create_subscription(String, "/active_speaker_info", self.on_speaker_update, 10)

        # Service Clients
        self.tts_client = self.create_client(TTS, 'sancho_hri/speech/tts', callback_group=self.cb_group)
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
=======
        self.transcription_sub = self.create_subscription(String, "/voice_events/user_transcription", self.on_transcription_received, 10, callback_group=self.cb_group)
        self.speaker_sub = self.create_subscription(String, "/active_speaker_info", self.on_speaker_update, 10, callback_group=self.cb_group)

        # Service Clients
        self.tts_client = self.create_client(TTS, 'sancho_hri/speech/tts', callback_group=self.cb_group)
        self.end_interaction_client = self.create_client(EndInteraction, '/attention_manager/interaction_finished', callback_group=self.cb_group)

        # Lifecycle Clients
        self.transcriptor_lc = ManagedLifecycleClient(self, self.transcriptor_node, self.cb_group)
        
        # Services
        self.start_interaction_srv = self.create_service(StartInteraction, '~/start_interaction', self.start_interaction_cb, callback_group=self.cb_group)
        
        self.reset_to_idle()
        self.get_logger().info(f"{self.get_name()} initialized")
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py

    def on_speaker_update(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.current_speaker_id = data.get("id", "0")
            self.current_speaker_name = data.get("name", "Unknown")
        except json.JSONDecodeError:
            self.get_logger().debug("Failed to decode speaker info JSON.")

<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
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
=======
    def on_transcription_received(self, msg: String):
        text = msg.data.strip()
        
        if not text:
            self.get_logger().info("No speech detected or timeout reached. Returning to idle state.")
            # Mandamos el error de transcripción a la cola también
            self.dialog_worker.submit(self._handle_empty_transcription)
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
            return

        self.get_logger().info(f"[USER -> SANCHO] {self.current_speaker_name}: {text}")
        self.face_mode_pub.publish(String(data="thinking"))

<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        threading.Thread(target=self.process_user_transcription, args=(text,), daemon=True).start()

    def process_user_transcription(self, user_text):
        ai_response, emotion = self.call_mapirbot(user_text)
        self.log_conversation(user_text, ai_response, emotion)

        self.play_tts(ai_response, emotion, keep_asking=True)

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
=======
        # NUEVO: Enviamos la tarea al ThreadPool en lugar de crear un hilo nuevo
        self._interrupt_flag = False
        self.dialog_worker.submit(self._process_turn_task, text)

    def _handle_empty_transcription(self):
        self.play_tts("Lo siento, no te he entendido")
        self.reset_to_idle()

    def _process_turn_task(self, user_text):
        if self._interrupt_flag:
            return

        self.get_logger().info("Llamando a Mapirbot...")
        ai_response, emotion = asyncio.run(self.call_mapirbot(user_text))
        
        if not self._interrupt_flag:
            self.log_conversation(user_text, ai_response, emotion)
            self.play_tts(ai_response, emotion, keep_asking=True)

    async def call_mapirbot(self, text):        
        try:
            # Ponemos un timeout de 10 segundos para no quedarnos bloqueados eternamente
            async with websockets.connect(self.mapirbot_url, open_timeout=5.0) as websocket:
                self.get_logger().info("Conectado con Mapirbot")
                await websocket.send(self.current_speaker_name + ": " + text)
                
                # Esperamos la respuesta con timeout
                #res = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                res = await websocket.recv()
                self.get_logger().info(f"Mensaje recibido: {res}")
                return res, "happy"
                
        except (websockets.exceptions.WebSocketException, ConnectionRefusedError) as e:
            self.get_logger().error(f"Error de conexión WebSocket: {e}")
        except asyncio.TimeoutError:
            self.get_logger().error("Timeout: Mapirbot tardó demasiado en responder.")
        except Exception as e:
            self.get_logger().error(f"Error inesperado en Mapirbot: {e}")
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
            
        return "Lo siento, ha habido un error al conectar con mi agente.", "sad"

    def play_tts(self, text, emotion="neutral", keep_asking=False):
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        self.get_logger().info(f"[SANCHO -> USER] {text}")
        
=======
        if self._interrupt_flag:
            return

        self.get_logger().info(f"[SANCHO -> USER] {text}")
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        self.face_mode_pub.publish(String(data="speaking"))
        self.face_mode_pub.publish(String(data=emotion.lower())) 

        req = TTS.Request()
        req.text = text
        future = self.tts_client.call_async(req)
        
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
=======
        # Bloqueo seguro: estamos en un hilo worker independiente
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        event = threading.Event()
        future.add_done_callback(lambda _: event.set())
        event.wait()
        
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
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
=======
        if future.result() and not self._interrupt_flag:
            audio = future.result().audio
            sample_rate = future.result().sample_rate
            
            # NUEVO: Reproducción no bloqueante e interrumpible
            duration = len(audio) / sample_rate
            start_time = time.time()
            
            sd.play(audio, samplerate=sample_rate)
            
            # Esperamos activamente chequeando si nos interrumpen
            while (time.time() - start_time) < duration:
                if self._interrupt_flag:
                    self.get_logger().info("Audio interrumpido abruptamente.")
                    sd.stop()
                    break
                time.sleep(0.05) # Chequeo a 20Hz

        if self._interrupt_flag:
            return # Salimos limpiamente si fuimos interrumpidos

        if keep_asking:
            self.face_mode_pub.publish(String(data="listening"))
            self.transcriptor_lc.set_state(True)
        else:
            self.end_interaction("turn_finished")
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
            self.reset_to_idle()

    def reset_to_idle(self):
        self.face_mode_pub.publish(String(data="idle"))
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        self.set_node_state(self.hotword_enable_client, True, self.hotword_node)
=======
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py

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

    # ------- Communication with Attention Manager -----------

    def start_interaction_cb(self, request, response):
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        self._waiting_for_attention = False # Cancelamos el watchdog si existía
=======
        self.get_logger().info("Attention Manager ha delegado el control. Iniciando interacción...")
        
        # NUEVO: Si nos llaman, interrumpimos cualquier charla/proceso previo
        self._interrupt_flag = True
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        
        names_list = request.user_names
        user_name = names_list[0] if names_list else "Desconocido"

<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        threading.Thread(target=self.play_tts, args=(f"Hola {user_name}", "happy", True), daemon=True).start()
=======
        # Lanzamos el saludo inicial como una nueva tarea
        self._interrupt_flag = False
        self.dialog_worker.submit(self.play_tts, f"Hola {user_name}", "happy", True)
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py

        response.success = True
        response.message = "Interacción aceptada."
        return response
    
    def end_interaction(self, reason="unknown"):
        self.get_logger().info(f"Terminando interacción. Motivo: {reason}")
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        self._waiting_for_attention = False

        # 1. Apagamos el micro (por si acaso) y encendemos escucha pasiva
        self.set_node_state(self.transcriptor_enable_client, False, self.transcriptor_node)
        self.set_node_state(self.hotword_enable_client, True, self.hotword_node)
        self.face_mode_pub.publish(String(data="idle"))

        # 2. Devolvemos el control al cuerpo
=======
        
        self._interrupt_flag = True
        self.transcriptor_lc.set_state(False)
        self.face_mode_pub.publish(String(data="idle"))

>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        req = EndInteraction.Request()
        req.reason = reason
        self.end_interaction_client.call_async(req)

<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py

=======
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
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
<<<<<<< HEAD:sancho_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
=======
        # Apagamos el worker al salir
        node.dialog_worker.shutdown(wait=False)
>>>>>>> refactor:ros2_ws/src/sancho_audio/sancho_audio/dialog_manager_node.py
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()