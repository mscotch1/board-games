from collections import Counter
from threading import Lock

import rules
from variants import DEFAULT_VARIANT, VARIANTS

# Longer than any real turn; just bounds the work a client can ask for.
MAX_PATH_LENGTH = 64

# Fifty moves by each side with no capture and no piece reaching a castle.
FIFTY_MOVE_PLIES = 100
REPETITIONS_TO_CLAIM = 3

# bump when the saved form changes in a way old saves can't be read
SAVE_VERSION = 1


class IllegalMove(Exception):
    pass


def _turn_json(turn):
    return {"moves": list(turn.moves), "jumped": list(turn.jumped)}


def _history_entry(entry, variant):
    """A saved history entry, checked. Raises ValueError if it isn't a turn on this board."""
    try:
        moves, jumped, captured = entry["moves"], entry["jumped"], entry["captured"]
        valid_square = lambda s: type(s) is int and 0 <= s < variant.size  # noqa: E731
        if (
            entry["player"] not in (rules.WHITE, rules.BLACK)
            or not 2 <= len(moves) <= MAX_PATH_LENGTH
            or not all(valid_square(s) for s in moves)
            or len(jumped) != len(moves) - 1
            or not all(s is None or valid_square(s) for s in jumped)
            or type(entry["piece"]) is not int
            or not 1 <= entry["piece"] <= 4
            or not all(valid_square(s) and type(p) is int and 1 <= p <= 4 for s, p in captured)
        ):
            raise ValueError("a saved move isn't a valid turn")
        return {
            "player": entry["player"],
            "moves": list(moves),
            "jumped": list(jumped),
            "piece": entry["piece"],
            "captured": [[s, p] for s, p in captured],
        }
    except (KeyError, TypeError) as e:
        raise ValueError(f"a saved move is malformed: {e!r}") from e


class Game:
    """Authoritative state for one game: the board, whose turn it is, and how it ended.

    White always moves first. A game ends with a winner (`winner` and `win_reason`)
    or, in variants that allow it, a draw (`draw_reason`).
    """

    def __init__(self, variant=DEFAULT_VARIANT):
        self._lock = Lock()
        self.variant = variant
        self.board = list(variant.initial)
        self.turn = rules.WHITE
        self.winner = None
        self.win_reason = None
        self.draw_reason = None
        self.draw_offer = None  # the side that has offered a draw, if one is pending
        self.last_turn = None  # (side, Turn) of the most recent turn
        self.history = []  # every turn played, oldest first (see _history_entry)
        self.castle_moves = {rules.WHITE: 0, rules.BLACK: 0}  # moves made between the castle squares
        self.plies_without_progress = 0
        self._positions = Counter({self._position(): 1})
        self._legal = rules.legal_turns(variant, self.board, self.turn)

    @property
    def over(self):
        return self.winner is not None or self.draw_reason is not None

    @property
    def legal_turns(self):
        return list(self._legal)

    def _position(self):
        return (tuple(self.board), self.turn)

    def claimable(self):
        """Which draws a player could claim right now."""
        if not self.variant.draws or self.over:
            return {"repetition": False, "fiftyMoves": False}
        return {
            "repetition": self._positions[self._position()] >= REPETITIONS_TO_CLAIM,
            "fiftyMoves": self.plies_without_progress >= FIFTY_MOVE_PLIES,
        }

    def play_turn(self, player, moves):
        """Apply `player`'s turn, a path of square indices. Raises IllegalMove."""
        with self._lock:
            if self.over:
                raise IllegalMove("The game is over")

            if player != self.turn:
                raise IllegalMove("It is not your turn")

            turn = self._find_legal_turn(moves)

            # what the turn moved and took, written down before the board changes: it lets a client
            # show the turn as it was played and wind the board back to any earlier position
            self.history.append(
                {
                    "player": player,
                    **_turn_json(turn),
                    "piece": self.board[turn.moves[0]],
                    "captured": [[square, self.board[square]] for square in turn.jumped if square is not None],
                }
            )

            self.board = rules.apply_turn(self.board, turn)
            self.last_turn = (player, turn)
            self.draw_offer = None

            goal = self.variant.goal_castle[player]
            if turn.moves[0] in goal and turn.moves[-1] in goal:
                self.castle_moves[player] += 1
            if turn.is_capture or turn.moves[-1] in goal:
                self.plies_without_progress = 0
            else:
                self.plies_without_progress += 1

            self.turn = rules.other(player)
            self._positions[self._position()] += 1
            self._decide(player)

    def _decide(self, mover):
        """Work out whether the turn `mover` just played ended the game, and set up the next."""
        variant = self.variant
        self._legal = []

        self.winner, self.win_reason = rules.find_winner(variant, self.board)
        if self.winner:
            return

        mover_pieces = rules.count_pieces(self.board, mover)
        other_pieces = rules.count_pieces(self.board, rules.other(mover))
        if variant.draws and mover_pieces <= 1 and other_pieces <= 1:
            self.draw_reason = "lone-pieces"
            return

        self._legal = rules.legal_turns(variant, self.board, self.turn, self.castle_moves[self.turn])
        if not self._legal:
            if variant.wins_need_two_pieces and mover_pieces < 2:
                self.draw_reason = "stalemate"
            else:
                self.winner, self.win_reason = mover, "blocked"

    def resign(self, player):
        """`player` gives up, so the opponent wins. Raises IllegalMove if the game is over."""
        with self._lock:
            if self.over:
                raise IllegalMove("The game is over")
            self.winner, self.win_reason = rules.other(player), "resignation"
            self.draw_offer = None
            self._legal = []

    # --- draws ----------------------------------------------------------------

    def claim_draw(self, player):
        """`player` claims a draw by repetition or by the fifty-move rule. Raises IllegalMove."""
        with self._lock:
            self._check_draws_possible()
            claimable = self.claimable()
            if claimable["repetition"]:
                self._draw("repetition")
            elif claimable["fiftyMoves"]:
                self._draw("fifty-moves")
            else:
                raise IllegalMove("There is nothing to claim yet")

    def offer_draw(self, player):
        """`player` offers a draw. If the opponent has already offered one, it is agreed."""
        with self._lock:
            self._check_draws_possible()
            if self.draw_offer == rules.other(player):
                self._draw("agreed")
            else:
                self.draw_offer = player

    def respond_to_draw(self, player, accept):
        """`player` accepts or declines the opponent's pending offer."""
        with self._lock:
            self._check_draws_possible()
            if self.draw_offer is None or self.draw_offer == player:
                raise IllegalMove("There is no draw offer to answer")
            if accept:
                self._draw("agreed")
            else:
                self.draw_offer = None

    def _check_draws_possible(self):
        if not self.variant.draws:
            raise IllegalMove(f"{self.variant.name} has no draws")
        if self.over:
            raise IllegalMove("The game is over")

    def _draw(self, reason):
        self.draw_reason = reason
        self.draw_offer = None
        self._legal = []

    # --- saving ---------------------------------------------------------------

    def to_dict(self):
        """Everything needed to carry on this game later, as JSON-ready data."""
        with self._lock:
            last = None
            if self.last_turn is not None:
                side, turn = self.last_turn
                last = {"player": side, **_turn_json(turn)}

            return {
                "version": SAVE_VERSION,
                "variant": self.variant.key,
                "board": list(self.board),
                "turn": self.turn,
                "winner": self.winner,
                "winReason": self.win_reason,
                "drawReason": self.draw_reason,
                "drawOffer": self.draw_offer,
                "lastTurn": last,
                "castleMoves": dict(self.castle_moves),
                "pliesWithoutProgress": self.plies_without_progress,
                "history": [dict(entry) for entry in self.history],
                # board as hex (every square holds 0-4), which keeps repeated positions compact
                "positions": [[bytes(board).hex(), turn, count] for (board, turn), count in self._positions.items()],
            }

    @classmethod
    def from_dict(cls, data):
        """The game saved by `to_dict`. Raises ValueError if the data isn't a valid save."""
        try:
            if data["version"] != SAVE_VERSION:
                raise ValueError(f"unknown save version {data['version']!r}")

            variant = VARIANTS[data["variant"]]
            game = cls(variant)

            board = data["board"]
            if len(board) != variant.size or any(type(p) is not int or not 0 <= p <= 4 for p in board):
                raise ValueError("the saved board doesn't fit the variant")
            if data["turn"] not in (rules.WHITE, rules.BLACK):
                raise ValueError("the saved turn is not a side")

            game.board = list(board)
            game.turn = data["turn"]
            game.winner = data["winner"]
            game.win_reason = data["winReason"]
            game.draw_reason = data["drawReason"]
            game.draw_offer = data["drawOffer"]
            game.castle_moves = {side: int(data["castleMoves"][side]) for side in (rules.WHITE, rules.BLACK)}
            game.plies_without_progress = int(data["pliesWithoutProgress"])

            last = data["lastTurn"]
            if last is not None:
                game.last_turn = (last["player"], rules.Turn(tuple(last["moves"]), tuple(last["jumped"])))

            game.history = [_history_entry(entry, variant) for entry in data.get("history", [])]

            game._positions = Counter(
                {(tuple(bytes.fromhex(hex_board)), turn): count for hex_board, turn, count in data["positions"]}
            )
            game._legal = (
                []
                if game.over
                else rules.legal_turns(variant, game.board, game.turn, game.castle_moves[game.turn])
            )
            return game
        except (KeyError, TypeError, AttributeError, IndexError) as e:
            raise ValueError(f"not a valid saved game: {e!r}") from e

    # --- snapshots ------------------------------------------------------------

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
                "drawsAllowed": variant.draws,
                "rows": variant.rows,
                "cols": variant.cols,
                "mask": list(variant.mask),
                "board": list(self.board),
                "turn": self.turn,
                "winner": self.winner,
                "winReason": self.win_reason,
                "draw": self.draw_reason,
                "drawOffer": self.draw_offer,
                "claimable": self.claimable(),
                "castleMovesLeft": {
                    side: max(variant.castle_moves - used, 0) for side, used in self.castle_moves.items()
                },
                "legal": [_turn_json(t) for t in self._legal],
                "lastTurn": last,
                "moveCount": len(self.history),
                "lastMove": dict(self.history[-1]) if self.history else None,
                "castles": {
                    "top": list(variant.home_castle[rules.BLACK]),
                    "bottom": list(variant.home_castle[rules.WHITE]),
                },
            }

    def history_snapshot(self):
        """Every turn played so far, as JSON-ready data: each is {player, moves, jumped, piece, captured}."""
        with self._lock:
            return [dict(entry) for entry in self.history]

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
