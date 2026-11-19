"""Camelot rules, ported as-is from web/games/camelot/scripts/board.js.

Boards are flat lists of ROWS * COLS ints: 0 is empty, 1/2 are player 1's
man/knight and 3/4 are player 2's man/knight. Players are the strings "1"/"2".
Only squares where BOARD_MASK is 1 are part of the board.
"""

ROWS = 16
COLS = 12

BOARD_MASK = (
    0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0,
    0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0,
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1,
    0, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0,
    0, 0, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0,
    0, 0, 0, 0, 0, 1, 1, 0, 0, 0, 0, 0,
)

INITIAL_BOARD = (
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 4, 3, 3, 3, 3, 3, 3, 4, 0, 0,
    0, 0, 0, 4, 3, 3, 3, 3, 4, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 2, 1, 1, 1, 1, 2, 0, 0, 0,
    0, 0, 2, 1, 1, 1, 1, 1, 1, 2, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
)

_NEIGHBOR_OFFSETS = (
    -COLS - 1, -COLS, -COLS + 1,
    -1, 1,
    COLS - 1, COLS, COLS + 1,
)


def _on_board(index):
    return 0 <= index < ROWS * COLS and BOARD_MASK[index] == 1


def row_from_index(index):
    return index // COLS


def col_from_index(index):
    return index % COLS


def adjacent_squares(index):
    row, col = row_from_index(index), col_from_index(index)
    return [
        candidate
        for candidate in (index + offset for offset in _NEIGHBOR_OFFSETS)
        if _on_board(candidate)
        and abs(row_from_index(candidate) - row) <= 1
        and abs(col_from_index(candidate) - col) <= 1
    ]


def jumpable_squares(index):
    row, col = row_from_index(index), col_from_index(index)
    result = []
    for offset in _NEIGHBOR_OFFSETS:
        candidate = index + offset * 2
        if not _on_board(candidate):
            continue
        row_diff = abs(row_from_index(candidate) - row)
        col_diff = abs(col_from_index(candidate) - col)
        if row_diff in (0, 2) and col_diff in (0, 2):
            result.append(candidate)
    return result


def is_empty(board, index):
    return board[index] == 0


def is_man(board, index):
    return board[index] != 0 and board[index] % 2 == 1


def player_of(piece):
    """The player ("1" or "2") who owns a non-empty piece."""
    return "1" if (piece - 1) // 2 == 0 else "2"


def is_same_team(board, index1, index2):
    return (
        board[index1] > 0
        and board[index2] > 0
        and player_of(board[index1]) == player_of(board[index2])
    )


def is_players_piece(board, player, index):
    return board[index] != 0 and player_of(board[index]) == player


def make_moves(board, moves):
    """Apply a path of moves to a copy of `board`, removing any jumped piece."""
    new_board = list(board)

    for i in range(1, len(moves)):
        start, end = moves[i - 1], moves[i]

        captured = None
        if end in jumpable_squares(start):
            jumped = (start + end) // 2
            if new_board[jumped] != 0 and not is_same_team(new_board, jumped, start):
                captured = jumped

        new_board[end] = new_board[start]
        new_board[start] = 0
        if captured is not None:
            new_board[captured] = 0

    return new_board


def is_valid_move(board, player, moves):
    """Whether `moves` (a path of square indices) is legal for `player`.

    A single index is a valid selection of one of the player's pieces. Longer
    paths are either one step to an adjacent square, or a series of jumps
    over opposing pieces and canters over own pieces.
    """
    if len(moves) < 1:
        return False

    if len(moves) == 1:
        return is_players_piece(board, player, moves[0])

    if len(moves) == 2 and moves[1] in adjacent_squares(moves[0]):
        return is_empty(board, moves[1])

    is_man_piece = is_man(board, moves[0])
    is_jumping = False
    is_cantering = False

    temp_board = list(board)
    for i in range(1, len(moves)):
        start, end = moves[i - 1], moves[i]

        if end not in jumpable_squares(start):
            return False

        jumped = (start + end) // 2
        next_is_jump = not is_empty(temp_board, jumped) and not is_same_team(board, jumped, moves[0])
        next_is_canter = is_same_team(board, jumped, moves[0])

        if not next_is_jump and not next_is_canter:
            return False

        if i >= 2 and moves[i - 2] == end:
            return False

        if not is_empty(temp_board, end):
            return False

        if is_cantering and next_is_jump and is_man_piece:
            return False  # only knights can do a knight's charge

        if is_jumping and not next_is_jump:
            return False

        is_jumping = next_is_jump
        is_cantering = next_is_canter

        temp_board = make_moves(board, moves[: i + 1])

    return True


def find_winner(board):
    """The winning player ("1" or "2"), or None if the game is still going."""
    back_row = [board[i] for i in range(COLS) if BOARD_MASK[i]]
    front_row = [board[i] for i in range((ROWS - 1) * COLS, ROWS * COLS) if BOARD_MASK[i]]

    if all(0 < v < 3 for v in back_row):
        return "1"

    if all(v >= 3 for v in front_row):
        return "2"

    if not any(is_players_piece(board, "1", i) for i in range(len(board))):
        return "2"

    if not any(is_players_piece(board, "2", i) for i in range(len(board))):
        return "1"

    return None
