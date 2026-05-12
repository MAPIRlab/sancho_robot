import threading
import ctypes
from contextlib import contextmanager
from enum import Enum, auto
import numpy as np
import pyaudio

import rclpy
from rclpy.lifecycle import LifecycleNode, State, TransitionCallbackReturn

from std_msgs.msg import Empty
from sancho_interfaces.msg import ChunkMono
from sancho_interfaces.srv import SetAudioSession


# ---------------------------------------------------------------------------
# ALSA error suppression (avoids noisy "underrun" log spam)
# ---------------------------------------------------------------------------

_ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(
    None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p
)


def _py_error_handler(filename, line, function, err, fmt):  # noqa: D401
    pass


_c_error_handler = _ERROR_HANDLER_FUNC(_py_error_handler)


@contextmanager
def _no_alsa_err():
    try:
        asound = ctypes.cdll.LoadLibrary("libasound.so.2")
        asound.snd_lib_error_set_handler(_c_error_handler)
        yield
        asound.snd_lib_error_set_handler(None)
    except Exception:
        yield


# ---------------------------------------------------------------------------
# ALSA error suppression (avoids noisy "underrun" log spam)
# ---------------------------------------------------------------------------

_ERROR_HANDLER_FUNC = ctypes.CFUNCTYPE(
    None, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p
)


def _py_error_handler(filename, line, function, err, fmt):  # noqa: D401
    pass


_c_error_handler = _ERROR_HANDLER_FUNC(_py_error_handler)


@contextmanager
def _no_alsa_err():
    try:
        asound = ctypes.cdll.LoadLibrary("libasound.so.2")
        asound.snd_lib_error_set_handler(_c_error_handler)
        yield
        asound.snd_lib_error_set_handler(None)
    except Exception:
        yield


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------


class _GatewayMode(Enum):
    LISTENING = auto()     # OWW runs in-process; no audio on the ROS bus
    CONVERSATION = auto()  # ChunkMono is published; OWW is suspended


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------


class AudioGatewayNode(LifecycleNode):
    """Single owner of the microphone stream and audio session lifecycle.

    In **LISTENING** mode the node runs OpenWakeWord (OWW) directly against
    the PyAudio buffer — nothing is published over ROS.  When the hotword
    fires it publishes an ``Empty`` event and waits for the Behavior Tree to
    call :srv:`SetAudioSession` to open a session.

    In **CONVERSATION** mode the node publishes ``ChunkMono`` on the
    configured topic for as long as the BT keeps the session open.  There is
    no hard time-limit; the BT decides when to close the session by calling
    ``SetAudioSession(active=False)``.
    """

    def __init__(self):
        super().__init__("audio_gateway")

        self.declare_parameters(
            namespace="",
            parameters=[
                ("device_name", "xvf3800"),
                ("chunk_size", 1024),
                # Index of the channel to extract as mono (0 = left/first).
                # Change this if the XVF3800 DSP output is on a different channel.
                ("mic_channel", 0),
                ("hotword_event_topic", "/voice_events/hotword_detected"),
                ("audio_topic", "sancho_audio/microphone/mono"),
                ("set_audio_session_service", "sancho_audio/set_audio_session"),
            ],
        )

        # populated during configure / activate
        self._oww = None
        self._pa: pyaudio.PyAudio | None = None
        self._stream: pyaudio.Stream | None = None
        self._hotword_pub = None
        self._mono_pub = None
        self._session_srv = None
        self._thread = None
        self._running = False

        self._mode = _GatewayMode.LISTENING
        self._sample_rate: int = 16000
        self._num_channels: int = 1
        self._mic_channel: int = 0
        self._chunk_size: int = 1280 #specific to the traning of the onnx model

    # ------------------------------------------------------------------
    # Lifecycle callbacks
    # ------------------------------------------------------------------

    def on_configure(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Configuring AudioGatewayNode…")

        try:
            from .utils.openwakeword_hotword import OpenWakeWordHotword  # lazy import
            self._oww = OpenWakeWordHotword()
        except Exception as exc:
            self.get_logger().error(f"Failed to load OWW model: {exc}")
            return TransitionCallbackReturn.FAILURE

        hotword_topic = self.get_parameter("hotword_event_topic").value
        audio_topic = self.get_parameter("audio_topic").value
        session_srv_name = self.get_parameter("set_audio_session_service").value

        self._hotword_pub = self.create_lifecycle_publisher(Empty, hotword_topic, 10)
        self._mono_pub = self.create_lifecycle_publisher(ChunkMono, audio_topic, 10)
        self._session_srv = self.create_service(
            SetAudioSession, session_srv_name, self._on_set_audio_session
        )

        self.get_logger().info("AudioGatewayNode configured.")
        return TransitionCallbackReturn.SUCCESS

    def on_activate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Activating AudioGatewayNode — opening mic stream…")

        self._chunk_size = self.get_parameter("chunk_size").value
        self._mic_channel = self.get_parameter("mic_channel").value
        device_name = self.get_parameter("device_name").value

        with _no_alsa_err():
            self._pa = pyaudio.PyAudio()

        device = self._find_device(device_name)
        if device is None:
            self.get_logger().error(f"Mic device '{device_name}' not found.")
            return TransitionCallbackReturn.FAILURE

        self._sample_rate = int(device.get("defaultSampleRate", 16000))
        self._num_channels = 1 # Force MONO

        try:
            self._stream = self._pa.open(
                format=pyaudio.paInt16,
                channels=self._num_channels,
                rate=self._sample_rate,
                input=True,
                frames_per_buffer=self._chunk_size,
                input_device_index=device["index"],
            )
        except Exception as exc:
            self.get_logger().error(f"Failed to open mic stream: {exc}")
            return TransitionCallbackReturn.FAILURE

        self.get_logger().info(
            f"Mic='{device['name']}' sr={self._sample_rate}Hz "
            f"ch={self._num_channels} chunk={self._chunk_size} → LISTENING mode"
        )

        self._running = True
        self._thread = threading.Thread(target=self._audio_loop, daemon=True)
        self._thread.start()

        return super().on_activate(state)

    def on_deactivate(self, state: State) -> TransitionCallbackReturn:
        self.get_logger().info("Deactivating AudioGatewayNode…")
        self._stop_thread()
        self._close_stream()
        self._mode = _GatewayMode.LISTENING
        return super().on_deactivate(state)

    def on_cleanup(self, state: State) -> TransitionCallbackReturn:
        self._stop_thread()
        self._close_stream()
        self._oww = None
        return TransitionCallbackReturn.SUCCESS

    def on_shutdown(self, state: State) -> TransitionCallbackReturn:
        self._stop_thread()
        self._close_stream()
        return TransitionCallbackReturn.SUCCESS

    def _stop_thread(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)
            self._thread = None

    # ------------------------------------------------------------------
    # Core audio loop (runs in background thread)
    # ------------------------------------------------------------------

    def _audio_loop(self):
        while self._running:
            try:
                raw = self._stream.read(self._chunk_size, exception_on_overflow=False)
            except Exception as exc:
                self.get_logger().warn(f"Stream read error: {exc} — skipping chunk")
                continue

            pcm = np.frombuffer(raw, dtype=np.int16)

            # Extract the configured channel from interleaved multi-channel data
            if self._num_channels > 1:
                mono_np = pcm[self._mic_channel :: self._num_channels]
            else:
                mono_np = pcm

            # Always run OWW detection (allows re-triggers during conversation)
            mono_list = mono_np.tolist()
            if self._oww.detect(mono_list, self._sample_rate):
                self.get_logger().info("🔔 Hotword detected!")
                self._hotword_pub.publish(Empty())

            # Only publish to ROS if we are in CONVERSATION mode
            if self._mode is _GatewayMode.CONVERSATION:
                msg = ChunkMono(sample_rate=self._sample_rate)
                msg.chunk_mono = mono_list
                self._mono_pub.publish(msg)


    def _on_set_audio_session(
        self, request: SetAudioSession.Request, response: SetAudioSession.Response
    ) -> SetAudioSession.Response:
        if request.active:
            if self._mode is _GatewayMode.CONVERSATION:
                response.accepted = True
                response.message = "Already in CONVERSATION mode."
            else:
                self._mode = _GatewayMode.CONVERSATION
                self.get_logger().info("▶ Audio session STARTED — streaming ChunkMono")
                response.accepted = True
                response.message = "Session started."
        else:
            if self._mode is _GatewayMode.LISTENING:
                response.accepted = True
                response.message = "Already in LISTENING mode."
            else:
                self._mode = _GatewayMode.LISTENING
                self.get_logger().info("⏸ Audio session ENDED — back to hotword detection")
                response.accepted = True
                response.message = "Session ended."

        return response

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _find_device(self, name_substr: str) -> dict | None:
        """Return the first input device whose name contains name_substr.

        All matching devices are logged so the user can verify which one
        is selected and spot alternative subdevices on the same hardware.
        """
        first_match = None
        for i in range(self._pa.get_device_count()):
            dev = self._pa.get_device_info_by_index(i)
            if dev.get("maxInputChannels", 0) > 0 and name_substr.lower() in dev["name"].lower():
                self.get_logger().info(
                    f"[device scan] idx={i} name='{dev['name']}' "
                    f"ch={dev['maxInputChannels']} sr={int(dev['defaultSampleRate'])}Hz"
                )
                if first_match is None:
                    d = dict(dev)
                    d["index"] = i
                    first_match = d
        return first_match

    def _cancel_timer(self):
        pass # removed timer usage

    def _close_stream(self):
        if self._stream:
            try:
                self._stream.stop_stream()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        if self._pa:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main(args=None):
    rclpy.init(args=args)
    node = AudioGatewayNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()
