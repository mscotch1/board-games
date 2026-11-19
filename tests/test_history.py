import copy
import random

import pytest

import app as app_module
import rules
from game import Game
from registry import Registry
from rules import BLACK, WHITE
from store import MemoryStore
from test_app import connect, messages
from variants import CAM, CAMELOT


def undo(board, entry):
    """The board before `entry` was played: what a client does to show an earlier position."""
    board = list(board)
    start, end = entry["moves"][0], entry["moves"][-1]
    if end != start:
        board[end] = 0
    board[start] = entry["piece"]
    for square, piece in entry["captured"]:
        board[square] = piece
    return board


def play_randomly(variant, seed, plies=80):
    """A game of random turns; returns it and the board before each turn."""
    rng = random.Random(seed)
    game = Game(variant)
    boards = []
    for _ in range(plies):
        if game.over:
            break
        boards.append(list(game.board))
        game.play_turn(game.turn, list(rng.choice(game.legal_turns).moves))
    return game, boards


@pytest.mark.parametrize("variant", [CAM, CAMELOT], ids=lambda v: v.key)
def test_every_turn_is_recorded_and_the_board_can_be_wound_back(variant):
    for seed in range(4):
        game, boards = play_randomly(variant, seed)
        assert len(game.history) == len(boards)
        board = list(game.board)
        for entry, before in zip(reversed(game.history), reversed(boards)):
            board = undo(board, entry)
            assert board == before
        assert board == list(variant.initial)


def test_an_entry_says_who_moved_which_piece_and_what_it_took():
    game = Game(CAM)
    rng = random.Random(2)
    while not game.over and not any(t.is_capture for t in game.legal_turns):
        game.play_turn(game.turn, list(rng.choice(game.legal_turns).moves))
    capture = next(t for t in game.legal_turns if t.is_capture)
    mover, piece = game.turn, game.board[capture.moves[0]]
    taken = [[s, game.board[s]] for s in capture.jumped if s is not None]
    game.play_turn(mover, list(capture.moves))
    entry = game.history[-1]
    assert entry == {
        "player": mover,
        "moves": list(capture.moves),
        "jumped": list(capture.jumped),
        "piece": piece,
        "captured": taken,
    }
    assert taken, "a capture takes something"


def test_the_snapshot_counts_the_turns_and_shows_the_last():
    game = Game(CAM)
    assert game.snapshot()["moveCount"] == 0 and game.snapshot()["lastMove"] is None
    game.play_turn(WHITE, list(game.legal_turns[0].moves))
    snap = game.snapshot()
    assert snap["moveCount"] == 1
    assert snap["lastMove"] == game.history[-1]


def test_history_survives_saving_and_loading():
    game, _ = play_randomly(CAMELOT, 5, plies=30)
    loaded = Game.from_dict(copy.deepcopy(game.to_dict()))
    assert loaded.history == game.history
    assert loaded.snapshot()["moveCount"] == len(game.history)


def test_a_save_from_before_history_existed_still_loads():
    game, _ = play_randomly(CAM, 1, plies=10)
    data = game.to_dict()
    del data["history"]
    loaded = Game.from_dict(data)
    assert loaded.history == [] and loaded.board == game.board
    # and it carries on recording from here
    loaded.play_turn(loaded.turn, list(loaded.legal_turns[0].moves))
    assert len(loaded.history) == 1


@pytest.mark.parametrize(
    "damage",
    [
        lambda e: e.update(player="green"),
        lambda e: e.update(moves=[0]),
        lambda e: e.update(moves=[0, 10_000]),
        lambda e: e.update(jumped=[]),
        lambda e: e.update(piece=9),
        lambda e: e.update(captured=[[0, 7]]),
        lambda e: e.pop("piece"),
    ],
)
def test_a_damaged_saved_move_is_refused(damage):
    game, _ = play_randomly(CAM, 3, plies=6)
    data = copy.deepcopy(game.to_dict())
    damage(data["history"][0])
    with pytest.raises(ValueError):
        Game.from_dict(data)


def test_a_player_who_comes_back_is_sent_the_history(monkeypatch):
    monkeypatch.setattr(app_module, "registry", Registry(MemoryStore()))
    white = connect("h1", WHITE)
    black = connect("h1")
    ready = [m for t, m in messages(black) if t == "game-ready"][0]
    token = ready["token"]
    assert ready["history"] == []

    white.get_received()
    white.emit("message", {"topic": "end-turn", "message": {"moves": ready["state"]["legal"][0]["moves"]}})
    black.get_received()
    black.disconnect()

    back = connect("h1", token=token)
    ready_again = [m for t, m in messages(back) if t == "game-ready"][0]
    assert len(ready_again["history"]) == 1
    assert ready_again["history"][0]["player"] == WHITE
    assert ready_again["state"]["moveCount"] == 1
    assert rules.other(WHITE) == BLACK
