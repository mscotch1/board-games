import { describe, expect, it } from 'vitest';
import { describeMove, ghostsOf, positionAfter, replayFrames, undoMove } from './history.js';

const geometry = { rows: 16, cols: 12 };
const sq = (row, col) => row * 12 + col;

// white's man on f4 steps to f5; later it jumps black's man on f6 to land on f7
const step = { player: 'white', moves: [sq(11, 5), sq(10, 5)], jumped: [null], piece: 1, captured: [] };
const jump = {
  player: 'white',
  moves: [sq(10, 5), sq(8, 5)],
  jumped: [sq(9, 5)],
  piece: 1,
  captured: [[sq(9, 5), 3]],
};

describe('winding the board back', () => {
  const start = Array(192).fill(0);
  start[sq(11, 5)] = 1;
  start[sq(9, 5)] = 3;

  const afterStep = [...start];
  afterStep[sq(11, 5)] = 0;
  afterStep[sq(10, 5)] = 1;

  const afterJump = [...afterStep];
  afterJump[sq(10, 5)] = 0;
  afterJump[sq(9, 5)] = 0;
  afterJump[sq(8, 5)] = 1;

  it('undoes a plain step', () => {
    expect(undoMove(afterStep, step)).toEqual(start);
  });

  it('undoes a jump, putting the captured piece back', () => {
    expect(undoMove(afterJump, jump)).toEqual(afterStep);
  });

  it('does not mutate the board it is given', () => {
    const board = [...afterJump];
    undoMove(board, jump);
    expect(board).toEqual(afterJump);
  });

  it('finds the position after any number of turns', () => {
    const history = [step, jump];
    expect(positionAfter(afterJump, history, 2)).toEqual(afterJump);
    expect(positionAfter(afterJump, history, 1)).toEqual(afterStep);
    expect(positionAfter(afterJump, history, 0)).toEqual(start);
  });

  it('copes with a piece that ends where it began', () => {
    // a knight's charge that jumps round and lands on its own starting square
    const loop = {
      player: 'black',
      moves: [sq(5, 5), sq(7, 5), sq(7, 7), sq(5, 5)],
      jumped: [sq(6, 5), null, sq(6, 6)],
      piece: 4,
      captured: [
        [sq(6, 5), 1],
        [sq(6, 6), 2],
      ],
    };
    const after = Array(192).fill(0);
    after[sq(5, 5)] = 4;
    const before = undoMove(after, loop);
    expect(before[sq(5, 5)]).toBe(4);
    expect(before[sq(6, 5)]).toBe(1);
    expect(before[sq(6, 6)]).toBe(2);
  });
});

describe('writing a turn out', () => {
  it('uses a dash for a step and a cross for a jump', () => {
    expect(describeMove(step, geometry)).toBe('f5–f6');
    expect(describeMove(jump, geometry)).toBe('f6×f8');
  });

  it('writes a charge that mixes a canter and a jump', () => {
    const charge = { ...jump, moves: [sq(10, 5), sq(8, 5), sq(6, 5)], jumped: [null, sq(7, 5)] };
    expect(describeMove(charge, geometry)).toBe('f6–f8×f10');
  });
});

describe('playing a turn back', () => {
  it('has a frame for each square the piece visits', () => {
    const chain = { ...jump, moves: [1, 2, 3, 4], jumped: [10, null, 11], captured: [] };
    expect(replayFrames(chain)).toEqual([
      { path: [1], captured: [] },
      { path: [1, 2], captured: [10] },
      { path: [1, 2, 3], captured: [10] },
      { path: [1, 2, 3, 4], captured: [10, 11] },
    ]);
  });

  it('lists the taken pieces to ghost', () => {
    expect(ghostsOf(jump)).toEqual([{ index: sq(9, 5), piece: 3 }]);
    expect(ghostsOf(step)).toEqual([]);
  });
});
