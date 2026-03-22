# OpenWhisper

A fully local, open-source voice dictation app for macOS — inspired by Wispr Flow.

Hold the **Fn key**, speak, release — your words appear wherever your cursor is.
Everything runs on your Mac. Nothing leaves your machine.

---

## Features

- **Hold Fn to record** — release to transcribe and inject text at the cursor
- **Fully local** — uses OpenAI Whisper running on your Mac, no internet required
- **AI-powered cleanup** — fixes punctuation, handles self-corrections ("I mean…", "never mind…"), formats bullet points
- **Optional Ollama integration** — connect a local LLM for smarter post-processing
- **Transcript history** — browse, search, and copy past recordings
- **No Xcode required** — pure Python, runs directly or as a packaged `.app`

---

## Quick Start (run directly with Python)

### 1. Requirements

- macOS 12 Monterey or later
- Python 3.10+ (from [python.org](https://python.org) — **not** the system Python)

### 2. Install

```bash
git clone https://github.com/yourname/openwhisper.git
cd openwhisper

# Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

The first run will download the Whisper model (~150 MB for `base.en`).

### 3. Run

```bash
python run.py
```

### 4. Grant permissions (one-time)

macOS will prompt you — or go to **System Settings → Privacy & Security**:

| Permission | Why |
|---|---|
| **Microphone** | Record your voice |
| **Input Monitoring** | Detect the Fn hotkey |
| **Accessibility** | Type/paste transcribed text |

Grant all three, then relaunch the app.

---

## Build a standalone .app (no Python needed)

```bash
bash build.sh
```

This creates `dist/OpenWhisper.app`. Drag it to `/Applications/`.

> **Note:** On first launch macOS may show _"OpenWhisper can't be opened because it's from an unidentified developer."_
> Go to **System Settings → Privacy & Security → Open Anyway**, or right-click the app and choose **Open**.

---

## Configuration

Click **Settings** in the sidebar:

| Setting | Default | Description |
|---|---|---|
| Hotkey | `fn` | Key to hold for recording. Try `right_alt` if Fn doesn't work |
| Whisper model | `base.en` | Larger = more accurate, slower to load |
| Language | `en` | Set to `auto` for multilingual |
| Inject via clipboard | On | Uses Cmd+V paste (most reliable) |
| Auto-format text | On | Fix punctuation and verbal corrections |
| Use Ollama AI | Off | Connect a local LLM for smarter editing |

Settings are saved to `~/.openwhisper/config.json`.

---

## Hotkey troubleshooting

If the **Fn key** doesn't work:

1. Open **System Settings → Keyboard → Keyboard Shortcuts**
2. Check whether _"Use F1, F2, etc. keys as standard function keys"_ affects your setup
3. In OpenWhisper Settings, try switching the hotkey to `right_alt` (right Option key)
4. Ensure **Input Monitoring** permission is granted to Terminal (or OpenWhisper.app)

---

## Whisper models

| Model | Size | Speed | Accuracy |
|---|---|---|---|
| `tiny.en` | 39 MB | Very fast | Basic |
| `base.en` | 74 MB | Fast | Good ✓ |
| `small.en` | 244 MB | Medium | Better |
| `medium.en` | 769 MB | Slow | Great |
| `large-v3` | 1.5 GB | Slow | Best |

Use `.en` variants for English-only (faster). Drop the `.en` suffix for multilingual.

---

## Optional: Ollama AI post-processing

Install [Ollama](https://ollama.ai) and pull a model:

```bash
brew install ollama
ollama pull llama3.1
ollama serve
```

Then enable **Use Ollama AI** in OpenWhisper Settings.

The AI reformats text, resolves corrections, and formats lists — making dictation feel more like editing.

---

## How it works

```
Fn held down
     │
     ▼
AudioRecorder (sounddevice)  ←─ captures 16kHz mono PCM
     │
     ▼ (on release)
Transcriber (faster-whisper)  ←─ runs Whisper locally
     │
     ▼
AIProcessor (rules or Ollama)  ←─ cleans up text
     │
     ▼
TextInjector (clipboard paste)  ←─ types text at cursor
     │
     ▼
Storage (SQLite)  ←─ saves transcript to history
```

---

## Privacy

- **No data is ever sent to the cloud.** Audio, transcripts, and settings stay on your Mac.
- Transcripts are stored in `~/.openwhisper/transcripts.db` (SQLite).
- To delete everything: `rm -rf ~/.openwhisper`

---

## Development

```bash
source .venv/bin/activate
python run.py
```

Project layout:

```
openwhisper/
├── run.py                  # Entry point
├── src/
│   ├── config.py           # Settings management
│   ├── storage.py          # SQLite transcript store
│   ├── audio_recorder.py   # Hotkey + microphone capture
│   ├── transcriber.py      # Whisper transcription
│   ├── ai_processor.py     # Text cleanup (rules + Ollama)
│   ├── text_injector.py    # Paste text at cursor
│   ├── main.py             # App orchestrator
│   └── ui/
│       └── app.py          # customtkinter UI
├── requirements.txt
├── setup.py                # py2app build config
└── build.sh                # Build script
```

---

## License

MIT — free to use, modify, and distribute.
