[← Back to Main README](../../../README.md)

# sancho_audio

The `sancho_audio` package provides the complete audio pipeline for the Sancho robot: microphone capture, Voice Activity Detection (VAD), Direction of Arrival (DOA) estimation, wake-word detection, Speech-to-Text preparation, audio playback, and the conversational assistant logic that connects to external LLMs.

---

## Launch Files

| Launch File | Description |
|-------------|-------------|
| `audio_hardware.launch.py` | Microphone capture nodes |
| `audio_player.launch.py` | Audio playback lifecycle node |
| `audio_processing.launch.py` | VAD + DOA processing |
| `dialog_core.launch.py` | Assistant helper + assistant node |
| `mic_doa.launch.py` | Microphone + DOA combined launch |

---

## Nodes

| Node | Type | Description |
|------|------|-------------|
| `audio_player_node` | Lifecycle | Action server (`play_audio`) for `.wav`/`.mp3` playback via `playsound` |
| `microphone_capturer_node` | Standard | Captures audio from ALSA/PulseAudio, publishes raw data, estimates noise floor |
| `microphone_node` | Standard | Alternative capturer publishing `ChunkMono` and `ChunkStereo` messages |
| `vad_node` | Standard | Voice Activity Detection using `pyannote/voice-activity-detection` |
| `audio_direction_node` | Standard | TDOA-based sound angle estimation (GCC or NCC) on stereo VAD segments |
| `audio_doa_lifecycle_node` | Lifecycle | DOA computation from stereo mic topics using GCC-PHAT or NCC |
| `audio_doa_xvf3800_lifecycle_node` | Lifecycle | Reads pre-processed DOA from XMOS XVF3800 DSP hardware |
| `audio_doa_overlay_node` | Standard | Overlays DOA angle on camera image stream |
| `assistant_helper_lifecycle_node` | Lifecycle | Manages listening state: wake-word detection, speech chunking, STT requests |
| `assistant_node` | Standard | Core conversational agent: receives transcriptions, queries LLM, generates TTS responses |
| `recorder_node` / `stereo_recorder_node` | Standard | Debug utilities for recording audio to `.wav` files |
| `audio_node` | Standard | Mock microphone: plays local `.wav` sample in a loop |

---

## ROS 2 API

### Subscribed Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/audio/raw` | `sancho_interfaces/msg/AudioData` | Raw audio data |
| `/audio/vad_segment` | `sancho_interfaces/msg/VADSegment` | Speech segments for DOA |
| `sancho_audio/microphone/mono` | `sancho_interfaces/msg/ChunkMono` | Mono mic chunks |
| `sancho_audio/microphone/stereo` | `sancho_interfaces/msg/ChunkStereo` | Stereo mic chunks |
| `sancho_audio/assistant_helper/mode` | `std_msgs/msg/Int16` | Mode control (NAME, COMMAND, etc.) |
| `sancho_audio/assistant_helper/transcription` | `sancho_interfaces/msg/UserTranscription` | Transcribed user speech |
| `sancho_audio/doa` | `std_msgs/msg/Float32` | DOA estimate in degrees |
| `face_recognitions` | `sancho_interfaces/msg/FaceRecognitionArray` | Recognized user face data |
| `input_tts` | `sancho_interfaces/msg/InputTTS` | TTS requests |
| `question_tts` | `sancho_interfaces/msg/QuestionTTS` | Questions to audibly ask |
| `/sancho_camera/image_rect` | `sensor_msgs/msg/Image` | Camera images for DOA overlay |
| `/sancho_camera/camera_info` | `sensor_msgs/msg/CameraInfo` | Camera intrinsics |
| `/wxxms/joint_states` | `sensor_msgs/msg/JointState` | Head pan/tilt states |
| `assistant/cancel_question` | `std_msgs/msg/Empty` | Interrupt active questioning |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `/audio/raw` | `sancho_interfaces/msg/AudioData` | Published by mic capturers |
| `/audio/angle` | `std_msgs/msg/Float32` | TDOA angle |
| `/audio/vad_segment` | `sancho_interfaces/msg/VADSegment` | Detected speech segments |
| `sancho_audio/microphone/mono` | `sancho_interfaces/msg/ChunkMono` | Mono output |
| `sancho_audio/microphone/stereo` | `sancho_interfaces/msg/ChunkStereo` | Stereo output |
| `face/mode` | `std_msgs/msg/String` | Facial expression commands ("listening", "speaking", etc.) |
| `sancho_audio/assistant_helper/transcription` | `sancho_interfaces/msg/UserTranscription` | User transcription output |
| `question_tts` | `sancho_interfaces/msg/QuestionTTS` | Outgoing questions |
| `/gui/name_answer` | `std_msgs/msg/String` | GUI dialog answer strings |
| `/gui/confirm_name` | `std_msgs/msg/Bool` | GUI name confirmation |
| `conversation_log/add` | `sancho_interfaces/msg/ConversationTurn` | Dialogue logs |
| `/sancho_camera/image_audio_doa` | `sensor_msgs/msg/Image` | DOA visualization overlay |
| `sancho_audio/doa` | `std_msgs/msg/Float32` | DOA output from lifecycle nodes |

### Services & Actions

| Service / Action | Type | Description |
|------------------|------|-------------|
| `play_audio` | `sancho_interfaces/action/PlayAudio` | Action server for audio playback |
| `/get_noise_floor` | `sancho_interfaces/srv/GetNoiseFloor` | Current audio noise floor |
| `sancho_audio/ask_user` | `sancho_interfaces/srv/AskUser` | Commands helper to ask a question |
| `sancho_audio/assistant_helper/set_active` | `std_srvs/srv/SetBool` | Enable/disable voice assistant |
| `assistant/greet_people` | `sancho_interfaces/srv/GreetPeople` | Generate and speak a greeting |

**Client calls to:** `sancho_hri/speech/stt`, `sancho_hri/llm/prompt`, `sancho_hri/speech/tts`, `gui/request`

---

## Parameters

### `audio_direction_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `method` | string | `"gcc"` | TDOA computation method |
| `mic_distance` | float | `0.1225` | Distance between microphones (m) |

### `microphone_capturer_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `device_search_name` | string | `"ORBBEC"` | Mic hardware identifier |
| `chunk_size` | int | `1024` | Frames per PyAudio buffer |
| `noise_floor_alpha` | float | `0.01` | EMA coefficient for noise tracking |

### `vad_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `model_name` | string | `"pyannote/voice-activity-detection"` | HuggingFace model ID |
| `chunk_duration` | double | `1.0` | Seconds of audio per analysis |

### `assistant_helper_lifecycle_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | string | `"Sancho"` | Wake word |
| `helper_chunk_size` | double | `0.5` | Chunk duration in seconds |
| `intensity_threshold` | int | `900` | Audio level qualifying as speech |
| `timeout_seconds` | double | `5.0` | Silence timeout |
| `hotword` | string | `"openwakeword"` | Wake-word engine |
| `attach_criterion` | string | `"intensity"` | Speech detection logic |

### `assistant_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `mapirbot_url` | string | *(cloudflare URL)* | LLM remote agent endpoint |

### `audio_doa_lifecycle_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `doa_method` | string | `"ncc"` | DOA processing method |
| `enable_bandpass` | bool | `true` | Filter for human speech frequencies |
| `min_energy_dbfs` | double | `-40.0` | VAD energy threshold |

### `audio_doa_overlay_node`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `pan_joint` | string | `"pan"` | Name of the head panning joint |
| `mic_to_cam_yaw_deg` | double | `0.0` | Fallback yaw offset |

---

## Lifecycle Information

| Node | `on_configure` | `on_activate` |
|------|----------------|---------------|
| `audio_player_lifecycle` | Internal setup | Opens ActionServer for playback |
| `assistant_helper` | Connects to STT, loads wake-word models | Opens subscriptions, timers, `ask_user` service |
| `audio_doa` | Sets up DSP structures (Hann windows, DOA methods) | Starts stereo mic processing |
| `audio_doa_xvf3800` | Sets polling frequency | Starts XMOS CLI polling timer |

---

## Dependencies

- **Internal:** `sancho_interfaces`, `sancho_lifecycle_utils`
- **External:** `rclpy`, `lifecycle_msgs`, `std_msgs`, `numpy`, `pyaudio`, `playsound`, `soundfile`, `pyannote.audio`, `scipy`, `requests`
