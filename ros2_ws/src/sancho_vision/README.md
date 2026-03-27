[← Back to Main README](../../../README.md)

# sancho_vision

The `sancho_vision` package handles human face detection, recognition, body-face fusion tracking, spatial clustering, and the HRI graphical interface. It maintains a database of recognized people, tracks them spatially, and provides the logic to identify users and initiate dialogs when a user is unknown.

---

## Launch Files

| Launch File | Description |
|-------------|-------------|
| `identification.launch.py` | Launches the body-face fusion pipeline, face manager, visualizer, and GUI |

---

## Nodes

| Node | Type | Description |
|------|------|-------------|
| `body_face_fusion_node` | Standard | Fuses body tracking with face recognition: crops head region, runs MTCNN + EfficientFace, publishes `FaceRecognitionArray` |
| `face_visualizer_node` | Standard | Annotates image with bounding boxes, names, and distances |
| `human_face_manager_lifecycle_node` | Lifecycle | Tracks "currently seen" people, triggers GUI/voice for unknown faces |
| `hri_gui` | Standard | Qt/web GUI for face interaction prompts ("What is your name?") |
| `face_cluster_node` | Standard | Projects faces to 3D via TF, tracks with Kalman/SORT, clusters via DBSCAN |
| `central_faces_cluster_node` | Standard | Pixel-space DBSCAN clustering, returns most central face cluster centroid |
| `video_node` | Standard | Dev tool: mock camera from `.mp4` file |
| `human_face_detector_lifecycle_node` | Lifecycle (Legacy) | Standalone face detection via `dlib`/`mtcnn` |
| `human_face_recognizer_lifecycle_node` | Lifecycle (Legacy) | Standalone face recognition with `facenet` embeddings |

---

## ROS 2 API

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/sancho_perception/human_tracking` | `sancho_interfaces/msg/FaceDetectionArray` | Body tracks (input to fusion) |
| `/face_recognitions` | `sancho_interfaces/msg/FaceRecognitionArray` | Recognition results |
| `/gui/face_name_response` | `sancho_interfaces/msg/FaceNameResponse` | User name from GUI |
| `/gui/face_question_response` | `sancho_interfaces/msg/FaceQuestionResponse` | Confirmation from GUI |
| `/gui/face_timeout_response` | `std_msgs/msg/Empty` | GUI timeout signal |
| `/gui/name_answer` | `std_msgs/msg/String` | Raw GUI name input |
| `/gui/confirm_name` | `std_msgs/msg/Bool` | Raw GUI confirmation |
| `/sancho_camera/camera_info` | `sensor_msgs/msg/CameraInfo` | Intrinsics for 3D projection |
| `/sancho_camera/image_raw` | `sensor_msgs/msg/Image` | Camera images (legacy pipeline) |
| `/face_detections` | `sancho_interfaces/msg/FaceDetectionArray` | Face detections (legacy pipeline) |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/face_recognitions` | `sancho_interfaces/msg/FaceRecognitionArray` | Fused/recognized face data |
| `/face_recognitions/visual` | `sensor_msgs/msg/Image` | Debug image with bounding boxes |
| `/logs/add` | `sancho_interfaces/msg/Log` | System logs (DB additions, encounters) |
| `/logic/info/actual_people` | `std_msgs/msg/String` | JSON with currently active people |
| `/input_tts` | `sancho_interfaces/msg/InputTTS` | Speech commands (greetings, etc.) |
| `face_markers` | `visualization_msgs/msg/MarkerArray` | RViz markers for tracked faces |
| `recognition/event` | `sancho_interfaces/msg/FaceprintEvent` | Database update events |

### Services Provided

| Service | Type | Description |
|---------|------|-------------|
| `/recognition/training` | `sancho_interfaces/srv/Training` | Add, rename, or delete faces in DB |
| `/recognition/get_faceprint` | `sancho_interfaces/srv/GetString` | Retrieve database entries |
| `/recognition/clear_no_name` | `std_srvs/srv/Empty` | Remove unnamed faces |
| `/gui/request` | `sancho_interfaces/srv/TriggerUserInteraction` | Popup GUI dialogs |
| `compute_cluster` | `std_srvs/srv/Empty` | Request 2D spatial clusters |
| `~/get_central_cluster` | `sancho_interfaces/srv/GetCentralFaceCluster` | Central face cluster |

### Services Consumed

| Service | Type | Description |
|---------|------|-------------|
| `sancho_audio/ask_user` | `sancho_interfaces/srv/AskUser` | Trigger voice questions |

---

## Parameters

### `body_face_fusion_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `detector_name` | string | `"mtcnn"` | Face detection algorithm |
| `encoder_name` | string | `"efficientface"` | Embedding generation algorithm |
| `head_fraction` | double | `0.40` | Top % of body bbox to search for head |
| `cache_ttl` | double | `15.0` | Recognition cache time-to-live (s) |
| `no_face_cooldown_sec` | double | `2.0` | Backoff before re-checking for face |

### `human_face_manager_lifecycle_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `processing_rate` | double | `10.0` | Tick rate in Hz |
| `service_wait_attempts` | int | `10` | Attempts for service connection |

### `face_cluster_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `camera_frame` | string | `"camera_link"` | TF frame for camera |
| `head_frame` | string | `"base_link"` | TF base frame |
| `dbscan.eps` | double | `0.35` | DBSCAN epsilon |
| `dbscan.min_samples` | int | `2` | DBSCAN minimum points |
| `track.max_misses` | int | `60` | SORT max missed frames |
| `track.dt` | double | `0.1` | Kalman filter time step |

### `central_faces_cluster_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `eps_default` | double | `60.0` | Pixel-space DBSCAN epsilon |
| `min_samples_default` | int | `1` | Pixel-space DBSCAN min samples |

---

## Lifecycle Information

| Node | `on_configure` | `on_activate` |
|------|----------------|---------------|
| `human_face_manager_lifecycle_node` | Initializes QoS, action/service clients (TTS, GUI, Training) | Subscribes to GUI/recognitions, starts main spin timer |
| `human_face_detector_lifecycle_node` (Legacy) | Loads AI models (`dlib`, `mtcnn`) | Opens camera subscriptions, starts inference |
| `human_face_recognizer_lifecycle_node` (Legacy) | Loads embedding models (`facenet`), database files | Opens subscriptions, starts inference |

---

## Dependencies

- **Internal:** `sancho_interfaces`
- **External:** `rclpy`, `sensor_msgs`, `cv_bridge`, `std_msgs`, `geometry_msgs`, `numpy`, `mediapipe`, `dlib`, `tf_transformations`, `filterpy`, `scikit-image`
