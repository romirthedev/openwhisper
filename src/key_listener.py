"""
Native macOS keyboard listener using CGEventSource key state polling.

Polls the key state every 30ms in a background thread instead of using
Quartz event taps (which conflict with Tk's CFRunLoop and cause segfaults).

Requires no special permissions beyond what pynput would need.
"""
import threading
import time
from typing import Callable, Optional

import Quartz

# macOS virtual keycodes
_KEYCODE_MAP = {
    "right_cmd":   0x36,
    "left_cmd":    0x37,
    "right_shift": 0x3C,
    "left_shift":  0x38,
    "right_alt":   0x3D,
    "left_alt":    0x3A,
    "right_ctrl":  0x3E,
    "left_ctrl":   0x3B,
    "caps_lock":   0x39,
    "fn":          0x3F,
    "f1":  0x7A, "f2":  0x78, "f3":  0x63, "f4":  0x76,
    "f5":  0x60, "f6":  0x61, "f7":  0x62, "f8":  0x64,
    "f9":  0x65, "f10": 0x6D, "f11": 0x67, "f12": 0x6F,
}

POLL_INTERVAL = 0.03  # 30ms — responsive without hammering the CPU


def resolve_hotkey(hotkey_str: str) -> Optional[int]:
    return _KEYCODE_MAP.get(hotkey_str)


class KeyListener:
    def __init__(
        self,
        hotkey: str = "right_cmd",
        on_press: Optional[Callable] = None,
        on_release: Optional[Callable] = None,
    ):
        self._hotkey = hotkey
        self._keycode = resolve_hotkey(hotkey)
        self._on_press = on_press or (lambda: None)
        self._on_release = on_release or (lambda: None)
        self._thread: Optional[threading.Thread] = None
        self._running = False
        self._was_down = False

    def start(self):
        if self._keycode is None:
            print(f"Warning: unknown hotkey '{self._hotkey}'")
            return
        self._running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _poll_loop(self):
        source = Quartz.kCGEventSourceStateHIDSystemState
        while self._running:
            is_down = Quartz.CGEventSourceKeyState(source, self._keycode)
            if is_down and not self._was_down:
                self._was_down = True
                try:
                    self._on_press()
                except Exception as e:
                    print(f"[KeyListener] on_press error: {e}")
            elif not is_down and self._was_down:
                self._was_down = False
                try:
                    self._on_release()
                except Exception as e:
                    print(f"[KeyListener] on_release error: {e}")
            time.sleep(POLL_INTERVAL)
