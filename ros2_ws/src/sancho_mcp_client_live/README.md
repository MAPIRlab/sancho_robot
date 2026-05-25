# Sancho MCP Live Client (`sancho_mcp_client_live`)

This client implements a continuous, real-time, low-latency audio/video streaming connection to the **Gemini Live** API using the `google-genai` SDK (v2.6.0). It dynamically connects to the Sancho MCP server to expose and execute robot tools (such as navigation, rotation, and camera frame capturing).

## Features
- **Native Audio Streaming**: The model listens to your microphone and replies directly through your speakers (no terminal text printing needed for voice conversation).
- **1 Hz Video Streaming**: Continuous camera frames are sent from the robot (subscribes to `/sancho_camera/image_rect` ROS topic with automatic fallback to local webcam `/dev/video0`).
- **User Interruption Handling**: Instantly cancels and clears active speaker playback streams when the user interrupts by speaking.
- **MCP Tool Integration**: Seamlessly maps MCP tools to Gemini function declarations, executing tool requests on the robot and returning responses.

---

## Configuration and Setup

### 1. System Dependencies
Ensure you have the PortAudio library headers installed on your Linux system so that `pyaudio` can compile:
```bash
sudo apt-get install portaudio19-dev python3-pyaudio
```

### 2. Environment Variables (`.env`)
Configure your API Key and server URLs in the `.env` file:
```ini
GOOGLE_API_KEY=YOUR_GEMINI_API_KEY
SANCHO_MCP_LLM_MODEL=gemini-2.0-flash-exp
SANCHO_MCP_SERVER_URL=http://127.0.0.1:8000/mcp
```

### 3. Installation
The `run.sh` script automatically handles virtual environment creation and installation, but you can also install the dependencies manually:
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

---

## Running the Client

1. Start the Sancho MCP server (by default listening at `http://127.0.0.1:8000/mcp`).
2. Make sure your ROS camera topics are active or your local webcam is connected.
3. Run the live client script:
   ```bash
   ./run.sh
   ```
4. Start conversing with Sancho!
