import pytest

import rules
from rules import BLACK, WHITE, Turn, apply_turn
from variants import CAMELOT as V

COLS = V.cols
INITIAL_BOARD = V.initial


def legal_turns(board, side):
    return rules.legal_turns(V, board, side)


def find_winner(board):
    return rules.find_winner(V, board)


def sq(row, col):
    return row * COLS + col


def board_with(pieces):
    board = [0] * (V.rows * COLS)
    for (row, col), piece in pieces.items():
        board[sq(row, col)] = piece
    return board


def path(*squares):
    return tuple(sq(*s) for s in squares)


def paths(turns):
    return {t.moves for t in turns}


# --- geometry ---------------------------------------------------------------


def test_board_shape():
    assert len(V.mask) == len(INITIAL_BOARD) == V.rows * V.cols
    assert sum(V.mask) == 160
    assert all(INITIAL_BOARD[i] == 0 or V.mask[i] for i in range(len(INITIAL_BOARD)))


def test_castle_squares_are_the_end_squares():
    assert V.home_castle[BLACK] == (sq(0, 5), sq(0, 6))
    assert V.home_castle[WHITE] == (sq(15, 5), sq(15, 6))
    assert V.goal_castle[WHITE] == V.home_castle[BLACK]


def test_each_side_starts_with_ten_men_and_four_knights():
    for side, men, knights in ((WHITE, 1, 2), (BLACK, 3, 4)):
        assert INITIAL_BOARD.count(men) == 10
        assert INITIAL_BOARD.count(knights) == 4
        assert all(rules.owner(p) == side for p in (men, knights))


def test_adjacent_squares_respect_edges_and_mask():
    assert sorted(V.adjacent_squares(sq(0, 5))) == sorted([sq(0, 6), sq(1, 4), sq(1, 5), sq(1, 6)])
    # the left edge must not wrap around to the previous row
    assert V.adjacent_squares(sq(3, 0)) == [sq(2, 1), sq(3, 1), sq(4, 0), sq(4, 1)]
    assert V.adjacent_squares(0) == []


def test_jumpable_squares_respect_edges_and_mask():
    assert sorted(V.jumpable_squares(sq(3, 0))) == sorted([sq(1, 2), sq(3, 2), sq(5, 0), sq(5, 2)])
    assert all(V.mask[i] for i in V.jumpable_squares(sq(1, 2)))
    assert -5 not in V.jumpable_squares(sq(0, 5))


# --- plain moves ------------------------------------------------------------


def test_opening_moves_are_plain_steps_for_both_sides():
    for side in (WHITE, BLACK):
        turns = legal_turns(list(INITIAL_BOARD), side)
        assert turns
        assert not any(t.is_capture for t in turns)
        assert all(rules.owner(INITIAL_BOARD[t.moves[0]]) == side for t in turns)

    assert path((9, 4), (8, 4)) in paths(legal_turns(list(INITIAL_BOARD), WHITE))
    assert path((6, 4), (7, 4)) in paths(legal_turns(list(INITIAL_BOARD), BLACK))


def test_men_step_in_any_direction():
    board = board_with({(8, 5): 1})
    around = [(7, 4), (7, 5), (7, 6), (8, 4), (8, 6), (9, 4), (9, 5), (9, 6)]
    assert paths(legal_turns(board, WHITE)) == {path((8, 5), s) for s in around}


def test_cannot_step_onto_an_occupied_square():
    board = board_with({(8, 5): 1, (7, 5): 1, (4, 5): 3})
    assert path((8, 5), (7, 5)) not in paths(legal_turns(board, WHITE))
    assert path((8, 5), (8, 4)) in paths(legal_turns(board, WHITE))


def test_only_moves_the_players_own_pieces():
    turns = legal_turns(board_with({(8, 5): 1, (4, 5): 3}), WHITE)
    assert {t.moves[0] for t in turns} == {sq(8, 5)}


# --- jumping ----------------------------------------------------------------


def test_jump_over_an_enemy_captures_it():
    board = board_with({(9, 4): 1, (8, 4): 3})
    assert legal_turns(board, WHITE) == [Turn(path((9, 4), (7, 4)), (sq(8, 4),))]

    after = apply_turn(board, legal_turns(board, WHITE)[0])
    assert after[sq(7, 4)] == 1
    assert after[sq(9, 4)] == after[sq(8, 4)] == 0


def test_cannot_jump_an_empty_square_or_onto_a_piece():
    assert not any(t.is_capture for t in legal_turns(board_with({(9, 4): 1}), WHITE))
    blocked = board_with({(9, 4): 1, (8, 4): 3, (7, 4): 3})
    assert not any(t.is_capture for t in legal_turns(blocked, WHITE))


def test_capturing_is_mandatory():
    board = board_with({(9, 4): 1, (8, 4): 3, (12, 2): 1})
    turns = legal_turns(board, WHITE)
    assert paths(turns) == {path((9, 4), (7, 4))}  # no plain moves, and the other man can't move


def test_a_chain_of_jumps_must_be_completed():
    board = board_with({(12, 4): 1, (11, 4): 3, (9, 4): 3})
    turns = legal_turns(board, WHITE)
    assert paths(turns) == {path((12, 4), (10, 4), (8, 4))}
    assert turns[0].jumped == (sq(11, 4), sq(9, 4))

    after = apply_turn(board, turns[0])
    assert sum(1 for v in after if v) == 1 and after[sq(8, 4)] == 1


def test_different_capture_routes_are_all_offered():
    board = board_with({(9, 4): 1, (8, 4): 3, (9, 5): 3})
    assert paths(legal_turns(board, WHITE)) == {path((9, 4), (7, 4)), path((9, 4), (9, 6))}


def test_a_jump_chain_can_branch():
    board = board_with({(12, 4): 1, (11, 4): 3, (9, 5): 3, (9, 3): 3})
    assert paths(legal_turns(board, WHITE)) == {
        path((12, 4), (10, 4), (8, 6)),
        path((12, 4), (10, 4), (8, 2)),
    }


def test_jumping_into_your_own_castle_is_allowed():
    board = board_with({(13, 5): 1, (14, 5): 3})
    assert paths(legal_turns(board, WHITE)) == {path((13, 5), (15, 5))}


# --- cantering --------------------------------------------------------------


def test_canter_over_a_friend_leaves_it_in_place():
    board = board_with({(9, 4): 1, (8, 4): 1})
    turns = legal_turns(board, WHITE)
    canter = [t for t in turns if t.moves == path((9, 4), (7, 4))]
    assert canter and not canter[0].is_capture
    assert apply_turn(board, canter[0])[sq(8, 4)] == 1


def test_canters_chain_and_can_stop_after_any_of_them():
    board = board_with({(12, 4): 1, (11, 4): 1, (9, 4): 1})
    turns = paths(legal_turns(board, WHITE))
    assert path((12, 4), (10, 4)) in turns
    assert path((12, 4), (10, 4), (8, 4)) in turns


def test_a_canter_cannot_come_back_to_where_it_began():
    board = board_with({(12, 4): 1, (11, 4): 1})
    turns = paths(legal_turns(board, WHITE))
    assert path((12, 4), (10, 4)) in turns
    assert path((12, 4), (10, 4), (12, 4)) not in turns


def test_a_canter_may_go_over_the_same_friend_twice():
    # The Federation only forbids beginning and ending a canter on the same square. Here the man on (6,2) goes
    # over the friend on (5,3) to (4,4), over (4,3) to (4,2), then over the friend on (5,3) again to (6,4):
    # a square that cannot be reached any other way.
    board = board_with({(6, 2): 1, (5, 3): 1, (4, 3): 1})
    turns = paths(legal_turns(board, WHITE))
    assert path((6, 2), (4, 4), (4, 2), (6, 4)) in turns
    assert all(p[-1] != sq(6, 4) or len(p) == 4 for p in turns if p[0] == sq(6, 2))


def test_cannot_canter_over_a_friend_onto_an_occupied_square():
    board = board_with({(9, 4): 1, (8, 4): 1, (7, 4): 3, (6, 4): 3})
    assert path((9, 4), (7, 4)) not in paths(legal_turns(board, WHITE))


def test_cantering_is_optional_but_capturing_is_not():
    board = board_with({(12, 4): 1, (11, 4): 1, (4, 4): 1, (3, 4): 3})
    assert paths(legal_turns(board, WHITE)) == {path((4, 4), (2, 4))}


# --- knight's charge --------------------------------------------------------


@pytest.mark.parametrize("piece, charges", [(1, False), (2, True)])
def test_only_knights_can_canter_then_jump(piece, charges):
    board = board_with({(12, 4): piece, (11, 4): 1, (9, 4): 3})
    turns = {t.moves: t for t in legal_turns(board, WHITE)}
    charge = path((12, 4), (10, 4), (8, 4))
    assert (charge in turns) is charges
    if charges:
        assert turns[charge].jumped == (None, sq(9, 4))
    else:
        # the man has no capture, so it may only canter or step
        assert path((12, 4), (10, 4)) in turns


def test_a_knight_may_chain_canters_then_jumps():
    board = board_with({(14, 4): 2, (13, 4): 1, (11, 4): 1, (9, 4): 3, (7, 4): 3})
    turns = paths(legal_turns(board, WHITE))
    assert path((14, 4), (12, 4), (10, 4), (8, 4), (6, 4)) in turns
    # (the chain of jumps must finish, so nothing stops after the first jump)
    assert path((14, 4), (12, 4), (10, 4), (8, 4)) not in turns


# --- the duty to jump, and the knight's charge (World Camelot Federation rules) ---


def test_a_knight_is_never_obliged_to_charge():
    # "A Knight is never obliged to make a Knight's Charge": no piece can jump directly here, so the charge
    # is only one of the turns on offer, alongside plain moves and canters
    board = board_with({(12, 4): 2, (11, 4): 1, (9, 4): 3})
    turns = {t.moves: t for t in legal_turns(board, WHITE)}
    charge = path((12, 4), (10, 4), (8, 4))
    assert charge in turns and turns[charge].is_capture
    assert path((12, 4), (12, 5)) in turns  # a plain move is allowed
    assert path((11, 4), (10, 4)) in turns  # and so is moving another piece


def test_a_direct_jump_must_be_made_and_a_charge_is_one_way_to_make_it():
    # the man on (9,1) can jump the enemy next to it, so the duty to jump applies: only captures are legal,
    # and "when compelled to jump, a player may, if he can, capture by a Knight's Charge instead"
    board = board_with({(9, 1): 1, (8, 1): 3, (12, 4): 2, (11, 4): 1, (9, 4): 3})
    turns = legal_turns(board, WHITE)
    assert all(t.is_capture for t in turns)
    assert path((9, 1), (7, 1)) in paths(turns)
    assert path((12, 4), (10, 4), (8, 4)) in paths(turns)


def test_a_knight_whose_canter_lands_next_to_a_jumpable_enemy_must_jump():
    # "If the Canter of a Knight brings it next to an enemy piece that can be jumped, it must do so"
    board = board_with({(12, 4): 2, (11, 4): 1, (9, 4): 3})
    turns = paths(legal_turns(board, WHITE))
    assert path((12, 4), (10, 4)) not in turns  # it would stop next to the enemy man
    assert path((12, 4), (10, 4), (8, 4)) in turns


def test_a_man_may_canter_to_a_square_next_to_an_enemy_piece():
    # only a knight has to jump after cantering; a man's turn simply ends there
    board = board_with({(12, 4): 1, (11, 4): 1, (9, 4): 3})
    assert path((12, 4), (10, 4)) in paths(legal_turns(board, WHITE))


def test_a_knight_may_canter_on_instead_when_it_captures_elsewhere_later_in_the_same_move():
    # "...unless by a different route later in that same move it captures one or more enemy pieces elsewhere"
    board = board_with({(12, 4): 2, (11, 4): 1, (10, 5): 1, (9, 4): 3, (9, 6): 3})
    turns = paths(legal_turns(board, WHITE))
    assert path((12, 4), (10, 4), (8, 4)) in turns  # jump the man beside the first landing
    assert path((12, 4), (10, 4), (10, 6), (8, 6)) in turns  # or canter on and jump the other one
    assert path((12, 4), (10, 4)) not in turns  # but not stop beside either of them
    assert path((12, 4), (10, 4), (10, 6)) not in turns


def test_nothing_can_follow_a_jump_but_another_jump():
    # after capturing (8,4) the man lands next to a friend it could canter over
    for piece in (1, 2):
        turns = paths(legal_turns(board_with({(9, 4): piece, (8, 4): 3, (7, 3): 1}), WHITE))
        assert path((9, 4), (7, 4)) in turns
        assert path((9, 4), (7, 4), (7, 2)) not in turns


# --- castles ----------------------------------------------------------------


def test_plain_move_into_own_castle_is_not_allowed():
    turns = paths(legal_turns(board_with({(14, 5): 1}), WHITE))
    assert path((14, 5), (15, 5)) not in turns
    assert path((14, 5), (15, 6)) not in turns
    assert path((14, 5), (13, 5)) in turns


def test_canter_into_own_castle_is_not_allowed():
    board = board_with({(13, 5): 1, (14, 5): 1})
    assert path((13, 5), (15, 5)) not in paths(legal_turns(board, WHITE))


def test_black_castle_is_the_top_one():
    assert path((1, 5), (0, 5)) not in paths(legal_turns(board_with({(1, 5): 3}), BLACK))
    assert path((14, 5), (15, 5)) in paths(legal_turns(board_with({(14, 5): 3}), BLACK))
    assert path((1, 5), (0, 5)) in paths(legal_turns(board_with({(1, 5): 1}), WHITE))


def test_a_piece_in_the_enemy_castle_cannot_step_out():
    turns = paths(legal_turns(board_with({(0, 5): 1}), WHITE))
    assert turns == {path((0, 5), (0, 6))}


def test_a_piece_in_the_enemy_castle_cannot_leave_even_by_jumping():
    # (2,5) is empty beyond the black man, but the castle piece may not use it
    board = board_with({(0, 5): 1, (1, 5): 3})
    assert paths(legal_turns(board, WHITE)) == {path((0, 5), (0, 6))}


def test_a_piece_in_the_enemy_castle_cannot_canter_out():
    board = board_with({(0, 5): 1, (1, 5): 1})
    from_castle = {t for t in paths(legal_turns(board, WHITE)) if t[0] == sq(0, 5)}
    assert from_castle == {path((0, 5), (0, 6))}


# --- winning ----------------------------------------------------------------


def test_apply_turn_moves_the_piece():
    board = board_with({(9, 4): 2})
    after = apply_turn(board, Turn(path((9, 4), (8, 4)), (None,)))
    assert after[sq(8, 4)] == 2 and after[sq(9, 4)] == 0
    assert board[sq(9, 4)] == 2  # the input is untouched


def test_no_winner_at_start():
    assert find_winner(list(INITIAL_BOARD)) == (None, None)


def test_white_wins_by_filling_the_top_castle():
    board = board_with({(0, 5): 1, (0, 6): 2, (9, 4): 1, (5, 3): 3})
    assert find_winner(board) == (WHITE, "castle")


def test_black_wins_by_filling_the_bottom_castle():
    board = board_with({(15, 5): 3, (15, 6): 4, (9, 4): 1, (5, 3): 3})
    assert find_winner(board) == (BLACK, "castle")


def test_half_filled_or_contested_castle_is_not_a_win():
    assert find_winner(board_with({(0, 5): 1, (9, 4): 1, (5, 3): 3})) == (None, None)
    assert find_winner(board_with({(0, 5): 1, (0, 6): 3, (9, 4): 1, (5, 3): 3})) == (None, None)


def test_capturing_every_piece_wins_with_two_pieces_left():
    assert find_winner(board_with({(9, 4): 1, (9, 5): 2})) == (WHITE, "capture")
    assert find_winner(board_with({(5, 4): 4, (5, 5): 3})) == (BLACK, "capture")


def test_capturing_every_piece_is_not_a_win_with_one_piece_left():
    assert find_winner(board_with({(9, 4): 1})) == (None, None)
    assert find_winner(board_with({(5, 4): 4})) == (None, None)


# --- properties -------------------------------------------------------------


def random_board(rng):
    density = rng.choice([0.05, 0.15, 0.3, 0.5])
    return [
        rng.choice([1, 2, 3, 4]) if V.mask[i] and rng.random() < density else 0
        for i in range(V.rows * COLS)
    ]


def test_legal_turns_are_consistent_on_random_boards():
    import random

    rng = random.Random(7)
    for _ in range(400):
        board = random_board(rng)
        for side in (WHITE, BLACK):
            turns = legal_turns(board, side)
            assert len({t.moves for t in turns}) == len(turns)  # no duplicates
            starts_with_a_jump = [t for t in turns if t.jumped[0] is not None]
            if starts_with_a_jump:
                # a piece is next to an exposed enemy piece: jumping is compulsory (a charge is one way)
                assert all(t.is_capture for t in turns)
            else:
                # nothing can jump directly, so a charge is only optional: every capture is a charge
                assert all(t.jumped[0] is None for t in turns)

            for turn in turns:
                assert rules.owner(board[turn.moves[0]]) == side
                assert len(turn.jumped) == len(turn.moves) - 1
                assert all(V.mask[m] for m in turn.moves)

                jumped = [j for j in turn.jumped if j is not None]
                assert len(jumped) == len(set(jumped))
                assert all(board[j] != 0 and rules.owner(board[j]) != side for j in jumped)

                after = apply_turn(board, turn)
                assert after[turn.moves[-1]] == board[turn.moves[0]]
                assert sum(1 for v in board if v) - sum(1 for v in after if v) == len(jumped)

                if turn.is_capture and turn.moves[-1] not in V.goal_castle[side]:
                    # a capture must be played out (unless it ended in the enemy castle, which
                    # ends the turn): nothing more can be jumped from where it ends
                    end = turn.moves[-1]
                    for landing in V.jumpable_squares(end):
                        over = (end + landing) // 2
                        extendable = (
                            after[landing] == 0
                            and after[over] != 0
                            and rules.owner(after[over]) != side
                        )
                        assert not extendable
