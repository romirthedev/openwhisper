#!/usr/bin/env python3
"""
whisper_worker.py - Transcription worker for OpenWhisper Swift app.

Usage: python whisper_worker.py <wav_file_path> [duration_seconds]
Prints transcribed text to stdout. Saves to ~/.openwhisper/transcripts.db.
"""
import sys
import os
import json
import signal
import sqlite3
from pathlib import Path
from datetime import datetime

signal.signal(signal.SIGTRAP, signal.SIG_IGN)


CONFIG_PATH = Path.home() / ".openwhisper" / "config.json"
DB_PATH     = Path.home() / ".openwhisper" / "transcripts.db"


def load_config() -> dict:
    defaults = {"whisper_model": "base.en", "language": "en"}
    if CONFIG_PATH.exists():
        try:
            with open(CONFIG_PATH) as f:
                defaults.update(json.load(f))
        except Exception:
            pass
    return defaults


def save_transcript(text: str, duration: float):
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
            (text, text, duration, len(text.split()), datetime.now().isoformat()),
        )
        conn.commit()


def transcribe(wav_path: str) -> str:
    import logging
    logging.getLogger("faster_whisper").setLevel(logging.WARNING)

    config = load_config()
    model_size = config.get("whisper_model", "base.en")
    language   = config.get("language", "en") or None

    try:
        from faster_whisper import WhisperModel
    except ImportError:
        print("[whisper_worker] faster-whisper not installed", file=sys.stderr)
        sys.exit(1)

    print(f"[whisper_worker] model={model_size} lang={language}", file=sys.stderr)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    # Don't pass language for .en models
    lang_arg = None if model_size.endswith(".en") else language
    segments, _ = model.transcribe(
        wav_path,
        language=lang_arg,
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    return " ".join(s.text.strip() for s in segments).strip()


def main():
    if len(sys.argv) < 2:
        print("Usage: whisper_worker.py <wav_file> [duration]", file=sys.stderr)
        sys.exit(1)

    wav_path = sys.argv[1]
    duration = float(sys.argv[2]) if len(sys.argv) >= 3 else 0.0

    if not os.path.exists(wav_path):
        print(f"[whisper_worker] File not found: {wav_path}", file=sys.stderr)
        sys.exit(1)

    text = transcribe(wav_path)

    if text:
        save_transcript(text, duration)
        print(text)  # stdout → Swift reads this


if __name__ == "__main__":
    main()
