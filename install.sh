#!/bin/bash
# OpenWhisper installer for macOS
# Usage: curl -fsSL https://raw.githubusercontent.com/romirthedev/openwhisper/main/install.sh | bash

set -e

REPO_DIR="$HOME/openwhisper"
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'

echo ""
echo "${BOLD}OpenWhisper Installer${NC}"
echo "━━━━━━━━━━━━━━━━━━━━━"
echo ""

# ── 1. Xcode Command Line Tools (Swift) ──────────────────────────────────────
if ! xcode-select -p &>/dev/null; then
    echo "📦 Installing Xcode Command Line Tools (required for Swift)..."
    xcode-select --install
    echo "${YELLOW}After the installer finishes, re-run this script.${NC}"
    exit 0
fi
echo "✅ Swift tools found"

# ── 2. Homebrew ───────────────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "📦 Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    eval "$(/opt/homebrew/bin/brew shellenv)" 2>/dev/null || eval "$(/usr/local/bin/brew shellenv)" 2>/dev/null
fi
echo "✅ Homebrew found"

# ── 3. Python 3.12 + tcl-tk ───────────────────────────────────────────────────
if ! command -v pyenv &>/dev/null; then
    echo "📦 Installing pyenv..."
    brew install pyenv tcl-tk
fi

if ! pyenv versions | grep -q "3.12"; then
    echo "📦 Installing Python 3.12 (this takes a few minutes)..."
    brew install tcl-tk 2>/dev/null || true
    pyenv install 3.12.11
fi
PYTHON=$(pyenv root)/versions/3.12.11/bin/python3
echo "✅ Python 3.12 found"

# ── 4. Ollama ─────────────────────────────────────────────────────────────────
if ! command -v ollama &>/dev/null; then
    echo "📦 Installing Ollama..."
    brew install ollama
fi

if ! ollama list 2>/dev/null | grep -q "llama3.2"; then
    echo "📦 Downloading llama3.2 AI model (~2GB, one-time)..."
    ollama pull llama3.2:latest
fi

# Start Ollama in background if not running
if ! curl -s http://localhost:11434 &>/dev/null; then
    echo "🚀 Starting Ollama..."
    brew services start ollama 2>/dev/null || ollama serve &>/dev/null &
    sleep 2
fi
echo "✅ Ollama ready"

# ── 5. Clone / update repo ────────────────────────────────────────────────────
if [ -d "$REPO_DIR" ]; then
    echo "📦 Updating OpenWhisper..."
    git -C "$REPO_DIR" pull --quiet
else
    echo "📦 Downloading OpenWhisper..."
    git clone https://github.com/romirthedev/openwhisper.git "$REPO_DIR"
fi
cd "$REPO_DIR"
echo "✅ Source ready"

# ── 6. Python venv + deps ─────────────────────────────────────────────────────
if [ ! -d ".venv" ]; then
    echo "📦 Setting up Python environment..."
    $PYTHON -m venv .venv
fi
echo "📦 Installing Python dependencies..."
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q faster-whisper pyobjc-framework-Quartz
echo "✅ Python dependencies installed"

# ── 7. Build Swift app ────────────────────────────────────────────────────────
echo "🔨 Building OpenWhisper.app..."
cd swift && make 2>&1 | grep -E "(error:|Build complete|warning:)" || true
cd ..

APP_DEST="/Applications/OpenWhisper.app"
echo "📦 Installing to /Applications..."
rm -rf "$APP_DEST"
cp -R swift/OpenWhisper.app "$APP_DEST"
echo "✅ Installed to /Applications/OpenWhisper.app"

# ── 8. Config ─────────────────────────────────────────────────────────────────
mkdir -p ~/.openwhisper
cat > ~/.openwhisper/config.json << 'CONFIG'
{
  "hotkey": "right_cmd",
  "whisper_model": "base.en",
  "use_ai": true,
  "ollama_model": "llama3.2:latest",
  "ollama_url": "http://localhost:11434",
  "language": "en",
  "use_clipboard_paste": true
}
CONFIG
echo "✅ Config written"

# ── 9. Launch ─────────────────────────────────────────────────────────────────
echo ""
echo "${GREEN}${BOLD}✅ OpenWhisper installed!${NC}"
echo ""
echo "Opening OpenWhisper now..."
echo ""
echo "${BOLD}First-time setup:${NC}"
echo "  1. Grant ${BOLD}Microphone${NC} permission when prompted"
echo "  2. Grant ${BOLD}Accessibility${NC} permission in System Settings"
echo "  3. Hold ${BOLD}Right ⌘ (Command)${NC} to record"
echo "  4. Release to transcribe and paste"
echo ""
open "$APP_DEST"
