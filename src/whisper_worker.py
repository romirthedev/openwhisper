#!/usr/bin/env python3
"""
whisper_worker.py - Transcription worker for OpenWhisper Swift app.

Usage: python whisper_worker.py <wav_file_path> [duration_seconds]
Prints cleaned text to stdout. Saves raw + cleaned to DB.
"""
import sys
import os
import json
import signal
import sqlite3
import urllib.request
import urllib.error
from pathlib import Path
from datetime import datetime

signal.signal(signal.SIGTRAP, signal.SIG_IGN)

CONFIG_PATH = Path.home() / ".openwhisper" / "config.json"
DB_PATH     = Path.home() / ".openwhisper" / "transcripts.db"


def load_config() -> dict:
    defaults = {
        "whisper_model": "base.en",
        "language": "en",
        "ollama_model": "llama3.2:latest",
        "ollama_url": "http://localhost:11434",
        "use_ai": True,
    }
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                defaults.update(json.load(f))
        except Exception:
            pass
    return defaults


def save_transcript(cleaned: str, raw: str, duration: float):
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transcripts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                text TEXT NOT NULL,
                raw_text TEXT,
                duration_seconds REAL,
                word_count INTEGER,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute(
            "INSERT INTO transcripts (text, raw_text, duration_seconds, word_count, created_at) VALUES (?,?,?,?,?)",
            (cleaned, raw, duration, len(cleaned.split()), datetime.now().isoformat()),
        )
        conn.commit()


def transcribe_audio(wav_path: str, config: dict) -> str:
    import logging
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)

    model_size = config.get("whisper_model", "base.en")
    language   = config.get("language", "en") or None

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[whisper_worker] faster-whisper not installed", file=sys.stderr)
        sys.exit(1)

    print(f"[whisper_worker] transcribing: model={model_size}", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    lang_arg = None if model_size.endswith(".en") else language
    segments, _ = model.transcribe(
        wav_path,
        language=lang_arg,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    return " ".join(s.text.strip() for s in segments).strip()


def clean_with_ollama(raw: str, config: dict) -> str:
    """
    Send raw transcript to Ollama for cleanup.
    Returns cleaned text, or raw text if Ollama is unavailable.
    """
    model    = config.get("ollama_model", "llama3.2:latest")
    base_url = config.get("ollama_url", "http://localhost:11434").rstrip("/")

    # Tight prompt — fewer tokens = faster response
    prompt = (
        "Fix this voice transcript. Return ONLY the fixed text with no preamble or explanation.\n"
        "Rules: fix grammar/punctuation, remove filler words (um uh like you know), "
        "remove false starts (keep the corrected version), keep casual tone.\n\n"
        f"{raw}"
    )

    payload = json.dumps({
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": 0.1,   # low temp = consistent, fast
            "num_predict": 512,
        }
    }).encode()

    try:
        req = urllib.request.Request(
            f"{base_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read())
            cleaned = result.get("response", "").strip()
            print(f"[whisper_worker] ollama cleaned: {repr(cleaned[:80])}", file=sys.stderr)
            return cleaned if cleaned else raw
    except urllib.error.URLError:
        print("[whisper_worker] Ollama not reachable, using raw transcript", file=sys.stderr)
        return raw
    except Exception as e:
        print(f"[whisper_worker] Ollama error: {e}, using raw", file=sys.stderr)
        return raw


def main():
    if len(sys.argv) < 2:
        print("Usage: whisper_worker.py <wav_file> [duration]", file=sys.stderr)
        sys.exit(1)

    wav_path = sys.argv[1]
    duration = float(sys.argv[2]) if len(sys.argv) >= 3 else 0.0

    if not os.path.exists(wav_path):
        print(f"[whisper_worker] File not found: {wav_path}", file=sys.stderr)
        sys.exit(1)

    config = load_config()

    raw = transcribe_audio(wav_path, config)
    if not raw:
        sys.exit(0)

    # Clean with Ollama if enabled
    if config.get("use_ai", True):
        cleaned = clean_with_ollama(raw, config)
    else:
        cleaned = raw

    save_transcript(cleaned, raw, duration)
    print(cleaned)  # stdout → Swift reads this


if __name__ == "__main__":
    main()
