"""SQLite-backed centralized storage adapter for limits / Flask-Limiter.

Provides a thread-safe and process-safe rate-limiting backend in SQLite WAL mode.
Allows multi-worker Gunicorn deployments to share rate-limit counters without
requiring external Redis or Memcached infrastructure.
"""
import os
import sqlite3
import time
from urllib.parse import urlparse

import limits.storage
from limits.storage import Storage


class SqliteStorage(Storage):
    """Storage implementation using SQLite with WAL mode."""

    STORAGE_SCHEME = "sqlite"

    def __init__(self, uri: str, **kwargs):
        parsed = urlparse(uri)
        if uri.startswith("sqlite:///") and not uri.startswith("sqlite:////"):
            path = uri[len("sqlite:///"):]
        elif uri.startswith("sqlite:////"):
            path = "/" + uri[len("sqlite:////"):]
        else:
            path = parsed.path or ":memory:"

        self.db_path = path or ":memory:"
        if self.db_path != ":memory:":
            os.makedirs(os.path.dirname(os.path.abspath(self.db_path)), exist_ok=True)
        self._init_db()
        super().__init__(uri, **kwargs)

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=15.0)
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn

    def _init_db(self) -> None:
        with self._get_conn() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS rate_limits (
                    key TEXT PRIMARY KEY,
                    count INTEGER NOT NULL,
                    expires_at REAL NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_rate_limits_expires ON rate_limits(expires_at)"
            )

    @property
    def base_exceptions(self):
        return (sqlite3.Error, ValueError)

    def incr(self, key: str, expiry: float, amount: int = 1) -> int:
        now = time.time()
        expires = now + expiry
        with self._get_conn() as conn:
            conn.execute(
                "DELETE FROM rate_limits WHERE key = ? AND expires_at <= ?",
                (key, now),
            )
            cur = conn.execute(
                "SELECT count, expires_at FROM rate_limits WHERE key = ?",
                (key,),
            ).fetchone()
            if cur is None:
                new_count = amount
                conn.execute(
                    "INSERT INTO rate_limits (key, count, expires_at) VALUES (?, ?, ?)",
                    (key, new_count, expires),
                )
            else:
                new_count = cur[0] + amount
                conn.execute(
                    "UPDATE rate_limits SET count = ? WHERE key = ?",
                    (new_count, key),
                )
            conn.commit()
            return new_count

    def get(self, key: str) -> int:
        now = time.time()
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT count FROM rate_limits WHERE key = ? AND expires_at > ?",
                (key, now),
            ).fetchone()
            return cur[0] if cur else 0

    def get_expiry(self, key: str) -> float:
        now = time.time()
        with self._get_conn() as conn:
            cur = conn.execute(
                "SELECT expires_at FROM rate_limits WHERE key = ? AND expires_at > ?",
                (key, now),
            ).fetchone()
            return cur[0] if cur else now

    def clear(self, key: str) -> None:
        with self._get_conn() as conn:
            conn.execute("DELETE FROM rate_limits WHERE key = ?", (key,))
            conn.commit()

    def check(self) -> bool:
        try:
            with self._get_conn() as conn:
                conn.execute("SELECT 1").fetchone()
            return True
        except Exception:
            return False

    def reset(self) -> int | None:
        with self._get_conn() as conn:
            cur = conn.execute("DELETE FROM rate_limits")
            conn.commit()
            return cur.rowcount


# Automatically register the scheme on import
def register_sqlite_scheme():
    limits.storage.SCHEMES["sqlite"] = SqliteStorage
    # Also register under async variant if referenced
    if hasattr(limits.storage, "SCHEMES"):
        limits.storage.SCHEMES["sqlite"] = SqliteStorage
