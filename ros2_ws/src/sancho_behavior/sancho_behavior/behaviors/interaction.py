import py_trees
import py_trees_ros
import json
import random

from std_msgs.msg import String

from sancho_interfaces.srv import GetCentralFaceCluster, SanchoPrompt
from sancho_interfaces.action import PlayTTS, ListenVoice

class GreetUser(py_trees_ros.action_clients.FromCallback):
    """
    Reads user information and plays a random greeting message
    """
    def __init__(self, name="GreetUser"):
        super().__init__(
            name=name,
            action_type=PlayTTS,
            action_name="/play_tts",
            wait_for_server_timeout_sec=0.0
        )
        
        self.blackboard.register_key("speaker_info_json", access=py_trees.common.Access.READ)

    def get_goal(self):
        # Read user name
        try:
            raw_json = self.blackboard.speaker_info_json if self.blackboard.exists("speaker_info_json") else "{}"
            speaker_data = json.loads(raw_json)
            speaker_name = speaker_data.get("name", "amigo")
            speaker_id = str(speaker_data.get("id", "0"))
        except (TypeError, json.JSONDecodeError):
            speaker_name = "amigo"
            speaker_id = "0"

        # Check if the person is truly unknown
        if speaker_name == "Unknown" or speaker_id == "":
            greetings = [
                "¡Hola! ¿En qué puedo ayudarte?",
                "¡Hola! Creo que no nos conocemos. Soy Sancho.",
                "¿Qué tal? ¡Dime!"
            ]
        else:
            greetings = [
                f"¡Hola {speaker_name}!",
                f"¿Qué tal, {speaker_name}?",
                f"Me alegra verte, {speaker_name}."
            ]

        action_goal = PlayTTS.Goal()    
        action_goal.text = random.choice(greetings)
        return action_goal


class IdentifyCentralTarget(py_trees_ros.service_clients.FromConstant):
    """
    Sends a service request to select a target and make its information available in the blackboard
    """
    def __init__(self, name="IdentifyCentralTarget", eps=0.0, min_samples=0):
        request = GetCentralFaceCluster.Request()
        request.eps = float(eps)
        request.min_samples = int(min_samples)

        super().__init__(
            name=name,
            service_type=GetCentralFaceCluster,
            service_name='/central_faces_cluster_node/get_central_cluster',
            service_request=request,
            wait_for_server_timeout_sec=2.0
        )

        self.blackboard.register_key(key="speaker_info_json", access=py_trees.common.Access.WRITE)

    def update(self):
        status = super().update()

        if status == py_trees.common.Status.SUCCESS:
            if self.response and self.response.ids and len(self.response.ids) > 0:
                speaker_data = {
                    "id": self.response.ids[0],
                    "name": self.response.names[0],
                }
                self.blackboard.speaker_info_json = json.dumps(speaker_data)
            else:
                return py_trees.common.Status.FAILURE

        return status

class SetFaceMode(py_trees.behaviour.Behaviour):
    """Publishes a string to /face/mode to update the UI (idle, listening, thinking, speaking)"""
    def __init__(self, mode: str, name="SetFaceMode"):
        super().__init__(name=f"SetFace_{mode}")
        self.mode = mode
        self.publisher = None

    def setup(self, **kwargs):
        self.node = kwargs['node']
        self.publisher = self.node.create_publisher(String, "/face/mode", 10)

    def update(self):
        msg = String()
        msg.data = self.mode
        self.publisher.publish(msg)
        return py_trees.common.Status.SUCCESS

class ListenToUser(py_trees_ros.action_clients.FromConstant):
    """Action Client that triggers the VAD Transcriptor and writes text to blackboard"""
    def __init__(self, name="ListenToUser", timeout_sec=10.0):
        goal = ListenVoice.Goal()
        goal.timeout_sec = float(timeout_sec)

        super().__init__(
            name=name,
            action_type=ListenVoice,
            action_name="listen_voice",
            action_goal=goal,
            wait_for_server_timeout_sec=0.0
        )
        
        # The parent class creates self.blackboard automatically
        self.blackboard.register_key("user_transcription", access=py_trees.common.Access.WRITE)

    def update(self):
        # 1. Let the parent class tick the ROS 2 Action Client
        status = super().update()
        
        # 2. Intercept the SUCCESS state to read the result
        if status == py_trees.common.Status.SUCCESS:
            
            # Extract the actual result payload from the ROS 2 wrapper
            action_result = self.result_message.result if hasattr(self, 'result_message') else None
            
            if action_result and action_result.success:
                self.blackboard.user_transcription = action_result.text
                self.logger.info(f"User said: '{action_result.text}'")
                return py_trees.common.Status.SUCCESS
            else:
                self.logger.info("Listening failed or timed out with no audio.")
                # Return FAILURE so the Conversation Sequence aborts and the robot goes to Idle
                return py_trees.common.Status.FAILURE
                
        return status

class GenerateLLMResponse(py_trees_ros.service_clients.FromCallback):
    """Native PyTrees ROS 2 Service Client that dynamically builds its request"""
    def __init__(self, name="GenerateLLMResponse"):
        super().__init__(
            name=name,
            service_type=SanchoPrompt,
            service_name="sancho_hri/llm/prompt",
            wait_for_server_timeout_sec=0.0
        )
        
        # Register keys on the automatically created self.blackboard
        self.blackboard.register_key("user_transcription", access=py_trees.common.Access.READ)
        self.blackboard.register_key("speaker_info_json", access=py_trees.common.Access.READ)
        
        self.blackboard.register_key("ai_response_text", access=py_trees.common.Access.WRITE)
        self.blackboard.register_key("ai_emotion", access=py_trees.common.Access.WRITE)

    def get_request(self):
        """Called automatically by the parent's initialise() method"""
        text = self.blackboard.user_transcription if self.blackboard.exists("user_transcription") else ""
        
        try:
            speaker_data = json.loads(self.blackboard.speaker_info_json)
            user_id = str(speaker_data.get("id", "Unknown"))
            user_name = str(speaker_data.get("name", "Unknown"))
        except (TypeError, json.JSONDecodeError):
            user_id = "Unknown"
            user_name = "Unknown"

        # Build and return the fresh request
        req = SanchoPrompt.Request()
        req.chat_id = "0"
        req.text = text
        req.args_json = json.dumps({"user_id": user_id, "user_name": user_name})
        req.mode = "normal"
        
        return req

    def update(self):
        # Let the parent class check the ROS 2 future
        status = super().update()

        if status == py_trees.common.Status.SUCCESS:
            try:
                value = json.loads(self.response.value_json)
                
                # Use .get("text") with a fallback to .get("response") just in case
                response_text = value.get("text", value.get("response", "Ha habido un fallo al pensar."))
                
                self.blackboard.ai_response_text = response_text
                self.blackboard.ai_emotion = value.get("emotion", "neutral")
                self.logger.info(f"LLM Response: {self.blackboard.ai_response_text}")
                
            except Exception as e:
                self.logger.error(f"Error parsing SanchoPrompt response: {e}")
                self.blackboard.ai_response_text = "Me he liado un poco, perdona."
                self.blackboard.ai_emotion = "sad"
                
        elif status == py_trees.common.Status.FAILURE:
            self.logger.error("LLM Service call failed or wasn't ready.")
            self.blackboard.ai_response_text = "Perdona, no he podido conectar con mi cerebro."
            self.blackboard.ai_emotion = "sad"
            
        # Always return SUCCESS so that the sequence doesn't get aborted
        return py_trees.common.Status.SUCCESS
    
class RespondUser(py_trees_ros.action_clients.AttributesFromBlackboard):
    """Reads AI text from blackboard and sends to PlayTTS Action Server"""
    def __init__(self, name="RespondUser"):
        super().__init__(
            name=name,
            action_type=PlayTTS,
            action_name="/play_tts",
            goal_fields={'text': 'ai_response_text'}, # {Goal Field: BB Key}
            wait_for_server_timeout_sec=0.0
        )