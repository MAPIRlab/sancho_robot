import time
import json
import threading
import asyncio
import websockets
import sounddevice as sd
from concurrent.futures import ThreadPoolExecutor

import rclpy
from rclpy.node import Node
from rclpy.callback_groups import ReentrantCallbackGroup
from rclpy.executors import MultiThreadedExecutor

from std_msgs.msg import String
from sancho_lifecycle_utils.lifecycle_client import ManagedLifecycleClient
from sancho_interfaces.msg import ConversationTurn
from sancho_interfaces.srv import StartInteraction, EndInteraction
from sancho_interfaces.srv import TTS

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

        self.cb_group = ReentrantCallbackGroup()
        
        # --- NUEVO: Control de Concurrencia e Interrupciones ---
        # Un solo worker garantiza que Sancho piense y hable secuencialmente
        self.dialog_worker = ThreadPoolExecutor(max_workers=1)
        self._interrupt_flag = False

        # Publishers
        self.face_mode_pub = self.create_publisher(String, "face/mode", 10)
        self.log_pub = self.create_publisher(ConversationTurn, "conversation_log/add", 10)
        
        # Subscribers
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

    def on_speaker_update(self, msg: String):
        try:
            data = json.loads(msg.data)
            self.current_speaker_id = data.get("id", "0")
            self.current_speaker_name = data.get("name", "Unknown")
        except json.JSONDecodeError:
            self.get_logger().debug("Failed to decode speaker info JSON.")

    def on_transcription_received(self, msg: String):
        text = msg.data.strip()
        
        if not text:
            self.get_logger().info("No speech detected or timeout reached. Returning to idle state.")
            # Mandamos el error de transcripción a la cola también
            self.dialog_worker.submit(self._handle_empty_transcription)
            return

        self.get_logger().info(f"[USER -> SANCHO] {self.current_speaker_name}: {text}")
        self.face_mode_pub.publish(String(data="thinking"))

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
            
        return "Lo siento, ha habido un error al conectar con mi agente.", "sad"

    def play_tts(self, text, emotion="neutral", keep_asking=False):
        if self._interrupt_flag:
            return

        self.get_logger().info(f"[SANCHO -> USER] {text}")
        self.face_mode_pub.publish(String(data="speaking"))
        self.face_mode_pub.publish(String(data=emotion.lower())) 

        req = TTS.Request()
        req.text = text
        future = self.tts_client.call_async(req)
        
        # Bloqueo seguro: estamos en un hilo worker independiente
        event = threading.Event()
        future.add_done_callback(lambda _: event.set())
        event.wait()
        
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
            self.reset_to_idle()

    def reset_to_idle(self):
        self.face_mode_pub.publish(String(data="idle"))

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
        self.get_logger().info("Attention Manager ha delegado el control. Iniciando interacción...")
        
        # NUEVO: Si nos llaman, interrumpimos cualquier charla/proceso previo
        self._interrupt_flag = True
        
        names_list = request.user_names
        user_name = names_list[0] if names_list else "Desconocido"

        # Lanzamos el saludo inicial como una nueva tarea
        self._interrupt_flag = False
        self.dialog_worker.submit(self.play_tts, f"Hola {user_name}", "happy", True)

        response.success = True
        response.message = "Interacción aceptada."
        return response
    
    def end_interaction(self, reason="unknown"):
        self.get_logger().info(f"Terminando interacción. Motivo: {reason}")
        
        self._interrupt_flag = True
        self.transcriptor_lc.set_state(False)
        self.face_mode_pub.publish(String(data="idle"))

        req = EndInteraction.Request()
        req.reason = reason
        self.end_interaction_client.call_async(req)

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
        # Apagamos el worker al salir
        node.dialog_worker.shutdown(wait=False)
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()