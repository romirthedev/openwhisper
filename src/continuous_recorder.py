"""
Continuous Flow recording mode.

While the hotkey is held, audio is captured and chunked every ~1.5 seconds.
Each chunk is transcribed immediately and injected — giving a near-real-time
"live typing" effect with no AI corrections (what you say is what gets typed).

Transcription accuracy is maximised by using faster-whisper's VAD filter so
silence-only chunks are skipped, and each chunk is transcribed independently
so no cross-chunk state accumulates.
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

SAMPLE_RATE = 16000
CHUNK_SECONDS = 1.5       # transcribe a chunk every N seconds while recording
MIN_CHUNK_SAMPLES = int(SAMPLE_RATE * 0.3)   # ignore clips shorter than 0.3 s


def _resolve_key(hotkey_str: str):
    """Maps config hotkey string → pynput Key (mirrors audio_recorder.py)."""
    if not PYNPUT_AVAILABLE:
        return None
    mapping = {
        "fn":         pynput_keyboard.Key.fn,
        "right_alt":  pynput_keyboard.Key.alt_r,
        "right_cmd":  pynput_keyboard.Key.cmd_r,
        "right_ctrl": pynput_keyboard.Key.ctrl_r,
        "caps_lock":  pynput_keyboard.Key.caps_lock,
    }
    for i in range(1, 13):
        mapping[f"f{i}"] = getattr(pynput_keyboard.Key, f"f{i}", None)
    return mapping.get(hotkey_str, pynput_keyboard.Key.fn)


class ContinuousRecorder:
    """
    Records audio while the hotkey is held and transcribes in ~1.5 s chunks.

    Callbacks
    ---------
    on_recording_start()
    on_recording_stop()
    on_chunk_ready(text: str)
        Called with each chunk's transcribed text so it can be injected
        immediately.  Text has no AI post-processing — accuracy is purely from
        the Whisper model.
    on_session_complete(full_text: str, duration: float)
        Called once when the key is released and all chunks are done.
    on_error(msg: str)
    """

    def __init__(
        self,
        hotkey: str = "fn",
        transcriber=None,
        on_recording_start: Optional[Callable] = None,
        on_recording_stop: Optional[Callable] = None,
        on_chunk_ready: Optional[Callable] = None,
        on_session_complete: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        self.hotkey = hotkey
        self.transcriber = transcriber
        self.on_recording_start   = on_recording_start  or (lambda: None)
        self.on_recording_stop    = on_recording_stop   or (lambda: None)
        self.on_chunk_ready       = on_chunk_ready      or (lambda t: None)
        self.on_session_complete  = on_session_complete or (lambda t, d: None)
        self.on_error             = on_error            or (lambda msg: None)

        self._is_recording = False
        self._lock = threading.Lock()
        self._stream = None
        self._listener = None
        self._target_key = _resolve_key(hotkey)

        # Audio buffer for the current in-progress chunk
        self._chunk_buf: list[np.ndarray] = []
        self._chunk_samples: int = 0
        self._chunk_timer: Optional[threading.Timer] = None

        # Accumulates all chunk texts for the full session transcript
        self._session_texts: list[str] = []
        self._session_start: float = 0.0

    # ------------------------------------------------------------------ #
    #  Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self):
        """Start the keyboard listener. Non-blocking."""
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
                "Grant Input Monitoring in System Settings → Privacy & Security."
            )

    def stop(self):
        if self._listener:
            self._listener.stop()
            self._listener = None
        self._cancel_timer()
        self._stop_stream()

    def update_hotkey(self, hotkey: str):
        self.hotkey = hotkey
        self._target_key = _resolve_key(hotkey)

    @property
    def is_recording(self) -> bool:
        return self._is_recording

    # ------------------------------------------------------------------ #
    #  Keyboard callbacks                                                   #
    # ------------------------------------------------------------------ #

    def _on_press(self, key):
        if key == self._target_key and not self._is_recording:
            self._begin_session()

    def _on_release(self, key):
        if key == self._target_key and self._is_recording:
            self._end_session()

    # ------------------------------------------------------------------ #
    #  Session lifecycle                                                    #
    # ------------------------------------------------------------------ #

    def _begin_session(self):
        with self._lock:
            self._is_recording = True
            self._chunk_buf = []
            self._chunk_samples = 0
            self._session_texts = []
            self._session_start = time.time()

        self.on_recording_start()

        try:
            self._stream = sd.InputStream(
                samplerate=SAMPLE_RATE,
                channels=1,
                dtype=np.float32,
                blocksize=int(SAMPLE_RATE * 0.1),  # 100 ms blocks
                callback=self._audio_callback,
            )
            self._stream.start()
        except Exception as exc:
            with self._lock:
                self._is_recording = False
            self.on_error(
                f"Microphone error: {exc}\n"
                "Grant Microphone access in System Settings → Privacy & Security."
            )
            return

        self._schedule_next_chunk()

    def _end_session(self):
        with self._lock:
            self._is_recording = False
            duration = time.time() - self._session_start
            remaining = (
                np.concatenate(self._chunk_buf) if self._chunk_buf else None
            )
            self._chunk_buf = []

        self._cancel_timer()
        self._stop_stream()
        self.on_recording_stop()

        if remaining is not None and len(remaining) >= MIN_CHUNK_SAMPLES:
            # Process leftover audio, then fire session_complete
            threading.Thread(
                target=self._process_chunk,
                args=(remaining, True, duration),
                daemon=True,
            ).start()
        else:
            full = " ".join(self._session_texts)
            self.on_session_complete(full, duration)

    # ------------------------------------------------------------------ #
    #  Chunk scheduling                                                     #
    # ------------------------------------------------------------------ #

    def _schedule_next_chunk(self):
        """Fire every CHUNK_SECONDS to drain the current buffer."""
        if not self._is_recording:
            return
        self._chunk_timer = threading.Timer(CHUNK_SECONDS, self._on_chunk_timer)
        self._chunk_timer.daemon = True
        self._chunk_timer.start()

    def _on_chunk_timer(self):
        with self._lock:
            if not self._is_recording or not self._chunk_buf:
                if self._is_recording:
                    self._schedule_next_chunk()
                return
            audio = np.concatenate(self._chunk_buf)
            self._chunk_buf = []
            self._chunk_samples = 0

        threading.Thread(
            target=self._process_chunk,
            args=(audio, False, None),
            daemon=True,
        ).start()
        self._schedule_next_chunk()

    def _cancel_timer(self):
        if self._chunk_timer:
            self._chunk_timer.cancel()
            self._chunk_timer = None

    # ------------------------------------------------------------------ #
    #  Transcription                                                        #
    # ------------------------------------------------------------------ #

    def _process_chunk(self, audio: np.ndarray, is_final: bool, duration: Optional[float]):
        if self.transcriber is None or not self.transcriber.is_ready:
            if is_final:
                self.on_session_complete(" ".join(self._session_texts), duration or 0)
            return

        text = self.transcriber.transcribe(audio)
        text = text.strip() if text else ""

        if text:
            with self._lock:
                self._session_texts.append(text)
            # Inject immediately — no AI correction in continuous mode
            self.on_chunk_ready(text)

        if is_final:
            full = " ".join(self._session_texts)
            self.on_session_complete(full, duration or 0)

    # ------------------------------------------------------------------ #
    #  Audio stream callback                                                #
    # ------------------------------------------------------------------ #

    def _audio_callback(self, indata: np.ndarray, frames: int, time_info, status):
        with self._lock:
            if self._is_recording:
                self._chunk_buf.append(indata[:, 0].copy())
                self._chunk_samples += frames

    # ------------------------------------------------------------------ #
    #  Cleanup                                                              #
    # ------------------------------------------------------------------ #

    def _stop_stream(self):
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
