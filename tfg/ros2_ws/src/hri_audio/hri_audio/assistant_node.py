import json
import rclpy
import sounddevice as sd
from rclpy.node import Node

from queue import Queue

from std_msgs.msg import String, Bool
from hri_msgs.srv import SanchoPrompt, TriggerUserInteraction
from speech_msgs.srv import TTS

from hri_audio.assistant_helper_node import HELPER_STATE
from sancho_ai.prompts.commands import COMMANDS


def try_json_loads(text):
    try:
        return json.loads(text)
    except Exception:
        return None


class AssistantNode(Node):

    def __init__(self):
        super().__init__("assistant")

        self.face_mode_pub = self.create_publisher(String, "face/mode", 10)
        self.helper_mode_pub = self.create_publisher(String, 'hri_audio/assistant_helper/mode', 10)
        self.name_answer_pub = self.create_publisher(String, "gui/name_answer", 10)
        self.confirm_name_pub = self.create_publisher(Bool, "gui/confirm_name", 10)

        self.text_sub = self.create_subscription(String, 'hri_audio/assistant_helper/transcription', self.text_callback, 10)
        self.tts_sub = self.create_subscription(String, 'input_tts', self.tts_callback, 10)

        self.sancho_prompt_client = self.create_client(SanchoPrompt, "sancho_ai/prompt")
        while not self.sancho_prompt_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().warning("Sancho Prompt Service not available, waiting...")

        self.tts_client = self.create_client(TTS, 'speech_tools/tts')
        while not self.tts_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('TTS service not available, waiting again...')

        self.gui_client = self.create_client(TriggerUserInteraction, 'gui/request')
        while not self.gui_client.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('GUI service not available, waiting again...')
        
        self.queue = Queue(maxsize=1)
        self.tts_queue = Queue(maxsize=1)

        self.get_logger().info("Assistant Node initializated succesfully.")

    def text_callback(self, msg):
        if self.queue.qsize() < 1:
            self.queue.put(msg.data)

    def tts_callback(self, msg):
        if self.tts_queue.qsize() < 1:
            self.tts_queue.put(msg.data)


class Assistant:

    def __init__(self):
        self.node = AssistantNode()
    
    def spin(self):
        while rclpy.ok():
            if not self.node.queue.empty():
                user_dict = json.loads(self.node.queue.get())
                user_text = user_dict["text"]
                asking_mode = user_dict.get("asking_mode", "")
                for i in range(10):
                    self.node.get_logger().info(f"MODO AL ASSISTANT: {asking_mode}")
                self.node.face_mode_pub.publish(String(data="thinking"))

                if not asking_mode: # Si es un mensaje normal
                    ai_response, emotion, data, intent = self.sancho_prompt_request(user_text)
                    self.node.get_logger().info(f"✅✅✅ Respuesta recibida '{ai_response}'")

                    if intent == COMMANDS.TAKE_PICTURE:
                        data_json = json.dumps(data)
                        self.gui_request("show_photo", data_json) # Show photo

                    self.play_tts(ai_response, emotion)

                elif asking_mode == "get_name": # Si es la respuesta cual es tu nombre
                    name_said, name = self.sancho_get_name_request(user_text)
                    if name_said:
                        self.node.name_answer_pub.publish(String(data=name))
                        self.node.helper_mode_pub.publish(String(data=json.dumps({
                            "helper_state": HELPER_STATE.NAME.value,
                            "asking_mode": ""
                        })))
                        self.node.face_mode_pub.publish(String(data="idle"))
                    else:
                        self.play_tts("¿Podrías repetirlo? No he reconocido que hayas dicho ningún nombre.", "sad", asking_mode=asking_mode)

                elif asking_mode == "confirm_name": # Si es la respuesta a confirmar nombre
                    answer_said, answer = self.sancho_confirm_name_request(user_text)
                    if answer_said:
                        self.node.confirm_name_pub.publish(Bool(data=answer))
                        self.node.helper_mode_pub.publish(String(data=json.dumps({
                            "helper_state": HELPER_STATE.NAME.value,
                            "asking_mode": ""
                        })))
                        self.node.face_mode_pub.publish(String(data="idle"))
                    else:
                        self.play_tts("No te he entendido bien. ¿Podrías repetirlo?", "sad", asking_mode=asking_mode)

            if not self.node.tts_queue.empty():
                tts_text = self.node.tts_queue.get()

                tts_dict = try_json_loads(tts_text)
                if tts_dict:
                    tts_text = tts_dict["text"]
                    asking_mode = tts_dict["asking_mode"]
                else:
                    asking_mode = ""

                self.play_tts(tts_text, "neutral", asking_mode=asking_mode)

            rclpy.spin_once(self.node)

    def sancho_prompt_request(self, text):
        sancho_prompt_request = SanchoPrompt.Request()
        sancho_prompt_request.chat_id = "0"
        sancho_prompt_request.text = text

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
        sancho_prompt_request.asking_mode = "get_name"

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
        sancho_prompt_request.asking_mode = "confirm_name"

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
        req = TriggerUserInteraction.Request()
        req.mode = mode
        req.data_json = data_json

        future = self.node.gui_client.call_async(req)
        rclpy.spin_until_future_complete(self.node, future)
        result = future.result()

        return result.accepted

    def play_tts(self, text, emotion, asking_mode="", wait=True):
        self.node.face_mode_pub.publish(String(data="speaking")) # Mouth speaking
        self.node.helper_mode_pub.publish(String(data=json.dumps({ "helper_state": HELPER_STATE.SPEAKING.value }))) # Speaking mode
        if emotion:
            self.node.face_mode_pub.publish(String(data=emotion.lower())) # Mouth color

        audio, sample_rate = self.tts_request(text)
        self.node.get_logger().info(f"✅✅✅ Reproduciendo por audio: {text}")

        sd.play(audio, samplerate=sample_rate)
        if wait:
            sd.wait()

        face_mode = "listening" if asking_mode else "idle"
        helper_mode = HELPER_STATE.ASKING if asking_mode else HELPER_STATE.NAME 
        
        self.node.face_mode_pub.publish(String(data=face_mode)) # Mouth mode
        self.node.helper_mode_pub.publish(String(data=json.dumps({
            "helper_state": helper_mode.value,
            **({"asking_mode": asking_mode} if asking_mode else {})
        }))) # Helper mode


def main(args=None):
    rclpy.init(args=args)

    assistant = Assistant()

    assistant.spin()
    rclpy.shutdown()