// Helpers for building a turn out of the legal turns the server sends.
//
// `legal` is a list of `{ moves, jumped }`: `moves` is the path of squares a
// piece travels and `jumped[i]` is the square captured on the step to
// `moves[i + 1]` (or null for a plain move or canter). The server decides what
// is legal; the client only narrows the list down as the player clicks.

const startsWith = (moves, path) => path.every((square, i) => moves[i] === square);

/** The turns that begin with `path`. */
export function turnsStartingWith(legal, path) {
  return legal.filter((turn) => startsWith(turn.moves, path));
}

/** Squares holding a piece that has a legal turn. */
export function startSquares(legal) {
  return new Set(legal.map((turn) => turn.moves[0]));
}

/**
 * The squares the piece can go to next from `path`, as a Map of
 * square -> { capture }, where `capture` is true if the step jumps a piece.
 */
export function nextSquares(legal, path) {
  const next = new Map();
  if (path.length === 0) {
    return next; // nothing is selected yet; see startSquares
  }
  for (const turn of turnsStartingWith(legal, path)) {
    if (turn.moves.length <= path.length) {
      continue;
    }
    const square = turn.moves[path.length];
    const capture = turn.jumped[path.length - 1] !== null;
    next.set(square, { capture: capture || (next.get(square)?.capture ?? false) });
  }
  return next;
}

/** The legal turn that is exactly `path`, or null if it isn't finished yet. */
export function exactTurn(legal, path) {
  return legal.find((turn) => turn.moves.length === path.length && startsWith(turn.moves, path)) ?? null;
}

/** The squares whose pieces `path` captures so far. */
export function capturedSoFar(legal, path) {
  if (path.length < 2) {
    return [];
  }
  const turn = turnsStartingWith(legal, path)[0];
  if (!turn) {
    return [];
  }
  return turn.jumped.slice(0, path.length - 1).filter((square) => square !== null);
}

/**
 * Whether the player has to jump: some piece is next to an exposed enemy piece, so every legal turn
 * takes a piece. (A knight's charge on its own is optional: it begins with a canter, not a jump.)
 */
export function mustCapture(legal) {
  return legal.some((turn) => turn.jumped[0] !== null) && legal.every((turn) => turn.jumped.some((s) => s !== null));
}

/** Whether `path` is a complete turn that can't be continued. */
export function isFinished(legal, path) {
  return exactTurn(legal, path) !== null && nextSquares(legal, path).size === 0;
}
