import json
import py_trees

from std_msgs.msg import String
from lifecycle_msgs.srv import ChangeState
from lifecycle_msgs.msg import Transition


class ManageFaceTracker(py_trees.behaviour.Behaviour):
    """
    Activates the face tracker Lifecycle node when this behavior starts,
    and deactivates it when preempted or stopped.
    """
    def __init__(self, name="ManageFaceTracker", lifecycle_node_name="face_tracker"):
        super().__init__(name)
        self.service_name = f'/{lifecycle_node_name}/change_state'
        self.client = None

    def setup(self, **kwargs):
        self.node = kwargs['node']
        self.client = self.node.create_client(ChangeState, self.service_name)

    def _send_transition(self, transition_id):
        if not self.client.wait_for_service(timeout_sec=0.5):
            self.logger.warning(f"Lifecycle service {self.service_name} not available.")
            return

        req = ChangeState.Request()
        req.transition.id = transition_id
        # Use async call to prevent blocking the behavior tree tick
        self.client.call_async(req)

    def initialise(self):
        self.logger.info("Engaging: Activating face tracker...")
        self._send_transition(Transition.TRANSITION_ACTIVATE)

    def update(self):
        # Stays running as long as the robot is engaged
        return py_trees.common.Status.RUNNING

    def terminate(self, new_status):
        self.logger.info("Preempted/Finished: Deactivating face tracker...")
        self._send_transition(Transition.TRANSITION_DEACTIVATE)


class UpdateTrackingTarget(py_trees.behaviour.Behaviour):
    """
    Monitors the speaker_info_json on the Blackboard. 
    If the active speaker ID changes, it publishes the new target.
    """
    def __init__(self, name="UpdateTrackingTarget", topic_name="/face_tracker/set_target"):
        super().__init__(name)
        self.topic_name = topic_name
        self.publisher = None
        self.current_target_id = None
        
        self.blackboard = py_trees.blackboard.Client(name=self.name)
        self.blackboard.register_key("speaker_info_json", access=py_trees.common.Access.READ)

    def setup(self, **kwargs):
        self.node = kwargs['node']
        self.publisher = self.node.create_publisher(String, self.topic_name, 10)

    def update(self):
        if self.blackboard.exists("speaker_info_json"):
            try:
                data = json.loads(self.blackboard.speaker_info_json)
                target_id = str(data.get("id"))
                
                if target_id and target_id != self.current_target_id:
                    self.current_target_id = target_id
                    
                    msg = String()
                    msg.data = target_id
                    self.publisher.publish(msg)
                    self.logger.info(f"Published new tracking target: ID {target_id}")
                    
            except (json.JSONDecodeError, TypeError):
                self.logger.debug("Failed to parse speaker_info_json")

        return py_trees.common.Status.RUNNING