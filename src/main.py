"""
OpenWhisper – main application orchestrator.

Wires together the audio recorder, transcriber, AI processor, text injector,
and UI. Runs as a standard macOS desktop app (no menubar-only mode).
"""
import sys
import os
import queue
import threading

# Ensure src/ is on the path when run directly
sys.path.insert(0, os.path.dirname(__file__))

from config import Config
from storage import Storage
from audio_recorder import AudioRecorder
from transcriber import Transcriber
from ai_processor import AIProcessor
from text_injector import TextInjector


class OpenWhisperApp:
    """
    Central coordinator. The UI imports and instantiates this class, then
    calls `start()` after the Tk main loop is running.
    """

    def __init__(self):
        self.config = Config()
        self.storage = Storage()

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

        self.recorder = AudioRecorder(
            hotkey=self.config["hotkey"],
            on_recording_start=self._on_recording_start,
            on_recording_stop=self._on_recording_stop,
            on_audio_ready=self._on_audio_ready,
            on_error=self._on_error,
        )

        # Thread-safe event queue consumed by the UI via polling
        self._events: queue.Queue = queue.Queue()

        # Callbacks registered by the UI
        self._ui_callbacks: dict[str, list] = {
            "recording_start": [],
            "recording_stop": [],
            "transcript_ready": [],
            "model_loading": [],
            "model_ready": [],
            "error": [],
        }

    # ------------------------------------------------------------------ #
    #  Public API                                                           #
    # ------------------------------------------------------------------ #

    def start(self):
        """Load model and start listening for the hotkey."""
        self.transcriber.load_model_async()
        self.recorder.start()

    def stop(self):
        self.recorder.stop()

    def on(self, event: str, callback):
        """Register a UI callback for a named event."""
        if event in self._ui_callbacks:
            self._ui_callbacks[event].append(callback)

    def emit(self, event: str, *args):
        """Post an event onto the queue (safe from any thread)."""
        self._events.put((event, args))

    def poll_events(self):
        """
        Drain the event queue and invoke registered callbacks.
        Should be called from the UI thread (e.g. via `root.after(100, ...)`).
        """
        while not self._events.empty():
            try:
                event, args = self._events.get_nowait()
                for cb in self._ui_callbacks.get(event, []):
                    cb(*args)
            except queue.Empty:
                break

    def reload_settings(self):
        """Apply changed settings without restarting the app."""
        self.config.load()

        new_hotkey = self.config["hotkey"]
        if new_hotkey != self.recorder.hotkey:
            self.recorder.update_hotkey(new_hotkey)

        self.text_injector.use_clipboard = self.config["use_clipboard_paste"]

        self.ai_processor.use_ollama = self.config["use_ai"]
        self.ai_processor.ollama_model = self.config["ollama_model"]
        self.ai_processor.ollama_url = self.config["ollama_url"]

        new_model = self.config["whisper_model"]
        new_lang = self.config.get("language")
        if new_model != self.transcriber.model_size or new_lang != self.transcriber.language:
            self.transcriber.update_model(new_model, new_lang)

    # ------------------------------------------------------------------ #
    #  Audio recorder callbacks (background threads)                        #
    # ------------------------------------------------------------------ #

    def _on_recording_start(self):
        self.emit("recording_start")

    def _on_recording_stop(self):
        self.emit("recording_stop")

    def _on_audio_ready(self, audio, duration: float):
        """Runs in a background thread spawned by AudioRecorder."""
        self.emit("recording_stop")  # ensure UI shows "processing" state

        raw_text = self.transcriber.transcribe(audio)
        if not raw_text:
            return

        cleaned = self.ai_processor.process(raw_text) if self.config["auto_format"] else raw_text

        # Inject text at cursor
        self.text_injector.inject(cleaned)

        # Persist
        self.storage.save_transcript(cleaned, raw_text=raw_text, duration=duration)

        self.emit("transcript_ready", cleaned, duration)

    # ------------------------------------------------------------------ #
    #  Transcriber callbacks (background threads)                           #
    # ------------------------------------------------------------------ #

    def _on_model_loading(self):
        self.emit("model_loading")

    def _on_model_ready(self):
        self.emit("model_ready")

    def _on_error(self, msg: str):
        self.emit("error", msg)
