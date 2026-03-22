#!/usr/bin/env bash
# ============================================================
# OpenWhisper – build script
# Creates a standalone macOS .app in dist/OpenWhisper.app
# ============================================================
set -euo pipefail

echo "==> OpenWhisper build script"
echo ""

# ── Check Python ─────────────────────────────────────────── #
PYTHON=${PYTHON:-python3}
PYTHON_VERSION=$("$PYTHON" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
echo "Python: $PYTHON_VERSION"

# ── Virtual environment ───────────────────────────────────── #
if [ ! -d ".venv" ]; then
    echo "==> Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi

source .venv/bin/activate

echo "==> Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q
pip install py2app -q

echo "==> Building .app bundle..."
rm -rf build dist
python setup.py py2app 2>&1 | tail -20

echo ""
echo "============================================"
echo "  Build complete!"
echo "  App: dist/OpenWhisper.app"
echo ""
echo "  To install:"
echo "    cp -r dist/OpenWhisper.app /Applications/"
echo ""
echo "  First launch:"
echo "    macOS will ask you to grant:"
echo "      • Microphone access"
echo "      • Input Monitoring (for hotkey)"
echo "      • Accessibility (for text injection)"
echo "    Grant all three in System Settings → Privacy & Security."
echo "============================================"
