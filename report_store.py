"""
report_store.py — Persistent storage for ARIA diagnosis reports and health history.
"""

import sqlite3
from datetime import datetime


class ReportStore:
    def __init__(self, path: str = "aria.db"):
        self.path = path
        self.conn: sqlite3.Connection | None = None

    def init(self):
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        cur = self.conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS reports (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ts          TEXT NOT NULL,
                health_score REAL NOT NULL,
                trigger     TEXT NOT NULL,
                content     TEXT NOT NULL
            )
        """)

        cur.execute("""
            CREATE TABLE IF NOT EXISTS health_log (
                id    INTEGER PRIMARY KEY AUTOINCREMENT,
                ts    TEXT NOT NULL,
                score REAL NOT NULL
            )
        """)

        self.conn.commit()

    def save_report(self, content: str, score: float, trigger: str = "auto"):
        if not self.conn:
            return
        ts = datetime.utcnow().isoformat()
        self.conn.execute(
            "INSERT INTO reports (ts, health_score, trigger, content) VALUES (?,?,?,?)",
            (ts, score, trigger, content)
        )
        self.conn.execute(
            "INSERT INTO health_log (ts, score) VALUES (?,?)",
            (ts, score)
        )
        self.conn.commit()

    def get_reports(self, limit: int = 10) -> list[dict]:
        if not self.conn:
            return []
        rows = self.conn.execute(
            "SELECT ts, health_score, trigger, content FROM reports ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    def get_health_history(self, limit: int = 60) -> list[dict]:
        if not self.conn:
            return []
        rows = self.conn.execute(
            "SELECT ts, score FROM health_log ORDER BY id DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [dict(r) for r in reversed(rows)]
