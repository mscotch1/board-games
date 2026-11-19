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


def match(variant, a, b, games, max_nodes):
    """Points for weights `a` against `b` (1 per win, 0.5 per draw), alternating colours."""
    points = 0.0
    for n in range(games):
        a_is_white = n % 2 == 0
        result = play(variant, a if a_is_white else b, b if a_is_white else a, max_nodes, rng=random.Random(n))
        if result == "draw":
            points += 0.5
        elif (result == WHITE) == a_is_white:
            points += 1
    return points


def tune(variant, rounds, games, max_nodes, seed=1):
    rng = random.Random(seed)
    best = dict(ai.DEFAULT_WEIGHTS)
    for r in range(rounds):
        trial = dict(best)
        key = rng.choice(["knight", "advance", "goal"])
        trial[key] = max(10, int(trial[key] * rng.choice([0.6, 0.8, 1.25, 1.6])))
        score = match(variant, trial, best, games, max_nodes)
        kept = score > games / 2 + 0.5
        print(f"round {r + 1}: {key}={trial[key]} scored {score}/{games} {'kept' if kept else 'dropped'}", flush=True)
        if kept:
            best = trial
    print("weights:", best)
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
        start = time.monotonic()
        results = [play(variant, ai.DEFAULT_WEIGHTS, ai.DEFAULT_WEIGHTS, rng=random.Random(n)) for n in range(4)]
        print(results, f"{time.monotonic() - start:.1f}s")
    elif command == "tune":
        tune(variant, rounds=int(sys.argv[3]) if len(sys.argv) > 3 else 8, games=6, max_nodes=1200)
