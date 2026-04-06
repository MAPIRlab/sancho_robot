#!/usr/bin/env python3
import math
import rclpy
import tf_transformations
from geometry_msgs.msg import PoseStamped
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn
from rclpy.executors import SingleThreadedExecutor
from rclpy.qos import QoSPresetProfiles
from sensor_msgs.msg import CameraInfo, JointState
from std_msgs.msg import Header, String

from sancho_interfaces.msg import FaceRecognitionArray

class FaceTrackerLifecycle(LifecycleNode):
    """
    ROS 2 lifecycle node for tracking a SPECIFIC face based on its ID 
    and controlling a robot's pan-tilt head mechanism.
    """

    def __init__(self):
        super().__init__("face_tracker_lifecycle")

        # Parámetros
        self.declare_parameter("face_topic", "/face_recognitions")
        self.declare_parameter("head_goal_topic", "/head_goal")
        self.declare_parameter("camera_info_topic", "/sancho_camera/camera_info")
        self.declare_parameter("target_topic", "/face_tracker/set_target")
        self.declare_parameter("base_frame", "base_link")
        self.declare_parameter("control_rate", 10.0)
        self.declare_parameter("ema_alpha", 0.6)
        self.declare_parameter("p_gain_pan", 1.3)
        self.declare_parameter("p_gain_tilt", 1.0)
        self.declare_parameter("timeout_no_detection", 2.0)
        self.declare_parameter("pan_joint", "pan")
        self.declare_parameter("tilt_joint", "tilt")

        # Variables de estado
        self.is_tracking_active = False
        self.target_id = None
        
        self.fx = self.fy = self.cx = self.cy = None
        self.camera_info_ready = False

        self.smoothed_u = None
        self.smoothed_v = None
        self.last_detection_time = None

        self.current_pan = 0.0
        self.current_tilt = 0.0

        self.get_logger().info("FaceTrackerLifecycle inicializado. Esperando on_configure().")

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        # Cargar parámetros
        self.camera_frame = self.get_parameter("base_frame").value
        self.control_rate = self.get_parameter("control_rate").value

        self.timeout_no_detection = self.get_parameter("timeout_no_detection").value
        self.pan_joint = self.get_parameter("pan_joint").value
        self.tilt_joint = self.get_parameter("tilt_joint").value

        qos_sensor = QoSPresetProfiles.SENSOR_DATA.value
        qos_default = QoSPresetProfiles.SYSTEM_DEFAULT.value

        # Publicadores
        self.goal_pub = self.create_lifecycle_publisher(
            PoseStamped, self.get_parameter("head_goal_topic").value, qos_default
        )

        # Suscriptores (Se crean una vez, procesan solo si is_tracking_active == True)
        self.camera_info_sub = self.create_subscription(
            CameraInfo, self.get_parameter("camera_info_topic").value, self.camera_info_callback, qos_sensor
        )
        self.face_sub = self.create_subscription(
            FaceRecognitionArray, self.get_parameter("face_topic").value, self.face_callback, qos_sensor
        )
        self.joint_sub = self.create_subscription(
            JointState, "/wxxms/joint_states", self.joint_states_callback, 10
        )
        self.target_sub = self.create_subscription(
            String, self.get_parameter("target_topic").value, self.target_callback, 10
        )

        # Bucle de control
        timer_period = 1.0 / self.control_rate
        self.control_timer = self.create_timer(timer_period, self.control_loop)

        self.get_logger().info("Nodo CONFIGURADO. Publicadores y suscriptores listos.")
        return super().on_configure(state)

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(">>> Face Tracker ACTIVADO <<<")
        self.is_tracking_active = True
        self.smoothed_u = None
        self.smoothed_v = None
        self.last_detection_time = self.get_clock().now().nanoseconds / 1e9
        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info(">>> Face Tracker DESACTIVADO <<<")
        self.is_tracking_active = False
        return super().on_deactivate(state)
        
    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self.destroy_timer(self.control_timer)
        self.destroy_subscription(self.camera_info_sub)
        self.destroy_subscription(self.face_sub)
        self.destroy_subscription(self.joint_sub)
        self.destroy_subscription(self.target_sub)
        return TransitionCallbackReturn.SUCCESS

    # --- Callbacks ---

    def target_callback(self, msg: String):
        """Recibe el ID de la persona a la que Sancho debe mirar."""
        self.target_id = msg.data
        self.get_logger().info(f"Nuevo objetivo fijado: ID {self.target_id}")
        self.smoothed_u = None # Reseteamos el suavizado para que no haga una transición extraña entre caras

    def joint_states_callback(self, msg: JointState):
        if not self.is_tracking_active:
            return
        try:
            idx_pan = msg.name.index(self.pan_joint)
            idx_tilt = msg.name.index(self.tilt_joint)
            self.current_pan = msg.position[idx_pan]
            self.current_tilt = msg.position[idx_tilt]
        except ValueError:
            pass

    def camera_info_callback(self, msg: CameraInfo):
        if not self.camera_info_ready:
            self.fx, self.fy = msg.k[0], msg.k[4]
            self.cx, self.cy = msg.k[2], msg.k[5]
            self.camera_info_ready = True

    def face_callback(self, msg: FaceRecognitionArray):
        if not self.is_tracking_active or not self.camera_info_ready or not msg.recognitions:
            return

        target_detection = None

        # 1. Buscar la cara que coincide con nuestro target_id
        if self.target_id:
            for recog, det in zip(msg.recognitions, msg.detections):
                if recog.classified_id == self.target_id:
                    target_detection = det
                    break
        
        # 2. Si no hay target_id (o perdimos al objetivo), seguimos a la cara más grande/centrada por defecto
        if not target_detection:
            target_detection = max(msg.detections, key=lambda d: d.width * d.height)

        if target_detection:
            u = target_detection.corner.x + (target_detection.width / 2.0)
            v = target_detection.corner.y + (target_detection.height * 0.15)

            alpha = self.get_parameter("ema_alpha").value
            self.smoothed_u = u if self.smoothed_u is None else alpha * u + (1 - alpha) * self.smoothed_u
            self.smoothed_v = v if self.smoothed_v is None else alpha * v + (1 - alpha) * self.smoothed_v
            
            self.last_detection_time = self.get_clock().now().nanoseconds / 1e9

    def control_loop(self):
        if not self.is_tracking_active or not self.camera_info_ready or self.smoothed_u is None:
            return

        now = self.get_clock().now().nanoseconds / 1e9
        time_diff = now - self.last_detection_time
        
        if time_diff > self.timeout_no_detection:
            # Perdimos la cara, no publicamos movimientos para no volvernos locos
            return

        # Pinhole model math
        err_x = self.smoothed_u - self.cx
        err_y = self.smoothed_v - self.cy

        delta_pan = -math.atan2(err_x, self.fx) 
        delta_tilt = math.atan2(err_y, self.fy) 

        p_gain_pan = self.get_parameter("p_gain_pan").value
        p_gain_tilt = self.get_parameter("p_gain_tilt").value

        pan_cmd = self.current_pan + (p_gain_pan * delta_pan)
        tilt_cmd = self.current_tilt + (p_gain_tilt * delta_tilt)

        # Evitar movimientos microscópicos que queman los motores
        if abs(delta_pan) < 0.05 and abs(delta_tilt) < 0.05:
            return

        msg = PoseStamped()
        msg.header = Header(stamp=self.get_clock().now().to_msg(), frame_id=self.camera_frame)
        
        # Orientación: Roll=0, Pitch=Tilt, Yaw=Pan
        q = tf_transformations.quaternion_from_euler(0.0, tilt_cmd, pan_cmd)
        msg.pose.orientation.x = q[0]
        msg.pose.orientation.y = q[1]
        msg.pose.orientation.z = q[2]
        msg.pose.orientation.w = q[3]

        self.goal_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = FaceTrackerLifecycle()
    executor = SingleThreadedExecutor()
    executor.add_node(node)
    try:
        executor.spin()
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == "__main__":
    main()