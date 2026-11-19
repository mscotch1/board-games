"""The games that exist, who is playing them, and who is connected right now.

Every game lives in a Record, saved to a store after each change so it
survives a restart. A player is identified by a secret token handed out when
they create or join a game, not by their connection: a reload, a dropped
connection or a server restart just reconnects with the token and carries on.
Connections (socket ids) are runtime-only; a player may have several (two tabs).

The registry holds state in process memory, so it assumes a single server
process, as the rest of the server does.
"""

import json
import logging
import random
import secrets
import time
from threading import RLock
from typing import NamedTuple

import rules
from ai import LEVELS
from game import Game
from variants import DEFAULT_VARIANT, VARIANTS

log = logging.getLogger(__name__)

RECORD_VERSION = 1
CHAT_LIMIT = 100
TOKEN_BYTES = 16
PURGE_INTERVAL = 300  # seconds between sweeps for expired games

# how long a game may go without a change before it is deleted, by status
DEFAULT_TTL = {
    "waiting": 24 * 3600,  # created, but nobody has joined
    "playing": 7 * 24 * 3600,
    "finished": 24 * 3600,  # kept a while so players can still look at the result
}


class Refused(Exception):
    """A connection that can't be accepted; `code` says why in a machine-readable way."""

    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


class Record:
    """One game's saved state: its players' tokens, the game itself and the chat."""

    def __init__(self, code, variant_key, creator_token, creator_side, now):
        self.code = code
        self.variant_key = variant_key
        self.creator_token = creator_token
        self.creator_side = creator_side  # the side the creator asked for, or None for random
        self.created_at = now
        self.updated_at = now
        self.seats = None  # {side: token} once an opponent has joined
        self.bot = None  # the computer opponent's level ("easy", "medium", "hard"), if there is one
        self.bot_token = None  # the computer's seat token; no human ever holds it
        self.game = None
        self.chat = []  # [{"side": ..., "text": ...}], the most recent CHAT_LIMIT

    @property
    def status(self):
        if self.game is None:
            return "waiting"
        return "finished" if self.game.over else "playing"

    def add_chat(self, side, text):
        self.chat.append({"side": side, "text": text})
        del self.chat[:-CHAT_LIMIT]

    def to_dict(self):
        return {
            "version": RECORD_VERSION,
            "code": self.code,
            "variant": self.variant_key,
            "creatorToken": self.creator_token,
            "creatorSide": self.creator_side,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "seats": self.seats,
            "bot": self.bot,
            "botToken": self.bot_token,
            "game": self.game.to_dict() if self.game else None,
            "chat": self.chat,
        }

    @classmethod
    def from_dict(cls, data):
        try:
            if data["version"] != RECORD_VERSION:
                raise ValueError(f"unknown record version {data['version']!r}")
            record = cls(data["code"], data["variant"], data["creatorToken"], data["creatorSide"], data["createdAt"])
            record.updated_at = data["updatedAt"]
            record.seats = data["seats"]
            record.bot = data.get("bot")
            record.bot_token = data.get("botToken")
            if record.bot is not None and (record.bot not in LEVELS or not record.bot_token):
                raise ValueError("the saved computer opponent isn't valid")
            record.game = Game.from_dict(data["game"]) if data["game"] is not None else None
            record.chat = [{"side": m["side"], "text": m["text"]} for m in data["chat"]]
            if record.game is not None and not (record.seats and set(record.seats) == {rules.WHITE, rules.BLACK}):
                raise ValueError("a game needs a token for each side")
            return record
        except (KeyError, TypeError, AttributeError) as e:
            raise ValueError(f"not a valid saved record: {e!r}") from e


class Attached(NamedTuple):
    kind: str  # "waiting" (no opponent yet), "started" (the second player just joined), "resumed"
    record: Record
    token: str  # the connecting player's token (new, for a first connection)
    first_connection: bool  # whether this player had no other connection before


class Detached(NamedTuple):
    record: Record
    token: str
    offline: bool  # the player has no connections left


class Session(NamedTuple):
    record: Record
    token: str
    seat: str  # "white" or "black", or None for a creator still waiting for an opponent


class Registry:
    def __init__(self, store, *, ttl=None, clock=time.time, rng=None, max_games=None):
        self._store = store
        self._max_games = max_games  # refuse new games beyond this many (None for no limit)
        self._ttl = {**DEFAULT_TTL, **(ttl or {})}
        self._clock = clock
        self._rng = rng or random.Random()
        self._lock = RLock()
        self._records = {}  # code -> Record, for games loaded from the store
        self._sessions = {}  # sid -> (code, token)
        self._sids = {}  # (code, token) -> set of sids
        self._last_purge = clock()
        self.purge_expired()

    # --- connecting -----------------------------------------------------------

    def attach(self, sid, code, *, token=None, resume=False, side=None, variant_key=None, computer=None,
               before_create=None):
        """Connect `sid` to the game `code`. Raises Refused.

        `token` is the player's secret. A token that belongs to the game means a returning
        player. Otherwise this is a new player: the creator of a new game, or the opponent
        joining a waiting one, and their token (made up here if they didn't bring one)
        is theirs from now on. `resume` says the player has been in this game before, so
        a game that can't be found is an error rather than a new game. `computer`, for a new game, is
        the level of a computer opponent, who takes the other seat at once. `before_create`, if given,
        is called just before a brand-new game is made, and may raise Refused to stop it.
        """
        with self._lock:
            self._maybe_purge()
            record = self._get(code)

            if record is not None and token is not None and self._owns(record, token):
                first = self._connect(sid, record, token)
                return Attached("resumed" if record.game else "waiting", record, token, first)

            if resume:
                raise Refused("That game could not be found. It may have expired.", "not-found")

            token = token or self._new_token()

            if record is None:
                if before_create is not None:
                    before_create()
                if self._max_games and len(self._store.meta()) >= self._max_games:
                    raise Refused("The server is full of games right now. Please try again later.", "busy")
                variant = VARIANTS.get(variant_key, DEFAULT_VARIANT)
                creator_side = side if side in (rules.WHITE, rules.BLACK) else None
                record = Record(code, variant.key, token, creator_side, self._clock())
                self._records[code] = record
                if computer in LEVELS:
                    record.bot, record.bot_token = computer, self._new_token()
                    self._start(record, record.bot_token)  # saves the game
                    return Attached("resumed", record, token, self._connect(sid, record, token))
                self.save(record)
                return Attached("waiting", record, token, self._connect(sid, record, token))

            if record.status == "waiting":
                self._start(record, token)
                return Attached("started", record, token, self._connect(sid, record, token))

            if record.status == "finished":
                raise Refused("That game has already finished", "finished")
            raise Refused("Game already full", "full")

    def detach(self, sid):
        """Forget a connection. Returns what changed, or None if it wasn't in a game."""
        with self._lock:
            entry = self._sessions.pop(sid, None)
            if entry is None:
                return None
            code, token = entry
            sids = self._sids.get((code, token), set())
            sids.discard(sid)
            offline = not sids
            if offline:
                self._sids.pop((code, token), None)
            record = self._get(code)
            return Detached(record, token, offline) if record else None

    def cancel(self, sid):
        """The creator gives up on a game nobody has joined; it is deleted. Returns whether it was."""
        with self._lock:
            session = self.session(sid)
            if session is None or session.record.status != "waiting" or session.token != session.record.creator_token:
                return False
            self._delete(session.record.code)
            return True

    def _start(self, record, joiner_token):
        creator_side = record.creator_side or self._rng.choice((rules.WHITE, rules.BLACK))
        record.seats = {creator_side: record.creator_token, rules.other(creator_side): joiner_token}
        record.game = Game(VARIANTS[record.variant_key])
        self.save(record)

    def _connect(self, sid, record, token):
        self._sessions[sid] = (record.code, token)
        sids = self._sids.setdefault((record.code, token), set())
        sids.add(sid)
        return len(sids) == 1

    # --- who is who -----------------------------------------------------------

    def session(self, sid):
        with self._lock:
            entry = self._sessions.get(sid)
            if entry is None:
                return None
            code, token = entry
            record = self._get(code)
            if record is None:
                return None
            return Session(record, token, self.seat_of(record, token))

    def seat_of(self, record, token):
        for side, seat_token in (record.seats or {}).items():
            if secrets.compare_digest(seat_token, token):
                return side
        return None

    def opponent_token(self, record, token):
        for seat_token in (record.seats or {}).values():
            if not secrets.compare_digest(seat_token, token):
                return seat_token
        return None

    def sids(self, record, token):
        """The live connections of the player holding `token`."""
        with self._lock:
            return sorted(self._sids.get((record.code, token), ()))

    def online(self, record, token):
        if record.bot_token is not None and token == record.bot_token:
            return True  # the computer is always there
        return bool(self.sids(record, token))

    def _owns(self, record, token):
        tokens = list((record.seats or {}).values()) or [record.creator_token]
        return any(secrets.compare_digest(token, t) for t in tokens)

    @staticmethod
    def _new_token():
        return secrets.token_urlsafe(TOKEN_BYTES)

    # --- keeping games --------------------------------------------------------

    def save(self, record):
        """Write the game to the store. Call after every change worth keeping."""
        with self._lock:
            record.updated_at = self._clock()
            self._store.save(record.code, record.status, record.updated_at, json.dumps(record.to_dict()))

    def _get(self, code):
        record = self._records.get(code)
        if record is not None:
            return record

        data = self._store.load(code)
        if data is None:
            return None
        try:
            record = Record.from_dict(json.loads(data))
        except (ValueError, json.JSONDecodeError) as e:
            # a game we can't read is as good as gone; the code can be used again
            log.warning("ignoring unreadable saved game %r: %s", code, e)
            return None
        self._records[code] = record
        return record

    def _delete(self, code):
        self._records.pop(code, None)
        self._store.delete(code)

    def records(self):
        """The games currently loaded in memory."""
        with self._lock:
            return list(self._records.values())

    def stats(self):
        """How many games there are by status, and how many players are connected. Reads the
        store, so it also shows whether the store is working."""
        with self._lock:
            games = {"waiting": 0, "playing": 0, "finished": 0}
            for _, status, _ in self._store.meta():
                games[status] = games.get(status, 0) + 1
            return {"games": games, "playersOnline": len(self._sids)}

    # --- expiry ---------------------------------------------------------------

    def purge_expired(self):
        """Delete games that have gone unchanged for longer than their status allows.
        Games with someone connected are kept. Returns how many were deleted."""
        with self._lock:
            now = self._clock()
            self._last_purge = now
            live = {code for code, _ in self._sids}
            deleted = 0
            for code, status, updated_at in self._store.meta():
                if code in live:
                    continue
                if now - updated_at > self._ttl.get(status, self._ttl["playing"]):
                    self._delete(code)
                    deleted += 1
            return deleted

    def _maybe_purge(self):
        if self._clock() - self._last_purge >= PURGE_INTERVAL:
            self.purge_expired()

