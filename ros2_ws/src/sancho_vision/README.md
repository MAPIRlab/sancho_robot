# sancho_vision

**Role:** The `sancho_vision` package handles human face detection, face recognition, facial tracking, and integrates with the human-robot interaction GUI. It maintains a database of recognized people, tracks them spatially, and provides the core logic to identify users and initiate dialogs if a user is unknown or needs confirmation.

## Core Nodes

### `body_face_fusion_node`
- **Specific Function:** Fuses robust body tracking with face recognition. It subscribes to human body tracks, crops the head region dynamically, and performs face detection/recognition (using MTCNN and EfficientFace) on the cropped image. It publishes the final `FaceRecognitionArray` maintaining the identity over the body track ID.

### `face_visualizer_node`
- **Specific Function:** Subscribes to face recognition results and publishes an annotated image stream (`/face_recognitions/visual`) with bounding boxes, names, and distances.

### `human_face_manager_lifecycle_node`
- **Specific Function:** A LifecycleNode that acts as the interaction brain for faces. It tracks when people are seen, maintains the "currently seen people" list, and triggers the `hri_gui` and voice assistant to ask for names when a face is unknown or uncertain. It also logs these interactions.

### `hri_gui`
- **Specific Function:** Manages the local Qt-based or web-based graphical interface for face interactions. Displays prompts to the user asking "What is your name?" or "Are you X?", capturing the input and returning it to the face manager.

### `face_cluster_node`
- **Specific Function:** Projects detected faces from camera 2D pixels into a pseudo-3D space (using TF and simplified depth from face scale). It tracks the faces temporally using a Kalman filter and SORT algorithm, and clusters them using DBSCAN to group people spatially. Essential for interactive group behaviors.

### `central_faces_cluster_node`
- **Specific Function:** Simplistic clustering node that groups faces in pixel space using DBSCAN and returns the centroid of the most central face cluster (useful for attention mechanisms or head panning).

### `video_node`
- **Specific Function:** Development tool that acts as a mock camera by publishing frames from a local `.mp4` video file to `camera/color/image_raw`.

### `human_face_detector_lifecycle_node` (Legacy)
- **Specific Function:** A standalone LifecycleNode for generic face detection (e.g., using `dlib` or `mtcnn`). Publishes `FaceDetectionArray` without recognition.

### `human_face_recognizer_lifecycle_node` (Legacy)
- **Specific Function:** A standalone LifecycleNode for face recognition. Takes `/face_detections`, aligns the faces, generates embeddings (using models like `facenet`), classifies them against the local database, and publishes `FaceRecognitionArray`.

---

## API (Topics/Services)

### Subscribed Topics
- `/sancho_perception/human_tracking` (`sancho_interfaces/msg/FaceDetectionArray`): Input body tracks.
- `/face_recognitions` (`sancho_interfaces/msg/FaceRecognitionArray`): Analyzed faces with IDs.
- `/gui/face_name_response` (`sancho_interfaces/msg/FaceNameResponse`): User input from GUI (new name).
- `/gui/face_question_response` (`sancho_interfaces/msg/FaceQuestionResponse`): Confirmation (Yes/No) from GUI.
- `/gui/face_timeout_response` (`std_msgs/msg/Empty`): Timeout signal if user doesn't answer GUI.
- `/gui/name_answer` (`std_msgs/msg/String`), `/gui/confirm_name` (`std_msgs/msg/Bool`): Raw GUI inputs.
- `/sancho_camera/camera_info` (`sensor_msgs/msg/CameraInfo`): Intrinsics for 3D projection.
- `/sancho_camera/image_raw` (`sensor_msgs/msg/Image`), `/face_detections` (`sancho_interfaces/msg/FaceDetectionArray`): Inputs for legacy pipelines.

### Published Topics
- `/face_recognitions` (`sancho_interfaces/msg/FaceRecognitionArray`): Main output of fused/recognized face data.
- `/face_recognitions/visual` (`sensor_msgs/msg/Image`): Image containing debug bounding boxes.
- `/logs/add` (`sancho_interfaces/msg/Log`): System logs about database additions or encounters.
- `/logic/info/actual_people` (`std_msgs/msg/String`): JSON string with currently active people's IDs and timestamps.
- `/input_tts` (`sancho_interfaces/msg/InputTTS`): Commands to speak (e.g., greetings).
- `face_markers` (`visualization_msgs/msg/MarkerArray`): RViz markers for 2D tracked faces.
- `recognition/event` (`sancho_interfaces/msg/FaceprintEvent`): Database update events.
- `/gui/face_name_response`, `/gui/face_question_response`: Bridged outputs from GUI forms.

### Services
- `/recognition/training` (`sancho_interfaces/srv/Training`): Interface to add, rename, or delete faces in the database (`add_class`, `add_features`, `delete_all`, etc.).
- `/recognition/get_faceprint` (`sancho_interfaces/srv/GetString`): Retrieve database entries.
- `/recognition/clear_no_name` (`std_srvs/srv/Empty`): Removes temporary or unnamed faces.
- `/gui/request` (`sancho_interfaces/srv/TriggerUserInteraction`): Used by logic to popup GUI dialogs (`get_name`, `ask_if_name`).
- `sancho_audio/ask_user` (`sancho_interfaces/srv/AskUser`): Client to trigger voice assistant questions.
- `compute_cluster` (`std_srvs/srv/Empty`): Request current 2D spatial clusters from SORT tracker.
- `~/get_central_cluster` (`sancho_interfaces/srv/GetCentralFaceCluster`): Get the center of the main face cluster in screen space.
- `detection` / `recognition`: Synchronous API calls to run inference directly for a single frame.

---

## Key Parameters

### `body_face_fusion_node`
- `detector_name` (string, default: "mtcnn"): Algorithm for face crops.
- `encoder_name` (string, default: "efficientface"): Algorithm for embeddings.
- `head_fraction` (double, default: 0.40): Top percentage of the body bounding box to search for a head.
- `cache_ttl` (double, default: 15.0): Time-to-live for smart recognition cache.
- `no_face_cooldown_sec` (double, default: 2.0): Backoff time before checking for a face again if none was found.

### `human_face_manager_lifecycle_node`
- `processing_rate` (double, default: 10.0): Node tick rate in Hz.
- `service_wait_attempts` (int, default: 10): Tries for connecting to required services.

### `face_cluster_node`
- `camera_frame` (string, default: "camera_link") / `head_frame` (string, default: "base_link"): TF frames.
- `dbscan.eps` (double, default: 0.35) / `dbscan.min_samples` (int, default: 2): Clustering settings.
- `track.max_misses` (int, default: 60) / `track.dt` (double, default: 0.1): SORT KF parameters.

### `central_faces_cluster_node`
- `eps_default` (double, default: 60.0) / `min_samples_default` (int, default: 1): Pixel-space DBSCAN settings.

---

## Lifecycle Information

Several key nodes orchestrate their initialization via `rclpy.lifecycle.LifecycleNode`:

- **`human_face_manager_lifecycle_node`**:
  - `on_configure`: Initializes QoS profiles, sets up action/service clients (TTS, GUI, Training) and waits for them.
  - `on_activate`: Subscribes to GUI responses and recognitions, starts the main `spin` timer to process human encounters.
- **Legacy Detector/Recognizer (`human_face_detector_lifecycle_node`, `human_face_recognizer_lifecycle_node`)**:
  - `on_configure`: Loads AI models (`dlib`, `facenet`) and database files into memory. 
  - `on_activate`: Opens subscriptions to camera streams or tracking topics, starts inference timers.
