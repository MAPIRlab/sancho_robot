import math
import py_trees
from py_trees.blackboard import Client

from nav_msgs.msg import Odometry
from tf_transformations import euler_from_quaternion

class OdomYawToBlackboard(py_trees.behaviour.Behaviour):
    """
    Se suscribe a la odometría, extrae el cuaternión, lo pasa a grados 
    y lo escribe continuamente en el Blackboard.
    """
    def __init__(self, name="OdomYaw2BB", topic_name="/odom"):
        super().__init__(name)
        self.topic_name = topic_name
        self.blackboard = Client(name=self.name)
        
        # Registramos que vamos a escribir esta variable
        self.blackboard.register_key("current_base_angle", access=py_trees.common.Access.WRITE)
        
        self.node = None
        self.subscriber = None
        self.latest_yaw_deg = 0.0
        self.msg_received = False

    def setup(self, **kwargs):
        """Se ejecuta al arrancar el árbol. Creamos el suscriptor de ROS 2."""
        self.node = kwargs['node']
        self.subscriber = self.node.create_subscription(
            Odometry,
            self.topic_name,
            self._odom_callback,
            10
        )

    def _odom_callback(self, msg: Odometry):
        """Callback asíncrono de ROS 2. Convierte el cuaternión a grados."""
        q = msg.pose.pose.orientation
        
        # euler_from_quaternion recibe una lista [x, y, z, w] y devuelve (roll, pitch, yaw)
        _, _, yaw_rad = euler_from_quaternion([q.x, q.y, q.z, q.w])
        
        self.latest_yaw_deg = math.degrees(yaw_rad)
        self.msg_received = True

    def update(self):
        """Se evalúa en cada tick del árbol (10 Hz)."""
        if self.msg_received:
            # Volcamos el último ángulo calculado a la pizarra
            self.blackboard.current_base_angle = self.latest_yaw_deg
            return py_trees.common.Status.SUCCESS
        else:
            # Si aún no ha llegado el primer mensaje de odometría, esperamos
            return py_trees.common.Status.RUNNING