import json
import time
import rclpy
import sounddevice as sd
from rclpy.node import Node
import requests

from enum import Enum
from queue import Queue

from std_msgs.msg import String, Int16, Bool, Empty
from std_srvs.srv import SetBool
from sancho_interfaces.srv import SanchoPrompt, TriggerUserInteraction
from sancho_interfaces.msg import InputTTS, QuestionTTS, UserTranscription, ConversationTurn
from sancho_interfaces.srv import GreetPeople
from sancho_interfaces.srv import TTS

from sancho_audio.assistant_helper_node import HELPER_STATE
from sancho_hri.ai.sancho_ai_node import MODE
from sancho_hri.ai.prompts.commands import COMMANDS

from lifecycle_msgs.srv import ChangeState, GetAvailableTransitions


def try_json_loads(text):
    try:
        return json.loads(text)
    except Exception:
        return None

class QUESTION(int, Enum):
    NO_QUESTION = 0
    GET_NAME = 1
    CONFIRM_NAME = 2


class AssistantNode(Node):

    def __init__(self, assistant: "Assistant"):
        super().__init__("assistant")

        self.assistant = assistant

        self.face_mode_pub = self.create_publisher(String, "face/mode", 10)
        self.helper_mode_pub = self.create_publisher(Int16, 'sancho_audio/assistant_helper/mode', 10)
        self.name_answer_pub = self.create_publisher(String, "/gui/name_answer", 10)
        self.confirm_name_pub = self.create_publisher(Bool, "/gui/confirm_name", 10)
        
        self.text_sub = self.create_subscription(UserTranscription, 'sancho_audio/assistant_helper/transcription', self.text_callback, 10)
        self.input_tts_sub = self.create_subscription(InputTTS, 'input_tts', self.tts_callback, 10)
        self.question_tts_sub = self.create_subscription(QuestionTTS, 'question_tts', self.question_callback, 10)
        self.cancel_question_sub = self.create_subscription(Empty, 'assistant/cancel_question', self.cancel_question_callback, 10)

        self.log_pub = self.create_publisher(ConversationTurn, "conversation_log/add", 10)

        self.sancho_greet_people_srv = self.create_service(GreetPeople, 'assistant/greet_people', self.sancho_greet_people_service)

        self.sancho_prompt_client = self.create_client(SanchoPrompt, "sancho_hri/llm/prompt")
        #while not self.sancho_prompt_client.wait_for_service(timeout_sec=1.0):
        self.get_logger().warning("Sancho Prompt Service not available, waiting...")

        self.tts_client = self.create_client(TTS, 'sancho_hri/speech/tts')
        #while not self.tts_client.wait_for_service(timeout_sec=1.0):
        self.get_logger().info('TTS service not available, waiting again...')

        self.gui_client = self.create_client(TriggerUserInteraction, 'gui/request')
        #while not self.gui_client.wait_for_service(timeout_sec=1.0):
        #    self.get_logger().info('GUI service not available, waiting again...')
        
        self.queue = Queue(maxsize=1)
        self.tts_queue = Queue(maxsize=1)
        self.question_queue = Queue()
        self.greet_queue = Queue(maxsize=1)

        self.declare_parameter("mapirbot_url", "https://alt-gone-ent-pensions.trycloudflare.com/ask")
        
        self.get_logger().info("Assistant Node initializated succesfully.")

    def text_callback(self, msg):
        if self.queue.qsize() < 1:
            self.queue.put([msg.text, msg.id, msg.name])

    def tts_callback(self, msg):
        if self.tts_queue.qsize() < 1:
            self.tts_queue.put([msg.text, msg.emotion])

    def question_callback(self, msg):
        self.question_queue.put([msg.question_id, json.loads(msg.args_json) if msg.args_json else {}])

    def cancel_question_callback(self, msg):
        self.assistant.cancel_question()

    def sancho_greet_people_service(self, request, response):
        if self.greet_queue.qsize() < 1:
            self.greet_queue.put([request.ids, request.names])
            response.accepted = True
        else:
            response.accepted = False

        return response


class Assistant:

    def __init__(self):
        self.node = AssistantNode(self)

        self.question_id = QUESTION.NO_QUESTION
        

    def spin(self):
        while rclpy.ok():
            if not self.node.queue.empty():
                [text, user_id, user_name] = self.node.queue.get()

                self.process_user_transcription(text, user_id, user_name)

            if not self.node.tts_queue.empty():
                [text, emotion] = self.node.tts_queue.get()

                self.play_tts(text, emotion=emotion)

            if not self.node.question_queue.empty():
                [self.question_id, args] = self.node.question_queue.get()

                text = self.create_question_text(self.question_id, args)
                self.play_tts(text, emotion="neutral", keep_asking=True)

            if not self.node.greet_queue.empty():
                [ids, names] = self.node.greet_queue.get()

                self.sancho_greet_people(ids, names)

            rclpy.spin_once(self.node)

    def call_mapirbot(self, text, user_id, user_name):
        """
        Call Mapirbot to get a response.

        Args:
            text (str): Text to send to Mapirbot.
            user_id (str): User ID.
            user_name (str): User name.
        
        Returns:
            tuple: (text, emotion)
        """
        # TODO: Change thread_id to a dynamic value
        url = self.node.get_parameter("mapirbot_url").get_parameter_value().string_value
        payload = {
            "query": text,
            "thread_id": user_id if user_id and user_id != "Unknown" else "Mapirbot_thread"
        }
        headers = {"Content-Type": "application/json"}
        
        try:
            response = requests.post(url, data=json.dumps(payload), headers=headers, timeout=1000)
            if response.status_code == 200:
                data = response.json()
                self.node.get_logger().info(f"[INFO] Respuesta de Mapirbot: {data}")
                if isinstance(data, dict):
                    text = data.get("response", str(data))
                    emotion = data.get("emotion", "happy")
                else:
                    text = str(data)
                    emotion = "happy"
                
                return text, emotion
            else:
                self.node.get_logger().error(f"[ERROR] Error de Mapirbot: {response.status_code}")
                return "Perdona, mi conexión con el agente remoto ha fallado.", "sad"
        except Exception as e:
            self.node.get_logger().error(f"[ERROR] Excepción llamando a Mapirbot: {e}")
            return "Lo siento, ha habido un error al conectar con mi agente.", "sad"
    
    def log_conversation(self, user_text, assistant_text, user_id, user_name, emotion):
        """
        Log a conversation turn.

        Args:
            user_text (str): Text from the user.
            assistant_text (str): Text from the assistant.
            user_id (str): User ID.
            user_name (str): User name.
            emotion (str): Emotion of the assistant.
        """
        # TODO: Change chat_id to a dynamic value
        turn = ConversationTurn()
        turn.chat_id = "0"
        turn.user_timestamp = time.time()
        turn.user_id = user_id or "Unknown"
        turn.user_name = user_name or "Usuario"
        turn.user_text = user_text
        turn.assistant_timestamp = time.time()
        turn.assistant_text = assistant_text
        turn.assistant_provider = "mapirbot"
        turn.assistant_model = "mapirbot"
        turn.assistant_value_json = json.dumps({"emotion": emotion})
        self.node.log_pub.publish(turn)
        

    def process_user_transcription(self, text, user_id, user_name):
        self.node.get_logger().info(f"{user_name or 'Desconocido'} dice: {text}")
        self.node.face_mode_pub.publish(String(data="thinking"))

        #if self.question_id == QUESTION.NO_QUESTION: # Si es un mensaje normal
        #    ai_response, emotion, data, intent = self.sancho_prompt_request(text, user_id, user_name)

        #    if intent == COMMANDS.TAKE_PICTURE:
        #        data_json = json.dumps(data)
        #        self.gui_request("show_photo", data_json) # Show photo

        #    self.play_tts(ai_response, emotion=emotion)

        
        if self.question_id == QUESTION.NO_QUESTION: # Si es un mensaje normal
            #if not user_id or user_id == "Unknown":
            #    # If we don't know the user, Mapirbot generates the question "who are you"
            #    ai_response, emotion = self.call_mapirbot(text, user_id, user_name)
            #    self.play_tts(ai_response, emotion=emotion, keep_asking=True)
            #    self.question_id = QUESTION.GET_NAME
            #    self.log_conversation(text, ai_response, user_id, user_name, emotion)
            #else:
            ai_response, emotion = self.call_mapirbot(text, user_id, user_name)
            self.play_tts(ai_response, emotion=emotion)
            self.log_conversation(text, ai_response, user_id, user_name, emotion)

        elif self.question_id == QUESTION.GET_NAME: # Si es la respuesta cual es tu nombre
            name_said, name = self.sancho_get_name_request(text)
            if name_said:
                self.node.name_answer_pub.publish(String(data=name))
                self.node.helper_mode_pub.publish(Int16(data=HELPER_STATE.NAME.value))
                self.node.face_mode_pub.publish(String(data="idle"))
            else:
                self.play_tts("¿Podrías repetirlo? No he reconocido que hayas dicho ningún nombre.", "sad", keep_asking=True)

        elif self.question_id == QUESTION.CONFIRM_NAME: # Si es la respuesta a confirmar nombre
            answer_said, answer = self.sancho_confirm_name_request(text)
            if answer_said:
                self.node.confirm_name_pub.publish(Bool(data=answer))
                self.node.helper_mode_pub.publish(Int16(data=HELPER_STATE.NAME.value))
                self.node.face_mode_pub.publish(String(data="idle"))
            else:
                self.play_tts("No te he entendido bien. ¿Podrías repetirlo?", "sad", keep_asking=True)

    def sancho_greet_people(self, ids, names): # Cuando Sancho busca a un grupo y los ve y se prepara para decirles algo, aqui se dice ese algo
        # Usamos Mapirbot para generar el saludo
        greet_text = f"Saluda a estas personas: {', '.join(names)}" if names else "Saluda a alguien que acabas de ver pero no conoces."
        text, emotion = self.call_mapirbot(greet_text, "0", "Varios")
        
        self.play_tts(text, emotion=emotion)

        self._activate_lifecycle_node("assistant_helper") # Activar assistant helper
        self._activate_lifecycle_node("face_manager") # Activar human face manager

    def sancho_prompt_greet_request(self, args_json, mode):
        sancho_prompt_request = SanchoPrompt.Request()
        sancho_prompt_request.args_json = args_json
        sancho_prompt_request.mode = mode

        future_sancho_prompt = self.node.sancho_prompt_client.call_async(sancho_prompt_request)
        
        rclpy.spin_until_future_complete(self.node, future_sancho_prompt)
        result_sancho_prompt = future_sancho_prompt.result()

        value = json.loads(result_sancho_prompt.value_json)

        response = value["response"]

        return response

    def sancho_prompt_request(self, text, id, name):
        sancho_prompt_request = SanchoPrompt.Request()
        sancho_prompt_request.chat_id = "0" # Dejarlo vacio y que con un servicio se pueda cambiar y decidir dinamicamente cuando iniciar nuevo chat
        sancho_prompt_request.text = text
        sancho_prompt_request.args_json = json.dumps({ "user_id": id, "user_name": name })
        sancho_prompt_request.mode = MODE.NORMAL.value

        future_sancho_prompt = self.node.sancho_prompt_client.call_async(sancho_prompt_request)
        rclpy.spin_until_future_complete(self.node, future_sancho_prompt)
        result_sancho_prompt = future_sancho_prompt.result()

        value = json.loads(result_sancho_prompt.value_json)

        text = value["text"]
        emotion = value["emotion"]
        data = value["data"]

        return text, emotion, data, result_sancho_prompt.intent

    def sancho_get_name_request(self, text):
        sancho_prompt_request = SanchoPrompt.Request()
        sancho_prompt_request.text = text
        sancho_prompt_request.mode = MODE.GET_NAME.value

        future_sancho_prompt = self.node.sancho_prompt_client.call_async(sancho_prompt_request)
        rclpy.spin_until_future_complete(self.node, future_sancho_prompt)
        result_sancho_prompt = future_sancho_prompt.result()

        value = json.loads(result_sancho_prompt.value_json)

        name_said = bool(value["name_said"])
        name = value["name"]

        return name_said, name
    
    def sancho_confirm_name_request(self, text):
        sancho_prompt_request = SanchoPrompt.Request()
        sancho_prompt_request.text = text
        sancho_prompt_request.mode = MODE.CONFIRM_NAME.value

        future_sancho_prompt = self.node.sancho_prompt_client.call_async(sancho_prompt_request)
        rclpy.spin_until_future_complete(self.node, future_sancho_prompt)
        result_sancho_prompt = future_sancho_prompt.result()

        value = json.loads(result_sancho_prompt.value_json)

        answer_said = bool(value["answer_said"])
        answer = True if value["answer"] == "yes" else False

        return answer_said, answer

    def tts_request(self, text):
        tts_request = TTS.Request()
        tts_request.text = text

        future_tts = self.node.tts_client.call_async(tts_request)
        rclpy.spin_until_future_complete(self.node, future_tts)
        result_tts = future_tts.result()

        return result_tts.audio, result_tts.sample_rate

    def gui_request(self, mode, data_json):
        if not self.node.gui_client.service_is_ready():
            self.node.get_logger().error("ERROR: GUI SERVICE IS NOT AVAILABLE")
            return
        
        req = TriggerUserInteraction.Request()
        req.mode = mode
        req.data_json = data_json

        future = self.node.gui_client.call_async(req)
        rclpy.spin_until_future_complete(self.node, future)
        result = future.result()

        return result.accepted

    def play_tts(self, text, emotion="neutral", keep_asking=False, wait=True):
        self.node.face_mode_pub.publish(String(data="speaking")) # Mouth speaking
        self.node.face_mode_pub.publish(String(data=emotion.lower())) # Mouth color
        self.node.helper_mode_pub.publish(Int16(data=HELPER_STATE.SPEAKING.value)) # Speaking mode
        
        audio, sample_rate = self.tts_request(text)
        
        sd.play(audio, samplerate=sample_rate)
        self.node.get_logger().info(f"✅✅✅ Sancho dice por audio: {text}")

        if wait:
            sd.wait()

        face_mode = "listening" if keep_asking else "idle"
        helper_mode = HELPER_STATE.ASKING if keep_asking else HELPER_STATE.NAME 
        self.question_id = self.question_id if keep_asking else QUESTION.NO_QUESTION
        
        self.node.face_mode_pub.publish(String(data=face_mode)) # Mouth mode
        self.node.get_logger().info(f"Cambiando estado del helper a: {helper_mode.name}")
        self.node.helper_mode_pub.publish(Int16(data=helper_mode.value)) # Helper mode

    def _get_available_transition_id(self, node_name: str, label: str):
        cli_get = self.node.create_client(GetAvailableTransitions, f'/{node_name}/get_available_transitions')
        if not cli_get.wait_for_service(timeout_sec=1.0):
            self.node.get_logger().debug(f'[{node_name}] get_available_transitions no está listo.')
            return None

        req = GetAvailableTransitions.Request()
        fut = cli_get.call_async(req)
        rclpy.spin_until_future_complete(self.node, fut)
        resp = fut.result()
        if not resp:
            return None

        for t in resp.available_transitions:
            if t.transition.label.lower() == label.lower():
                return t.transition.id
        return None

    def _change_state(self, node_name: str, transition_id: int) -> bool:
        cli_chg = self.node.create_client(ChangeState, f'/{node_name}/change_state')
        if not cli_chg.wait_for_service(timeout_sec=1.0):
            self.node.get_logger().warn(f'[{node_name}] change_state no está listo.')
            return False

        req = ChangeState.Request()
        req.transition.id = transition_id
        fut = cli_chg.call_async(req)
        rclpy.spin_until_future_complete(self.node, fut)
        resp = fut.result()
        return bool(resp and resp.success)

    def _activate_lifecycle_node(self, node_name: str, attempts: int = 10, sleep_s: float = 0.3):
        self.node.get_logger().info(f'Intentando ACTIVAR lifecycle node "{node_name}"...')

        for _ in range(attempts): # Intentar CONFIGURE si está disponible
            cfg_id = self._get_available_transition_id(node_name, "configure")
            if cfg_id is None:
                break  # Puede que ya esté configurado; pasamos a activar
            if self._change_state(node_name, cfg_id):
                self.node.get_logger().info(f'[{node_name}] CONFIGURADO correctamente.')
                break
            time.sleep(sleep_s)

        for _ in range(attempts): # Intentar ACTIVATE
            act_id = self._get_available_transition_id(node_name, "activate")
            if act_id is None:
                time.sleep(sleep_s)
                continue
            if self._change_state(node_name, act_id):
                self.node.get_logger().info(f'[{node_name}] ✅ ACTIVADO correctamente.')
                return True
            time.sleep(sleep_s)

        self.node.get_logger().error(f'[{node_name}] No se pudo activar después de los intentos.')
        return False

    def cancel_question(self):
        self.question_id = QUESTION.NO_QUESTION

        self.node.face_mode_pub.publish(String(data="idle"))
        self.node.helper_mode_pub.publish(Int16(data=HELPER_STATE.NAME.value))

    def create_question_text(self, question_id, args): # Hacer con templates mejor por variedad y demas. LLM meteria mas delay
        if question_id == QUESTION.GET_NAME:
            return "¿Cual es tu nombre?"
        elif question_id == QUESTION.CONFIRM_NAME:
            return f"Creo que eres {args['name']}, ¿es cierto?"
        else:
            raise ValueError(f"Question id {question_id} is not valid.")


def main(args=None):
    rclpy.init(args=args)

    assistant = Assistant()

    assistant.spin()
    rclpy.shutdown()
