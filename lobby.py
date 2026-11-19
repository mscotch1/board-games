from enum import Enum
from threading import Lock


class JoinResult(Enum):
    WAITING = "waiting"
    PAIRED = "paired"
    FULL = "full"


class Lobby:
    """Tracks which clients are waiting for an opponent and which are paired.

    All state lives in process memory, so the server must run as a single
    worker process. A lock keeps it consistent across worker threads.
    """

    def __init__(self):
        self._lock = Lock()
        self._waiting = {}  # game code -> sid of the player waiting for an opponent
        self._opponents = {}  # sid -> sid of that player's opponent
        self._codes = {}  # sid -> game code
        self._full = set()  # game codes with two players

    def join(self, code, sid):
        """Register `sid` for `code`. Returns (result, opponent_sid or None)."""
        with self._lock:
            if sid in self._codes:
                raise ValueError(f"{sid} has already joined a game")

            if code in self._full:
                return JoinResult.FULL, None

            self._codes[sid] = code

            if code in self._waiting:
                opponent = self._waiting.pop(code)
                self._opponents[sid] = opponent
                self._opponents[opponent] = sid
                self._full.add(code)
                return JoinResult.PAIRED, opponent

            self._waiting[code] = sid
            return JoinResult.WAITING, None

    def leave(self, sid):
        """Remove `sid` and free its game code. Returns the opponent's sid, if any."""
        with self._lock:
            code = self._codes.pop(sid, None)
            if code is None:
                return None

            if self._waiting.get(code) == sid:
                del self._waiting[code]

            opponent = self._opponents.pop(sid, None)
            if opponent is not None:
                # The game is over, so the opponent is no longer paired either.
                del self._opponents[opponent]
                self._codes.pop(opponent, None)
                self._full.discard(code)

            return opponent

    def opponent(self, sid):
        with self._lock:
            return self._opponents.get(sid)
