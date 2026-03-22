"""
Local speech-to-text transcription using Whisper.

Tries faster-whisper first (faster), then falls back to openai-whisper.
Model is loaded once and kept in memory.
"""
import threading
import numpy as np
from typing import Callable, Optional


class Transcriber:
    """
    Loads a Whisper model and transcribes float32 16kHz audio arrays.

    Callbacks:
        on_model_loading()       – model download/load started
        on_model_ready()         – model is loaded and ready
        on_error(msg)            – load or transcription error
    """

    def __init__(
        self,
        model_size: str = "base.en",
        language: Optional[str] = "en",
        on_model_loading: Optional[Callable] = None,
        on_model_ready: Optional[Callable] = None,
        on_error: Optional[Callable] = None,
    ):
        self.model_size = model_size
        self.language = language
        self.on_model_loading = on_model_loading or (lambda: None)
        self.on_model_ready = on_model_ready or (lambda: None)
        self.on_error = on_error or (lambda msg: None)

        self._model = None
        self._backend: Optional[str] = None  # 'faster' | 'openai'
        self._lock = threading.Lock()
        self._ready = threading.Event()

    # ------------------------------------------------------------------ #
    #  Public API                                                           #
    # ------------------------------------------------------------------ #

    def load_model_async(self):
        """Load the model in a background thread."""
        threading.Thread(target=self._load_model, daemon=True).start()

    def wait_until_ready(self, timeout: float = 120.0) -> bool:
        return self._ready.wait(timeout)

    @property
    def is_ready(self) -> bool:
        return self._ready.is_set()

    def transcribe(self, audio: np.ndarray) -> str:
        """
        Transcribe a float32 numpy array (16kHz mono).
        Blocks until complete. Returns the transcribed text, or "" on error.
        """
        if not self._ready.wait(timeout=120):
            self.on_error("Model not loaded yet.")
            return ""

        with self._lock:
            try:
                if self._backend == "faster":
                    return self._transcribe_faster(audio)
                else:
                    return self._transcribe_openai(audio)
            except Exception as exc:
                self.on_error(f"Transcription error: {exc}")
                return ""

    def update_model(self, model_size: str, language: Optional[str]):
        """Reload the model with new settings (runs in background)."""
        self._ready.clear()
        self._model = None
        self.model_size = model_size
        self.language = language
        self.load_model_async()

    # ------------------------------------------------------------------ #
    #  Internal                                                             #
    # ------------------------------------------------------------------ #

    def _load_model(self):
        self.on_model_loading()
        try:
            self._try_load_faster_whisper()
        except Exception:
            try:
                self._try_load_openai_whisper()
            except Exception as exc:
                self.on_error(
                    f"Could not load any Whisper backend: {exc}\n"
                    "Install with: pip install faster-whisper  OR  pip install openai-whisper"
                )
                return
        self._ready.set()
        self.on_model_ready()

    def _try_load_faster_whisper(self):
        from faster_whisper import WhisperModel  # noqa: PLC0415
        self._model = WhisperModel(
            self.model_size,
            device="cpu",
            compute_type="int8",
        )
        self._backend = "faster"

    def _try_load_openai_whisper(self):
        import whisper  # noqa: PLC0415
        # openai-whisper model names don't have ".en" suffix for the non-english models
        # but do support "base.en" etc.
        self._model = whisper.load_model(self.model_size)
        self._backend = "openai"

    def _transcribe_faster(self, audio: np.ndarray) -> str:
        segments, _ = self._model.transcribe(
            audio,
            language=self.language if self.language else None,
            beam_size=5,
            vad_filter=True,
            vad_parameters={"min_silence_duration_ms": 300},
        )
        return " ".join(seg.text.strip() for seg in segments).strip()

    def _transcribe_openai(self, audio: np.ndarray) -> str:
        import whisper  # noqa: PLC0415
        result = self._model.transcribe(
            audio,
            language=self.language if self.language else None,
            fp16=False,
        )
        return result["text"].strip()
