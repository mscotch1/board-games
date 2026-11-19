import pytest

import rules
from game import Game, IllegalMove, MAX_PATH_LENGTH
from rules import COLS


def sq(row, col):
    return row * COLS + col


def game_with(pieces, turn="1"):
    game = Game()
    game.board = [0] * len(game.board)
    for (row, col), piece in pieces.items():
        game.board[sq(row, col)] = piece
    game.turn = turn
    return game


def test_new_game_starts_with_player_one():
    game = Game()
    assert game.turn == "1"
    assert game.winner is None
    assert game.board == list(rules.INITIAL_BOARD)


def test_legal_turn_updates_board_and_passes_the_turn():
    game = Game()
    game.play_turn("1", [sq(9, 4), sq(8, 4)])

    assert game.board[sq(8, 4)] == 1
    assert game.board[sq(9, 4)] == 0
    assert game.turn == "2"
    assert game.winner is None


def test_players_alternate():
    game = Game()
    game.play_turn("1", [sq(9, 4), sq(8, 4)])
    game.play_turn("2", [sq(6, 4), sq(7, 4)])
    assert game.turn == "1"
    assert game.board[sq(7, 4)] == 3


def test_cannot_play_out_of_turn():
    game = Game()
    with pytest.raises(IllegalMove, match="not your turn"):
        game.play_turn("2", [sq(6, 4), sq(7, 4)])
    assert game.board == list(rules.INITIAL_BOARD)


def test_cannot_move_opponents_piece():
    game = Game()
    with pytest.raises(IllegalMove, match="own pieces"):
        game.play_turn("1", [sq(5, 3), sq(6, 2)])


def test_cannot_move_an_empty_square():
    with pytest.raises(IllegalMove):
        Game().play_turn("1", [sq(8, 4), sq(7, 4)])


def test_illegal_move_leaves_the_game_unchanged():
    game = Game()
    with pytest.raises(IllegalMove, match="not allowed"):
        game.play_turn("1", [sq(9, 4), sq(5, 4)])
    assert game.board == list(rules.INITIAL_BOARD)
    assert game.turn == "1"


@pytest.mark.parametrize("moves", [
    None,
    "9,4",
    {"0": 1},
    [],
    [sq(9, 4)],  # selecting a piece is not a turn
    [sq(9, 4), -1],
    [sq(9, 4), 192],
    [sq(9, 4), sq(8, 4) + 0.5],
    [sq(9, 4), float(sq(8, 4))],
    [sq(9, 4), str(sq(8, 4))],
    [sq(9, 4), True],
    [sq(9, 4), None],
    [-84, sq(8, 4)],  # a negative index would wrap around to the last squares
    [sq(9, 4)] * (MAX_PATH_LENGTH + 1),
])
def test_malformed_paths_are_rejected(moves):
    game = Game()
    with pytest.raises(IllegalMove):
        game.play_turn("1", moves)
    assert game.board == list(rules.INITIAL_BOARD)


def test_multi_jump_turn_captures_pieces():
    game = game_with({(12, 4): 1, (11, 4): 3, (9, 4): 3, (2, 2): 3})
    game.play_turn("1", [sq(12, 4), sq(10, 4), sq(8, 4)])
    assert game.board[sq(11, 4)] == game.board[sq(9, 4)] == 0
    assert game.board[sq(8, 4)] == 1


def test_reaching_the_goal_row_wins():
    game = game_with({(1, 5): 1, (0, 6): 2, (9, 4): 3})
    game.play_turn("1", [sq(1, 5), sq(0, 5)])
    assert game.winner == "1"


def test_capturing_the_last_piece_wins():
    game = game_with({(9, 4): 1, (8, 4): 3})
    game.play_turn("1", [sq(9, 4), sq(7, 4)])
    assert game.winner == "1"


def test_no_turns_after_the_game_is_over():
    game = game_with({(9, 4): 1, (8, 4): 3})
    game.play_turn("1", [sq(9, 4), sq(7, 4)])
    with pytest.raises(IllegalMove, match="over"):
        game.play_turn("2", [sq(0, 0), sq(1, 0)])
