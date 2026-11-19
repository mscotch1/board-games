import random

import pytest

import rules
from game import Game, IllegalMove
from rules import BLACK, WHITE, Turn, apply_turn, legal_turns
from variants import CAM, CAMELOT, DEFAULT_VARIANT, VARIANTS, cam_square


def square(variant, row, col):
    return row * variant.cols + col


def board_with(variant, pieces):
    board = [0] * variant.size
    for (row, col), piece in pieces.items():
        board[square(variant, row, col)] = piece
    return board


def game_with(variant, pieces, turn=WHITE):
    game = Game(variant)
    game.board = board_with(variant, pieces)
    game.turn = turn
    game._legal = legal_turns(variant, game.board, turn)
    return game


def names(variant, squares):
    """Squares as Cam notation, to make failures readable."""
    return [f"{chr(ord('A') + variant.col(i))}{variant.rows - variant.row(i)}" for i in squares]


# --- the registry -----------------------------------------------------------


def test_the_registry_holds_both_games():
    assert VARIANTS == {"camelot": CAMELOT, "cam": CAM}
    assert DEFAULT_VARIANT is CAMELOT


def test_variants_reject_a_pieces_off_the_board():
    with pytest.raises(ValueError, match="start on the board"):
        rules.Variant("bad", "Bad", 2, 2, (1, 0, 0, 0), (0, 1, 0, 0), {WHITE: (2,), BLACK: (0,)}, castle_to_win=1)


def test_variants_reject_a_wrong_sized_board():
    with pytest.raises(ValueError, match="rows \\* cols"):
        rules.Variant("bad", "Bad", 2, 2, (1, 1, 1), (0, 0, 0), {WHITE: (2,), BLACK: (0,)}, castle_to_win=1)


# --- the Cam board ----------------------------------------------------------


def test_cam_board_has_67_squares_13_ranks_and_7_files():
    assert (CAM.rows, CAM.cols) == (13, 7)
    assert sum(CAM.mask) == 67


def test_cam_ranks_have_the_published_shape():
    widths = [sum(CAM.mask[row * 7 : (row + 1) * 7]) for row in range(13)]  # rank 13 down to rank 1
    assert widths == [1, 3, 5, 7, 7, 7, 7, 7, 7, 7, 5, 3, 1]


def test_cam_board_is_symmetrical():
    flipped = tuple(reversed(CAM.mask))
    assert flipped == CAM.mask


def test_cam_squares_match_the_notation():
    assert cam_square("D1") == 87 and cam_square("D13") == 3
    assert cam_square("A4") == 9 * 7
    assert all(CAM.mask[cam_square(name)] for name in ["D1", "C2", "E2", "B3", "F3", "A4", "G10", "B11", "F11", "C12", "E12", "D13"])
    assert not any(CAM.mask[cam_square(name)] for name in ["C1", "E1", "B2", "A3", "G3", "A11", "A12", "G11", "C13"])


def test_cam_castles_are_single_squares_at_each_end():
    assert CAM.home_castle == {WHITE: (cam_square("D1"),), BLACK: (cam_square("D13"),)}
    assert CAM.goal_castle[WHITE] == (cam_square("D13"),)
    assert CAM.castle_to_win == 1


def test_cam_starting_position_matches_the_rules():
    expected = {
        2: ["C4", "E4"],
        1: ["B5", "C5", "D5", "E5", "F5"],
        4: ["C10", "E10"],
        3: ["B9", "C9", "D9", "E9", "F9"],
    }
    board = CAM.initial
    for piece, squares in expected.items():
        assert sorted(i for i, p in enumerate(board) if p == piece) == sorted(cam_square(s) for s in squares)
    assert sum(1 for p in board if p) == 14


def test_cam_geometry_is_not_camelots():
    # neighbours must not wrap round the 7-wide board
    assert sorted(CAM.adjacent_squares(cam_square("A5"))) == sorted(cam_square(s) for s in ["A6", "B6", "B5", "A4", "B4"])
    # A3 isn't a square on the Cam board, so it can't be jumped to
    assert sorted(CAM.jumpable_squares(cam_square("A5"))) == sorted(cam_square(s) for s in ["A7", "C7", "C5", "C3"])


# --- moving in Cam ----------------------------------------------------------


def test_cam_opening_moves_are_plain_steps_and_canters():
    for side in (WHITE, BLACK):
        turns = legal_turns(CAM, list(CAM.initial), side)
        assert turns and not any(t.is_capture for t in turns)
        assert all(rules.owner(CAM.initial[t.moves[0]]) == side for t in turns)

    white = {t.moves for t in legal_turns(CAM, list(CAM.initial), WHITE)}
    assert (cam_square("B5"), cam_square("B6")) in white  # plain move
    assert (cam_square("C4"), cam_square("C6")) in white  # a knight cantering over a man


def test_cam_jumps_and_chains_follow_the_family_rules():
    board = [0] * CAM.size
    board[cam_square("D5")] = 1
    board[cam_square("D6")] = 3
    board[cam_square("D8")] = 3
    turns = legal_turns(CAM, board, WHITE)
    assert [t.moves for t in turns] == [(cam_square("D5"), cam_square("D7"), cam_square("D9"))]
    assert turns[0].jumped == (cam_square("D6"), cam_square("D8"))


# --- winning ----------------------------------------------------------------


def test_one_piece_in_the_enemy_castle_wins():
    for side, piece, from_square, castle in ((WHITE, 1, "D12", "D13"), (BLACK, 3, "D2", "D1")):
        game = game_with(CAM, {}, turn=side)
        game.board = [0] * CAM.size
        game.board[cam_square(from_square)] = piece
        game.board[cam_square("A8")] = 3 if side == WHITE else 1  # something for the other side to own
        game._legal = legal_turns(CAM, game.board, side)

        game.play_turn(side, [cam_square(from_square), cam_square(castle)])
        assert (game.winner, game.win_reason) == (side, "castle")


def test_camelot_still_needs_both_castle_squares():
    board = board_with(CAMELOT, {(0, 5): 1, (9, 4): 3})
    assert rules.find_winner(CAMELOT, board) == (None, None)
    board[square(CAMELOT, 0, 6)] = 2
    assert rules.find_winner(CAMELOT, board) == (WHITE, "castle")


def test_capturing_everything_wins_in_cam():
    game = game_with(CAM, {(8, 3): 1, (7, 3): 3})
    game.play_turn(WHITE, [square(CAM, 8, 3), square(CAM, 6, 3)])
    assert (game.winner, game.win_reason) == (WHITE, "capture")


def test_a_blocked_player_still_loses():
    # black's only man is boxed into its own castle by white pieces it cannot jump
    pieces = {(0, 3): 3, (1, 2): 1, (1, 3): 1, (1, 4): 1, (2, 1): 1, (2, 3): 1, (2, 5): 1, (9, 3): 1}
    game = game_with(CAM, pieces)
    game.play_turn(WHITE, [square(CAM, 9, 3), square(CAM, 8, 3)])
    assert (game.winner, game.win_reason) == (WHITE, "blocked")


# --- entering the enemy castle ends the turn --------------------------------


def test_entering_the_enemy_castle_by_jumping_ends_the_turn():
    # white jumps D12 into D13; the man there is next to another exposed black piece,
    # which in Camelot it would have to keep jumping
    pieces = {(2, 3): 1, (1, 3): 3, (1, 2): 3}
    turns = legal_turns(CAM, board_with(CAM, pieces), WHITE)
    assert [t.moves for t in turns] == [(square(CAM, 2, 3), square(CAM, 0, 3))]
    assert turns[0].jumped == (square(CAM, 1, 3),)


def test_a_cantering_chain_stops_in_the_enemy_castle_too():
    pieces = {(2, 3): 1, (1, 3): 1}
    turns = legal_turns(CAM, board_with(CAM, pieces), WHITE)
    canter_into_castle = (square(CAM, 2, 3), square(CAM, 0, 3))
    assert canter_into_castle in {t.moves for t in turns}


# --- the castle you start beside ---------------------------------------------


def test_plain_moves_and_canters_cannot_enter_your_own_castle():
    turns = {t.moves for t in legal_turns(CAM, board_with(CAM, {(11, 3): 1}), WHITE)}
    assert (square(CAM, 11, 3), square(CAM, 12, 3)) not in turns
    assert (square(CAM, 11, 3), square(CAM, 10, 3)) in turns

    canter = {t.moves for t in legal_turns(CAM, board_with(CAM, {(10, 3): 1, (11, 3): 1}), WHITE)}
    assert (square(CAM, 10, 3), square(CAM, 12, 3)) not in canter


def test_a_knights_charge_cannot_canter_into_your_own_castle():
    board = board_with(CAM, {(10, 3): 2, (11, 3): 1, (12, 3): 0})
    turns = {t.moves for t in legal_turns(CAM, board, WHITE)}
    assert not any(t[-1] == square(CAM, 12, 3) for t in turns)


def test_jumping_into_your_own_castle_is_allowed_and_must_continue_if_it_can():
    board = board_with(CAM, {(10, 3): 1, (11, 3): 3})
    turns = legal_turns(CAM, board, WHITE)
    assert [t.moves for t in turns] == [(square(CAM, 10, 3), square(CAM, 12, 3))]

    # next to another exposed enemy piece, it must jump on out of the castle
    board = board_with(CAM, {(10, 3): 1, (11, 3): 3, (11, 2): 3, (10, 1): 0})
    turns = legal_turns(CAM, board, WHITE)
    assert [t.moves for t in turns] == [(square(CAM, 10, 3), square(CAM, 12, 3), square(CAM, 10, 1))]


def test_a_piece_that_jumped_into_its_castle_must_leave_next_turn():
    game = game_with(CAM, {(10, 3): 1, (11, 3): 3, (6, 3): 1, (2, 1): 3})
    game.play_turn(WHITE, [square(CAM, 10, 3), square(CAM, 12, 3)])
    assert game.board[square(CAM, 12, 3)] == 1
    game.play_turn(BLACK, list(game.legal_turns[0].moves))

    turns = game.legal_turns
    assert turns and all(t.moves[0] == square(CAM, 12, 3) for t in turns)
    assert not any(t.moves[-1] == square(CAM, 12, 3) for t in turns)


def test_the_trapped_piece_goes_ahead_of_every_other_move():
    game = game_with(CAM, {(12, 3): 1, (6, 3): 1, (3, 3): 3}, turn=WHITE)
    turns = game.legal_turns
    assert {t.moves[0] for t in turns} == {square(CAM, 12, 3)}
    with pytest.raises(IllegalMove, match="must leave"):
        game.play_turn(WHITE, [square(CAM, 6, 3), square(CAM, 5, 3)])


def test_a_trapped_piece_must_jump_out_if_it_can():
    # the man in the castle can jump the black man at D2, so it may not just step out
    game = game_with(CAM, {(12, 3): 1, (11, 3): 3, (11, 2): 0})
    turns = game.legal_turns
    assert [t.moves for t in turns] == [(square(CAM, 12, 3), square(CAM, 10, 3))]
    assert turns[0].is_capture


def test_a_trapped_piece_may_leave_instead_of_taking_a_capture_elsewhere():
    # white could capture on the other side of the board, but the castle piece has priority
    pieces = {(12, 3): 1, (6, 1): 1, (5, 1): 3}
    game = game_with(CAM, pieces)
    assert all(t.moves[0] == square(CAM, 12, 3) for t in game.legal_turns)
    assert not any(t.is_capture for t in game.legal_turns)


def test_a_trapped_knight_may_leave_with_a_charge():
    # the knight cantering out over a friend and then jumping satisfies the duty to capture
    pieces = {(12, 3): 2, (11, 3): 1, (9, 3): 3}
    turns = legal_turns(CAM, board_with(CAM, pieces), WHITE)
    charge = (square(CAM, 12, 3), square(CAM, 10, 3), square(CAM, 8, 3))
    assert charge in {t.moves for t in turns}
    assert all(t.is_capture for t in turns)


def test_camelot_has_no_forced_exit():
    board = board_with(CAMELOT, {(15, 5): 1, (9, 4): 1})
    starts = {t.moves[0] for t in legal_turns(CAMELOT, board, WHITE)}
    assert starts == {square(CAMELOT, 15, 5), square(CAMELOT, 9, 4)}


# --- canter loops (both games) ----------------------------------------------


@pytest.mark.parametrize("variant", [CAMELOT, CAM], ids=lambda v: v.key)
def test_a_canter_loop_cannot_end_where_it_began(variant):
    # four friends round a square: cantering over each in turn comes back to the start
    start, friends = (5, 1), [(5, 2), (6, 3), (7, 2), (6, 1)]
    board = board_with(variant, {start: 1, **{f: 1 for f in friends}})
    paths = {t.moves for t in legal_turns(variant, board, WHITE)}

    s = lambda rc: square(variant, *rc)
    loop = [s(start), s((5, 3)), s((7, 3)), s((7, 1)), s(start)]
    assert tuple(loop[:4]) in paths  # three canters are fine
    assert tuple(loop) not in paths  # but not all the way round


# --- properties -------------------------------------------------------------


def random_board(variant, rng):
    density = rng.choice([0.05, 0.15, 0.3, 0.5])
    return [
        rng.choice([1, 2, 3, 4]) if variant.mask[i] and rng.random() < density else 0
        for i in range(variant.size)
    ]


@pytest.mark.parametrize("variant", [CAMELOT, CAM], ids=lambda v: v.key)
def test_legal_turns_are_consistent_on_random_boards(variant):
    rng = random.Random(11)
    for _ in range(300):
        board = random_board(variant, rng)
        for side in (WHITE, BLACK):
            turns = legal_turns(variant, board, side)
            assert len({t.moves for t in turns}) == len(turns)
            assert len({t.is_capture for t in turns}) <= 1

            for turn in turns:
                assert all(variant.mask[m] for m in turn.moves)
                assert len(turn.jumped) == len(turn.moves) - 1
                assert apply_turn(board, turn)[turn.moves[-1]] == board[turn.moves[0]]
                assert turn.moves[-1] != turn.moves[0] or turn.is_capture


def test_cam_turns_never_pass_through_the_enemy_castle_or_land_in_your_own():
    rng = random.Random(5)
    for _ in range(300):
        board = random_board(CAM, rng)
        for side in (WHITE, BLACK):
            goal, home = CAM.goal_castle[side], CAM.home_castle[side]
            for turn in legal_turns(CAM, board, side):
                assert not any(m in goal for m in turn.moves[1:-1])  # entering the castle ends the turn
                for step, landing in enumerate(turn.moves[1:]):
                    if landing in home:
                        assert turn.jumped[step] is not None  # only a jump may land in your own castle


@pytest.mark.parametrize("variant", [CAMELOT, CAM], ids=lambda v: v.key)
def test_random_games_always_finish_or_keep_going_legally(variant):
    for seed in range(5):
        rng = random.Random(seed)
        game = Game(variant)
        for _ in range(400):
            if game.winner:
                break
            turn = rng.choice(game.legal_turns)
            game.play_turn(game.turn, list(turn.moves))
        assert game.winner or game.legal_turns


# --- snapshots --------------------------------------------------------------


def test_snapshots_describe_the_variant():
    snapshot = Game(CAM).snapshot()
    assert (snapshot["variant"], snapshot["variantName"], snapshot["castleToWin"]) == ("cam", "Cam", 1)
    assert (snapshot["rows"], snapshot["cols"]) == (13, 7)
    assert snapshot["castles"] == {"top": [3], "bottom": [87]}
    assert len(snapshot["mask"]) == len(snapshot["board"]) == 91

    camelot = Game().snapshot()
    assert (camelot["variant"], camelot["castleToWin"]) == ("camelot", 2)
