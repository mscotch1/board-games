"""Camelot as the World Camelot Federation's official rules have it."""

from collections import Counter

import pytest

import rules
from game import FIFTY_MOVE_PLIES, Game, IllegalMove
from rules import BLACK, WHITE, apply_turn, legal_turns
from variants import CAM, CAMELOT

V = CAMELOT


def sq(row, col):
    return row * V.cols + col


def board_with(pieces):
    board = [0] * V.size
    for (row, col), piece in pieces.items():
        board[sq(row, col)] = piece
    return board


def paths(turns):
    return {t.moves for t in turns}


def game_with(pieces, turn=WHITE, variant=CAMELOT):
    game = Game(variant)
    game.board = [0] * variant.size
    for (row, col), piece in pieces.items():
        game.board[row * variant.cols + col] = piece
    game.turn = turn
    game._legal = legal_turns(variant, game.board, turn)
    game._positions = Counter({game._position(): 1})
    return game


def play(game, *moves):
    for (frm, to) in moves:
        game.play_turn(game.turn, [sq(*frm), sq(*to)])


# --- the enemy castle -------------------------------------------------------


def test_jumping_into_the_enemy_castle_ends_the_turn():
    # from (0,5) the man could jump (1,4) on to (2,3), but the turn is over
    board = board_with({(2, 5): 1, (1, 5): 3, (1, 4): 3})
    turns = legal_turns(V, board, WHITE)
    assert [t.moves for t in turns] == [(sq(2, 5), sq(0, 5))]
    assert turns[0].jumped == (sq(1, 5),)


def test_cantering_into_the_enemy_castle_ends_the_turn_too():
    board = board_with({(2, 5): 1, (1, 5): 1})
    turns = paths(legal_turns(V, board, WHITE))
    assert (sq(2, 5), sq(0, 5)) in turns
    assert not any(len(t) > 2 and t[1] == sq(0, 5) for t in turns)


def test_a_piece_in_the_enemy_castle_can_only_move_to_the_other_castle_square():
    board = board_with({(0, 5): 1, (1, 5): 3})
    assert paths(legal_turns(V, board, WHITE)) == {(sq(0, 5), sq(0, 6))}


def test_a_castle_piece_is_not_bound_by_the_duty_to_capture():
    # white could capture elsewhere, but that is another piece's duty; the castle piece
    # has no capture to make, so the capture elsewhere stands
    board = board_with({(0, 5): 1, (1, 5): 3, (9, 4): 1, (8, 4): 3})
    assert paths(legal_turns(V, board, WHITE)) == {(sq(9, 4), sq(7, 4))}


@pytest.mark.parametrize("used, allowed", [(0, True), (1, True), (2, False), (5, False)])
def test_each_player_gets_two_castle_moves(used, allowed):
    board = board_with({(0, 5): 1, (9, 4): 1})
    turns = paths(legal_turns(V, board, WHITE, castle_moves_used=used))
    assert ((sq(0, 5), sq(0, 6)) in turns) is allowed


def test_castle_moves_are_counted_per_player_over_the_whole_game():
    pieces = {(0, 5): 1, (12, 4): 1, (3, 3): 3, (3, 8): 3}
    game = game_with(pieces)
    play(game, ((0, 5), (0, 6)))
    assert game.castle_moves == {WHITE: 1, BLACK: 0}
    play(game, ((3, 3), (3, 4)))
    play(game, ((0, 6), (0, 5)))
    assert game.castle_moves[WHITE] == 2
    assert game.snapshot()["castleMovesLeft"] == {WHITE: 0, BLACK: 2}
    play(game, ((3, 4), (3, 3)))

    castle_piece_moves = [t.moves for t in game.legal_turns if t.moves[0] == sq(0, 5)]
    assert castle_piece_moves == []
    assert game.legal_turns  # the other man can still move


def test_two_pieces_in_the_enemy_castle_win():
    game = game_with({(1, 5): 1, (0, 6): 2, (9, 4): 3, (9, 8): 3})
    play(game, ((1, 5), (0, 5)))
    assert (game.winner, game.win_reason) == (WHITE, "castle")


# --- your own castle --------------------------------------------------------


def test_a_piece_in_your_own_castle_must_leave_first():
    board = board_with({(15, 5): 1, (9, 4): 1})
    turns = legal_turns(V, board, WHITE)
    assert {t.moves[0] for t in turns} == {sq(15, 5)}
    # it may step out in any direction but not into the other castle square
    assert paths(turns) == {(sq(15, 5), sq(14, s)) for s in (4, 5, 6)}


def test_a_piece_leaving_its_castle_must_jump_if_it_can():
    board = board_with({(15, 5): 1, (14, 5): 3, (9, 4): 1, (8, 4): 3})
    turns = legal_turns(V, board, WHITE)
    assert paths(turns) == {(sq(15, 5), sq(13, 5))}  # and not the capture at (9,4)


def test_a_castle_piece_ignores_captures_elsewhere_when_it_has_none():
    board = board_with({(15, 5): 1, (9, 4): 1, (8, 4): 3})
    turns = legal_turns(V, board, WHITE)
    assert {t.moves[0] for t in turns} == {sq(15, 5)}
    assert not any(t.is_capture for t in turns)


def test_jumping_into_your_own_castle_forces_the_piece_out_next_turn():
    game = game_with({(13, 5): 1, (14, 5): 3, (9, 4): 1, (3, 3): 3, (3, 8): 3})
    play(game, ((13, 5), (15, 5)))
    assert game.board[sq(15, 5)] == 1
    play(game, ((3, 3), (3, 4)))

    assert game.legal_turns and {t.moves[0] for t in game.legal_turns} == {sq(15, 5)}
    with pytest.raises(IllegalMove, match="must leave"):
        game.play_turn(WHITE, [sq(9, 4), sq(9, 5)])


# --- how the game ends ------------------------------------------------------


def test_capturing_the_last_enemy_piece_with_a_single_piece_left_is_a_draw():
    game = game_with({(9, 4): 1, (8, 4): 3})
    play(game, ((9, 4), (7, 4)))
    assert game.winner is None
    assert game.draw_reason == "lone-pieces"
    assert game.over and game.legal_turns == []


def test_both_sides_down_to_one_piece_is_drawn_straight_away():
    game = game_with({(9, 4): 1, (5, 4): 3, (5, 8): 3, (9, 8): 1})
    assert game.draw_reason is None
    # white takes one of black's two pieces, leaving one each
    game = game_with({(9, 4): 1, (8, 4): 3, (2, 8): 3})
    play(game, ((9, 4), (7, 4)))
    assert game.draw_reason == "lone-pieces"


def test_blocking_the_opponent_wins_with_two_pieces():
    walls = {(1, 4): 1, (1, 5): 1, (1, 6): 1, (2, 3): 1, (2, 5): 1, (2, 7): 1}
    game = game_with({(0, 5): 3, (9, 4): 1, **walls})
    play(game, ((9, 4), (8, 4)))
    assert (game.winner, game.win_reason) == (WHITE, "blocked")


def test_blocking_the_opponent_with_a_single_piece_is_not_a_win():
    # black's man in its own castle is boxed in by its own men, and white has one piece left
    pieces = {(0, 5): 3, (1, 4): 3, (1, 5): 3, (1, 6): 3, (2, 3): 3, (2, 5): 3, (2, 7): 3, (12, 4): 1}
    game = game_with(pieces)
    play(game, ((12, 4), (11, 4)))
    assert game.winner is None
    assert game.draw_reason == "stalemate"


# --- draws by claim ---------------------------------------------------------


def shuffle_position():
    # nobody can capture, and each side has two pieces so it isn't a lone-pieces draw
    return game_with({(12, 4): 1, (12, 8): 1, (3, 4): 3, (3, 8): 3})


def shuffle(game, times=1):
    for _ in range(times):
        play(game, ((12, 4), (12, 5)), ((3, 4), (3, 5)), ((12, 5), (12, 4)), ((3, 5), (3, 4)))


def test_a_third_repetition_can_be_claimed():
    game = shuffle_position()
    assert game.claimable() == {"repetition": False, "fiftyMoves": False}
    shuffle(game)  # the starting position has now appeared twice
    assert not game.claimable()["repetition"]
    shuffle(game)  # ... and now three times
    assert game.claimable()["repetition"]

    game.claim_draw(BLACK)
    assert game.draw_reason == "repetition"
    assert game.over and game.winner is None


def test_a_repetition_only_counts_with_the_same_player_to_move():
    game = shuffle_position()
    play(game, ((12, 4), (12, 5)))  # same pieces, but black to move rather than white
    assert game._positions[game._position()] == 1


def test_the_fifty_move_rule_can_be_claimed():
    game = shuffle_position()
    game.plies_without_progress = FIFTY_MOVE_PLIES - 1
    assert not game.claimable()["fiftyMoves"]
    play(game, ((12, 4), (12, 5)))
    assert game.claimable()["fiftyMoves"]

    game.claim_draw(WHITE)
    assert game.draw_reason == "fifty-moves"


def test_a_capture_resets_the_fifty_move_count():
    game = game_with({(9, 4): 1, (12, 8): 1, (8, 4): 3, (2, 8): 3, (2, 2): 3})
    game.plies_without_progress = 80
    play(game, ((9, 4), (7, 4)))
    assert game.plies_without_progress == 0


def test_reaching_a_castle_resets_the_fifty_move_count():
    game = game_with({(1, 5): 1, (12, 8): 1, (3, 4): 3, (3, 8): 3})
    game.plies_without_progress = 80
    play(game, ((1, 5), (0, 5)))
    assert game.plies_without_progress == 0


def test_there_is_nothing_to_claim_at_first():
    with pytest.raises(IllegalMove, match="nothing to claim"):
        shuffle_position().claim_draw(WHITE)


# --- draws by agreement -----------------------------------------------------


def test_a_draw_offer_can_be_accepted():
    game = shuffle_position()
    game.offer_draw(WHITE)
    assert game.draw_offer == WHITE
    game.respond_to_draw(BLACK, True)
    assert game.draw_reason == "agreed" and game.draw_offer is None and game.over


def test_a_draw_offer_can_be_declined():
    game = shuffle_position()
    game.offer_draw(BLACK)
    game.respond_to_draw(WHITE, False)
    assert game.draw_offer is None and not game.over


def test_offering_while_the_opponent_has_offered_agrees_the_draw():
    game = shuffle_position()
    game.offer_draw(WHITE)
    game.offer_draw(BLACK)
    assert game.draw_reason == "agreed"


def test_you_cannot_answer_your_own_offer_or_a_missing_one():
    game = shuffle_position()
    with pytest.raises(IllegalMove, match="no draw offer"):
        game.respond_to_draw(BLACK, True)
    game.offer_draw(WHITE)
    with pytest.raises(IllegalMove, match="no draw offer"):
        game.respond_to_draw(WHITE, True)


def test_playing_a_move_withdraws_a_pending_offer():
    game = shuffle_position()
    game.offer_draw(BLACK)
    play(game, ((12, 4), (12, 5)))
    assert game.draw_offer is None


def test_nothing_happens_after_a_draw():
    game = shuffle_position()
    game.offer_draw(WHITE)
    game.respond_to_draw(BLACK, True)
    with pytest.raises(IllegalMove, match="over"):
        game.play_turn(WHITE, [sq(12, 4), sq(12, 5)])
    for action in (lambda: game.offer_draw(WHITE), lambda: game.claim_draw(WHITE)):
        with pytest.raises(IllegalMove, match="over"):
            action()
    assert game.snapshot()["legal"] == []


def test_cam_has_no_draws():
    game = Game(CAM)
    for action in (
        lambda: game.offer_draw(WHITE),
        lambda: game.claim_draw(WHITE),
        lambda: game.respond_to_draw(BLACK, True),
    ):
        with pytest.raises(IllegalMove, match="Cam has no draws"):
            action()
    assert game.claimable() == {"repetition": False, "fiftyMoves": False}


def test_cam_still_wins_by_capturing_or_blocking_with_one_piece():
    cam = Game(CAM)
    cam.board = [0] * CAM.size
    cam.board[8 * 7 + 3], cam.board[7 * 7 + 3] = 1, 3
    cam._legal = legal_turns(CAM, cam.board, WHITE)
    cam.play_turn(WHITE, [8 * 7 + 3, 6 * 7 + 3])
    assert (cam.winner, cam.win_reason) == (WHITE, "capture")


# --- snapshots --------------------------------------------------------------


def test_snapshots_report_draw_state():
    game = shuffle_position()
    snapshot = game.snapshot()
    assert snapshot["drawsAllowed"] is True
    assert snapshot["draw"] is None and snapshot["drawOffer"] is None
    assert snapshot["claimable"] == {"repetition": False, "fiftyMoves": False}
    assert snapshot["castleMovesLeft"] == {WHITE: 2, BLACK: 2}

    game.offer_draw(WHITE)
    assert game.snapshot()["drawOffer"] == WHITE
    game.respond_to_draw(BLACK, True)
    assert game.snapshot()["draw"] == "agreed"

    assert Game(CAM).snapshot()["drawsAllowed"] is False


# --- random play ------------------------------------------------------------


def test_random_camelot_games_end_cleanly_under_the_official_rules():
    import random

    outcomes = Counter()
    for seed in range(12):
        rng = random.Random(seed)
        game = Game(CAMELOT)
        for _ in range(500):
            if game.over:
                break
            turn = rng.choice(game.legal_turns)
            game.play_turn(game.turn, list(turn.moves))
        assert game.over or game.legal_turns
        outcomes[game.win_reason or game.draw_reason or "unfinished"] += 1
    assert sum(outcomes.values()) == 12
