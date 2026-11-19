import { describe, expect, it } from 'vitest';
import { boardMarkup, displayCell, squareName } from './board-view.js';

const geometry = { rows: 16, cols: 12 };

describe('square geometry', () => {
  it('draws white as the board is numbered', () => {
    expect(displayCell(0, geometry, 'white')).toEqual({ row: 0, col: 0 });
    expect(displayCell(5, geometry, 'white')).toEqual({ row: 0, col: 5 });
  });

  it('turns the board half a turn for black', () => {
    expect(displayCell(0, geometry, 'black')).toEqual({ row: 15, col: 11 });
    expect(displayCell(5, geometry, 'black')).toEqual({ row: 15, col: 6 });
    expect(displayCell(191, geometry, 'black')).toEqual({ row: 0, col: 0 });
  });

  it('keeps a square on the board when turned twice', () => {
    for (let index = 0; index < 192; index++) {
      const once = displayCell(index, geometry, 'black');
      const again = displayCell(once.row * 12 + once.col, geometry, 'black');
      expect(again).toEqual(displayCell(index, geometry, 'white'));
    }
  });

  it('names squares by file and rank from white\'s edge', () => {
    expect(squareName(185, geometry)).toBe('f1');
    expect(squareName(5, geometry)).toBe('f16');
    expect(squareName(36, geometry)).toBe('a13');
  });
});

describe('board markup', () => {
  const mask = new Array(192).fill(0);
  [5, 6, 17, 18, 100, 101, 185, 186].forEach((i) => (mask[i] = 1));

  const view = (overrides = {}) => ({
    ...geometry,
    mask,
    board: new Array(192).fill(0),
    side: 'white',
    castles: { top: [5, 6], bottom: [185, 186] },
    lastTurn: null,
    clickable: new Set(),
    movable: new Set(),
    candidates: new Map(),
    path: [],
    captured: [],
    opponentPath: [],
    opponentHover: null,
    ...overrides,
  });

  const count = (markup, text) => markup.split(text).length - 1;

  it('draws a square for every square on the board and none outside it', () => {
    expect(count(boardMarkup(view()), 'data-index=')).toBe(8);
  });

  it('marks the castles', () => {
    expect(count(boardMarkup(view()), 'sq castle')).toBe(4);
  });

  it('draws pieces in their owner\'s colour', () => {
    const board = new Array(192).fill(0);
    board[100] = 1;
    board[101] = 4;
    const markup = boardMarkup(view({ board }));
    expect(markup).toContain('piece white');
    expect(markup).toContain('href="#piece-man"');
    expect(markup).toContain('piece black');
    expect(markup).toContain('href="#piece-knight"');
  });

  it('only marks clickable squares as clickable', () => {
    const markup = boardMarkup(view({ clickable: new Set([100]) }));
    expect(count(markup, 'clickable')).toBe(1);
  });

  it('moves the piece to the end of the path being built', () => {
    const board = new Array(192).fill(0);
    board[100] = 1;
    const markup = boardMarkup(view({ board, path: [100, 18] }));
    expect(count(markup, 'piece white moving')).toBe(1);
    expect(count(markup, 'class="piece white "')).toBe(0); // nothing is left on the start square
    expect(markup).toContain('<polyline class="route ');
  });

  it('shows captured pieces as taken', () => {
    const board = new Array(192).fill(0);
    board[100] = 1;
    board[101] = 3;
    const markup = boardMarkup(view({ board, path: [100, 18], captured: [101] }));
    expect(markup).toContain('piece black captured');
    expect(markup).toContain('capture-mark');
  });

  it('draws the opponent\'s preview and hover', () => {
    const markup = boardMarkup(view({ opponentPath: [100, 18], opponentHover: 101 }));
    expect(markup).toContain('route theirs');
    expect(markup).toContain('opp-hover');
  });
});
