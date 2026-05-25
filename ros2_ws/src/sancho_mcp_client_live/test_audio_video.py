#!/usr/bin/env python3
"""
Isolated audio + video test for Gemini Live.
Streams mic audio + ROS camera (or webcam fallback) to verify video works.
Ask Gemini "¿Qué ves?" to test visual understanding.

API recommendations: max 1 FPS, 768x768 resolution, JPEG format.
"""
import asyncio
import os
import sys
import time

from dotenv import load_dotenv
import cv2
import pyaudio
import numpy as np
from google import genai
from google.genai import types

load_dotenv()

# Try ROS imports
try:
    import rclpy
    from rclpy.node import Node
    from sensor_msgs.msg import Image
    from cv_bridge import CvBridge

    ROS_AVAILABLE = True
except ImportError:
    ROS_AVAILABLE = False
    print("⚠️ ROS 2 not available — will try local webcam.")

AUDIO_RATE = 16000
CHUNK_SIZE = 1024
PLAYBACK_RATE = 24000
VIDEO_FPS = 1.0  # max 1 frame/sec per API docs
VIDEO_SIZE = 768  # recommended native resolution

_last_speaker_time: float = 0.0
ECHO_GUARD_SECONDS = 0.6


# ---------------------------------------------------------------------------
# ROS Camera
# ---------------------------------------------------------------------------
if ROS_AVAILABLE:

    class CameraSubscriber(Node):
        def __init__(self):
            super().__init__("test_video_camera_sub")
            self.bridge = CvBridge()
            self.latest_frame = None
            self.frame_count = 0
            self.subscription = self.create_subscription(
                Image, "/sancho_camera/image_rect", self._on_image, 10
            )

        def _on_image(self, msg):
            try:
                self.latest_frame = self.bridge.imgmsg_to_cv2(
                    msg, desired_encoding="bgr8"
                )
                self.frame_count += 1
            except Exception as e:
                print(f"  ⚠️ CvBridge error: {e}")


# ---------------------------------------------------------------------------
# Hardware mic detection
# ---------------------------------------------------------------------------
def find_respeaker(p: pyaudio.PyAudio) -> tuple[int | None, int]:
    for i in range(p.get_device_count()):
        try:
            dev = p.get_device_info_by_index(i)
            if dev.get("maxInputChannels", 0) > 0:
                name = dev.get("name", "").lower()
                if "xvf3800" in name or "respeaker" in name:
                    ch = int(dev["maxInputChannels"])
                    print(f"🎤 Found reSpeaker index {i} ({ch} channels)")
                    return i, ch
        except Exception:
            pass
    return None, 1


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------
async def send_audio(session, p, dev_idx, native_ch):
    global _last_speaker_time
    try:
        mic = p.open(
            format=pyaudio.paInt16, channels=native_ch,
            rate=AUDIO_RATE, input=True, input_device_index=dev_idx,
            frames_per_buffer=CHUNK_SIZE,
        )
        print(f"🎤 Mic opened (channels={native_ch})")
    except Exception as e:
        print(f"❌ Mic failed: {e}"); return

    try:
        while True:
            raw = await asyncio.to_thread(mic.read, CHUNK_SIZE, False)
            if not raw:
                continue
            samples = np.frombuffer(raw, dtype=np.int16)
            mono = samples[0::native_ch] if native_ch > 1 else samples
            if time.time() - _last_speaker_time < ECHO_GUARD_SECONDS:
                data = b'\x00' * (len(mono) * 2)
            else:
                data = mono.tobytes()
            await session.send_realtime_input(
                audio=types.Blob(data=data, mime_type=f"audio/pcm;rate={AUDIO_RATE}")
            )
            await asyncio.sleep(0.005)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"❌ send_audio error: {e}")
    finally:
        mic.stop_stream(); mic.close()


async def send_video(session):
    """Streams video at 1 FPS. Resizes to 768x768 per API recommendation."""
    node = None
    if ROS_AVAILABLE:
        try:
            if not rclpy.ok():
                rclpy.init()
            node = CameraSubscriber()
            print("📷 ROS camera subscriber created.")
            # Wait a moment for first frame
            for _ in range(20):  # 2 seconds
                rclpy.spin_once(node, timeout_sec=0.1)
                if node.latest_frame is not None:
                    print(f"📷 ROS camera ready! First frame: {node.latest_frame.shape}")
                    break
            else:
                print("⚠️ No ROS frames received after 2s.")
        except Exception as e:
            print(f"⚠️ ROS camera init failed: {e}")
            node = None

    cap = None
    if node is None or node.latest_frame is None:
        print("📷 Trying local webcam...")
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            print("📷 Webcam opened.")
        else:
            print("❌ No camera available! Video input disabled.")
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
                # Resize to 768x768 as recommended by API
                h, w = frame.shape[:2]
                size = min(h, w)
                y_start = (h - size) // 2
                x_start = (w - size) // 2
                square = frame[y_start:y_start+size, x_start:x_start+size]
                resized = cv2.resize(square, (VIDEO_SIZE, VIDEO_SIZE))

                _, buf = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, 80])
                jpeg_bytes = buf.tobytes()

                await session.send_realtime_input(
                    video=types.Blob(data=jpeg_bytes, mime_type="image/jpeg")
                )
                frames_sent += 1
                print(f"  📷 Frame {frames_sent} sent ({len(jpeg_bytes)} bytes, {VIDEO_SIZE}x{VIDEO_SIZE})")
            else:
                if frames_sent == 0:
                    print("  📷 Waiting for camera frame...")

            await asyncio.sleep(1.0 / VIDEO_FPS)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"❌ send_video error: {e}")
    finally:
        if cap is not None:
            cap.release()
        if node is not None:
            node.destroy_node()


async def receive_and_play(session, p):
    global _last_speaker_time
    try:
        spk = p.open(format=pyaudio.paInt16, channels=1, rate=PLAYBACK_RATE, output=True)
        print("🔊 Speaker ready")
    except Exception as e:
        print(f"❌ Speaker failed: {e}"); spk = None

    try:
        while True:
            async for response in session.receive():
                sc = response.server_content
                if not sc:
                    continue
                if sc.interrupted:
                    print("\n⚡ [Interrupted]")
                    if spk: spk.stop_stream(); spk.start_stream()
                    continue
                if sc.input_transcription:
                    print(f"\n👤 User: {sc.input_transcription.text}")
                if sc.output_transcription:
                    print(f"🤖 Gemini: {sc.output_transcription.text}", end="", flush=True)
                if sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and spk:
                            _last_speaker_time = time.time()
                            await asyncio.to_thread(spk.write, part.inline_data.data)
                            _last_speaker_time = time.time()
                if sc.turn_complete:
                    print("\n  📍 [turn_complete]")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"❌ receive error: {e}")
    finally:
        if spk: spk.stop_stream(); spk.close()


async def main():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not set"); sys.exit(1)

    model = os.environ.get("SANCHO_MCP_LLM_MODEL", "gemini-3.1-flash-live-preview")
    p = pyaudio.PyAudio()
    dev_idx, native_ch = find_respeaker(p)

    client = genai.Client(api_key=api_key)
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part.from_text(
                text="Eres Sancho, un robot con cámara. Habla siempre en español y sé breve. "
                     "Cuando el usuario pregunte qué ves, describe la imagen de la cámara."
            )]
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            turn_coverage="TURN_INCLUDES_ONLY_ACTIVITY",
        ),
    )

    print(f"\nConnecting to Gemini Live ({model})...")
    async with client.aio.live.connect(model=model, config=config) as session:
        print("✨ Connected! Ask '¿Qué ves?' to test video.\n")

        tasks = [
            asyncio.create_task(send_audio(session, p, dev_idx, native_ch)),
            asyncio.create_task(send_video(session)),
            asyncio.create_task(receive_and_play(session, p)),
        ]
        await asyncio.gather(*tasks)

    p.terminate()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExiting test.")
