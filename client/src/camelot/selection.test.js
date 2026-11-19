import { describe, expect, it } from 'vitest';
import {
  capturedSoFar,
  exactTurn,
  isFinished,
  mustCapture,
  nextSquares,
  startSquares,
  turnsStartingWith,
} from './selection.js';

const step = (from, to) => ({ moves: [from, to], jumped: [null] });
const chain = { moves: [10, 20, 30], jumped: [15, 25] };
const branch = { moves: [10, 20, 32], jumped: [15, 26] };
const canterThenJump = { moves: [40, 50, 60], jumped: [null, 55] };

describe('start squares', () => {
  it('are the squares pieces can move from', () => {
    expect(startSquares([step(1, 2), step(1, 3), step(7, 8)])).toEqual(new Set([1, 7]));
  });

  it('is empty when nothing can move', () => {
    expect(startSquares([])).toEqual(new Set());
  });
});

describe('next squares', () => {
  const legal = [step(1, 2), step(1, 3), chain, branch];

  it('lists where the selected piece can go', () => {
    expect([...nextSquares(legal, [1]).keys()].sort()).toEqual([2, 3]);
    expect([...nextSquares(legal, [10]).keys()]).toEqual([20]);
  });

  it('follows the path so far', () => {
    expect([...nextSquares(legal, [10, 20]).keys()].sort()).toEqual([30, 32]);
  });

  it('says whether a step captures', () => {
    expect(nextSquares(legal, [1]).get(2)).toEqual({ capture: false });
    expect(nextSquares(legal, [10]).get(20)).toEqual({ capture: true });
    expect(nextSquares([canterThenJump], [40]).get(50)).toEqual({ capture: false });
    expect(nextSquares([canterThenJump], [40, 50]).get(60)).toEqual({ capture: true });
  });

  it('has nothing left once a turn is complete', () => {
    expect(nextSquares(legal, [10, 20, 30]).size).toBe(0);
  });

  it('has nothing before a piece is selected', () => {
    expect(nextSquares(legal, []).size).toBe(0);
  });

  it('has nothing for a path that is not legal', () => {
    expect(nextSquares(legal, [9]).size).toBe(0);
    expect(nextSquares(legal, [1, 5]).size).toBe(0);
  });
});

describe('exact turns', () => {
  const legal = [step(1, 2), chain, { moves: [10, 20], jumped: [15] }];

  it('finds a complete turn', () => {
    expect(exactTurn(legal, [1, 2])).toEqual(step(1, 2));
  });

  it('matches whole turns only', () => {
    expect(exactTurn(legal, [1])).toBeNull();
    expect(exactTurn([chain], [10, 20])).toBeNull();
    expect(exactTurn([chain], [10, 20, 30, 40])).toBeNull();
  });

  it('can be complete and still continue', () => {
    expect(exactTurn(legal, [10, 20])).not.toBeNull();
    expect(isFinished(legal, [10, 20])).toBe(false);
    expect(isFinished(legal, [10, 20, 30])).toBe(true);
    expect(isFinished(legal, [1, 2])).toBe(true);
    expect(isFinished(legal, [1])).toBe(false);
  });
});

describe('captures', () => {
  it('reports what the path has jumped so far', () => {
    expect(capturedSoFar([chain], [10])).toEqual([]);
    expect(capturedSoFar([chain], [10, 20])).toEqual([15]);
    expect(capturedSoFar([chain], [10, 20, 30])).toEqual([15, 25]);
    expect(capturedSoFar([canterThenJump], [40, 50])).toEqual([]);
    expect(capturedSoFar([canterThenJump], [40, 50, 60])).toEqual([55]);
  });

  it('is empty before anything is moved', () => {
    expect(capturedSoFar([chain], [])).toEqual([]);
    expect(capturedSoFar([chain], [10])).toEqual([]);
  });

  it('is empty for an unknown path', () => {
    expect(capturedSoFar([chain], [1, 2])).toEqual([]);
  });

  it('knows when capturing is forced', () => {
    expect(mustCapture([chain, branch])).toBe(true);
    expect(mustCapture([step(1, 2), chain])).toBe(false);
    expect(mustCapture([step(1, 2)])).toBe(false);
    expect(mustCapture([])).toBe(false);
  });
});

it('filters turns by prefix', () => {
  expect(turnsStartingWith([step(1, 2), chain, branch], [10, 20])).toEqual([chain, branch]);
  expect(turnsStartingWith([step(1, 2)], [])).toEqual([step(1, 2)]);
});
