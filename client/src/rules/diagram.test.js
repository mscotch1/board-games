import { describe, expect, it } from 'vitest';
import { diagramMarkup } from './diagram.js';

const count = (markup, text) => markup.split(text).length - 1;

describe('a diagram', () => {
  it('draws every square of its grid, in alternating shades', () => {
    const markup = diagramMarkup({ cols: 5, rows: 3 });
    expect(count(markup, 'class="sq ')).toBe(15);
    expect(count(markup, 'sq light')).toBe(8);
    expect(count(markup, 'sq dark')).toBe(7);
    expect(markup).toContain('viewBox="0 0 500 300"');
  });

  it('draws pieces in their owners\' colours and kinds', () => {
    const markup = diagramMarkup({
      cols: 3,
      rows: 1,
      pieces: [
        { col: 0, row: 0, piece: 1 },
        { col: 1, row: 0, piece: 2 },
        { col: 2, row: 0, piece: 4 },
      ],
    });
    expect(count(markup, 'piece white')).toBe(2);
    expect(count(markup, 'piece black')).toBe(1);
    expect(count(markup, 'href="#piece-man"')).toBe(1);
    expect(count(markup, 'href="#piece-knight"')).toBe(2);
  });

  it('places pieces on the right squares', () => {
    const markup = diagramMarkup({ cols: 3, rows: 3, pieces: [{ col: 2, row: 1, piece: 3 }] });
    expect(markup).toContain('x="200" y="100"');
  });

  it('marks pieces taken by the route', () => {
    const markup = diagramMarkup({
      cols: 3,
      rows: 1,
      pieces: [
        { col: 0, row: 0, piece: 1 },
        { col: 1, row: 0, piece: 3 },
      ],
      captured: [[1, 0]],
      route: [[0, 0], [2, 0]],
    });
    expect(count(markup, 'piece black captured')).toBe(1);
    expect(count(markup, 'capture-mark')).toBe(1);
    expect(count(markup, 'piece white captured')).toBe(0);
  });

  it('draws the route as an arrow through the centres of its squares', () => {
    const markup = diagramMarkup({ cols: 5, rows: 1, route: [[0, 0], [2, 0], [4, 0]] }, 'x');
    expect(markup).toContain('points="50,50 250,50 450,50"');
    expect(markup).toContain('marker-end="url(#arrow-x)"');
    expect(markup).toContain('id="arrow-x"');
    expect(count(markup, 'route-stop')).toBe(1); // the square it lands on in between
  });

  it('has no route to draw for a single square', () => {
    expect(diagramMarkup({ cols: 3, rows: 1, route: [[0, 0]] })).not.toContain('<polyline');
  });

  it('draws dots for the squares a piece could move to', () => {
    const markup = diagramMarkup({ cols: 3, rows: 3, dots: [[0, 0], [1, 0], [2, 2]] });
    expect(count(markup, 'class="cand"')).toBe(3);
  });

  it('describes itself for screen readers, safely', () => {
    const markup = diagramMarkup({ cols: 1, rows: 1, label: 'A "quoted" move' });
    expect(markup).toContain('aria-label="A &quot;quoted&quot; move"');
  });

  it('gives each diagram its own arrowhead', () => {
    const a = diagramMarkup({ cols: 3, rows: 1, route: [[0, 0], [2, 0]] }, '1');
    const b = diagramMarkup({ cols: 3, rows: 1, route: [[0, 0], [2, 0]] }, '2');
    expect(a).toContain('arrow-1');
    expect(b).toContain('arrow-2');
    expect(a).not.toContain('arrow-2');
  });
});
