#!/usr/bin/env python3
"""
Minimal Gemini Live audio test — matching official Google example pattern.
Key fixes:
  1. while True around session.receive() (re-enter after turn_complete)
  2. turn_coverage="TURN_INCLUDES_ONLY_ACTIVITY" in config
"""
import asyncio
import os
import sys
import time

from dotenv import load_dotenv
import pyaudio
import numpy as np
from google import genai
from google.genai import types

load_dotenv()

AUDIO_RATE = 16000
CHUNK_SIZE = 1024
PLAYBACK_RATE = 24000

_last_speaker_time: float = 0.0
ECHO_GUARD_SECONDS = 0.6


def find_respeaker(p: pyaudio.PyAudio) -> tuple[int | None, int]:
    for i in range(p.get_device_count()):
        try:
            dev = p.get_device_info_by_index(i)
            if dev.get("maxInputChannels", 0) > 0:
                name = dev.get("name", "").lower()
                if "xvf3800" in name or "respeaker" in name:
                    channels = int(dev["maxInputChannels"])
                    print(f"🎤 Found reSpeaker at index {i}: {dev['name']} (channels: {channels})")
                    return i, channels
        except Exception:
            pass
    return None, 1


async def send_audio(session, p: pyaudio.PyAudio, device_index: int | None, native_channels: int):
    global _last_speaker_time
    try:
        stream = p.open(
            format=pyaudio.paInt16,
            channels=native_channels,
            rate=AUDIO_RATE,
            input=True,
            input_device_index=device_index,
            frames_per_buffer=CHUNK_SIZE,
        )
        print(f"🎤 Mic stream opened (channels={native_channels})")
    except Exception as e:
        print(f"❌ Failed to open mic: {e}")
        return

    chunks_sent = 0
    was_speech = False
    try:
        while True:
            data = await asyncio.to_thread(
                stream.read, CHUNK_SIZE, exception_on_overflow=False
            )
            if not data:
                continue

            samples = np.frombuffer(data, dtype=np.int16)
            if native_channels > 1:
                mono_samples = samples[0::native_channels]
            else:
                mono_samples = samples

            rms = np.sqrt(np.mean(mono_samples.astype(float) ** 2))

            since_speaker = time.time() - _last_speaker_time
            is_muted = since_speaker < ECHO_GUARD_SECONDS

            if is_muted:
                mono_bytes = b'\x00' * (len(mono_samples) * 2)
            else:
                mono_bytes = mono_samples.tobytes()

            await session.send_realtime_input(
                audio=types.Blob(
                    data=mono_bytes, mime_type=f"audio/pcm;rate={AUDIO_RATE}"
                )
            )
            chunks_sent += 1

            is_speech = rms > 200
            if is_speech and not was_speech:
                label = "🔇(muted)" if is_muted else "🟢"
                print(f"  >> SPEECH START {label} chunk={chunks_sent} RMS={rms:.0f}")
            elif not is_speech and was_speech:
                print(f"  >> SPEECH END   chunk={chunks_sent} RMS={rms:.0f}")
            was_speech = is_speech

            if chunks_sent % 100 == 0:
                status = "🔇 MUTED" if is_muted else "🟢 LIVE"
                print(f"  [mic] {chunks_sent} chunks | RMS={rms:.1f} | {status}")

            await asyncio.sleep(0.005)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"❌ send_audio error: {e}")
    finally:
        stream.stop_stream()
        stream.close()


async def receive_and_play(session, p: pyaudio.PyAudio):
    global _last_speaker_time
    try:
        speaker = p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=PLAYBACK_RATE,
            output=True,
        )
        print("🔊 Speaker ready")
    except Exception as e:
        print(f"❌ Speaker failed: {e}")
        speaker = None

    try:
        # KEY FIX: wrap in while True — session.receive() exits after turn_complete
        while True:
            async for response in session.receive():
                sc = response.server_content

                if not sc:
                    continue

                if sc.interrupted:
                    print("\n⚡ [Interrupted by User]")
                    if speaker:
                        speaker.stop_stream()
                        speaker.start_stream()
                    continue

                if sc.turn_complete:
                    print("  📍 [turn_complete] — re-entering receive loop.")

                if sc.input_transcription:
                    print(f"\n👤 User: {sc.input_transcription.text}")

                if sc.output_transcription:
                    print(f"🤖 Gemini: {sc.output_transcription.text}", end="", flush=True)

                if sc.model_turn:
                    for part in sc.model_turn.parts:
                        if part.inline_data and speaker:
                            _last_speaker_time = time.time()
                            await asyncio.to_thread(speaker.write, part.inline_data.data)
                            _last_speaker_time = time.time()

            # session.receive() iterator completed — re-enter to keep listening
            print("  🔄 Receive iterator ended, re-entering...")

    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"❌ receive_and_play error: {e}")
    finally:
        if speaker:
            speaker.stop_stream()
            speaker.close()


async def main():
    api_key = os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        print("❌ GOOGLE_API_KEY not set"); sys.exit(1)

    model = os.environ.get("SANCHO_MCP_LLM_MODEL", "gemini-3.1-flash-live-preview")
    p = pyaudio.PyAudio()
    device_index, native_channels = find_respeaker(p)

    client = genai.Client(api_key=api_key)
    config = types.LiveConnectConfig(
        response_modalities=["AUDIO"],
        system_instruction=types.Content(
            parts=[types.Part.from_text(
                text="Eres Sancho, un robot. Habla siempre en español y sé breve."
            )]
        ),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        # KEY FIX: only include detected speech activity in user turns
        realtime_input_config=types.RealtimeInputConfig(
            turn_coverage="TURN_INCLUDES_ONLY_ACTIVITY",
        ),
    )

    print(f"\nConnecting to Gemini Live ({model})...")
    async with client.aio.live.connect(model=model, config=config) as session:
        print("✨ Connected! Speak into the microphone.\n")

        task_mic = asyncio.create_task(send_audio(session, p, device_index, native_channels))
        task_recv = asyncio.create_task(receive_and_play(session, p))
        await asyncio.gather(task_mic, task_recv)

    p.terminate()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n\nExiting test.")
