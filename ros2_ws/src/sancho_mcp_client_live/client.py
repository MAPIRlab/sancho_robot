"""Sancho MCP Live Client — real-time voice & video interaction via Gemini Live API.

Streams microphone audio and (optionally) ROS camera frames to Gemini Live,
plays back model audio responses, and dispatches tool calls to the MCP server.
"""
from __future__ import annotations

import asyncio
import base64
import logging
import os
from pathlib import Path
import time
from typing import Any

from dotenv import load_dotenv
import cv2
import pyaudio
import numpy as np
from google import genai
from google.genai import types

from langchain_mcp_adapters.sessions import create_session

# ---------------------------------------------------------------------------
# Optional ROS 2 imports (graceful degradation when ROS is not sourced)
# ---------------------------------------------------------------------------
try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import Image
    from cv_bridge import CvBridge

    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("sancho_mcp_client_live")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
DEFAULT_PROMPT_PATH = Path(__file__).resolve().parent / "SYSTEM_PROMPT.md"
AUDIO_INPUT_RATE = 16000  # mic capture rate (Hz)
AUDIO_OUTPUT_RATE = 24000  # Gemini playback rate (Hz)
CHUNK_SIZE = 1024  # samples per mic read
ECHO_GUARD_SECONDS = 0.6  # mute mic this long after speaker stops
VIDEO_SIZE = 768  # recommended native resolution

# Shared mutable state for echo suppression
_last_speaker_time: float = 0.0


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def load_system_prompt() -> str:
    """Load the system prompt from disk or use a sensible default."""
    prompt_path = Path(
        os.environ.get("SANCHO_SYSTEM_PROMPT_PATH", str(DEFAULT_PROMPT_PATH))
    )
    if not prompt_path.exists():
        return "You are controlling Sancho, a mobile robot. Use the MCP tools."
    return prompt_path.read_text(encoding="utf-8")


def mcp_schema_to_gemini_schema(schema: dict) -> dict:
    """Recursively converts an MCP inputSchema (JSON Schema) to Gemini Schema dict."""
    gemini_schema = {}
    if "type" in schema:
        t = schema["type"]
        gemini_schema["type"] = t.upper() if isinstance(t, str) else t
    if "description" in schema:
        gemini_schema["description"] = schema["description"]
    if "properties" in schema:
        gemini_schema["properties"] = {
            k: mcp_schema_to_gemini_schema(v)
            for k, v in schema["properties"].items()
        }
    if "required" in schema:
        gemini_schema["required"] = schema["required"]
    if "items" in schema:
        gemini_schema["items"] = mcp_schema_to_gemini_schema(schema["items"])
    if "enum" in schema:
        gemini_schema["enum"] = schema["enum"]
    return gemini_schema


def mcp_tool_to_gemini_declaration(tool: Any) -> types.FunctionDeclaration:
    """Converts an MCP tool object into a Gemini FunctionDeclaration."""
    params = None
    if tool.inputSchema:
        params = mcp_schema_to_gemini_schema(tool.inputSchema)
    return types.FunctionDeclaration(
        name=tool.name,
        description=tool.description or "",
        parameters=params,
    )


def find_hardware_mic(p: pyaudio.PyAudio) -> tuple[int | None, int]:
    """Scan PyAudio devices for the reSpeaker XVF3800 hardware mic array.

    Returns (device_index, native_channel_count).
    Falls back to (None, 1) if not found (uses OS default).
    """
    for i in range(p.get_device_count()):
        try:
            dev = p.get_device_info_by_index(i)
            if dev.get("maxInputChannels", 0) > 0:
                name = dev.get("name", "").lower()
                if "xvf3800" in name or "respeaker" in name:
                    channels = int(dev["maxInputChannels"])
                    print(
                        f"🎤 Selected hardware microphone: "
                        f"{dev.get('name')} (Index {i}, channels={channels})"
                    )
                    return i, channels
        except Exception:
            pass
    return None, 1


# ---------------------------------------------------------------------------
# ROS 2 camera subscriber (optional)
# ---------------------------------------------------------------------------
if ROS_AVAILABLE:

    class CameraSubscriber(Node):
        """ROS 2 Node subscribing to the robot's camera topic."""

        def __init__(self):
            super().__init__("live_client_camera_subscriber")
            self.bridge = CvBridge()
            self.latest_frame = None
            self.subscription = self.create_subscription(
                Image,
                "/sancho_camera/image_rect",
                self._on_image,
                10,
            )

        def _on_image(self, msg):
            try:
                self.latest_frame = self.bridge.imgmsg_to_cv2(
                    msg, desired_encoding="bgr8"
                )
            except Exception as e:
                logger.debug(f"CvBridge conversion error: {e}")


# ---------------------------------------------------------------------------
# Streaming tasks
# ---------------------------------------------------------------------------
async def send_audio(
    session: Any,
    p: pyaudio.PyAudio,
    device_index: int | None,
    native_channels: int,
) -> None:
    """Captures microphone audio, extracts mono channel 0, and streams to Gemini."""
    global _last_speaker_time

    try:
        mic_stream = p.open(
            format=pyaudio.paInt16,
            channels=native_channels,
            rate=AUDIO_INPUT_RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK_SIZE,
        )
    except Exception as e:
        print(f"⚠️ Could not open microphone: {e}")
        return

    if device_index is None:
        print("🎤 Connected to default microphone.")

    try:
        while True:
            raw = await asyncio.to_thread(
                mic_stream.read, CHUNK_SIZE, exception_on_overflow=False
            )
            if not raw:
                continue

            samples = np.frombuffer(raw, dtype=np.int16)

            # Extract channel 0 as mono when device is multi-channel
            if native_channels > 1:
                mono = samples[0::native_channels]
            else:
                mono = samples

            # Echo suppression: send silence while speaker is active
            if time.time() - _last_speaker_time < ECHO_GUARD_SECONDS:
                payload = b"\x00" * (len(mono) * 2)
            else:
                payload = mono.tobytes()

            await session.send_realtime_input(
                audio=types.Blob(
                    data=payload,
                    mime_type=f"audio/pcm;rate={AUDIO_INPUT_RATE}",
                )
            )
            # Give event loop time for WebSocket keepalive pings
            await asyncio.sleep(0.005)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"send_audio error: {e}")
    finally:
        mic_stream.stop_stream()
        mic_stream.close()


async def send_video(session: Any) -> None:
    """Streams camera frames at ≤1 Hz from ROS topic, falling back to webcam.

    Resizes/crops frames to a 768x768 square as recommended by Gemini Live API.
    """
    node = None
    if ROS_AVAILABLE:
        try:
            if not rclpy.ok():
                rclpy.init()
            node = CameraSubscriber()
            logger.info("📷 ROS camera subscriber created. Waiting for frames...")
            # Wait up to 2 seconds for the first frame
            for _ in range(20):
                rclpy.spin_once(node, timeout_sec=0.1)
                if node.latest_frame is not None:
                    logger.info(f"📷 ROS camera ready! First frame: {node.latest_frame.shape}")
                    break
            else:
                logger.warning("⚠️ No ROS camera frames received after 2 seconds.")
        except Exception as e:
            logger.warning(f"ROS camera initialization failed: {e}")
            node = None

    cap = None
    if node is None or node.latest_frame is None:
        logger.info("📷 Trying local webcam as fallback...")
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            logger.info("📷 Webcam opened successfully.")
        else:
            logger.warning("❌ No camera available! Video input disabled.")
            cap = None

    frames_sent = 0
    try:
        while True:
            frame = None

            if node is not None:
                rclpy.spin_once(node, timeout_sec=0.01)
                frame = node.latest_frame

            if frame is None and cap is not None:
                ret, frame = cap.read()
                if not ret:
                    frame = None

            if frame is not None:
                # Crop to square and resize to 768x768
                h, w = frame.shape[:2]
                size = min(h, w)
                y_start = (h - size) // 2
                x_start = (w - size) // 2
                square = frame[y_start:y_start + size, x_start:x_start + size]
                resized = cv2.resize(square, (VIDEO_SIZE, VIDEO_SIZE))

                _, buf = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
                jpeg_bytes = buf.tobytes()

                await session.send_realtime_input(
                    video=types.Blob(data=jpeg_bytes, mime_type="image/jpeg")
                )
                frames_sent += 1
                logger.debug(f"Frame {frames_sent} sent ({len(jpeg_bytes)} bytes)")
            else:
                if frames_sent == 0:
                    logger.info("📷 Waiting for camera frame...")

            await asyncio.sleep(1.0)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"send_video error: {e}")
    finally:
        if cap is not None:
            cap.release()
        if node is not None:
            node.destroy_node()


# ---------------------------------------------------------------------------
# Tool call handling
# ---------------------------------------------------------------------------
async def handle_tool_call(
    session: Any, mcp_session: Any, tool_call: Any
) -> None:
    """Executes incoming tool calls on the MCP server and sends results back."""
    function_responses = []
    for fc in tool_call.function_calls:
        print(f"\n🔧 [Tool Call] {fc.name}({fc.args})")
        try:
            result = await mcp_session.call_tool(fc.name, fc.args)
            response_data: dict[str, Any] = {"status": "success"}
            text_parts: list[str] = []

            for block in result.content:
                if block.type == "text":
                    text_parts.append(block.text)
                elif block.type == "image":
                    try:
                        image_bytes = base64.b64decode(block.data)
                        await session.send_realtime_input(
                            video=types.Blob(
                                data=image_bytes,
                                mime_type=block.mimeType or "image/jpeg",
                            )
                        )
                        text_parts.append("[Image streamed to visual context]")
                        print("   📸 Image injected into Gemini visual stream.")
                    except Exception as img_err:
                        text_parts.append(f"[Image error: {img_err}]")

            response_data["result"] = "\n".join(text_parts)
            print(f"   ✅ {response_data['result']}")
        except Exception as e:
            logger.error(f"Tool {fc.name} failed: {e}")
            response_data = {"status": "error", "error": str(e)}

        function_responses.append(
            types.FunctionResponse(
                name=fc.name, id=fc.id, response=response_data
            )
        )

    await session.send_tool_response(function_responses=function_responses)


# ---------------------------------------------------------------------------
# Receive loop
# ---------------------------------------------------------------------------
async def receive_and_play(
    session: Any, mcp_session: Any, p: pyaudio.PyAudio
) -> None:
    """Receives Gemini Live responses — plays audio and dispatches tool calls.

    Wraps session.receive() in `while True` because the iterator exits after
    each turn_complete and must be re-entered for multi-turn conversation.
    """
    global _last_speaker_time

    try:
        speaker = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=AUDIO_OUTPUT_RATE,
            output=True,
        )
        print("🔊 Speaker playback connected.")
    except Exception as e:
        print(f"⚠️ Speaker unavailable: {e}")
        speaker = None

    try:
        while True:  # re-enter after each turn_complete
            async for response in session.receive():
                sc = response.server_content

                # Handle tool calls
                if response.tool_call:
                    await handle_tool_call(
                        session, mcp_session, response.tool_call
                    )
                    continue

                # Skip non-content messages (session_resumption_update, etc.)
                if not sc:
                    continue

                # User barge-in
                if sc.interrupted:
                    print("\n⚡ [Interrupted by User]")
                    if speaker:
                        speaker.stop_stream()
                        speaker.start_stream()
                    continue

                # Transcriptions
                if sc.input_transcription:
                    print(f"\n👤 User: {sc.input_transcription.text}")
                if sc.output_transcription:
                    print(
                        f"🤖 Gemini: {sc.output_transcription.text}",
                        end="",
                        flush=True,
                    )

                # Audio playback
                if sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and speaker:
                            _last_speaker_time = time.time()
                            await asyncio.to_thread(
                                speaker.write, part.inline_data.data
                            )
                            _last_speaker_time = time.time()

                if sc.turn_complete:
                    logger.debug("Turn complete — re-entering receive loop.")

    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"receive_and_play error: {e}")
    finally:
        if speaker:
            speaker.stop_stream()
            speaker.close()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------
async def main() -> None:
    load_dotenv()
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is required.")

    mcp_server_url = os.environ.get(
        "SANCHO_MCP_SERVER_URL", "http://127.0.0.1:8000/mcp"
    )
    model = os.environ.get(
        "SANCHO_MCP_LLM_MODEL", "gemini-3.1-flash-live-preview"
    )
    system_prompt = load_system_prompt()

    # --- PyAudio & hardware mic detection (shared across tasks) ---
    p = pyaudio.PyAudio()
    device_index, native_channels = find_hardware_mic(p)

    # --- MCP connection ---
    connection = {"transport": "streamable_http", "url": mcp_server_url}
    print(f"Connecting to MCP server at {mcp_server_url}...")

    async with create_session(connection) as mcp_session:
        await mcp_session.initialize()

        mcp_tools_list = await mcp_session.list_tools()
        function_declarations = [
            mcp_tool_to_gemini_declaration(t) for t in mcp_tools_list.tools
        ]

        print("\nExposing MCP Tools to Gemini Live:")
        for fd in function_declarations:
            print(f"  • {fd.name}: {fd.description}")

        # --- Gemini Live session ---
        client = genai.Client(api_key=api_key)
        config = types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            system_instruction=types.Content(
                parts=[types.Part.from_text(text=system_prompt)]
            ),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                turn_coverage="TURN_INCLUDES_ONLY_ACTIVITY",
            ),
            tools=[types.Tool(function_declarations=function_declarations)],
        )

        print(f"\nConnecting to Gemini Live ({model})...")
        async with client.aio.live.connect(
            model=model, config=config
        ) as session:
            print("✨ Gemini Live connection established! Speak to Sancho.\n")

            tasks = [
                asyncio.create_task(
                    send_audio(session, p, device_index, native_channels)
                ),
                asyncio.create_task(send_video(session)),
                asyncio.create_task(
                    receive_and_play(session, mcp_session, p)
                ),
            ]
            await asyncio.gather(*tasks)

    p.terminate()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting live client.")
