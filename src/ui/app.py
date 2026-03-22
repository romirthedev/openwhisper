"""
OpenWhisper main UI window.

Layout:
  ┌──────────┬────────────────────────────┐
  │ Sidebar  │  Main content (swappable)  │
  │  - Home  │                            │
  │  - Hist. │                            │
  │  - Sett. │                            │
  └──────────┴────────────────────────────┘

The sidebar contains a persistent mode toggle:
  ┌─────────────────────────┐
  │  ⚡ Continuous Flow      │  ← live, word-by-word
  │  ✓  Standard            │  ← wait, correct, paste
  └─────────────────────────┘
"""
import sys
import os
import threading
import time
from datetime import datetime
from typing import Optional

import customtkinter as ctk

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from main import MODE_STANDARD, MODE_CONTINUOUS

# ── Palette ─────────────────────────────────────────────────────────────────── #
SIDEBAR_BG    = "#1A1A2E"
SIDEBAR_HOVER = "#252542"
SIDEBAR_SEL   = "#6C63FF"
CONTENT_BG    = "#F7F7F2"
CARD_BG       = "#FFFFFF"
ACCENT        = "#6C63FF"
TEXT_PRIMARY  = "#1A1A1A"
TEXT_SECONDARY= "#666666"
TEXT_TIMESTAMP= "#9E9E9E"
REC_RED       = "#FF3B30"
GREEN         = "#34C759"
ORANGE        = "#FF9500"
BORDER        = "#E5E5E5"

MODE_COLORS = {
    MODE_STANDARD:   {"bg": "#252542", "fg": "#AAAACC", "active_bg": SIDEBAR_SEL, "active_fg": "white"},
    MODE_CONTINUOUS: {"bg": "#252542", "fg": "#AAAACC", "active_bg": ORANGE,      "active_fg": "white"},
}


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
    return f"{n / 1000:.1f}k" if n >= 1000 else str(n)


# ── Recording Overlay ────────────────────────────────────────────────────────── #
class RecordingOverlay(ctk.CTkToplevel):
    """Floating banner at the top of the screen shown while recording."""

    def __init__(self, mode: str = MODE_STANDARD):
        super().__init__()
        self.overrideredirect(True)
        self.wm_attributes("-topmost", True)
        self.wm_attributes("-alpha", 0.93)

        color = ORANGE if mode == MODE_CONTINUOUS else REC_RED
        label = "⚡ Continuous Flow…" if mode == MODE_CONTINUOUS else "● Recording…"

        self.configure(fg_color=color)

        w, h = 240, 48
        sw = self.winfo_screenwidth()
        self.geometry(f"{w}x{h}+{(sw - w) // 2}+24")

        frame = ctk.CTkFrame(self, fg_color=color, corner_radius=24)
        frame.pack(fill="both", expand=True)

        self._lbl = ctk.CTkLabel(
            frame, text=label,
            text_color="white",
            font=ctk.CTkFont(size=15, weight="bold"),
        )
        self._lbl.pack(expand=True)

        self._running = True
        if mode == MODE_CONTINUOUS:
            threading.Thread(target=self._pulse_continuous, daemon=True).start()
        else:
            threading.Thread(target=self._pulse_standard, daemon=True).start()

    def _pulse_standard(self):
        frames = ["● Recording", "● Recording.", "● Recording..", "● Recording…"]
        i = 0
        while self._running:
            self._lbl.configure(text=frames[i % len(frames)])
            i += 1
            time.sleep(0.5)

    def _pulse_continuous(self):
        frames = ["⚡ Flow…", "⚡ Flow .", "⚡ Flow ..", "⚡ Flow …"]
        i = 0
        while self._running:
            self._lbl.configure(text=frames[i % len(frames)])
            i += 1
            time.sleep(0.4)

    def destroy(self):
        self._running = False
        super().destroy()


# ── Transcript Card ───────────────────────────────────────────────────────────── #
class TranscriptCard(ctk.CTkFrame):
    def __init__(self, parent, record: dict, on_delete=None, **kwargs):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=10, **kwargs)
        self.configure(border_width=1, border_color=BORDER)
        self._record = record
        self._on_delete = on_delete
        self._build()

    def _build(self):
        rec = self._record

        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(12, 4))

        ctk.CTkLabel(
            header, text=fmt_datetime(rec.get("created_at", "")),
            font=ctk.CTkFont(size=11), text_color=TEXT_TIMESTAMP,
        ).pack(side="left")

        wc  = rec.get("word_count") or 0
        dur = rec.get("duration_seconds") or 0
        meta = f"{wc} words" + (f"  ·  {dur:.0f}s" if dur else "")
        ctk.CTkLabel(
            header, text=meta,
            font=ctk.CTkFont(size=11), text_color=TEXT_TIMESTAMP,
        ).pack(side="right")

        # Text
        text = rec.get("text", "")
        tb = ctk.CTkTextbox(
            self,
            height=max(40, min(160, len(text) // 3 + 40)),
            fg_color="transparent",
            border_width=0,
            font=ctk.CTkFont(size=13),
            text_color=TEXT_PRIMARY,
            wrap="word",
            activate_scrollbars=False,
        )
        tb.pack(fill="x", padx=14, pady=(0, 4))
        tb.insert("1.0", text)
        tb.configure(state="disabled")

        # Footer buttons
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
            text_color=REC_RED,
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

    def _delete(self):
        if self._on_delete:
            self._on_delete(self._record["id"])


# ── Mode Toggle Widget ────────────────────────────────────────────────────────── #
class ModeToggle(ctk.CTkFrame):
    """
    Two-button segmented toggle for Standard / Continuous Flow modes.
    Displayed in the sidebar.
    """

    def __init__(self, parent, current_mode: str, on_change, **kwargs):
        super().__init__(parent, fg_color="#111126", corner_radius=12, **kwargs)
        self._on_change = on_change
        self._btns: dict[str, ctk.CTkButton] = {}
        self._current = current_mode
        self._build()

    def _build(self):
        ctk.CTkLabel(
            self, text="Mode",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color="#555577",
        ).pack(anchor="w", padx=10, pady=(8, 4))

        modes = [
            (MODE_STANDARD,   "✓  Standard",        "Wait, correct & paste"),
            (MODE_CONTINUOUS, "⚡  Continuous Flow",  "Live word-by-word typing"),
        ]
        for key, label, tooltip in modes:
            btn = ctk.CTkButton(
                self,
                text=label,
                height=34,
                anchor="w",
                font=ctk.CTkFont(size=13),
                fg_color="transparent",
                hover_color=SIDEBAR_HOVER,
                text_color="#AAAACC",
                corner_radius=8,
                command=lambda k=key: self._select(k),
            )
            btn.pack(fill="x", padx=6, pady=2)
            self._btns[key] = btn

            ctk.CTkLabel(
                self, text=tooltip,
                font=ctk.CTkFont(size=10),
                text_color="#444466",
            ).pack(anchor="w", padx=14, pady=(0, 2))

        ctk.CTkFrame(self, height=6, fg_color="transparent").pack()
        self._apply_style(self._current)

    def _select(self, key: str):
        if key == self._current:
            return
        self._current = key
        self._apply_style(key)
        self._on_change(key)

    def _apply_style(self, active: str):
        for key, btn in self._btns.items():
            if key == active:
                color = ORANGE if key == MODE_CONTINUOUS else SIDEBAR_SEL
                btn.configure(fg_color=color, text_color="white")
            else:
                btn.configure(fg_color="transparent", text_color="#AAAACC")

    def set_mode(self, mode: str):
        self._current = mode
        self._apply_style(mode)


# ── Home View ────────────────────────────────────────────────────────────────── #
class HomeView(ctk.CTkFrame):
    def __init__(self, parent, app_core, **kwargs):
        super().__init__(parent, fg_color=CONTENT_BG, **kwargs)
        self._app = app_core
        self._build()

    def _build(self):
        # Stats banner
        banner = ctk.CTkFrame(self, fg_color="#1A1A2E", corner_radius=16)
        banner.pack(fill="x", padx=20, pady=(20, 12))

        inner = ctk.CTkFrame(banner, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(
            inner, text="OpenWhisper",
            font=ctk.CTkFont(size=22, weight="bold"),
            text_color="white",
        ).pack(anchor="w")
        ctk.CTkLabel(
            inner, text="Local voice dictation · everything stays on your Mac",
            font=ctk.CTkFont(size=13), text_color="#AAAACC",
        ).pack(anchor="w", pady=(2, 16))

        stat_row = ctk.CTkFrame(inner, fg_color="transparent")
        stat_row.pack(anchor="w")
        self._streak_lbl = self._stat_chip(stat_row, "🔥", "0 weeks")
        self._words_lbl  = self._stat_chip(stat_row, "🚀", "0 words")
        self._wpm_lbl    = self._stat_chip(stat_row, "🏆", "0 WPM")

        # Status bar
        self._status_lbl = ctk.CTkLabel(
            self, text="⏳ Loading model…",
            font=ctk.CTkFont(size=13), text_color=TEXT_SECONDARY,
        )
        self._status_lbl.pack(anchor="w", padx=24, pady=(0, 8))

        # Recent transcripts
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
        lbl = ctk.CTkLabel(f, text=f"{icon}  {text}",
                           font=ctk.CTkFont(size=12), text_color="white")
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
                font=ctk.CTkFont(size=13), text_color=TEXT_SECONDARY, wraplength=400,
            ).pack(pady=40)
            return

        for rec in records:
            TranscriptCard(
                self._scroll, rec,
                on_delete=self._delete,
            ).pack(fill="x", pady=(0, 10))

    def set_status(self, text: str, color: str = TEXT_SECONDARY):
        self._status_lbl.configure(text=text, text_color=color)

    def _delete(self, tid: int):
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
            font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT_PRIMARY,
        ).pack(side="left")

        self._search = ctk.CTkEntry(
            top, placeholder_text="Search transcripts…",
            width=220, height=32, font=ctk.CTkFont(size=13),
        )
        self._search.pack(side="right")
        self._search.bind("<KeyRelease>", lambda _: self._on_search())

        self._scroll = ctk.CTkScrollableFrame(self, fg_color=CONTENT_BG)
        self._scroll.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.refresh()

    def _on_search(self):
        self._query = self._search.get().strip()
        self.refresh()

    def refresh(self):
        for w in self._scroll.winfo_children():
            w.destroy()

        records = (
            self._app.storage.search_transcripts(self._query)
            if self._query
            else self._app.storage.get_transcripts(limit=200)
        )

        if not records:
            ctk.CTkLabel(
                self._scroll,
                text="No transcripts yet." if not self._query else "No results.",
                font=ctk.CTkFont(size=13), text_color=TEXT_SECONDARY,
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
                    font=ctk.CTkFont(size=10, weight="bold"), text_color=TEXT_TIMESTAMP,
                ).pack(anchor="w", padx=8, pady=(12, 4))
            TranscriptCard(
                self._scroll, rec,
                on_delete=self._delete,
            ).pack(fill="x", pady=(0, 8))

    def _delete(self, tid: int):
        self._app.storage.delete_transcript(tid)
        self.refresh()


# ── Settings View ──────────────────────────────────────────────────────────────── #
class SettingsView(ctk.CTkFrame):
    HOTKEY_OPTIONS = ["fn", "right_alt", "right_cmd", "right_ctrl", "caps_lock",
                      "f1","f2","f3","f4","f5","f6","f7","f8","f9","f10","f11","f12"]
    MODEL_OPTIONS  = ["tiny.en","base.en","small.en","medium.en","large-v3",
                      "tiny","base","small","medium"]

    def __init__(self, parent, app_core, **kwargs):
        super().__init__(parent, fg_color=CONTENT_BG, **kwargs)
        self._app = app_core
        self._build()

    def _build(self):
        scroll = ctk.CTkScrollableFrame(self, fg_color=CONTENT_BG)
        scroll.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            scroll, text="Settings",
            font=ctk.CTkFont(size=22, weight="bold"), text_color=TEXT_PRIMARY,
        ).pack(anchor="w", pady=(0, 20))

        cfg = self._app.config

        self._section(scroll, "Recording")
        self._hotkey_var = ctk.StringVar(value=cfg["hotkey"])
        self._labeled_combo(scroll, "Hotkey", self._hotkey_var, self.HOTKEY_OPTIONS,
                            note="Hold this key to record. 'fn' = Fn/Globe key.")
        self._paste_var = ctk.BooleanVar(value=cfg["use_clipboard_paste"])
        self._labeled_switch(scroll, "Inject via clipboard paste (Standard mode)", self._paste_var,
                             note="Uses Cmd+V. Most reliable. Continuous Flow always uses direct typing.")

        self._section(scroll, "Transcription")
        self._model_var = ctk.StringVar(value=cfg["whisper_model"])
        self._labeled_combo(scroll, "Whisper model", self._model_var, self.MODEL_OPTIONS,
                            note="Larger = more accurate, slower to load. Used by both modes.")
        self._lang_var = ctk.StringVar(value=cfg.get("language") or "auto")
        self._labeled_entry(scroll, "Language", self._lang_var,
                            note="e.g. 'en', 'fr', 'es'. 'auto' = detect automatically.")
        self._format_var = ctk.BooleanVar(value=cfg["auto_format"])
        self._labeled_switch(scroll, "Auto-format text (Standard mode only)", self._format_var,
                             note="Fix punctuation, capitalization, verbal corrections. Not applied in Continuous Flow.")

        self._section(scroll, "AI post-processing / Ollama (Standard mode)")
        self._ai_var = ctk.BooleanVar(value=cfg["use_ai"])
        self._labeled_switch(scroll, "Use local AI (Ollama)", self._ai_var,
                             note="Requires Ollama running. Ignored in Continuous Flow mode.")
        self._ollama_url_var = ctk.StringVar(value=cfg["ollama_url"])
        self._labeled_entry(scroll, "Ollama URL", self._ollama_url_var)
        self._ollama_model_var = ctk.StringVar(value=cfg["ollama_model"])
        self._labeled_entry(scroll, "Ollama model", self._ollama_model_var,
                            note="e.g. llama3.1, mistral, phi3")

        ctk.CTkButton(
            scroll, text="Save settings", height=38,
            fg_color=ACCENT, hover_color="#5a53d4",
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._save,
        ).pack(pady=(20, 4), anchor="w")

        self._saved_lbl = ctk.CTkLabel(scroll, text="",
                                       font=ctk.CTkFont(size=12), text_color=GREEN)
        self._saved_lbl.pack(anchor="w")

    def _section(self, parent, title):
        ctk.CTkLabel(
            parent, text=title,
            font=ctk.CTkFont(size=14, weight="bold"), text_color=TEXT_PRIMARY,
        ).pack(anchor="w", pady=(16, 4))
        ctk.CTkFrame(parent, height=1, fg_color=BORDER).pack(fill="x", pady=(0, 8))

    def _labeled_combo(self, parent, label, var, options, note=""):
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=4)
        ctk.CTkLabel(row, text=label, width=220, anchor="w",
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
        ctk.CTkLabel(row, text=label, width=220, anchor="w",
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
        ("home",     "⌂",  "Home"),
        ("history",  "◷",  "History"),
        ("settings", "⚙",  "Settings"),
    ]

    def __init__(self, parent, app_core, on_select, **kwargs):
        super().__init__(parent, fg_color=SIDEBAR_BG, width=210, corner_radius=0, **kwargs)
        self.pack_propagate(False)
        self._app = app_core
        self._on_select = on_select
        self._nav_btns: dict[str, ctk.CTkButton] = {}
        self._build()

    def _build(self):
        # Logo
        logo_f = ctk.CTkFrame(self, fg_color="transparent")
        logo_f.pack(fill="x", padx=20, pady=(24, 4))
        ctk.CTkLabel(
            logo_f, text="OpenWhisper",
            font=ctk.CTkFont(size=17, weight="bold"), text_color="white",
        ).pack(anchor="w")
        ctk.CTkLabel(
            logo_f, text="Local voice dictation",
            font=ctk.CTkFont(size=11), text_color="#8888AA",
        ).pack(anchor="w")

        ctk.CTkFrame(self, height=1, fg_color="#2D2D4E").pack(fill="x", padx=16, pady=10)

        # Nav buttons
        for key, icon, label in self.NAV_ITEMS:
            btn = ctk.CTkButton(
                self,
                text=f"  {icon}  {label}",
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
            self._nav_btns[key] = btn

        self._select("home")

        ctk.CTkFrame(self, height=1, fg_color="#2D2D4E").pack(fill="x", padx=16, pady=(16, 8))

        # ── Mode toggle ── #
        self._mode_toggle = ModeToggle(
            self,
            current_mode=self._app.mode,
            on_change=self._on_mode_change,
        )
        self._mode_toggle.pack(fill="x", padx=10, pady=(0, 8))

        # Version
        ctk.CTkLabel(
            self, text="v1.0.0  ·  open source",
            font=ctk.CTkFont(size=10), text_color="#444466",
        ).pack(side="bottom", pady=10)

    def _select(self, key: str):
        for k, btn in self._nav_btns.items():
            btn.configure(fg_color=SIDEBAR_SEL if k == key else "transparent")
        self._on_select(key)

    def _on_mode_change(self, mode: str):
        self._app.set_mode(mode)

    def sync_mode(self, mode: str):
        """Keep the toggle in sync when mode changes externally."""
        self._mode_toggle.set_mode(mode)


# ── Main Window ───────────────────────────────────────────────────────────────── #
class MainWindow:
    def __init__(self, app_core):
        self._app = app_core
        self._overlay: Optional[RecordingOverlay] = None
        self._views: dict[str, ctk.CTkFrame] = {}
        self._sidebar: Optional[Sidebar] = None

        ctk.set_appearance_mode(app_core.config.get("theme", "dark"))
        ctk.set_default_color_theme("blue")

        self.root = ctk.CTk()
        self.root.title("OpenWhisper")
        self.root.geometry("980x680")
        self.root.minsize(760, 520)

        self._build()
        self._register_events()
        self._start_poll()

    # ------------------------------------------------------------------ #
    #  Layout                                                               #
    # ------------------------------------------------------------------ #

    def _build(self):
        self.root.grid_rowconfigure(0, weight=1)
        self.root.grid_columnconfigure(1, weight=1)

        self._sidebar = Sidebar(self.root, self._app, on_select=self._show_view)
        self._sidebar.grid(row=0, column=0, sticky="nsew")

        content = ctk.CTkFrame(self.root, fg_color=CONTENT_BG, corner_radius=0)
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

    # ------------------------------------------------------------------ #
    #  App event handlers                                                   #
    # ------------------------------------------------------------------ #

    def _register_events(self):
        self._app.on("recording_start",  self._on_rec_start)
        self._app.on("recording_stop",   self._on_rec_stop)
        self._app.on("transcript_ready", self._on_transcript_ready)
        self._app.on("model_loading",    self._on_model_loading)
        self._app.on("model_ready",      self._on_model_ready)
        self._app.on("error",            self._on_error)
        self._app.on("mode_changed",     self._on_mode_changed)

    def _on_rec_start(self):
        mode = self._app.mode
        home: HomeView = self._views["home"]
        if mode == MODE_CONTINUOUS:
            home.set_status("⚡ Continuous Flow — typing as you speak…", ORANGE)
        else:
            home.set_status("🔴 Recording…", REC_RED)

        if self._overlay is None:
            try:
                self._overlay = RecordingOverlay(mode)
            except Exception:
                pass

    def _on_rec_stop(self):
        home: HomeView = self._views["home"]
        if self._app.mode == MODE_CONTINUOUS:
            home.set_status("⚡ Wrapping up…", ORANGE)
        else:
            home.set_status("⚙ Transcribing…", ACCENT)

        if self._overlay:
            try:
                self._overlay.destroy()
            except Exception:
                pass
            self._overlay = None

    def _on_transcript_ready(self, text: str, duration: float):
        home: HomeView = self._views["home"]
        home.set_status("● Ready — hold hotkey to record", GREEN)
        home.refresh()
        self._views["history"].refresh()
        self.root.after(4000, lambda: home.set_status("● Ready — hold hotkey to record", GREEN))

    def _on_model_loading(self):
        self._views["home"].set_status(
            "⏳ Loading Whisper model (first run may take a minute)…", TEXT_SECONDARY
        )

    def _on_model_ready(self):
        mode = self._app.mode
        if mode == MODE_CONTINUOUS:
            self._views["home"].set_status("⚡ Ready — Continuous Flow active", ORANGE)
        else:
            self._views["home"].set_status("● Ready — hold hotkey to record", GREEN)

    def _on_error(self, msg: str):
        self._views["home"].set_status(f"⚠ {msg[:80]}", REC_RED)
        print(f"[OpenWhisper ERROR] {msg}")

    def _on_mode_changed(self, mode: str):
        """Sync sidebar toggle and status label when mode changes."""
        if self._sidebar:
            self._sidebar.sync_mode(mode)
        home: HomeView = self._views["home"]
        if mode == MODE_CONTINUOUS:
            home.set_status("⚡ Continuous Flow — live typing mode active", ORANGE)
        else:
            home.set_status("● Standard — hold hotkey to record", GREEN)

    # ------------------------------------------------------------------ #
    #  Event loop                                                           #
    # ------------------------------------------------------------------ #

    def _start_poll(self):
        def poll():
            self._app.poll_events()
            self.root.after(100, poll)
        self.root.after(100, poll)

    def run(self):
        self._app.start()
        self.root.mainloop()
        self._app.stop()
