import re
from pathlib import Path

import pytest

import rules
from rules import COLS, INITIAL_BOARD, adjacent_squares, find_winner, is_valid_move, jumpable_squares, make_moves

BOARD_JS = Path(__file__).parent.parent / "web" / "games" / "camelot" / "scripts" / "board.js"


def sq(row, col):
    return row * COLS + col


def board_with(pieces):
    board = [0] * (rules.ROWS * COLS)
    for (row, col), piece in pieces.items():
        board[sq(row, col)] = piece
    return board


def path(*squares):
    return [sq(*s) for s in squares]


def js_array(name):
    source = BOARD_JS.read_text()
    match = re.search(rf"{name} = new Uint8Array\(\[(.*?)\]\)", source, re.DOTALL)
    return tuple(int(v) for v in match.group(1).replace("\n", "").split(",") if v.strip())


def test_constants_match_the_client():
    # the client still draws its initial board from these, so they must not drift
    assert js_array("BOARD_MASK") == rules.BOARD_MASK
    assert js_array("state") == INITIAL_BOARD


def test_board_shape():
    assert len(rules.BOARD_MASK) == len(INITIAL_BOARD) == rules.ROWS * rules.COLS
    assert all(INITIAL_BOARD[i] == 0 or rules.BOARD_MASK[i] for i in range(len(INITIAL_BOARD)))


def test_adjacent_squares_respect_edges_and_mask():
    assert sorted(adjacent_squares(sq(0, 5))) == sorted([sq(0, 6), sq(1, 4), sq(1, 5), sq(1, 6)])
    # left edge of a full row must not wrap around to the previous row
    assert all(rules.row_from_index(i) in (2, 3, 4) for i in adjacent_squares(sq(3, 0)))
    assert adjacent_squares(sq(3, 0)) == [sq(2, 1), sq(3, 1), sq(4, 0), sq(4, 1)]


def test_jumpable_squares_respect_edges_and_mask():
    assert sq(5, 6) in jumpable_squares(sq(7, 4))
    assert sorted(jumpable_squares(sq(3, 0))) == sorted([sq(1, 2), sq(3, 2), sq(5, 0), sq(5, 2)])
    assert all(rules.BOARD_MASK[i] for i in jumpable_squares(sq(1, 2)))


def test_square_off_the_board_is_never_reachable():
    assert adjacent_squares(0) == []
    assert -5 not in jumpable_squares(sq(0, 5))


def test_simple_step():
    assert is_valid_move(INITIAL_BOARD, "1", path((9, 4), (8, 4)))
    assert is_valid_move(INITIAL_BOARD, "1", path((9, 4), (8, 3)))


def test_simple_step_onto_occupied_square_is_invalid():
    assert not is_valid_move(INITIAL_BOARD, "1", path((9, 4), (9, 5)))


def test_cannot_select_opponent_or_empty_piece():
    assert not is_valid_move(INITIAL_BOARD, "1", [sq(5, 3)])
    assert not is_valid_move(INITIAL_BOARD, "1", [sq(8, 4)])
    assert is_valid_move(INITIAL_BOARD, "1", [sq(9, 4)])
    assert is_valid_move(INITIAL_BOARD, "2", [sq(5, 3)])


def test_empty_path_is_invalid():
    assert not is_valid_move(INITIAL_BOARD, "1", [])


def test_far_step_is_invalid():
    assert not is_valid_move(INITIAL_BOARD, "1", path((9, 4), (7, 4)))


def test_jump_over_opponent_captures_it():
    board = board_with({(9, 4): 1, (8, 4): 3})
    moves = path((9, 4), (7, 4))
    assert is_valid_move(board, "1", moves)

    after = make_moves(board, moves)
    assert after[sq(7, 4)] == 1
    assert after[sq(9, 4)] == after[sq(8, 4)] == 0


def test_jump_over_empty_square_is_invalid():
    assert not is_valid_move(board_with({(9, 4): 1}), "1", path((9, 4), (7, 4)))


def test_canter_over_own_piece_keeps_it():
    board = board_with({(9, 4): 1, (8, 4): 1})
    moves = path((9, 4), (7, 4))
    assert is_valid_move(board, "1", moves)

    after = make_moves(board, moves)
    assert after[sq(8, 4)] == 1 and after[sq(7, 4)] == 1 and after[sq(9, 4)] == 0


def test_cannot_land_on_occupied_square():
    board = board_with({(9, 4): 1, (8, 4): 3, (7, 4): 3})
    assert not is_valid_move(board, "1", path((9, 4), (7, 4)))


def test_multiple_jumps_capture_everything_jumped():
    board = board_with({(12, 4): 1, (11, 4): 3, (9, 4): 3})
    moves = path((12, 4), (10, 4), (8, 4))
    assert is_valid_move(board, "1", moves)

    after = make_moves(board, moves)
    assert after[sq(8, 4)] == 1
    assert sum(1 for v in after if v) == 1


def test_cannot_jump_the_same_piece_twice():
    board = board_with({(12, 4): 1, (11, 4): 3})
    assert not is_valid_move(board, "1", path((12, 4), (10, 4), (12, 4)))


def test_cannot_go_back_and_forth_cantering():
    board = board_with({(12, 4): 1, (11, 4): 1})
    assert is_valid_move(board, "1", path((12, 4), (10, 4)))
    assert not is_valid_move(board, "1", path((12, 4), (10, 4), (12, 4)))


def test_chain_of_canters_is_valid():
    board = board_with({(12, 4): 1, (11, 4): 1, (9, 4): 1})
    assert is_valid_move(board, "1", path((12, 4), (10, 4), (8, 4)))


def test_cannot_canter_after_jumping():
    board = board_with({(12, 4): 1, (11, 4): 3, (9, 4): 1})
    assert not is_valid_move(board, "1", path((12, 4), (10, 4), (8, 4)))


@pytest.mark.parametrize("piece, valid", [(1, False), (2, True)])
def test_only_knights_can_charge(piece, valid):
    # canter over an own piece, then jump an opponent in the same turn
    board = board_with({(12, 4): piece, (11, 4): 1, (9, 4): 3})
    assert is_valid_move(board, "1", path((12, 4), (10, 4), (8, 4))) is valid


def test_player_two_moves_use_their_own_pieces():
    board = board_with({(5, 4): 3, (6, 4): 1})
    assert is_valid_move(board, "2", path((5, 4), (7, 4)))
    assert make_moves(board, path((5, 4), (7, 4)))[sq(6, 4)] == 0


def test_no_winner_at_start():
    assert find_winner(list(INITIAL_BOARD)) is None


def test_player_one_wins_by_filling_the_back_row():
    board = board_with({(0, 5): 1, (0, 6): 2, (9, 4): 1, (5, 3): 3})
    assert find_winner(board) == "1"


def test_player_two_wins_by_filling_the_front_row():
    board = board_with({(15, 5): 3, (15, 6): 4, (9, 4): 1, (5, 3): 3})
    assert find_winner(board) == "2"


def test_partly_filled_goal_row_is_not_a_win():
    board = board_with({(0, 5): 1, (9, 4): 1, (5, 3): 3})
    assert find_winner(board) is None
    board = board_with({(0, 5): 1, (0, 6): 3, (9, 4): 1, (5, 3): 3})
    assert find_winner(board) is None


def test_capturing_every_opponent_piece_wins():
    assert find_winner(board_with({(9, 4): 1})) == "1"
    assert find_winner(board_with({(5, 4): 4})) == "2"
