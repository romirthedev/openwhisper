"""
OpenWhisper main UI window.

Built with customtkinter for a clean, modern look on macOS.
Layout:
  ┌──────────┬────────────────────────────┐
  │ Sidebar  │  Main content (swappable)  │
  │  - Home  │                            │
  │  - Hist. │                            │
  │  - Sett. │                            │
  └──────────┴────────────────────────────┘
"""
import sys
import os
import threading
import time
from datetime import datetime
from typing import Optional

import customtkinter as ctk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── Colours ────────────────────────────────────────────────────────────────── #
SIDEBAR_BG   = "#1A1A2E"
SIDEBAR_HOVER= "#252542"
SIDEBAR_SEL  = "#6C63FF"
CONTENT_BG   = "#F7F7F2"
CARD_BG      = "#FFFFFF"
ACCENT       = "#6C63FF"
TEXT_PRIMARY = "#1A1A1A"
TEXT_SECONDARY="#666666"
TEXT_TIMESTAMP="#9E9E9E"
REC_RED      = "#FF3B30"
GREEN        = "#34C759"
BORDER       = "#E5E5E5"


# ── Helpers ─────────────────────────────────────────────────────────────────── #
def fmt_datetime(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        today = datetime.now().date()
        if dt.date() == today:
            return dt.strftime("Today, %I:%M %p").lstrip("0")
        elif (today - dt.date()).days == 1:
            return dt.strftime("Yesterday, %I:%M %p").lstrip("0")
        else:
            return dt.strftime("%b %d, %I:%M %p").lstrip("0")
    except Exception:
        return iso[:16]


def fmt_words(n: int) -> str:
    if n >= 1000:
        return f"{n / 1000:.1f}k"
    return str(n)


# ── Recording Overlay ────────────────────────────────────────────────────────── #
class RecordingOverlay(ctk.CTkToplevel):
    """Small floating window shown while recording."""

    def __init__(self):
        super().__init__()
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.wm_attributes("-alpha", 0.92)
        self.configure(fg_color=REC_RED)

        w, h = 220, 48
        sw = self.winfo_screenwidth()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+24")

        frame = ctk.CTkFrame(self, fg_color=REC_RED, corner_radius=24)
        frame.pack(fill="both", expand=True)

        self._dot_label = ctk.CTkLabel(
            frame, text="● Recording…",
            text_color="white",
            font=ctk.CTkFont(family="SF Pro Display", size=15, weight="bold"),
        )
        self._dot_label.pack(expand=True)

        self._anim_on = True
        threading.Thread(target=self._pulse, daemon=True).start()

    def _pulse(self):
        dots = ["● Recording", "● Recording.", "● Recording..", "● Recording…"]
        i = 0
        while self._anim_on:
            self._dot_label.configure(text=dots[i % len(dots)])
            i += 1
            time.sleep(0.5)

    def destroy(self):
        self._anim_on = False
        super().destroy()


# ── Transcript Card ───────────────────────────────────────────────────────────── #
class TranscriptCard(ctk.CTkFrame):
    def __init__(self, parent, record: dict, on_delete=None, **kwargs):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=10, **kwargs)
        self.configure(border_width=1, border_color=BORDER)

        self._record = record
        self._on_delete = on_delete

        # ── Header row ──
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))

        ts = fmt_datetime(record.get("created_at", ""))
        ctk.CTkLabel(
            header, text=ts,
            font=ctk.CTkFont(size=11),
            text_color=TEXT_TIMESTAMP,
        ).pack(side="left")

        wc = record.get("word_count", 0) or 0
        dur = record.get("duration_seconds") or 0
        meta = f"{wc} words"
        if dur:
            meta += f"  ·  {dur:.0f}s"
        ctk.CTkLabel(
            header, text=meta,
            font=ctk.CTkFont(size=11),
            text_color=TEXT_TIMESTAMP,
        ).pack(side="right")

        # ── Text ──
        text = record.get("text", "")
        self._text_box = ctk.CTkTextbox(
            self,
            height=max(40, min(160, len(text) // 3 + 40)),
            fg_color="transparent",
            border_width=0,
            font=ctk.CTkFont(size=13),
            text_color=TEXT_PRIMARY,
            wrap="word",
            activate_scrollbars=False,
        )
        self._text_box.pack(fill="x", padx=14, pady=(0, 4))
        self._text_box.insert("1.0", text)
        self._text_box.configure(state="disabled")

        # ── Footer buttons ──
        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.pack(fill="x", padx=14, pady=(0, 10))

        ctk.CTkButton(
            footer, text="Copy", width=70, height=26,
            fg_color=ACCENT, hover_color="#5a53d4",
            font=ctk.CTkFont(size=12),
            command=self._copy,
        ).pack(side="left", padx=(0, 8))

        ctk.CTkButton(
            footer, text="Delete", width=70, height=26,
            fg_color="transparent", hover_color="#FFE5E5",
            border_width=1, border_color="#FFBBBB",
            text_color="#FF3B30",
            font=ctk.CTkFont(size=12),
            command=self._delete,
        ).pack(side="left")

    def _copy(self):
        try:
            import pyperclip
            pyperclip.copy(self._record.get("text", ""))
        except Exception:
            self.clipboard_clear()
            self.clipboard_append(self._record.get("text", ""))
        # Flash feedback
        for btn in self.winfo_children():
            pass  # simple – real apps would flash the button

    def _delete(self):
        if self._on_delete:
            self._on_delete(self._record["id"])


# ── Home View ────────────────────────────────────────────────────────────────── #
class HomeView(ctk.CTkFrame):
    def __init__(self, parent, app_core, **kwargs):
        super().__init__(parent, fg_color=CONTENT_BG, **kwargs)
        self._app = app_core
        self._build()

    def _build(self):
        # Stats banner
        stats_frame = ctk.CTkFrame(self, fg_color="#1A1A2E", corner_radius=16)
        stats_frame.pack(fill="x", padx=20, pady=(20, 12))

        inner = ctk.CTkFrame(stats_frame, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=24, pady=20)

        title = ctk.CTkLabel(
            inner, text="OpenWhisper",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="white",
        )
        title.pack(anchor="w")
        sub = ctk.CTkLabel(
            inner, text="Local voice dictation · everything stays on your Mac",
            font=ctk.CTkFont(size=13),
            text_color="#AAAACC",
        )
        sub.pack(anchor="w", pady=(2, 16))

        stat_row = ctk.CTkFrame(inner, fg_color="transparent")
        stat_row.pack(anchor="w")

        self._streak_lbl = self._stat_chip(stat_row, "🔥", "0 weeks")
        self._words_lbl  = self._stat_chip(stat_row, "🚀", "0 words")
        self._wpm_lbl    = self._stat_chip(stat_row, "🏆", "0 WPM")

        # Status badge
        self._status_badge = ctk.CTkLabel(
            self, text="⏳ Loading model…",
            font=ctk.CTkFont(size=13),
            text_color=TEXT_SECONDARY,
        )
        self._status_badge.pack(anchor="w", padx=24, pady=(0, 8))

        # Recent transcripts label
        ctk.CTkLabel(
            self, text="TODAY",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=TEXT_TIMESTAMP,
        ).pack(anchor="w", padx=24, pady=(8, 4))

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=CONTENT_BG, scrollbar_button_color=CONTENT_BG,
        )
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))

        self.refresh()

    def _stat_chip(self, parent, icon, text):
        f = ctk.CTkFrame(parent, fg_color="#252542", corner_radius=8)
        f.pack(side="left", padx=(0, 8))
        lbl = ctk.CTkLabel(f, text=f"{icon}  {text}", font=ctk.CTkFont(size=12), text_color="white")
        lbl.pack(padx=10, pady=5)
        return lbl

    def refresh(self):
        stats = self._app.storage.get_stats()
        weeks = stats["streak_days"] // 7
        self._streak_lbl.configure(text=f"🔥  {weeks} weeks")
        self._words_lbl.configure(text=f"🚀  {fmt_words(stats['total_words'])} words")
        self._wpm_lbl.configure(text=f"🏆  {stats.get('wpm', 0)} WPM")

        for w in self._scroll.winfo_children():
            w.destroy()

        records = self._app.storage.get_transcripts(limit=20)
        if not records:
            ctk.CTkLabel(
                self._scroll,
                text="Hold the Fn key (or your configured hotkey) to start recording.",
                font=ctk.CTkFont(size=13),
                text_color=TEXT_SECONDARY,
                wraplength=400,
            ).pack(pady=40)
            return

        for rec in records:
            card = TranscriptCard(
                self._scroll, rec,
                on_delete=self._delete_transcript,
            )
            card.pack(fill="x", pady=(0, 10))

    def set_status(self, text: str, color: str = TEXT_SECONDARY):
        self._status_badge.configure(text=text, text_color=color)

    def _delete_transcript(self, tid: int):
        self._app.storage.delete_transcript(tid)
        self.refresh()


# ── History View ──────────────────────────────────────────────────────────────── #
class HistoryView(ctk.CTkFrame):
    def __init__(self, parent, app_core, **kwargs):
        super().__init__(parent, fg_color=CONTENT_BG, **kwargs)
        self._app = app_core
        self._query = ""
        self._build()

    def _build(self):
        top = ctk.CTkFrame(self, fg_color=CONTENT_BG)
        top.pack(fill="x", padx=20, pady=(20, 8))

        ctk.CTkLabel(
            top, text="History",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(side="left")

        self._search = ctk.CTkEntry(
            top, placeholder_text="Search transcripts…",
            width=220, height=32,
            font=ctk.CTkFont(size=13),
        )
        self._search.pack(side="right")
        self._search.bind("<KeyRelease>", self._on_search)

        self._scroll = ctk.CTkScrollableFrame(
            self, fg_color=CONTENT_BG,
        )
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _on_search(self, _event=None):
        self._query = self._search.get().strip()
        self.refresh()

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        if self._query:
            records = self._app.storage.search_transcripts(self._query)
        else:
            records = self._app.storage.get_transcripts(limit=200)

        if not records:
            ctk.CTkLabel(
                self._scroll,
                text="No transcripts yet." if not self._query else "No results.",
                font=ctk.CTkFont(size=13),
                text_color=TEXT_SECONDARY,
            ).pack(pady=40)
            return

        current_day = None
        for rec in records:
            try:
                day = datetime.fromisoformat(rec["created_at"]).strftime("%A, %B %d %Y")
            except Exception:
                day = "Unknown"

            if day != current_day:
                current_day = day
                ctk.CTkLabel(
                    self._scroll, text=day.upper(),
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=TEXT_TIMESTAMP,
                ).pack(anchor="w", padx=8, pady=(12, 4))

            card = TranscriptCard(
                self._scroll, rec,
                on_delete=self._delete_transcript,
            )
            card.pack(fill="x", pady=(0, 8))

    def _delete_transcript(self, tid: int):
        self._app.storage.delete_transcript(tid)
        self.refresh()


# ── Settings View ──────────────────────────────────────────────────────────────── #
class SettingsView(ctk.CTkFrame):
    HOTKEY_OPTIONS = ["fn", "right_alt", "right_cmd", "right_ctrl", "caps_lock",
                      "f1", "f2", "f3", "f4", "f5", "f6", "f7", "f8", "f9", "f10", "f11", "f12"]
    MODEL_OPTIONS  = ["tiny.en", "base.en", "small.en", "medium.en", "large-v3",
                      "tiny", "base", "small", "medium"]

    def __init__(self, parent, app_core, **kwargs):
        super().__init__(parent, fg_color=CONTENT_BG, **kwargs)
        self._app = app_core
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=CONTENT_BG)
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            scroll, text="Settings",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 20))

        cfg = self._app.config

        # ── Recording ──
        self._section(scroll, "Recording")

        self._hotkey_var = ctk.StringVar(value=cfg["hotkey"])
        self._labeled_combo(scroll, "Hotkey", self._hotkey_var, self.HOTKEY_OPTIONS,
                            note="Hold this key to record. 'fn' = Fn/Globe key.")

        self._paste_var = ctk.BooleanVar(value=cfg["use_clipboard_paste"])
        self._labeled_switch(scroll, "Inject via clipboard paste", self._paste_var,
                             note="Recommended. Uses Cmd+V to insert text (most reliable).")

        # ── Transcription ──
        self._section(scroll, "Transcription")

        self._model_var = ctk.StringVar(value=cfg["whisper_model"])
        self._labeled_combo(scroll, "Whisper model", self._model_var, self.MODEL_OPTIONS,
                            note="Larger models are more accurate but slower to load.")

        self._lang_var = ctk.StringVar(value=cfg.get("language") or "auto")
        self._labeled_entry(scroll, "Language", self._lang_var,
                            note="e.g. 'en', 'fr', 'es'. Use 'auto' to detect automatically.")

        self._format_var = ctk.BooleanVar(value=cfg["auto_format"])
        self._labeled_switch(scroll, "Auto-format text", self._format_var,
                             note="Fix punctuation, capitalization, and verbal corrections.")

        # ── AI (Ollama) ──
        self._section(scroll, "AI post-processing (Ollama)")

        self._ai_var = ctk.BooleanVar(value=cfg["use_ai"])
        self._labeled_switch(scroll, "Use local AI (Ollama)", self._ai_var,
                             note="Requires Ollama running at the URL below.")

        self._ollama_url_var = ctk.StringVar(value=cfg["ollama_url"])
        self._labeled_entry(scroll, "Ollama URL", self._ollama_url_var)

        self._ollama_model_var = ctk.StringVar(value=cfg["ollama_model"])
        self._labeled_entry(scroll, "Ollama model", self._ollama_model_var,
                            note="e.g. llama3.1, mistral, phi3")

        # ── Save button ──
        ctk.CTkButton(
            scroll, text="Save settings", height=38,
            fg_color=ACCENT, hover_color="#5a53d4",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._save,
        ).pack(pady=(20, 4), anchor="w")

        self._saved_lbl = ctk.CTkLabel(scroll, text="", font=ctk.CTkFont(size=12),
                                       text_color=GREEN)
        self._saved_lbl.pack(anchor="w")

    def _section(self, parent, title: str):
        ctk.CTkLabel(
            parent, text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT_PRIMARY,
        ).pack(anchor="w", pady=(16, 4))
        ctk.CTkFrame(parent, height=1, fg_color=BORDER).pack(fill="x", pady=(0, 8))

    def _labeled_combo(self, parent, label, var, options, note=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, width=180, anchor="w",
                     font=ctk.CTkFont(size=13), text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkComboBox(row, values=options, variable=var, width=200,
                        font=ctk.CTkFont(size=13)).pack(side="left")
        if note:
            ctk.CTkLabel(parent, text=note, font=ctk.CTkFont(size=11),
                         text_color=TEXT_SECONDARY).pack(anchor="w", padx=4)

    def _labeled_switch(self, parent, label, var, note=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, anchor="w",
                     font=ctk.CTkFont(size=13), text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkSwitch(row, text="", variable=var, onvalue=True, offvalue=False,
                      progress_color=ACCENT).pack(side="right")
        if note:
            ctk.CTkLabel(parent, text=note, font=ctk.CTkFont(size=11),
                         text_color=TEXT_SECONDARY).pack(anchor="w", padx=4)

    def _labeled_entry(self, parent, label, var, note=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, width=180, anchor="w",
                     font=ctk.CTkFont(size=13), text_color=TEXT_PRIMARY).pack(side="left")
        ctk.CTkEntry(row, textvariable=var, width=240,
                     font=ctk.CTkFont(size=13)).pack(side="left")
        if note:
            ctk.CTkLabel(parent, text=note, font=ctk.CTkFont(size=11),
                         text_color=TEXT_SECONDARY).pack(anchor="w", padx=4)

    def _save(self):
        cfg = self._app.config
        cfg["hotkey"]             = self._hotkey_var.get()
        cfg["whisper_model"]      = self._model_var.get()
        lang                      = self._lang_var.get().strip()
        cfg["language"]           = None if lang in ("", "auto") else lang
        cfg["use_clipboard_paste"]= self._paste_var.get()
        cfg["auto_format"]        = self._format_var.get()
        cfg["use_ai"]             = self._ai_var.get()
        cfg["ollama_url"]         = self._ollama_url_var.get().strip()
        cfg["ollama_model"]       = self._ollama_model_var.get().strip()
        self._app.reload_settings()
        self._saved_lbl.configure(text="✓ Settings saved")
        self.after(3000, lambda: self._saved_lbl.configure(text=""))


# ── Sidebar ───────────────────────────────────────────────────────────────────── #
class Sidebar(ctk.CTkFrame):
    NAV_ITEMS = [
        ("home", "Home"),
        ("history", "History"),
        ("settings", "Settings"),
    ]

    def __init__(self, parent, on_select, **kwargs):
        super().__init__(parent, fg_color=SIDEBAR_BG, width=200, corner_radius=0, **kwargs)
        self.pack_propagate(False)
        self._on_select = on_select
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._current = "home"
        self._build()

    def _build(self):
        # App logo
        logo_frame = ctk.CTkFrame(self, fg_color="transparent")
        logo_frame.pack(fill="x", padx=20, pady=(24, 8))
        ctk.CTkLabel(
            logo_frame, text="OpenWhisper",
            font=ctk.CTkFont(size=17, weight="bold"),
            text_color="white",
        ).pack(anchor="w")
        ctk.CTkLabel(
            logo_frame, text="Local voice dictation",
            font=ctk.CTkFont(size=11),
            text_color="#8888AA",
        ).pack(anchor="w")

        ctk.CTkFrame(self, height=1, fg_color="#2D2D4E").pack(fill="x", padx=16, pady=12)

        icons = {"home": "⌂", "history": "◷", "settings": "⚙"}
        for key, label in self.NAV_ITEMS:
            btn = ctk.CTkButton(
                self,
                text=f"  {icons[key]}  {label}",
                anchor="w",
                height=40,
                fg_color="transparent",
                hover_color=SIDEBAR_HOVER,
                text_color="white",
                font=ctk.CTkFont(size=14),
                corner_radius=8,
                command=lambda k=key: self._select(k),
            )
            btn.pack(fill="x", padx=10, pady=2)
            self._buttons[key] = btn

        self._select("home")

        # Version at bottom
        ctk.CTkLabel(
            self, text="v1.0.0  ·  open source",
            font=ctk.CTkFont(size=10),
            text_color="#555577",
        ).pack(side="bottom", pady=12)

    def _select(self, key: str):
        for k, btn in self._buttons.items():
            btn.configure(fg_color=SIDEBAR_SEL if k == key else "transparent")
        self._current = key
        self._on_select(key)


# ── Main Application Window ───────────────────────────────────────────────────── #
class MainWindow:
    def __init__(self, app_core):
        self._app = app_core
        self._overlay: Optional[RecordingOverlay] = None
        self._views: dict[str, ctk.CTkFrame] = {}

        ctk.set_appearance_mode(app_core.config.get("theme", "dark"))
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("OpenWhisper")
        self.root.geometry("980x680")
        self.root.minsize(760, 520)

        self._build()
        self._register_app_events()
        self._start_event_poll()

    # ------------------------------------------------------------------ #
    #  Build layout                                                         #
    # ------------------------------------------------------------------ #

    def _build(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self._sidebar = Sidebar(self.root, on_select=self._show_view)
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        self._content = ctk.CTkFrame(self.root, fg_color=CONTENT_BG, corner_radius=0)
        self._content.grid(row=0, column=1, sticky="nsew")
        self._content.grid_rowconfigure(0, weight=1)
        self._content.grid_columnconfigure(0, weight=1)

        self._views["home"] = HomeView(self._content, self._app)
        self._views["history"] = HistoryView(self._content, self._app)
        self._views["settings"] = SettingsView(self._content, self._app)

        for v in self._views.values():
            v.grid(row=0, column=0, sticky="nsew")

        self._show_view("home")

    def _show_view(self, key: str):
        for k, v in self._views.items():
            if k == key:
                v.tkraise()
                if hasattr(v, "refresh"):
                    v.refresh()

    # ------------------------------------------------------------------ #
    #  App event handlers                                                   #
    # ------------------------------------------------------------------ #

    def _register_app_events(self):
        self._app.on("recording_start",   self._on_recording_start)
        self._app.on("recording_stop",    self._on_recording_stop)
        self._app.on("transcript_ready",  self._on_transcript_ready)
        self._app.on("model_loading",     self._on_model_loading)
        self._app.on("model_ready",       self._on_model_ready)
        self._app.on("error",             self._on_error)

    def _on_recording_start(self):
        home: HomeView = self._views["home"]
        home.set_status("🔴 Recording…", REC_RED)
        if self._overlay is None:
            try:
                self._overlay = RecordingOverlay()
            except Exception:
                pass

    def _on_recording_stop(self):
        home: HomeView = self._views["home"]
        home.set_status("⚙ Transcribing…", ACCENT)
        if self._overlay:
            try:
                self._overlay.destroy()
            except Exception:
                pass
            self._overlay = None

    def _on_transcript_ready(self, text: str, duration: float):
        home: HomeView = self._views["home"]
        home.set_status("✓ Ready — hold hotkey to record", GREEN)
        home.refresh()
        hist: HistoryView = self._views["history"]
        hist.refresh()
        # Reset status after 4 s
        self.root.after(4000, lambda: home.set_status("● Ready — hold hotkey to record", GREEN))

    def _on_model_loading(self):
        home: HomeView = self._views["home"]
        home.set_status("⏳ Loading Whisper model (first run may take a minute)…", TEXT_SECONDARY)

    def _on_model_ready(self):
        home: HomeView = self._views["home"]
        home.set_status("● Ready — hold hotkey to record", GREEN)

    def _on_error(self, msg: str):
        home: HomeView = self._views["home"]
        home.set_status(f"⚠ {msg[:80]}", REC_RED)
        print(f"[OpenWhisper ERROR] {msg}")

    # ------------------------------------------------------------------ #
    #  Event loop integration                                               #
    # ------------------------------------------------------------------ #

    def _start_event_poll(self):
        def poll():
            self._app.poll_events()
            self.root.after(100, poll)
        self.root.after(100, poll)

    def run(self):
        self._app.start()
        self.root.mainloop()
        self._app.stop()
