"""A computer opponent: iterative-deepening negamax with alpha-beta pruning.

The search uses the same rules as the server (rules.legal_turns and apply_turn), so the
computer can only ever play legal turns, and the rules exist in one place. A turn is a
whole jump chain, so one step of the search is one turn.

It looks for a given time or number of positions, deepening one ply at a time, and plays
the best move of the deepest search that finished. The difficulty levels differ only in
how long it looks and how often it plays a near-best move instead of the best one.
"""

import random
import time
from collections import Counter
from typing import NamedTuple

import rules
from rules import apply_turn, legal_turns, other, owner

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
    "medium": Level(0.6, 4, 15),
    "hard": Level(1.2, 30, 0),
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


def scan(variant, board, weights=DEFAULT_WEIGHTS):
    """One pass over `board`: ({side: pieces}, {side: pieces in the enemy castle}, {side: value})."""
    progress = _tables(variant).progress
    man, knight = weights["man"], weights["knight"]
    advance, goal_bonus = weights["advance"], weights["goal"]
    goal = variant.goal_castle
    pieces = {rules.WHITE: 0, rules.BLACK: 0}
    home = {rules.WHITE: 0, rules.BLACK: 0}
    value = {rules.WHITE: 0.0, rules.BLACK: 0.0}
    for square, piece in enumerate(board):
        if not piece:
            continue
        side = rules.WHITE if piece <= 2 else rules.BLACK
        pieces[side] += 1
        value[side] += (knight if piece % 2 == 0 else man) + advance * progress[side][square]
        if square in goal[side]:
            home[side] += 1
            value[side] += goal_bonus
    return pieces, home, value


def evaluate(variant, board, side, weights=DEFAULT_WEIGHTS):
    """How good `board` is for `side`, in hundredths of a man (higher is better)."""
    _, _, value = scan(variant, board, weights)
    return int(value[side] - value[other(side)])


class Searcher:
    """One search for one move. Make a new one for each move."""

    def __init__(self, variant, weights=DEFAULT_WEIGHTS, seconds=1.0, max_nodes=None, max_depth=30, min_depth=MIN_DEPTH):
        self.variant = variant
        self.weights = weights
        self.deadline = time.monotonic() + seconds if seconds else None
        self.max_nodes = max_nodes
        self.max_depth = max_depth
        self.min_depth = min_depth
        self.nodes = 0
        self.depth_reached = 0
        self._guaranteed = True  # the first MIN_DEPTH plies always finish, so no piece is hung to a reply
        self._table = {}

    def _tick(self):
        self.nodes += 1
        if self.nodes % CHECK_EVERY or self._guaranteed:
            return
        if self.max_nodes is not None and self.nodes >= self.max_nodes:
            raise _OutOfTime
        if self.deadline is not None and time.monotonic() >= self.deadline:
            raise _OutOfTime

    def _after(self, board, mover, castle_moves, need_legal=True):
        """What playing a turn led to: (score, legal turns, static value), all for the side that
        just moved or its opponent as noted. This mirrors Game._decide.

        If the game is over the score is its result for `mover` and the turns are None. Otherwise
        the score is None and the turns are the next side's legal ones, with the board's static
        value for `mover`. With `need_legal` false (at the leaves of the search) the turns aren't
        generated, which is most of the cost, so a player who is blocked there isn't noticed
        until the next ply."""
        variant = self.variant
        pieces, home, value = scan(variant, board, self.weights)
        nxt = other(mover)

        for side in (rules.WHITE, rules.BLACK):
            if home[side] >= variant.castle_to_win:
                return (WIN if side == mover else -WIN), None, 0
        for side in (rules.WHITE, rules.BLACK):
            if not pieces[side]:
                winner = other(side)
                if variant.wins_need_two_pieces and pieces[winner] < 2:
                    continue
                return (WIN if winner == mover else -WIN), None, 0

        if variant.draws and pieces[mover] <= 1 and pieces[nxt] <= 1:
            return 0, None, 0

        static = int(value[mover] - value[nxt])
        if not need_legal:
            return None, (), static

        legal = legal_turns(variant, board, nxt, castle_moves[nxt == rules.BLACK])
        if not legal:
            if variant.wins_need_two_pieces and pieces[mover] < 2:
                return 0, None, 0
            return WIN, None, 0
        return None, legal, static

    def _children(self, board, side, castle_moves, legal, first):
        """(turn, new board, new castle move counts) for each turn, most promising first."""
        goal = self.variant.goal_castle[side]
        index = side == rules.BLACK
        out = []
        for turn in legal:
            counts = castle_moves
            if turn.moves[0] in goal and turn.moves[-1] in goal:
                counts = (castle_moves[0] + (not index), castle_moves[1] + index)
            out.append((turn, apply_turn(board, turn), counts))
        # the best move found so far first, then the longest jumps; this makes pruning bite
        out.sort(key=lambda c: (c[0].moves == first, len(c[0].moves)), reverse=True)
        return out

    def _search(self, board, side, castle_moves, legal, depth, alpha, beta, ply):
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
        for turn, new_board, counts in self._children(board, side, castle_moves, legal, first):
            self._tick()
            score, replies, static = self._after(new_board, side, counts, depth > 1)
            if replies is None:
                # the game ended: prefer quicker wins and slower losses
                score = score - ply if score > 0 else score + ply if score < 0 else 0
            elif depth <= 1:
                score = static
            else:
                score = -self._search(new_board, other(side), counts, replies, depth - 1, -beta, -alpha, ply + 1)

            if score > best:
                best, best_moves = score, turn.moves
            alpha = max(alpha, best)
            if alpha >= beta:
                break

        if len(self._table) < TABLE_LIMIT:
            flag = 2 if best <= original_alpha else 1 if best >= beta else 0
            self._table[key] = (depth, flag, best, best_moves)
        return best

    def best_turns(self, board, side, castle_moves, legal, seen=None):
        """Score every legal turn at the deepest depth that finishes in time.

        Returns [(score, turn)], best first. `seen` is a Counter of positions already played,
        so the computer prefers not to repeat them.
        """
        scored = [(0, t) for t in legal]
        first = None
        if len(legal) == 1:
            return scored
        for depth in range(1, self.max_depth + 1):
            self._guaranteed = depth <= self.min_depth
            results = []
            try:
                alpha = -WIN - 1
                for turn, new_board, counts in self._children(board, side, castle_moves, legal, first):
                    self._tick()
                    score, replies, static = self._after(new_board, side, counts, depth > 1)
                    if replies is None:
                        score = score - 1 if score > 0 else score + 1 if score < 0 else 0
                    elif depth <= 1:
                        score = static
                    else:
                        # a full window for each move, so every move has a real score
                        score = -self._search(new_board, other(side), counts, replies, depth - 1, -WIN - 1, WIN + 1, 2)
                    if seen:
                        score -= PENALTY_PER_REPEAT * seen.get((tuple(new_board), other(side)), 0)
                    results.append((score, turn))
                    alpha = max(alpha, score)
            except _OutOfTime:
                break
            scored = sorted(results, key=lambda r: r[0], reverse=True)
            first = scored[0][1].moves
            self.depth_reached = depth
            if scored[0][0] >= WIN - 100 or scored[0][0] <= -WIN + 100:
                break  # a forced win or loss has been found; looking deeper won't change it
        return scored


def choose_turn(variant, board, side, castle_moves, legal, *, level=DEFAULT_LEVEL, seen=None,
                weights=DEFAULT_WEIGHTS, rng=random, max_nodes=None, min_depth=MIN_DEPTH):
    """The turn the computer plays: one of `legal`, chosen by searching.

    `castle_moves` is {side: moves already made between the castle squares}. Raises
    ValueError when there is nothing to play.
    """
    if not legal:
        raise ValueError("there is no legal turn to choose")
    settings = LEVELS[level]
    counts = (castle_moves[rules.WHITE], castle_moves[rules.BLACK])
    searcher = Searcher(variant, weights, settings.seconds, max_nodes, settings.max_depth, min_depth)
    scored = searcher.best_turns(list(board), side, counts, list(legal), seen)
    top = scored[0][0]
    # never gamble away a forced win or into a forced loss; otherwise sometimes play a near-best move
    candidates = [t for s, t in scored if s >= top - settings.slack and abs(s) < WIN - 100]
    return rng.choice(candidates) if candidates and settings.slack else scored[0][1]


def game_seen(game):
    """The positions a Game has been through, in the form `choose_turn` takes."""
    return Counter(game._positions)
