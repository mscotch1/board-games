"""The games the server can host: Camelot and its cousin Cam.

Camelot follows the World Camelot Federation's official rules: a piece that enters
the enemy castle can never leave it (bar two moves between the castle squares per
player) and entering ends the turn; a piece that jumps into its own castle must
leave on the next turn; capturing everything or blocking the opponent only wins
with two or more pieces left; and the game can be drawn.

Cam is Parker Brothers' 1949 pocket version of Camelot. Its rules, as published
by the World Camelot Federation, differ in a few ways: a much smaller board with
a single castle square at each end, 2 knights and 5 men a side, and a win as soon
as any one piece reaches the enemy castle. A piece that jumps into its own castle
and can't jump on must leave it on the next turn.
"""

from rules import BLACK, WHITE, Variant

# --- Camelot ----------------------------------------------------------------

_CAMELOT_ROWS = 16
_CAMELOT_COLS = 12

_CAMELOT_MASK = (
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

_CAMELOT_INITIAL = (
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

CAMELOT = Variant(
    "camelot",
    "Camelot",
    _CAMELOT_ROWS,
    _CAMELOT_COLS,
    _CAMELOT_MASK,
    _CAMELOT_INITIAL,
    home_castles={
        WHITE: ((_CAMELOT_ROWS - 1) * _CAMELOT_COLS + 5, (_CAMELOT_ROWS - 1) * _CAMELOT_COLS + 6),
        BLACK: (5, 6),
    },
    castle_to_win=2,
    enemy_castle_ends_turn=True,
    confine_in_enemy_castle=True,
    castle_moves=2,
    forced_exit=True,
    wins_need_two_pieces=True,
    draws=True,
)

# --- Cam --------------------------------------------------------------------

_CAM_ROWS = 13  # ranks 1 (white's edge) to 13
_CAM_COLS = 7  # files A to G

# the files each rank covers, from rank 13 (the top row) down to rank 1
_CAM_FILES_BY_ROW = [
    "D", "CDE", "BCDEF",
    "ABCDEFG", "ABCDEFG", "ABCDEFG", "ABCDEFG", "ABCDEFG", "ABCDEFG", "ABCDEFG",
    "BCDEF", "CDE", "D",
]


def cam_square(name):
    """The index of a square written like "C4": file letter, then rank."""
    return (_CAM_ROWS - int(name[1:])) * _CAM_COLS + (ord(name[0]) - ord("A"))


def _cam_mask():
    mask = [0] * (_CAM_ROWS * _CAM_COLS)
    for row, files in enumerate(_CAM_FILES_BY_ROW):
        for file in files:
            mask[row * _CAM_COLS + ord(file) - ord("A")] = 1
    return mask


def _cam_initial():
    board = [0] * (_CAM_ROWS * _CAM_COLS)
    placements = {
        2: ["C4", "E4"],  # white knights
        1: ["B5", "C5", "D5", "E5", "F5"],  # white men
        4: ["C10", "E10"],  # black knights
        3: ["B9", "C9", "D9", "E9", "F9"],  # black men
    }
    for piece, squares in placements.items():
        for name in squares:
            board[cam_square(name)] = piece
    return board


CAM = Variant(
    "cam",
    "Cam",
    _CAM_ROWS,
    _CAM_COLS,
    _cam_mask(),
    _cam_initial(),
    home_castles={WHITE: (cam_square("D1"),), BLACK: (cam_square("D13"),)},
    castle_to_win=1,
    enemy_castle_ends_turn=True,
    forced_exit=True,
)

VARIANTS = {variant.key: variant for variant in (CAMELOT, CAM)}
DEFAULT_VARIANT = CAMELOT
