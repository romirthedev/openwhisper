"""
Types/pastes transcribed text at the current cursor position.

Two injection strategies:

  Clipboard paste (Standard mode default)
    Saves clipboard → copies text → sends Cmd+V → restores clipboard.
    Most reliable across all macOS apps, handles any Unicode.
    Slight overhead (~150 ms setup + restore) is fine for single-shot injection.

  Direct typing (Continuous Flow mode)
    Uses pynput to type characters directly.
    No clipboard disruption — essential when chunks arrive rapidly.
    Requires Accessibility permission.
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
    Args:
        use_clipboard: Use clipboard paste for `inject()` (Standard mode).
                       `inject_immediate()` always uses direct typing.
    """

    def __init__(self, use_clipboard: bool = True):
        self.use_clipboard = use_clipboard
        self._controller = KeyboardController() if PYNPUT_AVAILABLE else None
        # Serialise clipboard operations so rapid standard-mode injections
        # don't race (shouldn't normally happen, but defensive).
        self._clipboard_lock = threading.Lock()

    # ------------------------------------------------------------------ #
    #  Standard mode — clipboard paste                                      #
    # ------------------------------------------------------------------ #

    def inject(self, text: str):
        """
        Inject text via clipboard paste (Standard mode).
        Non-blocking — fires in a background thread.
        """
        if not text:
            return
        threading.Thread(target=self._inject_sync, args=(text,), daemon=True).start()

    def _inject_sync(self, text: str):
        # Brief pause so the user's key-release event settles before we paste.
        time.sleep(0.15)

        if self.use_clipboard and PYPERCLIP_AVAILABLE and PYNPUT_AVAILABLE:
            self._paste_via_clipboard(text)
        elif PYNPUT_AVAILABLE:
            self._type_directly(text)
        else:
            print(f"[OpenWhisper] Cannot inject text (no pynput). Text: {text}")

    def _paste_via_clipboard(self, text: str):
        with self._clipboard_lock:
            try:
                old = pyperclip.paste()
            except Exception:
                old = ""

            pyperclip.copy(text)
            time.sleep(0.04)

            with self._controller.pressed(Key.cmd):
                self._controller.tap("v")

        # Restore clipboard after paste has settled (non-blocking)
        def _restore():
            time.sleep(0.5)
            try:
                pyperclip.copy(old)
            except Exception:
                pass

        threading.Thread(target=_restore, daemon=True).start()

    # ------------------------------------------------------------------ #
    #  Continuous Flow mode — direct typing                                 #
    # ------------------------------------------------------------------ #

    def inject_immediate(self, text: str):
        """
        Type text directly using pynput (Continuous Flow mode).
        Synchronous — blocks until typing is done, which is fast for
        short chunks. Does not disturb the clipboard.
        """
        if not text or not PYNPUT_AVAILABLE:
            return
        threading.Thread(target=self._type_directly, args=(text,), daemon=True).start()

    def _type_directly(self, text: str):
        try:
            self._controller.type(text)
        except Exception as exc:
            print(f"[OpenWhisper] Direct typing error: {exc}")
