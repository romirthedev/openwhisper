"""
OpenWhisper – main application orchestrator.

Manages two recording modes:

  Standard mode  (default)
    Hold hotkey → record → release → transcribe full clip → AI cleanup → paste.
    Target latency after key release: ≤ 2 s for typical utterances.

  Continuous Flow mode
    Hold hotkey → audio chunked every ~1.5 s → each chunk transcribed &
    injected immediately → no AI corrections.
    Target latency per chunk: ~0.3–0.8 s after each 1.5 s window.
"""
import sys
import os
import queue
import threading

sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from storage import Storage
from audio_recorder import AudioRecorder
from continuous_recorder import ContinuousRecorder
from transcriber import Transcriber
from ai_processor import AIProcessor
from text_injector import TextInjector

MODE_STANDARD   = "standard"
MODE_CONTINUOUS = "continuous"


class OpenWhisperApp:
    """
    Central coordinator.  The UI instantiates this, registers event callbacks
    via `on(event, callback)`, then calls `start()` after the Tk loop begins.
    """

    def __init__(self):
        self.config = Config()
        self.storage = Storage()

        self._mode: str = self.config.get("mode", MODE_STANDARD)

        # ── Shared components ──────────────────────────────────────────── #

        self.transcriber = Transcriber(
            model_size=self.config["whisper_model"],
            language=self.config.get("language"),
            on_model_loading=self._on_model_loading,
            on_model_ready=self._on_model_ready,
            on_error=self._on_error,
        )

        self.ai_processor = AIProcessor(
            use_ollama=self.config["use_ai"],
            ollama_url=self.config["ollama_url"],
            ollama_model=self.config["ollama_model"],
        )

        self.text_injector = TextInjector(
            use_clipboard=self.config["use_clipboard_paste"],
        )

        # ── Standard recorder ──────────────────────────────────────────── #

        self._std_recorder = AudioRecorder(
            hotkey=self.config["hotkey"],
            on_recording_start=self._on_recording_start,
            on_recording_stop=self._on_recording_stop,
            on_audio_ready=self._on_audio_ready_standard,
            on_error=self._on_error,
        )

        # ── Continuous recorder ────────────────────────────────────────── #

        self._cont_recorder = ContinuousRecorder(
            hotkey=self.config["hotkey"],
            transcriber=self.transcriber,
            on_recording_start=self._on_recording_start,
            on_recording_stop=self._on_recording_stop,
            on_chunk_ready=self._on_chunk_ready_continuous,
            on_session_complete=self._on_session_complete_continuous,
            on_error=self._on_error,
        )

        # ── Event queue (background → UI) ──────────────────────────────── #
        self._events: queue.Queue = queue.Queue()

        self._ui_callbacks: dict[str, list] = {
            "recording_start":  [],
            "recording_stop":   [],
            "transcript_ready": [],
            "model_loading":    [],
            "model_ready":      [],
            "error":            [],
            "mode_changed":     [],
        }

    # ------------------------------------------------------------------ #
    #  Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def active_recorder(self):
        return self._cont_recorder if self._mode == MODE_CONTINUOUS else self._std_recorder

    # ------------------------------------------------------------------ #
    #  Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self):
        """Load model and activate the current recording mode."""
        self.transcriber.load_model_async()
        self.active_recorder.start()

    def stop(self):
        self._std_recorder.stop()
        self._cont_recorder.stop()

    def set_mode(self, mode: str):
        """Switch between MODE_STANDARD and MODE_CONTINUOUS at runtime."""
        if mode not in (MODE_STANDARD, MODE_CONTINUOUS):
            return
        if mode == self._mode:
            return

        # Stop old recorder, start new one
        self.active_recorder.stop()
        self._mode = mode
        self.config.set("mode", mode)
        self.active_recorder.start()

        self.emit("mode_changed", mode)

    def on(self, event: str, callback):
        if event in self._ui_callbacks:
            self._ui_callbacks[event].append(callback)

    def emit(self, event: str, *args):
        self._events.put((event, args))

    def poll_events(self):
        """Drain event queue — call from the UI thread via `root.after()`."""
        while not self._events.empty():
            try:
                event, args = self._events.get_nowait()
                for cb in self._ui_callbacks.get(event, []):
                    cb(*args)
            except queue.Empty:
                break

    def reload_settings(self):
        """Apply changed config without restarting the app."""
        self.config.load()

        new_hotkey = self.config["hotkey"]
        if new_hotkey != self._std_recorder.hotkey:
            self._std_recorder.update_hotkey(new_hotkey)
            self._cont_recorder.update_hotkey(new_hotkey)

        self.text_injector.use_clipboard = self.config["use_clipboard_paste"]

        self.ai_processor.use_ollama   = self.config["use_ai"]
        self.ai_processor.ollama_model = self.config["ollama_model"]
        self.ai_processor.ollama_url   = self.config["ollama_url"]

        new_model = self.config["whisper_model"]
        new_lang  = self.config.get("language")
        if new_model != self.transcriber.model_size or new_lang != self.transcriber.language:
            self.transcriber.update_model(new_model, new_lang)

    # ------------------------------------------------------------------ #
    #  Standard mode callbacks                                              #
    # ------------------------------------------------------------------ #

    def _on_audio_ready_standard(self, audio, duration: float):
        """Runs in a background thread spawned by AudioRecorder."""
        raw_text = self.transcriber.transcribe(audio)
        if not raw_text:
            return

        cleaned = (
            self.ai_processor.process(raw_text)
            if self.config["auto_format"]
            else raw_text
        )

        self.text_injector.inject(cleaned)
        self.storage.save_transcript(cleaned, raw_text=raw_text, duration=duration)
        self.emit("transcript_ready", cleaned, duration)

    # ------------------------------------------------------------------ #
    #  Continuous mode callbacks                                            #
    # ------------------------------------------------------------------ #

    def _on_chunk_ready_continuous(self, text: str):
        """
        Called by ContinuousRecorder every ~1.5 s with a transcribed chunk.
        Inject immediately without going through the clipboard to avoid
        interfering with rapid successive chunks.
        """
        self.text_injector.inject_immediate(text + " ")

    def _on_session_complete_continuous(self, full_text: str, duration: float):
        """Save the complete session transcript once recording ends."""
        if full_text:
            self.storage.save_transcript(
                full_text, raw_text=full_text, duration=duration
            )
            self.emit("transcript_ready", full_text, duration)

    # ------------------------------------------------------------------ #
    #  Shared recorder callbacks                                            #
    # ------------------------------------------------------------------ #

    def _on_recording_start(self):
        self.emit("recording_start")

    def _on_recording_stop(self):
        self.emit("recording_stop")

    def _on_model_loading(self):
        self.emit("model_loading")

    def _on_model_ready(self):
        self.emit("model_ready")

    def _on_error(self, msg: str):
        self.emit("error", msg)
