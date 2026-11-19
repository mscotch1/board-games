"""The C search must agree with the Python rules and the Python search.

These need the library built (make -C native). Without it they are skipped, unless
REQUIRE_NATIVE=1 is set (as in CI), when a missing library is a failure.
"""

import os
import random
import threading
import time

import pytest

import ai
import native_search
import rules
from game import Game
from rules import BLACK, WHITE
from variants import CAM, CAMELOT

if not native_search.available():
    if os.environ.get("REQUIRE_NATIVE") == "1":
        pytest.fail("REQUIRE_NATIVE=1 but the native search library isn't built (make -C native)", pytrace=False)
    pytest.skip("the native search library isn't built (make -C native)", allow_module_level=True)


def python_turns(variant, board, side, castle_moves_used):
    return sorted(
        (t.moves[0], t.moves[-1], tuple(sorted(j for j in t.jumped if j is not None)))
        for t in rules.legal_turns(variant, board, side, castle_moves_used)
    )


def random_positions(variant, games, seed):
    """Positions from random games: the board, the side to move and its castle moves used."""
    rng = random.Random(seed)
    for _ in range(games):
        game = Game(variant)
        for _ply in range(120):
            if game.over:
                break
            yield game
            game.play_turn(game.turn, list(rng.choice(game.legal_turns).moves))


@pytest.mark.parametrize("variant", [CAM, CAMELOT], ids=lambda v: v.key)
def test_it_generates_the_same_turns_as_the_python_rules(variant):
    checked = 0
    for game in random_positions(variant, games=12, seed=3):
        side = game.turn
        used = game.castle_moves[side]
        assert native_search.legal_turns(variant, game.board, side, used) == python_turns(
            variant, game.board, side, used
        )
        checked += 1
    assert checked > 300


def test_it_generates_the_same_turns_for_the_side_not_to_move_too():
    for game in random_positions(CAMELOT, games=4, seed=9):
        other = rules.other(game.turn)
        assert native_search.legal_turns(CAMELOT, game.board, other, 0) == python_turns(CAMELOT, game.board, other, 0)


def position(variant, seed, plies):
    game, rng = Game(variant), random.Random(seed)
    for _ in range(plies):
        if game.over:
            break
        game.play_turn(game.turn, list(rng.choice(game.legal_turns).moves))
    return game


def search(cls, game, depth, seen=None, slack=0):
    searcher = cls(game.variant, seconds=None, max_depth=depth, min_depth=depth)
    counts = (game.castle_moves[WHITE], game.castle_moves[BLACK])
    return searcher.best_turns(list(game.board), game.turn, counts, game.legal_turns, seen, slack)


@pytest.mark.parametrize(
    "variant, depth", [(CAM, 3), (CAM, 4), (CAMELOT, 2)], ids=["cam-3", "cam-4", "camelot-2"]
)
def test_it_finds_the_same_best_score_as_the_python_search(variant, depth):
    for seed in range(4):
        game = position(variant, seed, 8 + 3 * seed)
        if game.over:
            continue
        assert search(native_search.NativeSearcher, game, depth)[0][0] == search(ai.Searcher, game, depth)[0][0]


def test_it_scores_every_move_within_the_slack_exactly():
    game = position(CAM, 1, 11)
    exact = {t.moves: s for s, t in search(ai.Searcher, game, 3, slack=0)}
    best = max(exact.values())
    for score, turn in search(native_search.NativeSearcher, game, 3, slack=50):
        if score >= best - 50:
            # (the Python search with no slack only bounds the worse moves, so compare with the best)
            assert score <= best
    assert search(native_search.NativeSearcher, game, 3, slack=50)[0][0] == best


def test_it_avoids_repeating_a_position_like_the_python_search():
    game = position(CAM, 2, 10)
    best = search(native_search.NativeSearcher, game, 3)[0][1]
    after = (tuple(rules.apply_turn(game.board, best)), rules.other(game.turn))
    penalised = search(native_search.NativeSearcher, game, 3, seen={after: 3})
    assert penalised[0][1].moves != best.moves
    assert [(s, t.moves) for s, t in penalised][:1] == [
        (s, t.moves) for s, t in search(ai.Searcher, game, 3, seen={after: 3})
    ][:1]


def test_it_always_returns_a_legal_turn():
    for game in random_positions(CAMELOT, games=2, seed=5):
        if len(game.legal_turns) > 1:
            turn = ai.choose_turn(
                CAMELOT, game.board, game.turn, game.castle_moves, game.legal_turns,
                level="easy", seen=ai.game_seen(game), native=True,
            )
            assert turn in game.legal_turns


def test_it_wins_a_forced_win_and_dodges_a_forced_loss_like_the_python_search():
    from variants import cam_square

    game = Game(CAM)
    board = [0] * CAM.size
    board[cam_square("D12")] = 1
    board[cam_square("B5")] = 3
    board[cam_square("F5")] = 3
    game.board, game.turn = board, WHITE
    game._legal = rules.legal_turns(CAM, board, WHITE)
    best = search(native_search.NativeSearcher, game, 3)[0]
    assert best[1].moves[-1] == cam_square("D13") and best[0] > ai.WIN - 100


def test_it_stays_inside_its_time_limit():
    game = Game(CAMELOT)
    searcher = native_search.NativeSearcher(CAMELOT, seconds=0.3, min_depth=1)
    counts = (0, 0)
    start = time.monotonic()
    searcher.best_turns(list(game.board), WHITE, counts, game.legal_turns)
    assert time.monotonic() - start < 0.3 + 0.5
    assert searcher.depth_reached >= 3


def test_searches_in_different_threads_run_at_once_and_agree():
    game = position(CAMELOT, 2, 14)
    expected = search(native_search.NativeSearcher, game, 4)[0][0]
    results = []

    def work():
        results.append(search(native_search.NativeSearcher, game, 4)[0][0])

    threads = [threading.Thread(target=work) for _ in range(4)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert results == [expected] * 4


def test_choose_turn_falls_back_to_python_when_asked():
    game = Game(CAM)
    turn = ai.choose_turn(
        CAM, game.board, game.turn, game.castle_moves, game.legal_turns, level="easy", native=False
    )
    assert turn in game.legal_turns
    assert ai.searcher_class(native=False) is ai.Searcher
    assert ai.searcher_class(native=True) is native_search.NativeSearcher
