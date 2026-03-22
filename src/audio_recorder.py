"""
Audio recording with hotkey detection.

Listens for the configured hotkey (default: Fn key). While the key is held,
captures microphone audio. On release, passes the captured audio to the
on_audio_ready callback.

Requires Input Monitoring permission on macOS.
"""
import threading
import time
import numpy as np
from typing import Callable, Optional

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False

try:
    from pynput import keyboard as pynput_keyboard
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False

SAMPLE_RATE = 16000  # 16 kHz required by Whisper

# Maps config hotkey string to pynput Key constant
def _resolve_key(hotkey_str: str):
    if not PYNPUT_AVAILABLE:
        return None
    mapping = {
        "fn": pynput_keyboard.Key.fn,
        "right_alt": pynput_keyboard.Key.alt_r,
        "right_cmd": pynput_keyboard.Key.cmd_r,
        "right_ctrl": pynput_keyboard.Key.ctrl_r,
        "caps_lock": pynput_keyboard.Key.caps_lock,
    }
    for i in range(1, 13):
        mapping[f"f{i}"] = getattr(pynput_keyboard.Key, f"f{i}", None)
    return mapping.get(hotkey_str, pynput_keyboard.Key.fn)


class AudioRecorder:
    """
    Captures microphone audio while the hotkey is held down.

    Callbacks:
        on_recording_start()  – called when the key is first pressed
        on_recording_stop()   – called when the key is released (before transcription)
        on_audio_ready(audio: np.ndarray, duration: float) – called with captured audio
        on_error(msg: str)    – called on errors (permissions, device problems, etc.)
    """

    def __init__(
        self,
        hotkey: str = "fn",
        on_recording_start: Optional[Callable] = None,
        on_recording_stop: Optional[Callable] = None,
        on_audio_ready: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        self.hotkey = hotkey
        self.on_recording_start = on_recording_start or (lambda: None)
        self.on_recording_stop = on_recording_stop or (lambda: None)
        self.on_audio_ready = on_audio_ready or (lambda a, d: None)
        self.on_error = on_error or (lambda msg: None)

        self._is_recording = False
        self._audio_chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._stream: Optional[object] = None
        self._start_time: float = 0.0
        self._listener: Optional[object] = None
        self._target_key = _resolve_key(hotkey)

    # ------------------------------------------------------------------ #
    #  Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self):
        """Start listening for the hotkey. Non-blocking."""
        if not PYNPUT_AVAILABLE:
            self.on_error("pynput not installed. Run: pip install pynput")
            return
        if not SOUNDDEVICE_AVAILABLE:
            self.on_error("sounddevice not installed. Run: pip install sounddevice")
            return

        try:
            self._listener = pynput_keyboard.Listener(
                on_press=self._on_press,
                on_release=self._on_release,
            )
            self._listener.start()
        except Exception as exc:
            self.on_error(
                f"Failed to start keyboard listener: {exc}\n"
                "Grant Input Monitoring permission in System Settings → Privacy & Security."
            )

    def stop(self):
        """Stop listening and clean up."""
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._stop_audio_stream()

    def update_hotkey(self, hotkey: str):
        self.hotkey = hotkey
        self._target_key = _resolve_key(hotkey)

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    # ------------------------------------------------------------------ #
    #  Internal                                                             #
    # ------------------------------------------------------------------ #

    def _on_press(self, key):
        if key == self._target_key and not self._is_recording:
            self._begin_recording()

    def _on_release(self, key):
        if key == self._target_key and self._is_recording:
            self._end_recording()

    def _begin_recording(self):
        with self._lock:
            self._is_recording = True
            self._audio_chunks = []
            self._start_time = time.time()

        self.on_recording_start()

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype=np.float32,
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as exc:
            self._is_recording = False
            self.on_error(
                f"Microphone error: {exc}\n"
                "Grant Microphone permission in System Settings → Privacy & Security."
            )

    def _end_recording(self):
        with self._lock:
            self._is_recording = False
            duration = time.time() - self._start_time
            chunks = list(self._audio_chunks)

        self._stop_audio_stream()
        self.on_recording_stop()

        if not chunks:
            return

        audio = np.concatenate(chunks)

        # Minimum length: 0.3 s to avoid noise blips
        if len(audio) < SAMPLE_RATE * 0.3:
            return

        # Run transcription in a background thread so we don't block the listener
        threading.Thread(
            target=self.on_audio_ready,
            args=(audio, duration),
            daemon=True,
        ).start()

    def _stop_audio_stream(self):
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        with self._lock:
            if self._is_recording:
                self._audio_chunks.append(indata[:, 0].copy())
