# sancho_hri

**Role:** The `sancho_hri` package centralizes all AI and speech intelligence capabilities of the Sancho robot. It provides dynamically loadable, provider-agnostic services for Large Language Models (LLMs), Speech-to-Text (STT), and Text-to-Speech (TTS). It also contains the high-level conversational AI logic (`sancho_ai`) that processes intents, manages per-user memory, and orchestrates multi-turn dialogues.

## Core Nodes

### `llm` (LLM Node)
- **Specific Function:** A provider-agnostic gateway to multiple LLM backends. It supports on-demand loading/unloading of models from providers including OpenAI, Mistral, LLaMA, Phi, Qwen, DeepSeek, Gemini, Gemma, Falcon, YI, and a custom Mapirbot provider. It also supports embedding generation via SBERT, E5, and BAAI providers. Models can be pre-loaded via parameters or loaded at runtime through services.

### `stt` (Speech-to-Text Node)
- **Specific Function:** Converts audio (float arrays with sample rate) into text. Supports Whisper (local) and Google (cloud API) backends. Includes an integrated Silero VAD pre-filter to reject non-speech audio before running inference, saving compute. Models are dynamically loadable via services.

### `tts` (Text-to-Speech Node)
- **Specific Function:** Synthesizes speech audio from text. Supports Bark, CSS10, Google, Piper, Tacotron2, XTTS, and YourTTS engines, each with configurable speaker voices. Returns raw audio data and sample rate. Models are dynamically loadable via services.

### `sancho_ai` (Conversational AI Node)
- **Specific Function:** The robot's conversational brain. Receives prompts with a `mode` indicator (e.g., `normal`, `get_name`, `confirm_name`, `all_known`) and dispatches to the appropriate AI task. In `normal` mode, it maintains per-chat history (last 10 turns), retrieves per-user long-term memory via `MemoryManager`, performs intent classification, and publishes structured `ConversationTurn` logs. Memory updates happen asynchronously in background threads.

### `embedding_generator` / `test_*` nodes
- **Specific Function:** Utility and testing entry points for evaluating LLM classification accuracy and embedding-based classification approaches.

---

## API (Topics/Services)

### Services (LLM Node)
- `sancho_hri/llm/prompt` (`Prompt`): Send a prompt with system instructions, message history, and parameters; receive the LLM response.
- `sancho_hri/llm/embedding` (`Embedding`): Generate embedding vectors for input text.
- `sancho_hri/llm/load_model` / `unload_model` (`LLMLoadModel`, `LLMUnloadModel`): Dynamically load/unload provider models.
- `sancho_hri/llm/get_all_models` / `get_available_models` / `get_active_models` (`GetModels`, `GetActiveModels`): Query model availability.
- `sancho_hri/llm/set_active_llm` / `set_active_embedding` (`SetActiveModel`): Set the default model for subsequent requests.

### Services (STT Node)
- `sancho_hri/speech/stt` (`STT`): Transcribe audio to text.
- `sancho_hri/speech/stt/load_model` / `unload_model` / `set_active_model` / `get_*` services.

### Services (TTS Node)
- `sancho_hri/speech/tts` (`TTS`): Synthesize text to audio.
- `sancho_hri/speech/tts/load_model` / `unload_model` / `set_active_model` / `get_*` services.

### Services (SanchoAI Node)
- `sancho_hri/ai/prompt` (`SanchoPrompt`): Main conversational endpoint with mode-based dispatch.
- `sancho_hri/ai/get_memories` / `update_memory` (`GetString`): Per-user memory CRUD.

### Published Topics
- `conversation_log/add` (`sancho_interfaces/msg/ConversationTurn`): Structured log of every user↔assistant exchange.

---

## Key Parameters

### `llm`
- `llm_load_models` (string, default: "[]"): List of `[provider, models, api_key]` to pre-load on startup.
- `llm_active_provider` / `llm_active_model` (string): Default provider/model for prompt requests.
- `embedding_load_models` / `embedding_active_provider` / `embedding_active_model`: Same pattern for embeddings.

### `stt`
- `load_models` (string, default: "[]"): List of `[model_name, api_key]` to pre-load.
- `active_model` (string): Default STT model.

### `tts`
- `load_models` (string, default: "[]"): List of `[model_name, api_key]` to pre-load.
- `active_model` / `active_speaker` (string): Default TTS model and speaker voice.

---

## Lifecycle Information

All nodes in this package are standard `rclpy.node.Node` implementations and do not use the ROS 2 Lifecycle architecture. They are active immediately upon startup.
