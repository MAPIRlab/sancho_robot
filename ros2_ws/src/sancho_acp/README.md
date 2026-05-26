# Sancho ACP Server (`sancho_acp`)

This package implements the **cognitive layer** of the three-layer HRI architecture. It functions as an **ACP server** (listening for TCP connections from front-end user interfaces) and acts as an **MCP client** (connecting to the `sancho_mcp_server` to run robot tools via LangChain and Google Gemini).

```
ACP Client (HRI) ──TCP:9100──► sancho_acp (Agent) ──HTTP──► sancho_mcp_server ──ROS 2──► Robot
```

## Structure

- `sancho_acp/tcp_server.py`: Starts the TCP server using `asyncio.start_server`. Each incoming TCP socket gets a dedicated `AgentSideConnection` and a fresh `SanchoAgent`.
- `sancho_acp/agent.py`: Implements the `acp.Agent` protocol interface. Receives prompts, runs them through the orchestrator, and streams agent thoughts and messages back.
- `sancho_acp/orchestrator.py`: ReAct reasoning loop. Lazily connects to the MCP server URL on the first prompt, handles multimodal cameras (`take_photo`), and executes tools using LangChain.
- `SYSTEM_PROMPT.md`: System prompt defining the robot's identity, navigation, and speech policies.
- `run.sh`: Shell script that automatically sets up the Python virtual environment (`.venv`), installs dependencies, and launches the server.

## Installation & Configuration

1. **Environment Variables**: Configure the credentials and endpoint URLs in `.env` within this directory:
   ```ini
   GOOGLE_API_KEY=AIzaSy...
   SANCHO_MCP_LLM_MODEL=gemini-3.1-flash-lite
   SANCHO_MCP_LLM_TEMPERATURE=0.2
   SANCHO_MCP_SERVER_URL=http://127.0.0.1:8000/mcp
   SANCHO_ACP_HOST=0.0.0.0
   SANCHO_ACP_PORT=9100
   ```

2. **Setup**: The launcher script `run.sh` will automatically create the virtual environment and install the required dependencies (such as `agent-client-protocol==0.10.1` and LangChain adapters).

## Execution

### Starting the Server

Simply execute the launcher script:
```bash
./run.sh
```

Alternatively, to run the module directly:
```bash
source .venv/bin/activate
python -m sancho_acp.tcp_server --port 9100 --debug
```

*Note: The ACP server utilizes a **lazy connection** strategy for the MCP backend. The TCP server will start instantly and accept user sessions even if the MCP server is not running yet. Connection to the MCP server is only established when the client sends their first prompt.*

### Testing

We have provided two test scripts to verify the functionality of the server:

1. **Protocol Handshake Smoke Test**:
   Validates the ACP connection handshake (initialize & new_session) over TCP without requiring the MCP server to be active.
   ```bash
   source .venv/bin/activate
   python test_smoke.py
   ```

2. **Interactive Client**:
   A terminal client that lets you type prompts, prints agent thoughts in real-time, and interacts with the LLM and the robot's MCP server.
   ```bash
   source .venv/bin/activate
   python test_client.py [HOST] [PORT]
   ```
