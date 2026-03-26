#!/usr/bin/env python3
"""
whisper_worker.py - Transcription worker for OpenWhisper Swift app.

Usage: python whisper_worker.py <wav_file_path> [duration_seconds]

Prints text to stdout TWICE:
  Line 1: raw Whisper transcript  (Swift pastes this immediately)
  Line 2: CLEANED:<ollama output> (Swift replaces pasted text with this)

This gives instant paste + async AI cleanup.
"""
import sys
import os
import json
import signal
import sqlite3
import urllib.request
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

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    lang_arg = None if model_size.endswith(".en") else language
    segments, _ = model.transcribe(
        wav_path,
        language=lang_arg,
        beam_size=3,          # was 5 — faster with minimal quality loss
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )
    return " ".join(s.text.strip() for s in segments).strip()


def clean_with_ollama(raw: str, config: dict) -> str:
    model    = config.get("ollama_model", "llama3.2:latest")
    base_url = config.get("ollama_url", "http://localhost:11434").rstrip("/")

    messages = [
        {
            "role": "system",
            "content": (
                "Clean up this voice transcript. Output ONLY the cleaned text. No explanations, no bullet points, no commentary.\n\n"
                "Rules: Remove filler (um, uh, hmm). Fix punctuation. If speaker corrects themselves (says 'never mind', 'actually', 'no wait'), keep only the correction. Keep everything else exactly as said.\n\n"
                "Example:\n"
                "User: hey um hope you are doing well I uh wanted to ask about the project\n"
                "Assistant: Hey, hope you are doing well. I wanted to ask about the project.\n\n"
                "Example:\n"
                "User: can we meet at three actually no five works better\n"
                "Assistant: Can we meet at five? That works better.\n\n"
                "Example:\n"
                "User: hey bob um I won't be in today at three just uh let me know what works\n"
                "Assistant: Hey Bob, I won't be in today at three. Just let me know what works."
            )
        },
        {"role": "user", "content": raw}
    ]

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "options": {
            "temperature": 0.0,
            "num_predict": 300,
            "num_ctx": 1024,
        }
    }).encode()

    try:
        req = urllib.request.Request(
            f"{base_url}/api/chat",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=20) as resp:
            result = json.loads(resp.read())
            cleaned = result.get("message", {}).get("content", "").strip()
            # Strip any quotes the model may wrap around the output
            if len(cleaned) > 2 and cleaned[0] == '"' and cleaned[-1] == '"':
                cleaned = cleaned[1:-1]
            # Strip prompt artifacts the model may echo back
            import re
            cleaned = re.sub(r'\[TRANSCRIPT (?:START|END)\]', '', cleaned).strip()
            cleaned = re.sub(r'^(?:Output|Cleaned|Result|Here\'s?|Cleaned transcript):\s*', '', cleaned, flags=re.IGNORECASE).strip()
            # If model added explanations after the transcript (bullet points, "I made", "Note:", etc.)
            # take only the first paragraph
            for marker in ['\n\n', '\n*', '\n-', '\nI made', '\nI added', '\nI changed',
                           '\nI removed', '\nI kept', '\nNote:', '\nHere', '\nSome',
                           '\nMinor', '\nThe ', '\nChanges']:
                idx = cleaned.find(marker)
                if idx > 0:
                    cleaned = cleaned[:idx].strip()
            return cleaned if cleaned else raw
    except Exception as e:
        print(f"[whisper_worker] Ollama error: {e}", file=sys.stderr)
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

    # Step 1: transcribe
    raw = transcribe_audio(wav_path, config)
    if not raw:
        sys.exit(0)

    if config.get("use_ai", True):
        cleaned = clean_with_ollama(raw, config)
        final = cleaned if cleaned else raw
    else:
        final = raw

    save_transcript(final, raw, duration)
    print(final, flush=True)


if __name__ == "__main__":
    main()
