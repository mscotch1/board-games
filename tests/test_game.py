import pytest

import rules
from game import MAX_PATH_LENGTH, Game, IllegalMove
from rules import BLACK, WHITE
from variants import CAMELOT

COLS = CAMELOT.cols


def sq(row, col):
    return row * COLS + col


def game_with(pieces, turn=WHITE):
    game = Game()
    game.board = [0] * len(game.board)
    for (row, col), piece in pieces.items():
        game.board[sq(row, col)] = piece
    game.turn = turn
    game._legal = rules.legal_turns(game.variant, game.board, turn)
    return game


def test_new_game_starts_with_white():
    game = Game()
    assert game.turn == WHITE
    assert game.winner is None
    assert game.board == list(CAMELOT.initial)
    assert game.legal_turns == rules.legal_turns(game.variant, game.board, WHITE)


def test_legal_turn_updates_board_and_passes_the_turn():
    game = Game()
    game.play_turn(WHITE, [sq(9, 4), sq(8, 4)])

    assert game.board[sq(8, 4)] == 1
    assert game.board[sq(9, 4)] == 0
    assert game.turn == BLACK
    assert game.winner is None
    assert game.legal_turns == rules.legal_turns(game.variant, game.board, BLACK)


def test_players_alternate():
    game = Game()
    game.play_turn(WHITE, [sq(10, 2), sq(11, 2)])
    game.play_turn(BLACK, [sq(6, 4), sq(7, 4)])
    assert game.turn == WHITE
    assert game.board[sq(7, 4)] == 3


def test_cannot_play_out_of_turn():
    game = Game()
    with pytest.raises(IllegalMove, match="not your turn"):
        game.play_turn(BLACK, [sq(6, 4), sq(7, 4)])
    assert game.board == list(CAMELOT.initial)


def test_cannot_move_the_opponents_piece_or_an_empty_square():
    game = Game()
    with pytest.raises(IllegalMove, match="not allowed"):
        game.play_turn(WHITE, [sq(5, 3), sq(6, 2)])
    with pytest.raises(IllegalMove, match="not allowed"):
        game.play_turn(WHITE, [sq(8, 4), sq(7, 4)])


def test_illegal_move_leaves_the_game_unchanged():
    game = Game()
    with pytest.raises(IllegalMove, match="not allowed"):
        game.play_turn(WHITE, [sq(9, 4), sq(5, 4)])
    assert game.board == list(CAMELOT.initial)
    assert game.turn == WHITE
    assert game.last_turn is None


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
        game.play_turn(WHITE, moves)
    assert game.board == list(CAMELOT.initial)


def test_a_shorter_path_than_the_full_jump_chain_is_rejected():
    game = game_with({(12, 4): 1, (11, 4): 3, (9, 4): 3, (2, 2): 3})
    with pytest.raises(IllegalMove, match="must capture"):
        game.play_turn(WHITE, [sq(12, 4), sq(10, 4)])
    game.play_turn(WHITE, [sq(12, 4), sq(10, 4), sq(8, 4)])
    assert game.board[sq(11, 4)] == game.board[sq(9, 4)] == 0
    assert game.board[sq(8, 4)] == 1


def test_a_capture_must_be_taken():
    game = game_with({(9, 4): 1, (8, 4): 3, (12, 2): 1, (1, 1): 3})
    with pytest.raises(IllegalMove, match="must capture"):
        game.play_turn(WHITE, [sq(12, 2), sq(11, 2)])
    game.play_turn(WHITE, [sq(9, 4), sq(7, 4)])


def test_the_last_turn_is_recorded():
    game = Game()
    game.play_turn(WHITE, [sq(9, 4), sq(8, 4)])
    assert game.last_turn[0] == WHITE
    assert game.last_turn[1].moves == (sq(9, 4), sq(8, 4))


def test_snapshot_describes_the_game_for_clients():
    game = Game()
    game.play_turn(WHITE, [sq(10, 2), sq(11, 2)])
    snapshot = game.snapshot()

    assert snapshot["rows"] == CAMELOT.rows and snapshot["cols"] == CAMELOT.cols
    assert snapshot["mask"] == list(CAMELOT.mask)
    assert snapshot["board"] == game.board
    assert snapshot["turn"] == BLACK
    assert snapshot["winner"] is None and snapshot["winReason"] is None
    assert snapshot["lastTurn"] == {"player": WHITE, "moves": [sq(10, 2), sq(11, 2)], "jumped": [None]}
    assert snapshot["castles"] == {"top": [5, 6], "bottom": [185, 186]}
    assert {"moves": [sq(6, 4), sq(7, 4)], "jumped": [None]} in snapshot["legal"]


def test_reaching_the_goal_castle_wins():
    game = game_with({(1, 5): 1, (0, 6): 2, (9, 4): 3})
    game.play_turn(WHITE, [sq(1, 5), sq(0, 5)])
    assert (game.winner, game.win_reason) == (WHITE, "castle")


def test_capturing_the_last_piece_wins_with_two_pieces_left():
    game = game_with({(9, 4): 1, (12, 2): 1, (8, 4): 3})
    game.play_turn(WHITE, [sq(9, 4), sq(7, 4)])
    assert (game.winner, game.win_reason) == (WHITE, "capture")
    assert game.draw_reason is None


def test_blocking_the_opponent_wins():
    # black's only man sits in its own castle, surrounded and unable to jump
    walls = {(1, 4): 1, (1, 5): 1, (1, 6): 1, (2, 3): 1, (2, 5): 1, (2, 7): 1}
    game = game_with({(0, 5): 3, (9, 4): 1, **walls})
    game.play_turn(WHITE, [sq(9, 4), sq(8, 4)])
    assert (game.winner, game.win_reason) == (WHITE, "blocked")
    assert game.legal_turns == []


def test_no_turns_after_the_game_is_over():
    game = game_with({(9, 4): 1, (12, 2): 1, (8, 4): 3})
    game.play_turn(WHITE, [sq(9, 4), sq(7, 4)])
    with pytest.raises(IllegalMove, match="over"):
        game.play_turn(BLACK, [sq(0, 5), sq(1, 5)])
    assert game.snapshot()["legal"] == []


def test_a_whole_game_of_legal_moves_never_gets_stuck():
    import random

    rng = random.Random(3)
    game = Game()
    for _ in range(300):
        if game.winner:
            break
        turn = rng.choice(game.legal_turns)
        game.play_turn(game.turn, list(turn.moves))
    assert game.winner or game.legal_turns


def test_stepping_into_range_gives_the_opponent_an_optional_charge():
    # after (9,4)->(8,4) a black knight can canter over its own men and capture the man; but no piece can
    # jump directly, and "a Knight is never obliged to make a Knight's Charge", so black may carry on as usual
    game = Game()
    game.play_turn(WHITE, [sq(9, 4), sq(8, 4)])
    charges = [t for t in game.legal_turns if t.is_capture]
    assert charges and all(t.jumped[0] is None for t in charges)
    assert any(not t.is_capture for t in game.legal_turns)
    game.play_turn(BLACK, [sq(6, 4), sq(7, 4)])  # an ordinary move is fine


def test_a_player_who_can_jump_directly_cannot_play_a_plain_move():
    game = Game()
    game.board = [0] * game.variant.size
    game.board[sq(9, 4)] = 1
    game.board[sq(8, 4)] = 3
    game.turn = WHITE
    game._legal = __import__("rules").legal_turns(game.variant, game.board, WHITE)
    with pytest.raises(IllegalMove, match="must capture"):
        game.play_turn(WHITE, [sq(9, 4), sq(9, 5)])
