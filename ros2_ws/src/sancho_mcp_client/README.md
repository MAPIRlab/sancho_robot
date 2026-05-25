# sancho_mcp_client

`sancho_mcp_client` is a CLI conversational client for the Sancho MCP server, built using a LangGraph ReAct agent. It allows you to command the Sancho robot using natural language by routing user requests to the server's MCP tools.

## How it works

The client connects to the running `sancho_mcp_server` over HTTP, dynamically imports the available MCP tools, and exposes them to a Google Gemini LLM. 
It uses:
- `langchain-mcp-adapters` to map MCP tools into LangChain tools.
- `langchain-google-genai` to run the agentic reasoning loop.
- A local `.env` configuration file to manage API keys and endpoints.

---

## Requirements

- Python 3.10+
- An active Google Gemini API Key (`GOOGLE_API_KEY`).
- A running instance of `sancho_mcp_server`.

---

## Setup

1. **Create and activate the virtual environment**:
   ```bash
   cd /home/mapir/sancho_mcp/ros2_ws/src/sancho_mcp_client
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Install the dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the Environment**:
   Ensure you have a `.env` file in the package root. Example configuration:
   ```ini
   GOOGLE_API_KEY=your-api-key-here
   SANCHO_MCP_LLM_MODEL=gemini-3.1-flash-lite
   SANCHO_MCP_LLM_TEMPERATURE=0.2
   SANCHO_MCP_SERVER_URL=http://127.0.0.1:8000/mcp
   ```

---

## Run

To launch the conversational CLI agent:

```bash
# 1. Activate virtual environment
source /home/mapir/sancho_mcp/ros2_ws/src/sancho_mcp_client/.venv/bin/activate

# 2. Run the client
python3 client.py
```

Once running, type your requests into the prompt (e.g., *"take a photo and describe what you see"*, *"go to room 2.3.7"*). Use `exit` or `quit` to stop the session.

---

## Environment Variables

| Variable | Description | Default |
| --- | --- | --- |
| `GOOGLE_API_KEY` | Required API Key to access Google Generative AI (Gemini). | *None* |
| `SANCHO_MCP_SERVER_URL` | Endpoint of the running `sancho_mcp_server`. | `http://127.0.0.1:8000/mcp` |
| `SANCHO_MCP_LLM_MODEL` | Gemini model to use for the agent's logic. | `gemini-3.1-flash-lite` |
| `SANCHO_MCP_LLM_TEMPERATURE` | Controls the creativity/determinism of the agent. | `0.2` |
| `SANCHO_SYSTEM_PROMPT_PATH` | Path to the system instruction prompt file. | `SYSTEM_PROMPT.md` |

---

## Notes

- **Multimodal Support**: The `take_photo()` tool is intercepted and wrapped so that raw base64 image data returned by the ROS camera is correctly passed to the Gemini LLM as an image block. This allows the model to "see" and reason about the image directly in the chat history.
- **Tool Tracing**: The client uses a custom callback logger (`ToolLogger`) to print logs in the console whenever the LLM triggers a tool and when the tool finishes execution.
- **Server Dependency**: The client only communicates with the robot through the HTTP MCP Server endpoint. Sourcing the ROS 2 environment is **not** required to run the client, as long as the server is reachable.
