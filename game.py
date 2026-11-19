from threading import Lock

import rules

# Longer than any real turn; just bounds the work a client can ask for.
MAX_PATH_LENGTH = 64


class IllegalMove(Exception):
    pass


class Game:
    """Authoritative state for one game: the board, whose turn it is, and the winner."""

    def __init__(self):
        self._lock = Lock()
        self.board = list(rules.INITIAL_BOARD)
        self.turn = "1"
        self.winner = None

    def play_turn(self, player, moves):
        """Apply `player`'s turn, a path of square indices. Raises IllegalMove."""
        with self._lock:
            if self.winner is not None:
                raise IllegalMove("The game is over")

            if player != self.turn:
                raise IllegalMove("It is not your turn")

            self._check_path(player, moves)

            self.board = rules.make_moves(self.board, moves)
            self.winner = rules.find_winner(self.board)
            self.turn = "2" if self.turn == "1" else "1"

    def _check_path(self, player, moves):
        if not isinstance(moves, list) or not 2 <= len(moves) <= MAX_PATH_LENGTH:
            raise IllegalMove("A turn must be a path of at least two squares")

        if not all(type(m) is int and 0 <= m < len(self.board) for m in moves):
            raise IllegalMove("Moves must be squares on the board")

        if not rules.is_players_piece(self.board, player, moves[0]):
            raise IllegalMove("You must move one of your own pieces")

        if not rules.is_valid_move(self.board, player, moves):
            raise IllegalMove("That move is not allowed")
