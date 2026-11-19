"""The rules shared by Camelot and its variants (see variants.py).

Boards are flat lists of rows * cols ints: 0 is empty, 1/2 are white's man/knight
and 3/4 are black's man/knight. Only squares where a variant's mask is 1 are on
the board. White starts at the bottom and moves up; black starts at the top.

A turn is a path of squares for one piece. Its first square is where the piece
starts and every later square is where it lands:

* plain move: one step to an adjacent empty square
* canter: jump over an adjacent friendly piece (which stays on the board)
* jump: jump over an adjacent enemy piece, capturing it
* knight's charge: a knight may canter and then jump. Men may only chain
  canters or chain jumps, never mix them.

Capturing is mandatory, and a capturing turn must continue while its piece can
still jump. A piece can't canter over the same friendly piece twice in a turn,
and a turn made only of canters can't end where it began.

Castles are the squares at each end of the board. A plain move or canter can't
enter your own castle (a jump can). Each variant says how many pieces in the
enemy castle win the game, and a few optional rules (see Variant).
"""

from typing import NamedTuple

WHITE = "white"
BLACK = "black"


def other(player):
    return BLACK if player == WHITE else WHITE


def owner(piece):
    """The side that owns a non-empty piece."""
    return WHITE if piece <= 2 else BLACK


def is_knight(piece):
    return piece != 0 and piece % 2 == 0


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


class Variant:
    """A board, a starting position and the options that tell the variants apart.

    `home_castles` maps each side to the castle squares beside its starting edge;
    a side's goal is the other side's castle. The options:

    castle_to_win           how many of your pieces in the enemy castle win the game
    enemy_castle_ends_turn  entering the enemy castle ends the turn at once, even
                            if the piece could keep jumping
    confine_in_enemy_castle a piece in the enemy castle can only leave by jumping
    forced_exit             a piece that jumped into its own castle and couldn't
                            jump on must leave it on the next turn, ahead of any
                            other move (jumping out if it can)
    """

    def __init__(
        self,
        key,
        name,
        rows,
        cols,
        mask,
        initial,
        home_castles,
        *,
        castle_to_win,
        enemy_castle_ends_turn=False,
        confine_in_enemy_castle=False,
        forced_exit=False,
    ):
        size = rows * cols
        if len(mask) != size or len(initial) != size:
            raise ValueError("mask and initial position must have rows * cols squares")
        if any(piece and not mask[i] for i, piece in enumerate(initial)):
            raise ValueError("every piece must start on the board")

        self.key = key
        self.name = name
        self.rows = rows
        self.cols = cols
        self.mask = tuple(mask)
        self.initial = tuple(initial)
        self.home_castle = {side: tuple(squares) for side, squares in home_castles.items()}
        self.goal_castle = {WHITE: self.home_castle[BLACK], BLACK: self.home_castle[WHITE]}
        self.castle_to_win = castle_to_win
        self.enemy_castle_ends_turn = enemy_castle_ends_turn
        self.confine_in_enemy_castle = confine_in_enemy_castle
        self.forced_exit = forced_exit

        self._offsets = (
            -cols - 1, -cols, -cols + 1,
            -1, 1,
            cols - 1, cols, cols + 1,
        )
        self._adjacent = tuple(self._compute_adjacent(i) for i in range(size))
        self._jumpable = tuple(self._compute_jumpable(i) for i in range(size))

    def __repr__(self):
        return f"Variant({self.key!r})"

    @property
    def size(self):
        return self.rows * self.cols

    def row(self, index):
        return index // self.cols

    def col(self, index):
        return index % self.cols

    def _on_board(self, index):
        return 0 <= index < self.size and self.mask[index] == 1

    def _compute_adjacent(self, index):
        row, col = self.row(index), self.col(index)
        return tuple(
            candidate
            for candidate in (index + offset for offset in self._offsets)
            if self._on_board(candidate)
            and abs(self.row(candidate) - row) <= 1
            and abs(self.col(candidate) - col) <= 1
        )

    def _compute_jumpable(self, index):
        row, col = self.row(index), self.col(index)
        result = []
        for offset in self._offsets:
            candidate = index + offset * 2
            if not self._on_board(candidate):
                continue
            if abs(self.row(candidate) - row) in (0, 2) and abs(self.col(candidate) - col) in (0, 2):
                result.append(candidate)
        return tuple(result)

    def adjacent_squares(self, index):
        return list(self._adjacent[index])

    def jumpable_squares(self, index):
        return list(self._jumpable[index])


def legal_turns(variant, board, player):
    """Every turn `player` may play on `board`, as a list of Turns.

    Capturing turns are returned only if at least one exists, and only once
    they can't be extended any further.
    """
    captures = []
    others = []

    if variant.forced_exit:
        trapped = [i for i in variant.home_castle[player] if board[i] and owner(board[i]) == player]
        if trapped:
            for start in trapped:
                _explore(variant, board, player, start, is_knight(board[start]), captures, others)
            return captures or others

    for start, piece in enumerate(board):
        if piece and owner(piece) == player:
            _explore(variant, board, player, start, is_knight(piece), captures, others)
    return captures or others


_START, _CANTER, _JUMP = "start", "canter", "jump"


def _explore(variant, board, player, start, knight, captures, others):
    home = variant.home_castle[player]
    goal = variant.goal_castle[player]
    # a piece in the enemy castle may be unable to leave it except by jumping
    confined = variant.confine_in_enemy_castle and start in goal

    work = list(board)
    work[start] = 0  # the moving piece is lifted off the board while it travels

    def can_land_without_jumping(square):
        return work[square] == 0 and square not in home and (not confined or square in goal)

    def visit(pos, moves, jumped, phase, cantered):
        entered_goal = variant.enemy_castle_ends_turn and len(moves) > 1 and pos in goal

        jumps = []
        if not entered_goal and (phase != _CANTER or knight):
            for landing in variant.jumpable_squares(pos):
                over = (pos + landing) // 2
                if work[landing] == 0 and work[over] != 0 and owner(work[over]) != player:
                    jumps.append((landing, over))

        if len(moves) > 1:
            turn = Turn(tuple(moves), tuple(jumped))
            if phase == _JUMP:
                if not jumps:
                    captures.append(turn)
            elif pos != start:  # cantering round to where it began would be passing
                others.append(turn)

        if entered_goal:
            return

        for landing, over in jumps:
            taken, work[over] = work[over], 0
            visit(landing, moves + [landing], jumped + [over], _JUMP, cantered)
            work[over] = taken

        if phase != _JUMP:
            for landing in variant.jumpable_squares(pos):
                over = (pos + landing) // 2
                if (
                    work[over] != 0
                    and owner(work[over]) == player
                    and over not in cantered
                    and can_land_without_jumping(landing)
                ):
                    visit(landing, moves + [landing], jumped + [None], _CANTER, cantered | {over})

        if phase == _START:
            for step in variant.adjacent_squares(pos):
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


def find_winner(variant, board):
    """(winner, reason) if a side has won on `board` outright, else (None, None).

    This doesn't know about blocked players; see Game for that.
    """
    for side in (WHITE, BLACK):
        in_castle = sum(1 for i in variant.goal_castle[side] if board[i] and owner(board[i]) == side)
        if in_castle >= variant.castle_to_win:
            return side, "castle"

    for side in (WHITE, BLACK):
        if not any(p and owner(p) == side for p in board):
            return other(side), "capture"

    return None, None
