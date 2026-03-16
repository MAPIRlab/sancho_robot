# GroupInfo.msg
# Mensaje personalizado para la información de un grupo detectado

std_msgs/Header header
geometry_msgs/Pose pose   # Centroide del grupo
float32 radius                  # Radio estimado del grupo (en metros)
