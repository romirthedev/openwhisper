"""
Configuration management for OpenWhisper.
Settings are persisted to ~/.openwhisper/config.json.
"""
import json
from pathlib import Path

APP_DIR = Path.home() / ".openwhisper"
CONFIG_FILE = APP_DIR / "config.json"
DB_FILE = APP_DIR / "transcripts.db"

DEFAULTS = {
    # Input hotkey: 'fn', 'right_alt', 'right_cmd', 'right_ctrl', 'f1'-'f12'
    "hotkey": "fn",
    # Whisper model size: 'tiny.en', 'base.en', 'small.en', 'medium.en', 'large-v3'
    "whisper_model": "base.en",
    # Whether to use Ollama LLM for smart post-processing
    "use_ai": False,
    "ollama_model": "llama3.1",
    "ollama_url": "http://localhost:11434",
    # Transcription language (None = auto-detect)
    "language": "en",
    # Whether to inject text via clipboard paste (True) or direct typing (False)
    "use_clipboard_paste": True,
    # UI theme: 'dark', 'light', 'system'
    "theme": "dark",
    # Whether to auto-format text (punctuation, capitalization)
    "auto_format": True,
    # Recording mode: 'standard' (wait→correct→paste) or 'continuous' (live typing)
    "mode": "standard",
}


class Config:
    def __init__(self):
        APP_DIR.mkdir(parents=True, exist_ok=True)
        self._data = dict(DEFAULTS)
        self.load()

    def load(self):
        if CONFIG_FILE.exists():
            try:
                with open(CONFIG_FILE) as f:
                    saved = json.load(f)
                self._data.update(saved)
            except Exception:
                pass

    def save(self):
        with open(CONFIG_FILE, "w") as f:
            json.dump(self._data, f, indent=2)

    def get(self, key, default=None):
        return self._data.get(key, default)

    def set(self, key, value):
        self._data[key] = value
        self.save()

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self.set(key, value)
