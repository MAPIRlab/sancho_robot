[← Back to Main README](../../../README.md)

# sancho_interfaces

The `sancho_interfaces` package defines all custom ROS 2 message (`.msg`), service (`.srv`), and action (`.action`) types used across the Sancho workspace. It is the single source of truth for inter-package communication contracts.

---

## Messages (33)

| Category | Messages |
|----------|----------|
| **Audio** | `AudioData`, `ChunkMono`, `ChunkStereo`, `VADSegment`, `InputTTS`, `QuestionTTS`, `UserTranscription` |
| **Vision / Face** | `Face`, `FaceArray`, `FaceDetection`, `FaceDetectionArray`, `FaceRecognition`, `FaceRecognitionArray`, `FacePosition`, `FaceNameResponse`, `FaceQuestionResponse`, `FaceprintEvent` |
| **People / Groups** | `PersonPose`, `PersonsPoses`, `GroupInfo` |
| **AI / HRI** | `ConversationTurn`, `LLMLoadModelMsg`, `LLMLoadUnloadResult`, `ProviderItem`, `ProviderModel`, `ModelItem`, `ModelSpeaker`, `SpeechLoadModelMsg`, `SpeechLoadUnloadResult` |
| **System** | `BoolStamped`, `Log`, `R2WMessage`, `SessionMessage` |

## Services (31)

| Category | Services |
|----------|----------|
| **Audio** | `AskUser`, `GetNoiseFloor` |
| **Vision** | `Detection`, `Recognition`, `Training`, `TriggerUserInteraction`, `GetCentralFaceCluster` |
| **LLM** | `Prompt`, `Embedding`, `LLMLoadModel`, `LLMUnloadModel`, `GetModels`, `GetActiveModels`, `SetActiveModel` |
| **STT** | `STT`, `STTGetModels`, `STTGetActiveModel`, `STTSetActiveModel` |
| **TTS** | `TTS`, `TTSGetModels`, `TTSGetActiveModel`, `TTSSetActiveModel` |
| **Speech Common** | `SpeechLoadModel`, `SpeechUnloadModel` |
| **AI** | `SanchoPrompt`, `GetString`, `GreetPeople` |
| **Navigation** | `SetHome`, `SocialState` |
| **Web** | `R2WSubscribe`, `SetSessionParams` |

## Actions (1)

| Action | Description |
|--------|-------------|
| `PlayAudio` | Plays an audio file with feedback and result |

---

## Dependencies

- **External:** `geometry_msgs`, `sensor_msgs`, `std_msgs`, `action_msgs`, `rosidl_default_generators`
- **Build type:** `ament_cmake`
