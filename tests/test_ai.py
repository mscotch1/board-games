import random
import time

import pytest

import ai
import rules
from game import Game
from rules import BLACK, WHITE
from variants import CAM, CAMELOT, cam_square


def pick(game, **options):
    options.setdefault("level", "easy")
    return ai.choose_turn(
        game.variant, game.board, game.turn, game.castle_moves, game.legal_turns,
        seen=ai.game_seen(game), rng=random.Random(1), **options,
    )


def cam_position(pieces, turn=WHITE):
    game = Game(CAM)
    board = [0] * CAM.size
    for name, piece in pieces.items():
        board[cam_square(name)] = piece
    game.board = board
    game.turn = turn
    game._legal = rules.legal_turns(CAM, board, turn)
    return game


@pytest.mark.parametrize("variant", [CAM, CAMELOT])
def test_it_chooses_a_legal_turn_at_every_level(variant):
    game = Game(variant)
    for level in ai.LEVELS:
        assert pick(game, level=level, max_nodes=400) in game.legal_turns


def test_it_wins_at_once_when_it_can():
    game = cam_position({"D12": 1, "B5": 3, "F5": 3})
    assert pick(game, level="hard").moves[-1] == cam_square("D13")


def test_it_takes_a_forced_win_even_on_easy():
    game = cam_position({"D12": 1, "B5": 3, "F5": 3})
    for seed in range(10):
        turn = ai.choose_turn(
            CAM, game.board, WHITE, game.castle_moves, game.legal_turns, level="easy", rng=random.Random(seed)
        )
        assert turn.moves[-1] == cam_square("D13")


def test_it_blocks_a_win_it_can_see_coming():
    # black's man on D2 is one step from white's castle; white's only way to stop it is to capture it
    game = cam_position({"D2": 3, "D3": 1, "A6": 3}, turn=WHITE)
    turn = pick(game, level="hard")
    assert turn.is_capture and cam_square("D2") in turn.jumped


def test_it_does_not_hang_a_piece_it_can_see_is_lost():
    # moving the man forward lets black jump it; the other moves are safe
    game = cam_position({"D6": 1, "A2": 1, "D8": 3, "G10": 3}, turn=WHITE)
    turn = pick(game, level="hard")
    after = rules.apply_turn(game.board, turn)
    replies = rules.legal_turns(CAM, after, BLACK)
    assert not any(t.is_capture for t in replies)


def test_it_stays_inside_its_time_limit():
    game = Game(CAMELOT)
    start = time.monotonic()
    pick(game, level="medium")
    assert time.monotonic() - start < ai.LEVELS["medium"].seconds + 1.5


def test_only_one_legal_turn_is_played_without_searching():
    game = cam_position({"D12": 1, "D13": 3}, turn=WHITE)
    legal = game.legal_turns
    searcher = ai.Searcher(CAM, seconds=0.1)
    assert len(searcher.best_turns(list(game.board), WHITE, (0, 0), legal[:1])) == 1
    assert searcher.nodes == 0


def test_it_refuses_when_there_is_nothing_to_play():
    with pytest.raises(ValueError):
        ai.choose_turn(CAM, list(CAM.initial), WHITE, {WHITE: 0, BLACK: 0}, [])


def test_it_prefers_not_to_repeat_a_position():
    game = cam_position({"D6": 1, "A2": 3, "G12": 3}, turn=WHITE)
    best = pick(game, level="hard")
    seen = {(tuple(rules.apply_turn(game.board, best)), BLACK): 3}
    searcher = ai.Searcher(CAM, seconds=0.3)
    scored = searcher.best_turns(list(game.board), WHITE, (0, 0), game.legal_turns, seen)
    assert scored[0][1] != best or len(scored) == 1


def test_evaluation_values_material_and_is_symmetric():
    board = list(CAM.initial)
    assert ai.evaluate(CAM, board, WHITE) == -ai.evaluate(CAM, board, BLACK)
    # a free extra man is worth about a man
    extra = list(board)
    extra[cam_square("D7")] = 1
    assert ai.evaluate(CAM, extra, WHITE) - ai.evaluate(CAM, board, WHITE) > 80


@pytest.mark.parametrize("variant", [CAM, CAMELOT])
def test_computer_games_run_to_the_end_with_only_legal_turns(variant):
    rng = random.Random(7)
    limit = 300 if variant is CAM else 120
    game = Game(variant)
    plies = 0
    while not game.over and plies < limit:
        turn = ai.choose_turn(
            variant, game.board, game.turn, game.castle_moves, game.legal_turns,
            level="easy", seen=ai.game_seen(game), rng=rng, max_nodes=150, min_depth=1,
        )
        game.play_turn(game.turn, list(turn.moves))  # raises IllegalMove if it weren't legal
        plies += 1
        claim = game.claimable()
        if claim["repetition"] or claim["fiftyMoves"]:
            game.claim_draw(game.turn)
    assert game.over or plies == limit
