import base64
from typing import Any
from sensor_msgs.msg import Image

def ros_image_to_data_uri(ros_image: Image, cv_bridge: Any, cv2: Any) -> str:
    cv_image = cv_bridge.imgmsg_to_cv2(ros_image, desired_encoding="bgr8")
    _, buffer = cv2.imencode(".jpg", cv_image)
    encoded_image = base64.b64encode(buffer.tobytes()).decode("utf-8")
    return f"data:image/jpeg;base64,{encoded_image}"