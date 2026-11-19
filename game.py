from threading import Lock

import rules
from variants import DEFAULT_VARIANT

# Longer than any real turn; just bounds the work a client can ask for.
MAX_PATH_LENGTH = 64


class IllegalMove(Exception):
    pass


def _turn_json(turn):
    return {"moves": list(turn.moves), "jumped": list(turn.jumped)}


class Game:
    """Authoritative state for one game: the board, whose turn it is, and the winner.

    White always moves first.
    """

    def __init__(self, variant=DEFAULT_VARIANT):
        self._lock = Lock()
        self.variant = variant
        self.board = list(variant.initial)
        self.turn = rules.WHITE
        self.winner = None
        self.win_reason = None
        self.last_turn = None  # (side, Turn) of the most recent turn
        self._legal = rules.legal_turns(variant, self.board, self.turn)

    @property
    def legal_turns(self):
        return list(self._legal)

    def play_turn(self, player, moves):
        """Apply `player`'s turn, a path of square indices. Raises IllegalMove."""
        with self._lock:
            if self.winner is not None:
                raise IllegalMove("The game is over")

            if player != self.turn:
                raise IllegalMove("It is not your turn")

            turn = self._find_legal_turn(moves)

            self.board = rules.apply_turn(self.board, turn)
            self.last_turn = (player, turn)

            self.winner, self.win_reason = rules.find_winner(self.variant, self.board)
            self.turn = rules.other(player)
            self._legal = [] if self.winner else rules.legal_turns(self.variant, self.board, self.turn)
            if self.winner is None and not self._legal:
                self.winner, self.win_reason = player, "blocked"

    def snapshot(self):
        """Everything a client needs to draw the game, as JSON-ready data."""
        with self._lock:
            variant = self.variant
            last = None
            if self.last_turn is not None:
                side, turn = self.last_turn
                last = {"player": side, **_turn_json(turn)}

            return {
                "variant": variant.key,
                "variantName": variant.name,
                "castleToWin": variant.castle_to_win,
                "rows": variant.rows,
                "cols": variant.cols,
                "mask": list(variant.mask),
                "board": list(self.board),
                "turn": self.turn,
                "winner": self.winner,
                "winReason": self.win_reason,
                "legal": [_turn_json(t) for t in self._legal],
                "lastTurn": last,
                "castles": {
                    "top": list(variant.home_castle[rules.BLACK]),
                    "bottom": list(variant.home_castle[rules.WHITE]),
                },
            }

    def _find_legal_turn(self, moves):
        if not isinstance(moves, list) or not 2 <= len(moves) <= MAX_PATH_LENGTH:
            raise IllegalMove("A turn must be a path of at least two squares")

        if not all(type(m) is int for m in moves):
            raise IllegalMove("Moves must be squares on the board")

        path = tuple(moves)
        for turn in self._legal:
            if turn.moves == path:
                return turn

        player = self.turn
        if self.variant.forced_exit and any(
            self.board[i] and rules.owner(self.board[i]) == player for i in self.variant.home_castle[player]
        ):
            raise IllegalMove("The piece in your castle must leave it first")
        if any(t.is_capture for t in self._legal):
            raise IllegalMove("You must capture when you can, and finish the jump")
        raise IllegalMove("That move is not allowed")
