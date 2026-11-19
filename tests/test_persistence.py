import copy
import json
import random

import pytest

import rules
from game import Game, IllegalMove
from rules import BLACK, WHITE
from variants import CAM, CAMELOT


def play_randomly(game, plies, seed):
    rng = random.Random(seed)
    for _ in range(plies):
        if game.over:
            break
        game.play_turn(game.turn, list(rng.choice(game.legal_turns).moves))
    return game


def same_game(a, b):
    assert a.snapshot() == b.snapshot()
    assert a.legal_turns == b.legal_turns
    assert a.castle_moves == b.castle_moves
    assert a.plies_without_progress == b.plies_without_progress
    assert a._positions == b._positions
    assert a.last_turn == b.last_turn


@pytest.mark.parametrize("variant", [CAMELOT, CAM], ids=lambda v: v.key)
def test_a_game_survives_being_saved_and_loaded(variant):
    for seed in range(6):
        game = play_randomly(Game(variant), 80, seed)
        saved = json.loads(json.dumps(game.to_dict()))  # through real JSON, as the store does
        same_game(game, Game.from_dict(saved))


def test_a_loaded_game_carries_on_exactly_like_the_original():
    game = play_randomly(Game(CAMELOT), 30, seed=2)
    loaded = Game.from_dict(json.loads(json.dumps(game.to_dict())))

    rng = random.Random(9)
    for _ in range(40):
        if game.over:
            break
        moves = list(rng.choice(game.legal_turns).moves)
        game.play_turn(game.turn, moves)
        loaded.play_turn(loaded.turn, moves)
        same_game(game, loaded)


def test_a_new_game_round_trips():
    for variant in (CAMELOT, CAM):
        game = Game(variant)
        same_game(game, Game.from_dict(game.to_dict()))


def test_draw_progress_is_kept():
    game = Game(CAMELOT)
    game.board = [0] * game.variant.size
    for index, piece in {148: 1, 152: 1, 40: 3, 44: 3}.items():
        game.board[index] = piece
    game._legal = rules.legal_turns(game.variant, game.board, WHITE)
    game._positions = type(game._positions)({game._position(): 1})

    for _ in range(2):
        for moves in ([148, 149], [40, 41], [149, 148], [41, 40]):
            game.play_turn(game.turn, moves)
    assert game.claimable()["repetition"]

    loaded = Game.from_dict(json.loads(json.dumps(game.to_dict())))
    assert loaded.claimable()["repetition"]
    loaded.claim_draw(WHITE)
    assert loaded.draw_reason == "repetition"


def test_castle_moves_and_offers_are_kept():
    game = Game(CAMELOT)
    game.castle_moves = {WHITE: 2, BLACK: 1}
    game.draw_offer = BLACK
    loaded = Game.from_dict(game.to_dict())
    assert loaded.castle_moves == {WHITE: 2, BLACK: 1}
    assert loaded.draw_offer == BLACK
    assert loaded.snapshot()["castleMovesLeft"] == {WHITE: 0, BLACK: 1}


def test_a_finished_game_stays_finished():
    game = Game(CAMELOT)
    game.resign(BLACK)
    loaded = Game.from_dict(game.to_dict())
    assert (loaded.winner, loaded.win_reason) == (WHITE, "resignation")
    assert loaded.over and loaded.legal_turns == []
    with pytest.raises(IllegalMove, match="over"):
        loaded.play_turn(WHITE, [1, 2])


def test_the_save_is_plain_json():
    data = Game(CAM).to_dict()
    assert json.loads(json.dumps(data)) == data


@pytest.mark.parametrize("damage", [
    lambda d: d.update(version=99),
    lambda d: d.update(variant="checkers"),
    lambda d: d.update(board=[0, 1, 2]),
    lambda d: d.update(board=[9] * 192),
    lambda d: d.update(board=["x"] * 192),
    lambda d: d.update(turn="green"),
    lambda d: d.pop("board"),
    lambda d: d.pop("positions"),
    lambda d: d.update(castleMoves={"white": 1}),
    lambda d: d.update(positions=[["zz", "white", 1]]),
    lambda d: d.update(lastTurn={"player": "white"}),
])
def test_damaged_saves_are_rejected(damage):
    data = copy.deepcopy(Game(CAMELOT).to_dict())
    damage(data)
    with pytest.raises(ValueError):
        Game.from_dict(data)


def test_not_a_save_at_all_is_rejected():
    for junk in (None, [], "text", 5):
        with pytest.raises(ValueError):
            Game.from_dict(junk)


# --- resigning ----------------------------------------------------------------


@pytest.mark.parametrize("variant", [CAMELOT, CAM], ids=lambda v: v.key)
def test_resigning_gives_the_opponent_the_win(variant):
    game = Game(variant)
    game.resign(WHITE)
    assert (game.winner, game.win_reason) == (BLACK, "resignation")
    assert game.over and game.legal_turns == []
    assert game.snapshot()["winner"] == BLACK and game.snapshot()["winReason"] == "resignation"


def test_a_player_can_resign_out_of_turn():
    game = Game(CAMELOT)
    game.resign(BLACK)  # white is to move
    assert game.winner == WHITE


def test_resigning_withdraws_a_pending_draw_offer():
    game = Game(CAMELOT)
    game.offer_draw(WHITE)
    game.resign(BLACK)
    assert game.draw_offer is None


def test_nobody_can_resign_a_finished_game():
    game = Game(CAMELOT)
    game.resign(WHITE)
    with pytest.raises(IllegalMove, match="over"):
        game.resign(BLACK)
