"""A computer opponent: iterative-deepening negamax with alpha-beta pruning.

The search uses the same rules as the server (rules.legal_turns and apply_turn), so the
computer can only ever play legal turns, and the rules exist in one place. A turn is a
whole jump chain, so one step of the search is one turn.

It looks for a given time or number of positions, deepening one ply at a time, and plays
the best move of the deepest search that finished. The difficulty levels differ only in
how long it looks and how often it plays a near-best move instead of the best one.
"""

import logging
import os
import random
import time
from collections import Counter
from typing import NamedTuple

import rules
from rules import apply_turn, legal_turns, other, owner

log = logging.getLogger(__name__)

WIN = 100_000

# how much each thing is worth, in hundredths of a man
DEFAULT_WEIGHTS = {
    "man": 100,
    "knight": 150,
    "advance": 60,  # for a piece that has crossed the whole board
    "goal": 120,  # for a piece standing in the enemy castle
}


class Level(NamedTuple):
    seconds: float
    max_depth: int
    slack: int  # may play any move within this many points of the best (0 always plays the best)


LEVELS = {
    "easy": Level(0.25, 2, 60),
    "medium": Level(0.5, 4, 15),
    "hard": Level(1.0, 30, 0),
}
DEFAULT_LEVEL = "medium"

TABLE_LIMIT = 300_000
CHECK_EVERY = 128
MIN_DEPTH = 2  # plies searched whatever the time limit
PENALTY_PER_REPEAT = 40  # steers away from repeating a position when not worse off


class _OutOfTime(Exception):
    pass


class _Tables:
    """Per-variant lookups, built once: how far along each square is for each side."""

    def __init__(self, variant):
        last = variant.rows - 1
        self.progress = {
            rules.WHITE: [(last - variant.row(i)) / last for i in range(variant.size)],
            rules.BLACK: [variant.row(i) / last for i in range(variant.size)],
        }


_tables_for = {}


def _tables(variant):
    if variant.key not in _tables_for:
        _tables_for[variant.key] = _Tables(variant)
    return _tables_for[variant.key]


def advance_table(variant, weights):
    """(white's, black's) value of standing on each square, in whole hundredths: all the arithmetic
    is on integers, so the Python and C searches agree exactly."""
    progress = _tables(variant).progress
    return tuple(
        tuple(int(round(weights["advance"] * p)) for p in progress[side]) for side in (rules.WHITE, rules.BLACK)
    )


def scan(variant, board, weights=DEFAULT_WEIGHTS):
    """One pass over `board`: ({side: pieces}, {side: pieces in the enemy castle}, {side: value})."""
    advance = dict(zip((rules.WHITE, rules.BLACK), advance_table(variant, weights)))
    man, knight, goal_bonus = weights["man"], weights["knight"], weights["goal"]
    goal = variant.goal_castle
    pieces = {rules.WHITE: 0, rules.BLACK: 0}
    home = {rules.WHITE: 0, rules.BLACK: 0}
    value = {rules.WHITE: 0, rules.BLACK: 0}
    for square, piece in enumerate(board):
        if not piece:
            continue
        side = rules.WHITE if piece <= 2 else rules.BLACK
        pieces[side] += 1
        value[side] += (knight if piece % 2 == 0 else man) + advance[side][square]
        if square in goal[side]:
            home[side] += 1
            value[side] += goal_bonus
    return pieces, home, value


def evaluate(variant, board, side, weights=DEFAULT_WEIGHTS):
    """How good `board` is for `side`, in hundredths of a man (higher is better)."""
    _, _, value = scan(variant, board, weights)
    return int(value[side] - value[other(side)])


class Searcher:
    """One search for one move. Make a new one for each move.

    The search carries each position's tally (pieces, pieces in the enemy castle, value) along
    and updates it from the turn just played, so a position at the edge of the search is scored
    from the turn alone, without copying the board or scanning it. Generating a position's
    legal turns is the expensive part, so the search tries hard to need as few positions
    expanded as it can: the best move from the last, shallower search goes first, then the
    rest by how good they look, and the root passes what it has learnt to each later move.
    """

    def __init__(self, variant, weights=DEFAULT_WEIGHTS, seconds=1.0, max_nodes=None, max_depth=30,
                 min_depth=MIN_DEPTH, beam=None):
        self.variant = variant
        self.weights = weights
        self.deadline = time.monotonic() + seconds if seconds else None
        self.max_nodes = max_nodes
        self.max_depth = max_depth
        self.min_depth = min_depth
        self.beam = beam  # past the first move, look only at this many of the best-looking turns (None for all)
        self.nodes = 0
        self.expanded = 0  # positions whose legal turns were generated
        self.depth_reached = 0
        self._guaranteed = True  # the first min_depth plies always finish, so no piece is hung to a reply
        self._table = {}

        self._sides = (rules.WHITE, rules.BLACK)
        self._advance = advance_table(variant, weights)
        self._goal = tuple(frozenset(variant.goal_castle[side]) for side in self._sides)
        self._goal_bonus = weights["goal"]
        self._base = (0, weights["man"], weights["knight"], weights["man"], weights["knight"])

    # --- bookkeeping ----------------------------------------------------------

    def _tick(self):
        self.nodes += 1
        if self.nodes % CHECK_EVERY or self._guaranteed:
            return
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            raise _OutOfTime
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise _OutOfTime

    def tally(self, board):
        """(white pieces, black pieces, white in enemy castle, black in enemy castle, white value, black value)."""
        pieces, home, value = scan(self.variant, board, self.weights)
        w, b = self._sides
        return pieces[w], pieces[b], home[w], home[b], value[w], value[b]

    def _played(self, tally, board, turn, mover):
        """The tally after `mover` (0 white, 1 black) plays `turn` on `board`, worked out from the turn alone."""
        opponent = 1 - mover
        t = list(tally)
        start, end = turn.moves[0], turn.moves[-1]
        if end != start:
            gain = self._advance[mover][end] - self._advance[mover][start]
            goal = self._goal[mover]
            if end in goal:
                gain += self._goal_bonus
                t[2 + mover] += 1
            if start in goal:
                gain -= self._goal_bonus
                t[2 + mover] -= 1
            t[4 + mover] += gain
        for square in turn.jumped:
            if square is not None:
                lost = self._base[board[square]] + self._advance[opponent][square]
                if square in self._goal[opponent]:
                    lost += self._goal_bonus
                    t[2 + opponent] -= 1
                t[4 + opponent] -= lost
                t[opponent] -= 1
        return tuple(t)

    def _result(self, t, mover):
        """The game's result for `mover` if `t` is a finished position (this mirrors Game._decide), else None."""
        variant = self.variant
        for side in (0, 1):
            if t[2 + side] >= variant.castle_to_win:
                return WIN if side == mover else -WIN
        for side in (0, 1):
            if not t[side]:
                winner = 1 - side
                if variant.wins_need_two_pieces and t[winner] < 2:
                    continue
                return WIN if winner == mover else -WIN
        if variant.draws and t[mover] <= 1 and t[1 - mover] <= 1:
            return 0
        return None

    def _children(self, board, side, castle_moves, legal, tally, first):
        """(static value for `side`, turn, tally, castle move counts) for each turn, most promising first."""
        goal = self.variant.goal_castle[self._sides[side]]
        out = []
        for turn in legal:
            counts = castle_moves
            if turn.moves[0] in goal and turn.moves[-1] in goal:
                counts = (castle_moves[0] + (side == 0), castle_moves[1] + (side == 1))
            after = self._played(tally, board, turn, side)
            static = after[4 + side] - after[5 - side]
            out.append((static, turn, after, counts))
        # the move the last search liked first, then whichever looks best on the board
        out.sort(key=lambda c: (c[1].moves == first, c[0]), reverse=True)
        return out

    def _score_child(self, board, side, turn, after, counts, static, depth, alpha, beta, ply):
        """The value, for `side`, of playing `turn` (searching `depth` plies, this one included)."""
        result = self._result(after, side)
        if result is None:
            if depth <= 1:
                return int(static)
            board_after = apply_turn(board, turn)
            opponent = 1 - side
            self.expanded += 1
            replies = legal_turns(self.variant, board_after, self._sides[opponent], counts[opponent])
            if replies:
                return -self._search(board_after, opponent, counts, replies, after, depth - 1, -beta, -alpha, ply + 1)
            # the opponent has no move: blocked, which wins unless that would leave a lone piece
            if self.variant.wins_need_two_pieces and after[side] < 2:
                return 0
            result = WIN
        # the game ended: prefer quicker wins and slower losses
        return result - ply if result > 0 else result + ply if result < 0 else 0

    # --- the search -----------------------------------------------------------

    def _search(self, board, side, castle_moves, legal, tally, depth, alpha, beta, ply):
        """The value of `board` for `side` (0 white, 1 black) to move, with `legal` its legal turns."""
        self._tick()
        key = (tuple(board), side, castle_moves)
        entry = self._table.get(key)
        first = None
        if entry is not None:
            stored_depth, flag, stored, first = entry
            if stored_depth >= depth:
                if flag == 0:
                    return stored
                if flag == 1:  # a lower bound
                    alpha = max(alpha, stored)
                else:  # an upper bound
                    beta = min(beta, stored)
                if alpha >= beta:
                    return stored

        original_alpha = alpha
        best, best_moves = -WIN - 1, None
        children = self._children(board, side, castle_moves, legal, tally, first)
        if self.beam and depth >= 2:
            # a forced capture leaves few turns, so this only ever trims the quiet moves
            children = children[: self.beam]
        for static, turn, after, counts in children:
            self._tick()
            score = self._score_child(board, side, turn, after, counts, static, depth, alpha, beta, ply)
            if score > best:
                best, best_moves = score, turn.moves
            alpha = max(alpha, best)
            if alpha >= beta:
                break

        if len(self._table) < TABLE_LIMIT:
            flag = 2 if best <= original_alpha else 1 if best >= beta else 0
            self._table[key] = (depth, flag, best, best_moves)
        return best

    def best_turns(self, board, side, castle_moves, legal, seen=None, slack=0):
        """Score the legal turns at the deepest depth that finishes in time. `side` is a side name.

        Returns [(score, turn)], best first. The best turn's score is exact, and so is any turn
        within `slack` of it; a worse one's score is only an upper bound, which is all that is
        needed to know it isn't a candidate. `seen` is a Counter of positions already played, so
        the computer prefers not to repeat them.
        """
        scored = [(0, t) for t in legal]
        if len(legal) == 1:
            return scored

        me = 0 if side == rules.WHITE else 1
        tally = self.tally(board)
        castle_moves = tuple(castle_moves)
        previous = {}
        for depth in range(1, self.max_depth + 1):
            self._guaranteed = depth <= self.min_depth
            results = []
            best = -WIN - 1
            try:
                children = self._children(board, me, castle_moves, legal, tally, None)
                # the last search's best moves first; that is what lets the later moves be pruned
                children.sort(key=lambda c: previous.get(c[1].moves, c[0]), reverse=True)
                for static, turn, after, counts in children:
                    penalty = 0
                    if seen:
                        penalty = PENALTY_PER_REPEAT * seen.get((tuple(apply_turn(board, turn)), other(side)), 0)
                    # a move more than `slack` worse than the best so far can't be chosen, so it is
                    # searched only far enough to show that (its score is then just an upper bound)
                    floor = max(best - slack - 1 + penalty, -WIN - 1)
                    self._tick()
                    score = self._score_child(board, me, turn, after, counts, static, depth, floor, WIN + 1, 1)
                    results.append((score - penalty, turn))
                    best = max(best, score - penalty)
            except _OutOfTime:
                break
            scored = sorted(results, key=lambda r: r[0], reverse=True)
            previous = {t.moves: sc for sc, t in scored}
            self.depth_reached = depth
            if scored[0][0] >= WIN - 100 or scored[0][0] <= -WIN + 100:
                break  # a forced win or loss has been found; looking deeper won't change it
        return scored


def searcher_class(native=None):
    """The search to use: the C one if it's built, else the Python one. `native` forces a choice
    (True needs the library); the environment variable AI_NATIVE=0 turns the C search off."""
    if native is None:
        native = os.environ.get("AI_NATIVE") != "0"
    if native:
        import native_search

        if native_search.available():
            return native_search.NativeSearcher
        if native is True:
            raise RuntimeError("the native search library isn't built")
    return Searcher


def choose_turn(variant, board, side, castle_moves, legal, *, level=DEFAULT_LEVEL, seen=None,
                weights=DEFAULT_WEIGHTS, rng=random, max_nodes=None, min_depth=MIN_DEPTH, native=None):
    """The turn the computer plays: one of `legal`, chosen by searching.

    `castle_moves` is {side: moves already made between the castle squares}. Raises
    ValueError when there is nothing to play.
    """
    if not legal:
        raise ValueError("there is no legal turn to choose")
    settings = LEVELS[level]
    counts = (castle_moves[rules.WHITE], castle_moves[rules.BLACK])
    def search(cls):
        searcher = cls(variant, weights, settings.seconds, max_nodes, settings.max_depth, min_depth)
        return searcher.best_turns(list(board), side, counts, list(legal), seen, settings.slack)

    cls = searcher_class(native)
    try:
        scored = search(cls)
    except RuntimeError:
        if cls is Searcher:
            raise
        log.exception("the native search failed; using the Python one")
        scored = search(Searcher)
    top = scored[0][0]
    # never gamble away a forced win or into a forced loss; otherwise sometimes play a near-best move
    candidates = [t for s, t in scored if s >= top - settings.slack and abs(s) < WIN - 100]
    return rng.choice(candidates) if candidates and settings.slack else scored[0][1]


def game_seen(game):
    """The positions a Game has been through, in the form `choose_turn` takes."""
    return Counter(game._positions)
