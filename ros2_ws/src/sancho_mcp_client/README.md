# sancho_mcp_client

CLI client for the Sancho MCP server using a LangGraph ReAct agent.

## Requirements

Create a local virtual environment and install deps:

```bash
cd /home/mapir/sancho_mcp/ros2_ws/src/sancho_mcp_client
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Environment

The client uses these environment variables:

- `SANCHO_MCP_SERVER_URL` (default: `http://127.0.0.1:8000/mcp`)
- `GOOGLE_API_KEY` (required for Gemini; set in `.env`)
- `SANCHO_MCP_LLM_MODEL` (default: `gemini-3.1-flash-lite`)
- `SANCHO_MCP_LLM_TEMPERATURE` (default: `0.2`)
- `SANCHO_SYSTEM_PROMPT_PATH` (default: `ros2_ws/src/sancho_mcp_server/SYSTEM_PROMPT.md`)

## Run

```bash
cd /home/mapir/sancho_mcp/ros2_ws/src/sancho_mcp_client
python client.py
```

Type your request in the prompt. Use `exit` or `quit` to stop.

## Quick start

```bash
cd /home/mapir/sancho_mcp/ros2_ws/src/sancho_mcp_client
source .venv/bin/activate
# Edit .env and paste your Google API key
python client.py
```

## Notes

- The client prints tool calls and tool outputs so you can see what the agent is doing.
- The `take_photo()` tool returns a multimodal image payload and is forwarded to the LLM as an image.
- The `interpret_photo()` tool requests a textual description from the vision model.
- MCP-to-LangChain integration uses `langchain-mcp-adapters`.
