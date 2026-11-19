"""Camelot rules.

Boards are flat lists of ROWS * COLS ints: 0 is empty, 1/2 are white's man/knight
and 3/4 are black's man/knight. Only squares where BOARD_MASK is 1 are on the
board. White starts at the bottom and moves up; black starts at the top.

A turn is a path of squares for one piece. Its first square is where the piece
starts and every later square is where it lands:

* plain move: one step to an adjacent empty square
* canter: jump over an adjacent friendly piece (which stays on the board)
* jump: jump over an adjacent enemy piece, capturing it
* knight's charge: a knight may canter and then jump. Men may only chain
  canters or chain jumps, never mix them.

Capturing is mandatory, and a capturing turn must continue while its piece can
still jump. A piece can't canter over the same friendly piece twice in a turn.

Castles are the two squares at each end of the board. A plain move or canter
can't enter your own castle (a jump can), and a piece inside the enemy castle
can only leave it by jumping. You win by occupying both squares of the enemy
castle, by capturing every enemy piece, or when your opponent has no legal turn.
"""

from typing import NamedTuple

ROWS = 16
COLS = 12

WHITE = "white"
BLACK = "black"

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

TOP_CASTLE = (5, 6)
BOTTOM_CASTLE = ((ROWS - 1) * COLS + 5, (ROWS - 1) * COLS + 6)

# the castle a side starts next to, and the enemy castle it is trying to occupy
HOME_CASTLE = {WHITE: BOTTOM_CASTLE, BLACK: TOP_CASTLE}
GOAL_CASTLE = {WHITE: TOP_CASTLE, BLACK: BOTTOM_CASTLE}

_NEIGHBOR_OFFSETS = (
    -COLS - 1, -COLS, -COLS + 1,
    -1, 1,
    COLS - 1, COLS, COLS + 1,
)


class Turn(NamedTuple):
    """One complete turn: the squares the piece visits, and what each step jumped.

    `jumped[i]` is the square captured on the step to `moves[i + 1]`, or None
    when that step was a plain move or a canter.
    """

    moves: tuple
    jumped: tuple

    @property
    def is_capture(self):
        return any(j is not None for j in self.jumped)


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


def owner(piece):
    """The side that owns a non-empty piece."""
    return WHITE if piece <= 2 else BLACK


def is_knight(piece):
    return piece != 0 and piece % 2 == 0


def other(player):
    return BLACK if player == WHITE else WHITE


def legal_turns(board, player):
    """Every turn `player` may play on `board`, as a list of Turns.

    Capturing turns are returned only if at least one exists, and only once
    they can't be extended any further.
    """
    captures = []
    others = []
    for start, piece in enumerate(board):
        if piece and owner(piece) == player:
            _explore(board, player, start, is_knight(piece), captures, others)
    return captures or others


_START, _CANTER, _JUMP = "start", "canter", "jump"


def _explore(board, player, start, knight, captures, others):
    home = HOME_CASTLE[player]
    goal = GOAL_CASTLE[player]
    # a piece in the enemy castle may not leave it except by jumping
    confined = start in goal

    work = list(board)
    work[start] = 0  # the moving piece is lifted off the board while it travels

    def can_land_without_jumping(square):
        return work[square] == 0 and square not in home and (not confined or square in goal)

    def visit(pos, moves, jumped, phase, cantered):
        jumps = []
        if phase != _CANTER or knight:
            for landing in jumpable_squares(pos):
                over = (pos + landing) // 2
                if work[landing] == 0 and work[over] != 0 and owner(work[over]) != player:
                    jumps.append((landing, over))

        if len(moves) > 1:
            turn = Turn(tuple(moves), tuple(jumped))
            if phase != _JUMP:
                others.append(turn)
            elif not jumps:
                captures.append(turn)

        for landing, over in jumps:
            taken, work[over] = work[over], 0
            visit(landing, moves + [landing], jumped + [over], _JUMP, cantered)
            work[over] = taken

        if phase != _JUMP:
            for landing in jumpable_squares(pos):
                over = (pos + landing) // 2
                if (
                    work[over] != 0
                    and owner(work[over]) == player
                    and over not in cantered
                    and can_land_without_jumping(landing)
                ):
                    visit(landing, moves + [landing], jumped + [None], _CANTER, cantered | {over})

        if phase == _START:
            for step in adjacent_squares(pos):
                if can_land_without_jumping(step):
                    others.append(Turn((pos, step), (None,)))

    visit(start, [start], [], _START, frozenset())


def apply_turn(board, turn):
    """The board after `turn`: the piece moves to its final square and jumped pieces go."""
    new_board = list(board)
    new_board[turn.moves[-1]] = new_board[turn.moves[0]]
    if turn.moves[-1] != turn.moves[0]:
        new_board[turn.moves[0]] = 0
    for over in turn.jumped:
        if over is not None:
            new_board[over] = 0
    return new_board


def find_winner(board):
    """(winner, reason) if a side has won on `board` outright, else (None, None).

    This doesn't know about blocked players; see Game for that.
    """
    for side in (WHITE, BLACK):
        if all(board[i] != 0 and owner(board[i]) == side for i in GOAL_CASTLE[side]):
            return side, "castle"

    for side in (WHITE, BLACK):
        if not any(p and owner(p) == side for p in board):
            return other(side), "capture"

    return None, None

