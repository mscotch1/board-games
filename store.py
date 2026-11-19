"""Where games are kept between requests, and across server restarts.

A store holds one text blob per game code (the registry decides what is in it)
plus two columns the registry queries without opening the blob: the game's
status and when it was last changed. SQLite keeps the file consistent if the
server is killed half way through a write.
"""

import os
import sqlite3
from threading import Lock

DATABASE_NAME = "games.sqlite3"


class MemoryStore:
    """Keeps games only for as long as the process lives. Used in tests."""

    def __init__(self):
        self._lock = Lock()
        self._rows = {}

    def load(self, code):
        with self._lock:
            row = self._rows.get(code)
            return row[2] if row else None

    def save(self, code, status, updated_at, data):
        with self._lock:
            self._rows[code] = (status, updated_at, data)

    def delete(self, code):
        with self._lock:
            self._rows.pop(code, None)

    def meta(self):
        """(code, status, updated_at) for every game."""
        with self._lock:
            return [(code, status, updated_at) for code, (status, updated_at, _) in self._rows.items()]

    def close(self):
        pass


class SqliteStore:
    """Keeps games in a SQLite file, so they survive a restart."""

    def __init__(self, path):
        directory = os.path.dirname(os.path.abspath(path))
        os.makedirs(directory, exist_ok=True)

        self._lock = Lock()
        # one connection shared by the server's threads, guarded by the lock
        self._db = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS games ("
            " code TEXT PRIMARY KEY,"
            " status TEXT NOT NULL,"
            " updated_at REAL NOT NULL,"
            " data TEXT NOT NULL)"
        )

    def load(self, code):
        with self._lock:
            row = self._db.execute("SELECT data FROM games WHERE code = ?", (code,)).fetchone()
            return row[0] if row else None

    def save(self, code, status, updated_at, data):
        with self._lock:
            self._db.execute(
                "INSERT INTO games (code, status, updated_at, data) VALUES (?, ?, ?, ?)"
                " ON CONFLICT(code) DO UPDATE SET status = excluded.status,"
                " updated_at = excluded.updated_at, data = excluded.data",
                (code, status, updated_at, data),
            )

    def delete(self, code):
        with self._lock:
            self._db.execute("DELETE FROM games WHERE code = ?", (code,))

    def meta(self):
        with self._lock:
            return self._db.execute("SELECT code, status, updated_at FROM games").fetchall()

    def close(self):
        with self._lock:
            self._db.close()


def open_store(location):
    """A store for DATA_DIR-style `location`: a directory, or "" / ":memory:" for no persistence."""
    if location in (None, "", ":memory:", "memory"):
        return MemoryStore()
    return SqliteStore(os.path.join(location, DATABASE_NAME))
