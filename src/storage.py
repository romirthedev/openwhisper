"""
SQLite storage for transcript history.
"""
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from config import DB_FILE


class Storage:
    def __init__(self):
        self._local = threading.local()
        self._db_path = str(DB_FILE)
        self._init_db()

    def _conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path)
            self._local.conn.row_factory = sqlite3.Row
        return self._local.conn

    def _init_db(self):
        with sqlite3.connect(self._db_path) as conn:
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
            conn.commit()

    def save_transcript(self, text: str, raw_text: str = None, duration: float = None) -> int:
        word_count = len(text.split())
        now = datetime.now().isoformat()
        with sqlite3.connect(self._db_path) as conn:
            cur = conn.execute(
                "INSERT INTO transcripts (text, raw_text, duration_seconds, word_count, created_at) VALUES (?,?,?,?,?)",
                (text, raw_text or text, duration, word_count, now),
            )
            conn.commit()
            return cur.lastrowid

    def get_transcripts(self, limit: int = 100, offset: int = 0) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM transcripts ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            ).fetchall()
        return [dict(r) for r in rows]

    def search_transcripts(self, query: str) -> list[dict]:
        with sqlite3.connect(self._db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM transcripts WHERE text LIKE ? ORDER BY created_at DESC LIMIT 200",
                (f"%{query}%",),
            ).fetchall()
        return [dict(r) for r in rows]

    def delete_transcript(self, transcript_id: int):
        with sqlite3.connect(self._db_path) as conn:
            conn.execute("DELETE FROM transcripts WHERE id = ?", (transcript_id,))
            conn.commit()

    def get_stats(self) -> dict:
        with sqlite3.connect(self._db_path) as conn:
            row = conn.execute("""
                SELECT
                    COUNT(*) as total_count,
                    SUM(word_count) as total_words,
                    SUM(duration_seconds) as total_seconds,
                    MIN(created_at) as first_at
                FROM transcripts
            """).fetchone()
        if not row or row[0] == 0:
            return {"total_count": 0, "total_words": 0, "total_seconds": 0, "streak_days": 0}

        total_words = row[1] or 0
        total_seconds = row[2] or 0
        wpm = round((total_words / (total_seconds / 60))) if total_seconds > 0 else 0

        # Compute streak (consecutive days with transcripts)
        streak = self._compute_streak()

        return {
            "total_count": row[0],
            "total_words": total_words,
            "total_seconds": total_seconds,
            "wpm": wpm,
            "streak_days": streak,
        }

    def _compute_streak(self) -> int:
        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                "SELECT DATE(created_at) as day FROM transcripts GROUP BY day ORDER BY day DESC"
            ).fetchall()
        if not rows:
            return 0

        streak = 1
        today = datetime.now().date()
        prev = datetime.fromisoformat(rows[0][0]).date()

        if (today - prev).days > 1:
            return 0

        for row in rows[1:]:
            d = datetime.fromisoformat(row[0]).date()
            if (prev - d).days == 1:
                streak += 1
                prev = d
            else:
                break
        return streak
