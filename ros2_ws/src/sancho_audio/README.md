# sancho_audio

**Role:** The `sancho_audio` package provides the complete audio pipeline for the Sancho robot, encompassing microphone capture, Voice Activity Detection (VAD), Direction of Arrival (DOA) estimation, Wake Word detection, Speech-to-Text (STT) preparation, audio playing, and the conversational assistant logic connecting to external LLMs.

## Core Nodes

### `audio_player_node` (`audio_player_lifecycle`)
- **Specific Function:** A LifecycleNode that provides an Action Server (`play_audio`) to play `.wav` or `.mp3` files locally using the `playsound` library.

### `audio_direction_node`
- **Specific Function:** Computes the angle of arrival of sound using Time Difference of Arrival (TDOA) techniques (GCC or NCC) on stereo VAD segments.

### `microphone_capturer_node`
- **Specific Function:** Captures audio data in chunks from a specific ALSA/PulseAudio device (e.g. Orbbec camera mic) and publishes it as raw data. Also estimates the ambient noise floor.

### `microphone_node`
- **Specific Function:** Alternative microphone capturer that publishes audio as `ChunkMono` and `ChunkStereo` messages directly.

### `recorder_node` & `stereo_recorder_node`
- **Specific Function:** Utilities for recording audio chunks from ROS topics into `.wav` files for debugging and testing.

### `vad_node`
- **Specific Function:** Voice Activity Detection using models from Hugging Face (`pyannote/voice-activity-detection`). Analyzes chunks to detect segments containing human speech.

### `assistant_helper_node` & `assistant_helper_lifecycle_node`
- **Specific Function:** Manages the active listening state of the robot. Detects wake words (e.g., "Sancho" via openwakeword, pvporcupine, or STT), chunks user speech using VAD/intensity, and requests STT transcription. Associates speech with detected faces/DOA.

### `assistant_node`
- **Specific Function:** The core conversational agent logic. Subscribes to user transcriptions, queries an LLM pipeline (e.g., mapirbot remote agent), generates TTS responses, and commands the GUI and facial tracking systems. Manages conversation state (e.g., getting unknown user names, logging conversation history).

### `audio_node`
- **Specific Function:** Simulates a microphone by repeatedly playing a local `.wav` sample and publishing it as `ChunkMono` and `ChunkStereo` messages.

### `audio_doa_lifecycle_node`
- **Specific Function:** LifecycleNode that calculates the acoustic Direction of Arrival (DOA) from stereo microphone topics using signal processing techniques (GCC-PHAT or NCC).

### `audio_doa_xvf3800_lifecycle_node`
- **Specific Function:** LifecycleNode that reads pre-processed DOA estimates directly from a hardware DSP device (XMOS XVF3800) using command-line polling.

### `audio_doa_overlay_node`
- **Specific Function:** Takes the estimated DOA angle and the robot's head yaw (from `joint_states`) and overlays a vertical line on the camera's image stream indicating the origin of the sound.

---

## API (Topics/Services)

### Subscribed Topics
- `/audio/raw` (`sancho_interfaces/msg/AudioData`) - Raw audio data.
- `/audio/vad_segment` (`sancho_interfaces/msg/VADSegment`) - Speech segments for DOA processing.
- `sancho_audio/microphone/mono` (`sancho_interfaces/msg/ChunkMono`) - Mono microphone chunks.
- `sancho_audio/microphone/stereo` (`sancho_interfaces/msg/ChunkStereo`) - Stereo microphone chunks.
- `sancho_audio/assistant_helper/mode` (`std_msgs/msg/Int16`) - Mode control for the assistant helper (NAME, COMMAND, etc.).
- `sancho_audio/assistant_helper/transcription` (`sancho_interfaces/msg/UserTranscription`) - Text transcribed from user speech.
- `sancho_audio/doa` (`std_msgs/msg/Float32`) - DOA estimate in degrees.
- `face_recognitions` (`sancho_interfaces/msg/FaceRecognitionArray`) - Data about recognized user faces.
- `input_tts` (`sancho_interfaces/msg/InputTTS`) - TTS requests to speak.
- `question_tts` (`sancho_interfaces/msg/QuestionTTS`) - Questions to audibly ask the user.
- `/sancho_camera/image_rect` (`sensor_msgs/msg/Image`) - Camera images for DOA overlay.
- `/sancho_camera/camera_info` (`sensor_msgs/msg/CameraInfo`) - Camera intrinsics.
- `/wxxms/joint_states` (`sensor_msgs/msg/JointState`) - Pan/tilt states of the robot head.
- `assistant/cancel_question` (`std_msgs/msg/Empty`) - Command to interrupt active questioning.

### Published Topics
- `/audio/raw` (`sancho_interfaces/msg/AudioData`) - Published by microphone capturers.
- `/audio/angle` (`std_msgs/msg/Float32`) - TDOA angle.
- `/audio/vad_segment` (`sancho_interfaces/msg/VADSegment`) - Found speech segments.
- `sancho_audio/microphone/mono` & `sancho_audio/microphone/stereo` (`sancho_interfaces/msg/ChunkMono` / `ChunkStereo`)
- `face/mode` (`std_msgs/msg/String`) - Facial expression requests ("listening", "speaking", "thinking", "idle").
- `sancho_audio/assistant_helper/transcription` (`sancho_interfaces/msg/UserTranscription`)
- `question_tts` (`sancho_interfaces/msg/QuestionTTS`)
- `/gui/name_answer` (`std_msgs/msg/String`) - Answer strings for GUI dialogs.
- `/gui/confirm_name` (`std_msgs/msg/Bool`)
- `conversation_log/add` (`sancho_interfaces/msg/ConversationTurn`) - Logs of human-robot dialogue.
- `/sancho_camera/image_audio_doa` (`sensor_msgs/msg/Image`) - Visualization of the sound source.
- `sancho_audio/doa` (`std_msgs/msg/Float32`) - DOA published by lifecycle nodes.

### Services
- `play_audio` (Action: `sancho_interfaces/action/PlayAudio`) - Action server to play a local sound file.
- `/get_noise_floor` (`sancho_interfaces/srv/GetNoiseFloor`) - Get current audio noise floor.
- `sancho_audio/ask_user` (`sancho_interfaces/srv/AskUser`) - Commands the helper to ask the user a specific question.
- `sancho_audio/assistant_helper/set_active` (`std_srvs/srv/SetBool`) - Enable/disable the voice assistant helper.
- `assistant/greet_people` (`sancho_interfaces/srv/GreetPeople`) - Command the assistant to generate and say a greeting.
- **Client calls out to:** `sancho_hri/speech/stt`, `sancho_hri/llm/prompt`, `sancho_hri/speech/tts`, `gui/request`.

---

## Key Parameters

### `audio_direction_node`
- `method` (string, default: "gcc"): TDOA computation method.
- `mic_distance` (float, default: 0.1225): Distance between mics in meters.

### `microphone_capturer_node`
- `device_search_name` (string, default: "ORBBEC"): Mic hardware string.
- `chunk_size` (int, default: 1024): Frames per PyAudio buffer.
- `noise_floor_alpha` (float, default: 0.01): EMA coefficient for noise tracking.

### `vad_node`
- `model_name` (string, default: "pyannote/voice-activity-detection"): HF model identifier.
- `chunk_duration` (double, default: 1.0): Seconds of audio to analyze at a time.

### `assistant_helper_lifecycle_node`
- `name` (string, default: "Sancho"): The wake word of the robot.
- `helper_chunk_size` (double, default: 0.5): Duration in seconds to process chunks.
- `intensity_threshold` (int, default: 900): Audio level to qualify as speech.
- `timeout_seconds` (double, default: 5.0): Seconds of silence to time out a command.
- `hotword` (string, default: "openwakeword"): Engine to use.
- `attach_criterion` (string, default: "intensity"): Logic to detect speech.

### `assistant_node`
- `mapirbot_url` (string, default: "https://dynamic-gig-networks-silk.trycloudflare.com/ask"): Endpoint of the LLM remote agent.

### `audio_doa_lifecycle_node`
- `doa_method` (string, default: "ncc"): Which DOA processing to apply.
- `enable_bandpass` (bool, default: True): Filter audio frequencies for human speech.
- `min_energy_dbfs` (double, default: -40.0): VAD threshold.

### `audio_doa_overlay_node`
- `pan_joint` (string, default: "pan"): Name of the head panning joint.
- `mic_to_cam_yaw_deg` (double, default: 0.0): Fallback offset if joint is missing.

---

## Lifecycle Information

Several nodes in this package inherit from `rclpy.lifecycle.LifecycleNode` to provide robust state management (`unconfigured` -> `inactive` -> `active`):

- **`audio_player_lifecycle`**: 
  - `on_configure`: Internal setup state logic.
  - `on_activate`: Opens the ActionServer for audio playback. Starts listening to actions.
- **`assistant_helper` (`assistant_helper_lifecycle_node.py`)**:
  - `on_configure`: Connects to `stt_service`, instantiates the backend helper logic (loads wakeword models).
  - `on_activate`: Opens subscriptions, enables prompt/question timers, binds `ask_user` service.
- **`audio_doa` (`audio_doa_lifecycle_node.py`)**: 
  - `on_configure`: Sets up DSP structures (Hann windows, selected DOAMethod instances).
  - `on_activate`: Turns on stereo microphone processing.
- **`audio_doa_xvf3800` (`audio_doa_xvf3800_lifecycle_node.py`)**: 
  - `on_configure`: Sets polling freq.
  - `on_activate`: Initiates the polling timer invoking the XMOS CLI tool.
