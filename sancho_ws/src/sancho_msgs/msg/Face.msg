std_msgs/Header header           # Cabecera con timestamp y frame_id
geometry_msgs/Point center       # Centro del bounding box (x,y,z)
float64 width                   # Anchura del bounding box
float64 height                  # Altura del bounding box
float32 confidence              # Confianza de la detección (0.0 - 1.0)