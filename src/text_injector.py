"""
Types/pastes transcribed text at the current cursor position.

Strategy (most reliable on macOS):
  1. Clipboard paste: saves clipboard, puts text in clipboard, sends Cmd+V,
     then restores the clipboard after a short delay.
  2. Direct typing: uses pynput to type each character (slower for long text,
     but doesn't disturb the clipboard).
"""
import time
import threading
from typing import Optional

try:
    import pyperclip
    PYPERCLIP_AVAILABLE = True
except ImportError:
    PYPERCLIP_AVAILABLE = False

try:
    from pynput.keyboard import Controller as KeyboardController, Key
    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False


class TextInjector:
    """
    Injects text at the current cursor position.

    Args:
        use_clipboard: Prefer clipboard paste (True) or direct typing (False).
    """

    def __init__(self, use_clipboard: bool = True):
        self.use_clipboard = use_clipboard
        self._controller = KeyboardController() if PYNPUT_AVAILABLE else None

    def inject(self, text: str):
        """Inject text at current cursor. Non-blocking – fires and forgets."""
        if not text:
            return
        threading.Thread(target=self._inject_sync, args=(text,), daemon=True).start()

    def _inject_sync(self, text: str):
        # Small delay so the user has time to release the hotkey before injection
        time.sleep(0.15)

        if self.use_clipboard and PYPERCLIP_AVAILABLE and PYNPUT_AVAILABLE:
            self._paste_via_clipboard(text)
        elif PYNPUT_AVAILABLE:
            self._type_directly(text)
        else:
            print(f"[OpenWhisper] Cannot inject text (no pynput). Text: {text}")

    def _paste_via_clipboard(self, text: str):
        try:
            old = pyperclip.paste()
        except Exception:
            old = ""

        pyperclip.copy(text)
        time.sleep(0.05)

        # Simulate Cmd+V
        with self._controller.pressed(Key.cmd):
            self._controller.tap("v")

        # Restore clipboard after a short delay
        def _restore():
            time.sleep(0.5)
            try:
                pyperclip.copy(old)
            except Exception:
                pass

        threading.Thread(target=_restore, daemon=True).start()

    def _type_directly(self, text: str):
        self._controller.type(text)
