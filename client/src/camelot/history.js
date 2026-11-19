// The game's history, as the server sends it: one entry per turn played, oldest first.
//
//   { player, moves, jumped, piece, captured }
//
// `moves` is the path of squares the piece took, `jumped[i]` the square taken on the step to
// `moves[i + 1]` (or null for a plain step or a canter), `piece` the piece that moved and
// `captured` the [square, piece] pairs it took. That is enough to wind the board back from
// where it is now to any earlier position.

import { squareName } from './board-view.js';

/** The board as it was before `entry` was played. */
export function undoMove(board, entry) {
  const before = [...board];
  const start = entry.moves[0];
  const end = entry.moves.at(-1);
  if (end !== start) {
    before[end] = 0;
  }
  before[start] = entry.piece;
  for (const [square, piece] of entry.captured) {
    before[square] = piece;
  }
  return before;
}

/** The board after the first `count` turns, given the board after all of `history`. */
export function positionAfter(finalBoard, history, count) {
  let board = finalBoard;
  for (let i = history.length - 1; i >= count; i--) {
    board = undoMove(board, history[i]);
  }
  return board;
}

/** A turn written out: "e6–e8" for steps and canters, "d6×f8×h10" for jumps. */
export function describeMove(entry, geometry) {
  const names = entry.moves.map((square) => squareName(square, geometry));
  return entry.jumped.reduce((text, jumped, i) => `${text}${jumped === null ? '–' : '×'}${names[i + 1]}`, names[0]);
}

/**
 * The frames of a turn being played back, for a board showing the position before it: one per
 * square the piece visits, with the path so far and the squares of the pieces it has taken.
 */
export function replayFrames(entry) {
  return entry.moves.map((_, i) => ({
    path: entry.moves.slice(0, i + 1),
    captured: entry.jumped.slice(0, i).filter((square) => square !== null),
  }));
}

/** The captured pieces of a turn, for drawing them faded where they stood. */
export function ghostsOf(entry) {
  return entry.captured.map(([index, piece]) => ({ index, piece }));
}
