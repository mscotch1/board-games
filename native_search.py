"""The computer player's search in C, called through ctypes (no Python dependency to install).

native/aisearch.c is a port of the Searcher in ai.py. This module loads the compiled library if
there is one and hands it the board geometry and weights, so the rules about the shape of the
board stay in variants.py/rules.py. Without the library (it needs a C compiler to build; see
native/Makefile and the Dockerfile) `available()` is false and the Python search is used instead.

ctypes lets go of the GIL during a call, so several searches really do run at the same time,
and the server stays responsive while one is thinking.
"""

import ctypes
import os
import sys
from pathlib import Path

import rules
from ai import DEFAULT_WEIGHTS, MIN_DEPTH, advance_table, scan

NATIVE_DIR = Path(__file__).resolve().parent / "native"
LIBRARY_NAMES = ("libaisearch.so", "libaisearch.dylib", "aisearch.dll")

_library = None
_looked = False
_handles = {}


def _load():
    global _library, _looked
    if _looked:
        return _library
    _looked = True
    candidates = [os.environ["AI_NATIVE_LIB"]] if os.environ.get("AI_NATIVE_LIB") else []
    candidates += [str(NATIVE_DIR / name) for name in LIBRARY_NAMES]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            library = ctypes.CDLL(path)
        except OSError as e:
            print(f"native search: couldn't load {path}: {e}", file=sys.stderr)
            continue
        i32, i64, vp = ctypes.c_int32, ctypes.c_int64, ctypes.c_void_p
        pi32, pi64 = ctypes.POINTER(i32), ctypes.POINTER(i64)
        library.ai_init.restype = None
        library.ai_create.restype = vp
        library.ai_create.argtypes = [ctypes.c_int] * 9 + [pi32, pi32, pi32] + [ctypes.c_int] * 3 + [pi32]
        library.ai_destroy.argtypes = [vp]
        library.ai_destroy.restype = None
        library.ai_legal_moves.restype = ctypes.c_int
        library.ai_legal_moves.argtypes = [vp, pi32, ctypes.c_int, ctypes.c_int, pi32, ctypes.c_int]
        library.ai_search.restype = ctypes.c_int
        library.ai_search.argtypes = (
            [vp, pi32, ctypes.c_int, ctypes.c_int, ctypes.c_int, pi32, ctypes.c_int, pi32, pi32]
            + [i64, i64]
            + [ctypes.c_int] * 4
            + [pi32, pi64]
        )
        library.ai_init()  # (before any thread can search)
        _library = library
        return _library
    return None


def available():
    return _load() is not None


def _array(values, kind=ctypes.c_int32):
    return (kind * len(values))(*values)


def _padded(rows, width):
    flat = []
    for row in rows:
        flat.extend(list(row) + [-1] * (width - len(row)))
    return flat


def handle(variant, weights=DEFAULT_WEIGHTS):
    """The C engine for `variant` with `weights`, made once and kept."""
    key = (variant.key, tuple(sorted(weights.items())))
    if key not in _handles:
        library = _load()
        adjacent = _padded(variant._adjacent, 8)
        jumpable = _padded(variant._jumpable, 8)
        homes = _padded([variant.home_castle[rules.WHITE], variant.home_castle[rules.BLACK]], 4)
        advance = [v for side in advance_table(variant, weights) for v in side]
        pointer = library.ai_create(
            variant.rows, variant.cols, variant.castle_to_win,
            int(variant.enemy_castle_ends_turn), int(variant.confine_in_enemy_castle), variant.castle_moves,
            int(variant.forced_exit), int(variant.wins_need_two_pieces), int(variant.draws),
            _array(adjacent), _array(jumpable), _array(homes),
            weights["man"], weights["knight"], weights["goal"], _array(advance),
        )
        if not pointer:
            raise RuntimeError(f"native search can't handle the {variant.name} board")
        _handles[key] = pointer
    return _handles[key]


def legal_turns(variant, board, side, castle_moves_used=0):
    """The C generator's turns as sorted (from, to, sorted captured squares): for the tests."""
    library = _load()
    out = (ctypes.c_int32 * 200_000)()
    n = library.ai_legal_moves(
        handle(variant), _array(board), 0 if side == rules.WHITE else 1, castle_moves_used, out, len(out)
    )
    if n < 0:
        raise RuntimeError(f"native move generation failed ({n})")
    turns, used = [], 0
    for _ in range(n):
        start, end, captured = out[used], out[used + 1], out[used + 2]
        turns.append((start, end, tuple(sorted(out[used + 3 : used + 3 + captured]))))
        used += 3 + captured
    return sorted(turns)


class NativeSearcher:
    """The same interface as ai.Searcher, doing the work in C."""

    def __init__(self, variant, weights=DEFAULT_WEIGHTS, seconds=1.0, max_nodes=None, max_depth=30,
                 min_depth=MIN_DEPTH, beam=None):
        self.variant = variant
        self.weights = weights
        self.seconds = seconds
        self.max_nodes = max_nodes
        self.max_depth = max_depth
        self.min_depth = min_depth
        self.beam = beam
        self.nodes = 0
        self.expanded = 0
        self.depth_reached = 0

    def best_turns(self, board, side, castle_moves, legal, seen=None, slack=0):
        """See ai.Searcher.best_turns."""
        library = _load()
        scored = [(0, t) for t in legal]
        if len(legal) == 1:
            return scored

        root = []
        for turn in legal:
            captured = [j for j in turn.jumped if j is not None]
            root.extend([turn.moves[0], turn.moves[-1], len(captured), *captured])
        penalty = [0] * len(legal)
        if seen:
            from ai import PENALTY_PER_REPEAT

            after = rules.other(side)
            for i, turn in enumerate(legal):
                penalty[i] = PENALTY_PER_REPEAT * seen.get((tuple(rules.apply_turn(board, turn)), after), 0)

        pieces, home, value = scan(self.variant, board, self.weights)
        w, b = rules.WHITE, rules.BLACK
        tally = [pieces[w], pieces[b], home[w], home[b], value[w], value[b]]

        scores = (ctypes.c_int32 * len(legal))()
        info = (ctypes.c_int64 * 3)()
        failure = library.ai_search(
            handle(self.variant, self.weights), _array(board), 0 if side == rules.WHITE else 1,
            int(castle_moves[0]), int(castle_moves[1]), _array(tally), len(legal), _array(root), _array(penalty),
            int(self.seconds * 1000) if self.seconds else 0, self.max_nodes or 0, self.max_depth, self.min_depth,
            self.beam or 0, slack, scores, info,
        )
        if failure:
            raise RuntimeError(f"native search failed ({failure})")
        self.depth_reached, self.nodes, self.expanded = info[0], info[1], info[2]
        return sorted(zip(scores, legal), key=lambda r: r[0], reverse=True)
