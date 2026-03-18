# sancho_interfaces

**Role:** The `sancho_interfaces` package defines all custom ROS 2 message (`.msg`), service (`.srv`), and action (`.action`) types used across the Sancho workspace. It serves as the single source of truth for inter-package communication contracts, ensuring type consistency across all nodes.

## Contents

### Messages (33 total)

| Category | Messages |
|---|---|
| **Audio** | `AudioData`, `ChunkMono`, `ChunkStereo`, `VADSegment`, `InputTTS`, `QuestionTTS`, `UserTranscription` |
| **Vision / Face** | `Face`, `FaceArray`, `FaceDetection`, `FaceDetectionArray`, `FaceRecognition`, `FaceRecognitionArray`, `FacePosition`, `FaceNameResponse`, `FaceQuestionResponse`, `FaceprintEvent` |
| **People / Groups** | `PersonPose`, `PersonsPoses`, `GroupInfo` |
| **AI / HRI** | `ConversationTurn`, `LLMLoadModelMsg`, `LLMLoadUnloadResult`, `ProviderItem`, `ProviderModel`, `ModelItem`, `ModelSpeaker`, `SpeechLoadModelMsg`, `SpeechLoadUnloadResult` |
| **System** | `BoolStamped`, `Log`, `R2WMessage`, `SessionMessage` |

### Services (31 total)

| Category | Services |
|---|---|
| **Audio** | `AskUser`, `GetNoiseFloor` |
| **Vision** | `Detection`, `Recognition`, `Training`, `TriggerUserInteraction`, `GetCentralFaceCluster` |
| **LLM** | `Prompt`, `Embedding`, `LLMLoadModel`, `LLMUnloadModel`, `GetModels`, `GetActiveModels`, `SetActiveModel` |
| **STT** | `STT`, `STTGetModels`, `STTGetActiveModel`, `STTSetActiveModel` |
| **TTS** | `TTS`, `TTSGetModels`, `TTSGetActiveModel`, `TTSSetActiveModel` |
| **Speech Common** | `SpeechLoadModel`, `SpeechUnloadModel` |
| **AI** | `SanchoPrompt`, `GetString`, `GreetPeople` |
| **Navigation** | `SetHome`, `SocialState` |
| **Web** | `R2WSubscribe`, `SetSessionParams` |

### Actions (1 total)
- `PlayAudio`: Action for playing an audio file with feedback and result.

## Build

Built with `ament_cmake` and `rosidl_default_generators`. Depends on `geometry_msgs`, `sensor_msgs`, `std_msgs`, and `action_msgs`.
