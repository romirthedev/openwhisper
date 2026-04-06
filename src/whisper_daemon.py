#!/usr/bin/env python3
"""
whisper_daemon.py - Persistent transcription daemon for OpenWhisper.

Loads the Whisper model once on startup, then listens for jobs on stdin.
Each job is a JSON line: {"wav": "/path/to/file.wav", "duration": 1.5, "raw_only": false}
Each response is a JSON line: {"text": "...", "error": null}

This eliminates the ~1-2s model load time on every transcription.
"""
import sys
import os
import json
import signal
import sqlite3
import logging
import urllib.request
from pathlib import Path
from datetime import datetime

signal.signal(signal.SIGTRAP, signal.SIG_IGN)
logging.getLogger("faster_whisper").setLevel(logging.WARNING)

CONFIG_PATH = Path.home() / ".openwhisper" / "config.json"
DB_PATH     = Path.home() / ".openwhisper" / "transcripts.db"


def load_config() -> dict:
    defaults = {
        "whisper_model": "base.en",
        "language": "en",
        "ollama_model": "llama3.2:latest",
        "ollama_url": "http://localhost:11434",
        "use_ai": False,
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


def clean_with_ollama(raw: str, config: dict) -> str:
    model    = config.get("ollama_model", "llama3.2:latest")
    base_url = config.get("ollama_url", "http://localhost:11434").rstrip("/")

    messages = [
        {
            "role": "system",
            "content": "Reformat dictated text. Remove filler (um, uh). Fix punctuation. Output ONLY the cleaned text."
        },
        {"role": "user", "content": "TRANSCRIPT: hey um hope you are doing well"},
        {"role": "assistant", "content": "Hey, hope you are doing well."},
        {"role": "user", "content": "TRANSCRIPT: how are you doing today um I was wondering if you could help me"},
        {"role": "assistant", "content": "How are you doing today? I was wondering if you could help me."},
        {"role": "user", "content": "TRANSCRIPT: hey how are you doing uh what time works for lunch"},
        {"role": "assistant", "content": "Hey, how are you doing? What time works for lunch?"},
        {"role": "user", "content": "TRANSCRIPT: can we meet at three actually no five works better"},
        {"role": "assistant", "content": "Can we meet at five? That works better."},
        {"role": "user", "content": f"TRANSCRIPT: {raw}"}
    ]

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": 0.0,
            "num_predict": 200,
            "num_ctx": 512,
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
            # Stream response tokens and accumulate
            tokens = []
            for line in resp:
                line = line.strip()
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        tokens.append(token)
                    if chunk.get("done"):
                        break
                except Exception:
                    continue
            cleaned = "".join(tokens).strip()
            if len(cleaned) > 2 and cleaned[0] == '"' and cleaned[-1] == '"':
                cleaned = cleaned[1:-1]
            import re
            cleaned = re.sub(r'\[TRANSCRIPT (?:START|END)\]', '', cleaned).strip()
            cleaned = re.sub(r'^(?:Output|Cleaned|Result|Here\'s?|Cleaned transcript):\s*', '', cleaned, flags=re.IGNORECASE).strip()
            for marker in ['\n\n', '\n*', '\n-', '\nI made', '\nI added', '\nI changed',
                           '\nI removed', '\nI kept', '\nNote:', '\nHere', '\nSome',
                           '\nMinor', '\nThe ', '\nChanges']:
                idx = cleaned.find(marker)
                if idx > 0:
                    cleaned = cleaned[:idx].strip()
            return cleaned if cleaned else raw
    except Exception as e:
        print(f"[whisper_daemon] Ollama error: {e}", file=sys.stderr, flush=True)
        return raw


def respond(obj: dict):
    print(json.dumps(obj), flush=True)


def main():
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        respond({"text": "", "error": "faster-whisper not installed"})
        sys.exit(1)

    config = load_config()
    model_size = config.get("whisper_model", "base.en")
    language   = config.get("language", "en") or None

    # Load model once — this is the expensive step
    try:
        model = WhisperModel(model_size, device="cpu", compute_type="int8")
    except Exception as e:
        respond({"text": "", "error": f"Model load failed: {e}"})
        sys.exit(1)

    # Signal ready
    respond({"ready": True, "model": model_size})

    lang_arg = None if model_size.endswith(".en") else language

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            job = json.loads(line)
        except json.JSONDecodeError:
            respond({"text": "", "error": "invalid json"})
            continue

        # Reload config on each request so settings changes take effect
        config = load_config()

        wav_path = job.get("wav", "")
        duration = float(job.get("duration", 0.0))
        raw_only = bool(job.get("raw_only", False))

        if not os.path.exists(wav_path):
            respond({"text": "", "error": f"file not found: {wav_path}"})
            continue

        try:
            if raw_only:
                # Live mode: no VAD (avoids ... artifacts), no context conditioning,
                # faster beam, higher no-speech threshold to skip silent chunks
                segments, _ = model.transcribe(
                    wav_path,
                    language=lang_arg,
                    beam_size=1,
                    vad_filter=False,
                    condition_on_previous_text=False,
                    no_speech_threshold=0.6,
                )
            else:
                segments, _ = model.transcribe(
                    wav_path,
                    language=lang_arg,
                    beam_size=3,
                    vad_filter=True,
                    vad_parameters={"min_silence_duration_ms": 300},
                )
            raw = " ".join(s.text.strip() for s in segments).strip()
            # Strip trailing ellipsis and lone punctuation artifacts from live chunks
            if raw_only:
                import re
                raw = re.sub(r'\s*\.{2,}$', '', raw).strip()
                raw = re.sub(r'^[,\.!\?]+\s*', '', raw).strip()
        except Exception as e:
            respond({"text": "", "error": f"transcription failed: {e}"})
            continue

        if not raw:
            respond({"text": ""})
            continue

        if raw_only:
            respond({"text": raw})
            continue

        if config.get("use_ai", True):
            cleaned = clean_with_ollama(raw, config)
            final = cleaned if cleaned else raw
        else:
            final = raw

        save_transcript(final, raw, duration)
        respond({"text": final})


if __name__ == "__main__":
    main()
