import py_trees
import py_trees_ros
from sancho_interfaces.srv import GetActionPrediction

class PredictHumanAction(py_trees.behaviour.Behaviour):
    def __init__(self, name="Predict Human Action"):
        super(PredictHumanAction, self).__init__(name)
        self.blackboard = self.attach_blackboard_client()
        self.blackboard.register_key(key="predicted_action", access=py_trees.common.Access.WRITE)
        self.node = None
        self.client = None
        self.future = None

    def setup(self, **kwargs):
        self.node = kwargs.get('node')
        self.client = self.node.create_client(GetActionPrediction, 'recognize_human_action')
        return self.client.wait_for_service(timeout_sec=2.0)

    def update(self):
        if not self.future:
            self.logger.info("Solicitando predicción de acción...")
            self.future = self.client.call_async(GetActionPrediction.Request())
            return py_trees.common.Status.RUNNING

        if self.future.done():
            try:
                res = self.future.result()
                self.blackboard.predicted_action = res.action
                self.logger.info(f"¡Acción recibida!: {res.action}")
                self.future = None 
                return py_trees.common.Status.SUCCESS
            except Exception as e:
                self.logger.error(f"Error en servicio: {e}")
                self.future = None
                return py_trees.common.Status.FAILURE
        
        return py_trees.common.Status.RUNNING