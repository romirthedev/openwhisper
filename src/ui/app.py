"""
OpenWhisper – main UI window.
Clean, minimal cream + black design.
"""
import sys
import os
import threading
import time
import math
from datetime import datetime
from typing import Optional

import customtkinter as ctk
import tkinter as tk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import MODE_STANDARD, MODE_CONTINUOUS

# ── Palette ──────────────────────────────────────────────────────────────────── #
BG          = "#F5F0E8"   # warm cream
BG_CARD     = "#EFEAD F"   # slightly darker cream for cards
BG_INPUT    = "#EDEAE2"
BORDER      = "#D8D2C6"
TEXT        = "#1A1A1A"
TEXT_MID    = "#6B6560"
TEXT_FAINT  = "#A8A39C"
ACCENT      = "#1A1A1A"   # black accent
ACCENT_SOFT = "#2D2D2D"
RED         = "#C0392B"
GREEN_DOT   = "#27AE60"
AMBER       = "#D4872A"

BG_CARD     = "#EDE8DF"   # fix the typo above


def fmt_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        today = datetime.now().date()
        diff = (today - dt.date()).days
        if diff == 0:
            return dt.strftime("%-I:%M %p")
        elif diff == 1:
            return "Yesterday"
        else:
            return dt.strftime("%b %-d")
    except Exception:
        return ""


# ── Animated Recording Pill ───────────────────────────────────────────────────── #
class RecordingPill(tk.Toplevel):
    """
    Floating pill at the bottom-center of the screen.
    Shows animated waveform bars while recording.
    """
    BAR_COUNT = 5
    BAR_W     = 4
    BAR_GAP   = 5
    BAR_MAX_H = 22
    BAR_MIN_H = 4
    PILL_W    = 160
    PILL_H    = 52

    def __init__(self, master):
        super().__init__(master)
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.wm_attributes("-alpha", 0.0)
        self.configure(bg="#1A1A1A")

        sw = self.winfo_screenwidth()
        sh = self.winfo_screenheight()
        x  = (sw - self.PILL_W) // 2
        y  = sh - self.PILL_H - 48
        self.geometry(f"{self.PILL_W}x{self.PILL_H}+{x}+{y}")

        # Rounded look via canvas
        self._canvas = tk.Canvas(
            self, width=self.PILL_W, height=self.PILL_H,
            bg="#1A1A1A", highlightthickness=0
        )
        self._canvas.pack()

        # Draw pill background
        r = self.PILL_H // 2
        self._canvas.create_arc(0, 0, 2*r, self.PILL_H, start=90, extent=180, fill="#1A1A1A", outline="#1A1A1A")
        self._canvas.create_arc(self.PILL_W - 2*r, 0, self.PILL_W, self.PILL_H, start=-90, extent=180, fill="#1A1A1A", outline="#1A1A1A")
        self._canvas.create_rectangle(r, 0, self.PILL_W - r, self.PILL_H, fill="#1A1A1A", outline="#1A1A1A")

        # Dot indicator
        self._dot = self._canvas.create_oval(16, 20, 26, 30, fill=RED, outline="")

        # Label
        self._label_id = self._canvas.create_text(
            42, self.PILL_H // 2,
            text="Recording",
            fill="white",
            font=("SF Pro Display", 13, "bold") if sys.platform == "darwin" else ("Helvetica", 13, "bold"),
            anchor="w"
        )

        # Waveform bars (right side)
        bar_area_x = 110
        self._bars = []
        for i in range(self.BAR_COUNT):
            x0 = bar_area_x + i * (self.BAR_W + self.BAR_GAP)
            cy = self.PILL_H // 2
            bar = self._canvas.create_rectangle(
                x0, cy - self.BAR_MIN_H // 2,
                x0 + self.BAR_W, cy + self.BAR_MIN_H // 2,
                fill="#FFFFFF", outline="", tags="bar"
            )
            self._bars.append(bar)

        self._animating = False
        self._anim_thread: Optional[threading.Thread] = None
        self._phase = 0.0

    def show(self):
        self._animating = True
        self._fade(0.0, 1.0, steps=12)
        self._anim_thread = threading.Thread(target=self._animate, daemon=True)
        self._anim_thread.start()

    def hide(self):
        self._animating = False
        self._fade(1.0, 0.0, steps=12)

    def _fade(self, start, end, steps=12):
        def step(i):
            alpha = start + (end - start) * (i / steps)
            try:
                self.wm_attributes("-alpha", alpha)
            except Exception:
                return
            if i < steps:
                self.after(20, lambda: step(i + 1))
        step(0)

    def _animate(self):
        cy = self.PILL_H // 2
        while self._animating:
            self._phase += 0.18
            for i, bar in enumerate(self._bars):
                offset = i * (math.pi * 2 / self.BAR_COUNT)
                h = self.BAR_MIN_H + (self.BAR_MAX_H - self.BAR_MIN_H) * (
                    0.5 + 0.5 * math.sin(self._phase + offset)
                )
                x0, _, x1, _ = self._canvas.coords(bar)
                self._canvas.coords(bar, x0, cy - h/2, x1, cy + h/2)
            time.sleep(0.045)

    def set_mode(self, mode: str):
        if mode == MODE_CONTINUOUS:
            self._canvas.itemconfig(self._dot, fill=AMBER)
            self._canvas.itemconfig(self._label_id, text="Listening")
        else:
            self._canvas.itemconfig(self._dot, fill=RED)
            self._canvas.itemconfig(self._label_id, text="Recording")


# ── Transcript Row ────────────────────────────────────────────────────────────── #
class TranscriptRow(ctk.CTkFrame):
    def __init__(self, parent, record: dict, on_delete=None, **kwargs):
        super().__init__(parent, fg_color=BG_CARD, corner_radius=10, **kwargs)
        self.configure(border_width=1, border_color=BORDER)
        self._record = record
        self._on_delete = on_delete
        self._build()

    def _build(self):
        rec = self._record
        text = rec.get("text", "")
        ts   = fmt_time(rec.get("created_at", ""))
        dur  = rec.get("duration_seconds") or 0
        wc   = rec.get("word_count") or 0

        # Top row: timestamp + duration
        meta_row = ctk.CTkFrame(self, fg_color="transparent")
        meta_row.pack(fill="x", padx=14, pady=(10, 0))

        ctk.CTkLabel(meta_row, text=ts,
                     font=ctk.CTkFont(size=11), text_color=TEXT_FAINT).pack(side="left")

        meta = f"{wc}w" + (f"  ·  {dur:.0f}s" if dur else "")
        ctk.CTkLabel(meta_row, text=meta,
                     font=ctk.CTkFont(size=11), text_color=TEXT_FAINT).pack(side="right")

        # Text
        preview = text if len(text) <= 180 else text[:180] + "…"
        ctk.CTkLabel(
            self, text=preview,
            font=ctk.CTkFont(size=13),
            text_color=TEXT,
            wraplength=480,
            justify="left",
            anchor="w",
        ).pack(fill="x", padx=14, pady=(4, 0))

        # Action row
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=12, pady=(6, 8))

        ctk.CTkButton(
            actions, text="Copy", width=60, height=24,
            fg_color=ACCENT, hover_color=ACCENT_SOFT, text_color="white",
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=self._copy,
        ).pack(side="left", padx=(0, 6))

        ctk.CTkButton(
            actions, text="Delete", width=60, height=24,
            fg_color="transparent", hover_color="#F0EBE2",
            border_width=1, border_color=BORDER, text_color=TEXT_MID,
            font=ctk.CTkFont(size=11), corner_radius=6,
            command=self._delete,
        ).pack(side="left")

    def _copy(self):
        try:
            import pyperclip
            pyperclip.copy(self._record.get("text", ""))
        except Exception:
            pass

    def _delete(self):
        if self._on_delete:
            self._on_delete(self._record["id"])


# ── Home View ─────────────────────────────────────────────────────────────────── #
class HomeView(ctk.CTkFrame):
    def __init__(self, parent, app_core, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._app = app_core
        self._build()

    def _build(self):
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(28, 0))

        ctk.CTkLabel(
            header, text="OpenWhisper",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=TEXT,
        ).pack(side="left", anchor="s")

        self._status_dot = ctk.CTkLabel(
            header, text="●",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_FAINT,
        )
        self._status_dot.pack(side="right", anchor="s", pady=4)

        self._status_lbl = ctk.CTkLabel(
            header, text="Loading model…",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_FAINT,
        )
        self._status_lbl.pack(side="right", anchor="s", padx=(0, 4), pady=4)

        # Divider
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=28, pady=(16, 0))

        # Hint
        self._hint = ctk.CTkLabel(
            self,
            text="Hold your hotkey to start recording",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_FAINT,
        )
        self._hint.pack(anchor="w", padx=28, pady=(14, 0))

        # Transcripts list
        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=BG,
            scrollbar_button_color=BORDER,
            scrollbar_button_hover_color=TEXT_FAINT,
        )
        self._scroll.pack(fill="both", expand=True, padx=20, pady=(10, 20))

        self.refresh()

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        records = self._app.storage.get_transcripts(limit=30)
        if not records:
            ctk.CTkLabel(
                self._scroll,
                text="No transcripts yet.\nHold your hotkey to record.",
                font=ctk.CTkFont(size=13),
                text_color=TEXT_FAINT,
                justify="center",
            ).pack(pady=60)
            return

        for rec in records:
            TranscriptRow(
                self._scroll, rec, on_delete=self._delete,
            ).pack(fill="x", pady=(0, 8))

    def set_status(self, text: str, dot_color: str = TEXT_FAINT):
        self._status_lbl.configure(text=text)
        self._status_dot.configure(text_color=dot_color)

    def _delete(self, tid: int):
        self._app.storage.delete_transcript(tid)
        self.refresh()


# ── History View ──────────────────────────────────────────────────────────────── #
class HistoryView(ctk.CTkFrame):
    def __init__(self, parent, app_core, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._app = app_core
        self._build()

    def _build(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=28, pady=(28, 0))

        ctk.CTkLabel(header, text="History",
                     font=ctk.CTkFont(size=26, weight="bold"), text_color=TEXT).pack(side="left")

        self._search = ctk.CTkEntry(
            header, placeholder_text="Search…",
            width=200, height=32, font=ctk.CTkFont(size=12),
            fg_color=BG_INPUT, border_color=BORDER, text_color=TEXT,
        )
        self._search.pack(side="right")
        self._search.bind("<KeyRelease>", lambda _: self.refresh())

        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=28, pady=(16, 0))

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=BG,
                                               scrollbar_button_color=BORDER)
        self._scroll.pack(fill="both", expand=True, padx=20, pady=(10, 20))
        self.refresh()

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        q = self._search.get().strip() if hasattr(self, "_search") else ""
        records = (
            self._app.storage.search_transcripts(q)
            if q else self._app.storage.get_transcripts(limit=200)
        )

        if not records:
            ctk.CTkLabel(self._scroll,
                         text="No results." if q else "No transcripts yet.",
                         font=ctk.CTkFont(size=13), text_color=TEXT_FAINT).pack(pady=60)
            return

        day = None
        for rec in records:
            try:
                d = datetime.fromisoformat(rec["created_at"]).strftime("%B %-d, %Y")
            except Exception:
                d = "Unknown"
            if d != day:
                day = d
                ctk.CTkLabel(self._scroll, text=d.upper(),
                             font=ctk.CTkFont(size=10, weight="bold"),
                             text_color=TEXT_FAINT).pack(anchor="w", padx=6, pady=(14, 4))
            TranscriptRow(self._scroll, rec, on_delete=self._delete).pack(fill="x", pady=(0, 6))

    def _delete(self, tid: int):
        self._app.storage.delete_transcript(tid)
        self.refresh()


# ── Settings View ─────────────────────────────────────────────────────────────── #
class SettingsView(ctk.CTkFrame):
    HOTKEYS = ["right_cmd", "right_alt", "right_ctrl", "caps_lock",
               "f1","f2","f3","f4","f5","f6","f7","f8","f9","f10","f11","f12"]
    MODELS  = ["tiny.en","base.en","small.en","medium.en","large-v3"]

    def __init__(self, parent, app_core, **kwargs):
        super().__init__(parent, fg_color=BG, **kwargs)
        self._app = app_core
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=BG, scrollbar_button_color=BORDER)
        scroll.pack(fill="both", expand=True, padx=28, pady=28)

        ctk.CTkLabel(scroll, text="Settings",
                     font=ctk.CTkFont(size=26, weight="bold"), text_color=TEXT).pack(anchor="w", pady=(0, 24))

        cfg = self._app.config

        self._hotkey_var = ctk.StringVar(value=cfg["hotkey"])
        self._row(scroll, "Hotkey", ctk.CTkComboBox(
            scroll, values=self.HOTKEYS, variable=self._hotkey_var,
            width=180, font=ctk.CTkFont(size=13),
            fg_color=BG_INPUT, border_color=BORDER, text_color=TEXT,
            button_color=BORDER, dropdown_fg_color=BG_CARD,
        ), note="Hold this key to dictate")

        self._model_var = ctk.StringVar(value=cfg["whisper_model"])
        self._row(scroll, "Whisper model", ctk.CTkComboBox(
            scroll, values=self.MODELS, variable=self._model_var,
            width=180, font=ctk.CTkFont(size=13),
            fg_color=BG_INPUT, border_color=BORDER, text_color=TEXT,
            button_color=BORDER, dropdown_fg_color=BG_CARD,
        ), note="Larger = more accurate, slower to load")

        self._lang_var = ctk.StringVar(value=cfg.get("language") or "auto")
        self._row(scroll, "Language", ctk.CTkEntry(
            scroll, textvariable=self._lang_var, width=180,
            font=ctk.CTkFont(size=13), fg_color=BG_INPUT,
            border_color=BORDER, text_color=TEXT,
        ), note="e.g. en, fr, es  ·  auto = detect")

        self._paste_var = ctk.BooleanVar(value=cfg["use_clipboard_paste"])
        self._row(scroll, "Inject via clipboard", ctk.CTkSwitch(
            scroll, text="", variable=self._paste_var,
            onvalue=True, offvalue=False,
            progress_color=ACCENT, button_color=BG,
        ), note="Uses Cmd+V — most compatible")

        ctk.CTkFrame(scroll, height=1, fg_color=BORDER).pack(fill="x", pady=(24, 20))

        self._saved_lbl = ctk.CTkLabel(scroll, text="",
                                       font=ctk.CTkFont(size=12), text_color=GREEN_DOT)

        ctk.CTkButton(
            scroll, text="Save", height=36, width=100,
            fg_color=ACCENT, hover_color=ACCENT_SOFT, text_color="white",
            font=ctk.CTkFont(size=13, weight="bold"), corner_radius=8,
            command=self._save,
        ).pack(anchor="w")
        self._saved_lbl.pack(anchor="w", pady=(8, 0))

    def _row(self, parent, label: str, widget, note: str = ""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=(0, 16))
        ctk.CTkLabel(row, text=label, width=160, anchor="w",
                     font=ctk.CTkFont(size=13), text_color=TEXT).pack(side="left")
        widget.pack(side="left")
        if note:
            ctk.CTkLabel(parent, text=note, anchor="w",
                         font=ctk.CTkFont(size=11), text_color=TEXT_FAINT).pack(anchor="w", pady=(0, 4))

    def _save(self):
        cfg = self._app.config
        cfg["hotkey"]              = self._hotkey_var.get()
        cfg["whisper_model"]       = self._model_var.get()
        lang                       = self._lang_var.get().strip()
        cfg["language"]            = None if lang in ("", "auto") else lang
        cfg["use_clipboard_paste"] = self._paste_var.get()
        self._app.reload_settings()
        self._saved_lbl.configure(text="✓ Saved")
        self.after(2500, lambda: self._saved_lbl.configure(text=""))


# ── Sidebar ───────────────────────────────────────────────────────────────────── #
SIDEBAR_W = 56  # icon-only slim sidebar

class Sidebar(ctk.CTkFrame):
    NAV = [
        ("home",     "⌂"),
        ("history",  "◷"),
        ("settings", "⚙"),
    ]

    def __init__(self, parent, on_select, **kwargs):
        super().__init__(parent, fg_color=BG_CARD, width=SIDEBAR_W, corner_radius=0, **kwargs)
        self.configure(border_width=0)
        self.pack_propagate(False)
        self._on_select = on_select
        self._btns: dict[str, ctk.CTkButton] = {}
        self._build()

    def _build(self):
        ctk.CTkFrame(self, height=20, fg_color="transparent").pack()

        # App icon / wordmark
        ctk.CTkLabel(
            self, text="OW",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT, fg_color="transparent",
        ).pack(pady=(0, 16))

        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=10, pady=(0, 8))

        for key, icon in self.NAV:
            btn = ctk.CTkButton(
                self, text=icon, width=36, height=36,
                fg_color="transparent", hover_color=BG_INPUT,
                text_color=TEXT_FAINT, font=ctk.CTkFont(size=18),
                corner_radius=8,
                command=lambda k=key: self._select(k),
            )
            btn.pack(pady=3)
            self._btns[key] = btn

        self._select("home")

    def _select(self, key: str):
        for k, btn in self._btns.items():
            if k == key:
                btn.configure(fg_color=BG_INPUT, text_color=TEXT)
            else:
                btn.configure(fg_color="transparent", text_color=TEXT_FAINT)
        self._on_select(key)


# ── Main Window ───────────────────────────────────────────────────────────────── #
class MainWindow:
    def __init__(self, app_core):
        self._app = app_core
        self._pill: Optional[RecordingPill] = None
        self._views: dict[str, ctk.CTkFrame] = {}

        ctk.set_appearance_mode("light")
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("OpenWhisper")
        self.root.geometry("820x580")
        self.root.minsize(680, 480)
        self.root.configure(fg_color=BG)

        self._build()
        self._register_events()
        self._start_poll()

    def _build(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        sidebar = Sidebar(self.root, on_select=self._show_view)
        sidebar.grid(row=0, column=0, sticky="nsew")

        # Right-side thin border
        ctk.CTkFrame(self.root, width=1, fg_color=BORDER).grid(row=0, column=0, sticky="nse")

        content = ctk.CTkFrame(self.root, fg_color=BG, corner_radius=0)
        content.grid(row=0, column=1, sticky="nsew")
        content.grid_rowconfigure(0, weight=1)
        content.grid_columnconfigure(0, weight=1)

        self._views["home"]     = HomeView(content, self._app)
        self._views["history"]  = HistoryView(content, self._app)
        self._views["settings"] = SettingsView(content, self._app)

        for v in self._views.values():
            v.grid(row=0, column=0, sticky="nsew")

        self._show_view("home")

    def _show_view(self, key: str):
        for k, v in self._views.items():
            if k == key:
                v.tkraise()
                if hasattr(v, "refresh"):
                    v.refresh()

    def _register_events(self):
        self._app.on("recording_start",  self._on_rec_start)
        self._app.on("recording_stop",   self._on_rec_stop)
        self._app.on("transcript_ready", self._on_transcript)
        self._app.on("model_loading",    self._on_model_loading)
        self._app.on("model_ready",      self._on_model_ready)
        self._app.on("error",            self._on_error)

    def _on_rec_start(self):
        home = self._views["home"]
        mode = self._app.mode
        if mode == MODE_CONTINUOUS:
            home.set_status("Listening…", AMBER)
        else:
            home.set_status("Recording…", RED)

        if self._pill is None:
            try:
                self._pill = RecordingPill(self.root)
                self._pill.set_mode(mode)
                self._pill.show()
            except Exception as e:
                print(f"Pill error: {e}")

    def _on_rec_stop(self):
        home = self._views["home"]
        home.set_status("Transcribing…", AMBER)

        if self._pill:
            try:
                self._pill.hide()
                self.root.after(300, self._destroy_pill)
            except Exception:
                pass

    def _destroy_pill(self):
        if self._pill:
            try:
                self._pill.destroy()
            except Exception:
                pass
            self._pill = None

    def _on_transcript(self, text: str, duration: float):
        home = self._views["home"]
        home.set_status("Ready", GREEN_DOT)
        home.refresh()
        self._views["history"].refresh()

    def _on_model_loading(self):
        self._views["home"].set_status("Loading model…", TEXT_FAINT)

    def _on_model_ready(self):
        hotkey = self._app.config.get("hotkey", "right_cmd")
        self._views["home"].set_status(f"Ready  ·  hold {hotkey}", GREEN_DOT)

    def _on_error(self, msg: str):
        self._views["home"].set_status(f"Error: {msg[:60]}", RED)
        print(f"[OpenWhisper] {msg}")

    def _start_poll(self):
        def poll():
            self._app.poll_events()
            self.root.after(80, poll)
        self.root.after(80, poll)

    def _start_db_watch(self):
        """Refresh history views whenever the DB is written by the Swift app."""
        last = [0]
        import os
        from pathlib import Path
        db = Path.home() / ".openwhisper" / "transcripts.db"

        def watch():
            try:
                mtime = os.path.getmtime(db) if db.exists() else 0
                if mtime != last[0]:
                    last[0] = mtime
                    self._views["home"].refresh()
                    self._views["history"].refresh()
            except Exception:
                pass
            self.root.after(1500, watch)
        self.root.after(1500, watch)

    def run(self):
        self._app.start()
        self._start_db_watch()
        self.root.mainloop()
        self._app.stop()
