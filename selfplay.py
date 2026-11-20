"""Play the computer against itself: to check it plays whole games, and to tune its weights.

    python selfplay.py speed              # how fast is the search?
    python selfplay.py match camelot      # a few games with default weights against each other
    python selfplay.py tune camelot       # hill-climb the weights, keeping changes that win
"""

import random
import sys
import time

import ai
from game import Game
from rules import BLACK, WHITE
from variants import VARIANTS


def play(variant, white_weights, black_weights, max_nodes=1500, max_plies=300, rng=None, level="hard"):
    """Play one game with a node budget (so it's repeatable). Returns 'white', 'black' or 'draw'."""
    rng = rng or random.Random(0)
    game = Game(variant)
    weights = {WHITE: white_weights, BLACK: black_weights}
    plies = 0
    while not game.over and plies < max_plies:
        side = game.turn
        turn = ai.choose_turn(
            variant, game.board, side, game.castle_moves, game.legal_turns,
            level=level, seen=ai.game_seen(game), weights=weights[side], rng=rng, max_nodes=max_nodes, min_depth=1,
        )
        game.play_turn(side, list(turn.moves))
        plies += 1
        claim = game.claimable()
        if claim["repetition"] or claim["fiftyMoves"]:
            game.claim_draw(side)
    return game.winner or "draw"


def play_from_opening(args):
    """One game of an arena match: `a` against `b` from a random opening. Returns A's points (1, 0.5 or 0)."""
    key, a, b, max_nodes, seed, a_is_white, opening_plies = args
    variant = VARIANTS[key]
    rng = random.Random(seed)
    game = Game(variant)
    for _ in range(opening_plies):  # the same opening for both colours, so the pair is fair
        if game.over:
            break
        game.play_turn(game.turn, list(rng.choice(game.legal_turns).moves))
    weights = {WHITE: a if a_is_white else b, BLACK: b if a_is_white else a}
    plies = 0
    while not game.over and plies < 240:
        side = game.turn
        turn = ai.choose_turn(
            variant, game.board, side, game.castle_moves, game.legal_turns,
            level="hard", seen=ai.game_seen(game), weights=weights[side], max_nodes=max_nodes, min_depth=1,
        )
        game.play_turn(side, list(turn.moves))
        plies += 1
        claim = game.claimable()
        if claim["repetition"] or claim["fiftyMoves"]:
            game.claim_draw(side)
    if not game.winner:
        return 0.5
    return 1.0 if (game.winner == WHITE) == a_is_white else 0.0


def arena(pool, key, a, b, pairs, max_nodes, first_seed=0, opening_plies=6):
    """Points for weights `a` against `b` over `pairs` openings, each played from both sides."""
    jobs = [
        (key, a, b, max_nodes, first_seed + n, a_white, opening_plies)
        for n in range(pairs)
        for a_white in (True, False)
    ]
    return sum(pool.map(play_from_opening, jobs, chunksize=2)), len(jobs)


def tune(pool, key, rounds, pairs, max_nodes, seed=1, start=None):
    """Coordinate hill-climbing: change one weight, keep it if it clearly beats the current best."""
    rng = random.Random(seed)
    best = dict(start or ai.DEFAULT_WEIGHTS)
    for r in range(rounds):
        trial = dict(best)
        name = rng.choice(["knight", "advance", "goal", "curve", "centre"])
        if name == "curve":
            trial[name] = round(max(0.4, min(3.0, trial[name] * rng.choice([0.7, 0.85, 1.2, 1.45]))), 2)
        elif name == "centre":
            trial[name] = max(0, int(trial[name] + rng.choice([-10, 10, 20, 30])))
        else:
            trial[name] = max(10, int(trial[name] * rng.choice([0.6, 0.8, 1.25, 1.6])))
        if trial == best:
            continue
        points, games = arena(pool, key, trial, best, pairs, max_nodes, first_seed=1000 * (r + 1))
        kept = points > games * 0.55
        print(f"round {r + 1}: {name}={trial[name]} scored {points}/{games} {'kept' if kept else 'dropped'}", flush=True)
        if kept:
            best = trial
    print("weights:", best, flush=True)
    return best


if __name__ == "__main__":
    command = sys.argv[1]
    variant = VARIANTS[sys.argv[2]] if len(sys.argv) > 2 else VARIANTS["camelot"]
    if command == "speed":
        for v in VARIANTS.values():
            game = Game(v)
            searcher = ai.Searcher(v, seconds=2.0)
            start = time.monotonic()
            scored = searcher.best_turns(list(game.board), WHITE, (0, 0), game.legal_turns)
            took = time.monotonic() - start
            print(f"{v.key}: depth {searcher.depth_reached}, {searcher.nodes} nodes in {took:.2f}s "
                  f"= {searcher.nodes / took:.0f}/s, {len(scored)} moves")
    elif command == "match":
        from multiprocessing import Pool

        with Pool() as pool:
            points, games = arena(pool, variant.key, ai.DEFAULT_WEIGHTS, ai.DEFAULT_WEIGHTS, 8, 100_000)
        print(f"{points}/{games}")
    elif command == "tune":
        from multiprocessing import Pool

        with Pool() as pool:
            tune(pool, variant.key, rounds=int(sys.argv[3]) if len(sys.argv) > 3 else 20, pairs=100, max_nodes=100_000)
