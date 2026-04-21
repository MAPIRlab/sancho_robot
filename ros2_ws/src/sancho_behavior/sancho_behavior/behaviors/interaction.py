import py_trees
import py_trees_ros
import json
import random

from sancho_interfaces.srv import GetCentralFaceCluster
from sancho_interfaces.action import PlayTTS

class GreetUser(py_trees_ros.actions.ActionClient):
    """
    Reads user information and plays a random greeting message
    """
    def __init__(self, name="GreetUser"):
        self.action_goal = PlayTTS.Goal()

        super().__init__(
            name=name,
            action_type=PlayTTS,
            action_name="/play_tts",
            action_goal=self.action_goal
        )
        
        self.blackboard.register_key("speaker_info_json", access=py_trees.common.Access.READ)

    def initialise(self):
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
            
        self.action_goal.text = random.choice(greetings)
        super().initialise()


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