[← Back to Main README](../../../README.md)

# sancho_hri

The `sancho_hri` package centralizes all AI and speech intelligence capabilities. It provides dynamically loadable, provider-agnostic services for Large Language Models (LLMs), Speech-to-Text (STT), and Text-to-Speech (TTS). It also contains the `sancho_ai` conversational brain that processes intents, manages per-user memory, and orchestrates multi-turn dialogues.

---

## Nodes

| Node | Description |
|------|-------------|
| `llm` | Provider-agnostic LLM gateway supporting OpenAI, Mistral, LLaMA, Phi, Qwen, DeepSeek, Gemini, Gemma, Falcon, YI, and Mapirbot. Also supports embeddings via SBERT, E5, and BAAI. |
| `stt` | Speech-to-Text service with Whisper (local) and Google (cloud) backends. Includes Silero VAD pre-filter. |
| `tts` | Text-to-Speech service supporting Bark, CSS10, Google, Piper, Tacotron2, XTTS, and YourTTS engines. |
| `sancho_ai` | Conversational brain with mode-based dispatch (`normal`, `get_name`, `confirm_name`, `all_known`), per-user memory via `MemoryManager`, chat history, and intent classification. |

---

## ROS 2 API

### Services (LLM)

| Service | Type | Description |
|---------|------|-------------|
| `sancho_hri/llm/prompt` | `sancho_interfaces/srv/Prompt` | Send prompt with system instructions and history |
| `sancho_hri/llm/embedding` | `sancho_interfaces/srv/Embedding` | Generate embedding vectors |
| `sancho_hri/llm/load_model` | `sancho_interfaces/srv/LLMLoadModel` | Load a provider model at runtime |
| `sancho_hri/llm/unload_model` | `sancho_interfaces/srv/LLMUnloadModel` | Unload a model |
| `sancho_hri/llm/get_all_models` | `sancho_interfaces/srv/GetModels` | Query all registered models |
| `sancho_hri/llm/get_active_models` | `sancho_interfaces/srv/GetActiveModels` | Query active models |
| `sancho_hri/llm/set_active_llm` | `sancho_interfaces/srv/SetActiveModel` | Set default LLM model |
| `sancho_hri/llm/set_active_embedding` | `sancho_interfaces/srv/SetActiveModel` | Set default embedding model |

### Services (STT)

| Service | Type | Description |
|---------|------|-------------|
| `sancho_hri/speech/stt` | `sancho_interfaces/srv/STT` | Transcribe audio to text |
| `sancho_hri/speech/stt/load_model` | *(speech model services)* | Load/unload/set STT models |

### Services (TTS)

| Service | Type | Description |
|---------|------|-------------|
| `sancho_hri/speech/tts` | `sancho_interfaces/srv/TTS` | Synthesize text to audio |
| `sancho_hri/speech/tts/load_model` | *(speech model services)* | Load/unload/set TTS models |

### Services (SanchoAI)

| Service | Type | Description |
|---------|------|-------------|
| `sancho_hri/ai/prompt` | `sancho_interfaces/srv/SanchoPrompt` | Main conversational endpoint |
| `sancho_hri/ai/get_memories` | `sancho_interfaces/srv/GetString` | Per-user memory retrieval |
| `sancho_hri/ai/update_memory` | `sancho_interfaces/srv/GetString` | Per-user memory update |

### Published Topics

| Topic | Type | Description |
|-------|------|-------------|
| `conversation_log/add` | `sancho_interfaces/msg/ConversationTurn` | Structured log of every exchange |

---

## Parameters

### `llm`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `llm_load_models` | string | `"[]"` | JSON list of `[provider, models, api_key]` to pre-load |
| `llm_active_provider` | string | — | Default LLM provider |
| `llm_active_model` | string | — | Default LLM model |
| `embedding_load_models` | string | `"[]"` | JSON list of embedding models to pre-load |
| `embedding_active_provider` | string | — | Default embedding provider |
| `embedding_active_model` | string | — | Default embedding model |

### `stt`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `load_models` | string | `"[]"` | JSON list of `[model_name, api_key]` to pre-load |
| `active_model` | string | — | Default STT model |

### `tts`

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `load_models` | string | `"[]"` | JSON list of `[model_name, api_key]` to pre-load |
| `active_model` | string | — | Default TTS model |
| `active_speaker` | string | — | Default speaker voice |

---

## Lifecycle Information

All nodes are standard `rclpy.node.Node` implementations — they do not use the ROS 2 Lifecycle architecture and are active immediately on startup.

---

## Dependencies

- **Internal:** `sancho_interfaces`
- **External:** `rclpy`
