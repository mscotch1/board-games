// Draws the board as SVG. Everything is regenerated from a view model on every
// render, which is plenty fast for 160 squares and keeps this free of state.
//
// Squares are identified by their index (row * cols + col), as in the server.
// Each side sees its own pieces at the bottom, so for black the board is
// rotated half a turn when it is drawn.

const CELL = 100;
const MARGIN = 74; // room for the frame and the file and rank labels around the board
const FRAME = 18; // how far the gold frame reaches past the squares

const FILES = 'abcdefghijklmnopqrstuvwxyz';

/** Where square `index` is drawn, in cells from the top left, for the given side. */
export function displayCell(index, { rows, cols }, side) {
  const row = Math.floor(index / cols);
  const col = index % cols;
  return side === 'black' ? { row: rows - 1 - row, col: cols - 1 - col } : { row, col };
}

/** The name of a square, like "e5": files run a-l, ranks count up from white's edge. */
export function squareName(index, { rows, cols }) {
  const row = Math.floor(index / cols);
  const col = index % cols;
  return `${FILES[col]}${rows - row}`;
}

const owner = (piece) => (piece <= 2 ? 'white' : 'black');
const kind = (piece) => (piece % 2 === 0 ? 'knight' : 'man');

/**
 * The SVG markup for one view of the board.
 *
 * `view` has: rows, cols, mask, board, side, castles, lastTurn, clickable (Set),
 * movable (Set), candidates (Map of square -> { capture }), path, captured,
 * opponentPath, opponentHover.
 */
export function boardMarkup(view) {
  const { rows, cols, mask, board, side, path, captured, opponentPath } = view;
  const geometry = { rows, cols };

  const at = (index) => {
    const { row, col } = displayCell(index, geometry, side);
    return { x: col * CELL, y: row * CELL, cx: col * CELL + CELL / 2, cy: row * CELL + CELL / 2 };
  };

  const castleSquares = new Set([...view.castles.top, ...view.castles.bottom]);
  const frame = [];
  const inner = [];
  const squares = [];
  const highlights = [];
  const markers = [];
  const pieces = [];

  const rect = (className, index, extra = '') => {
    const { x, y } = at(index);
    return `<rect class="${className}" x="${x}" y="${y}" width="${CELL}" height="${CELL}" ${extra}/>`;
  };

  const lastSquares = new Set(view.lastTurn?.moves ?? []);
  const pathSquares = new Set(path);
  const hasPath = path.length >= 2;

  for (let index = 0; index < mask.length; index++) {
    if (!mask[index]) {
      continue;
    }

    const { x, y } = at(index);
    const { row, col } = displayCell(index, geometry, side);
    const shade = castleSquares.has(index) ? 'castle' : (row + col) % 2 === 0 ? 'light' : 'dark';
    const clickable = view.clickable.has(index) ? ' clickable' : '';
    // the frame is every square grown a little, which outlines the whole board
    frame.push(
      `<rect class="frame-outer" x="${x - FRAME}" y="${y - FRAME}" width="${CELL + 2 * FRAME}" height="${CELL + 2 * FRAME}" rx="14" />`,
    );
    inner.push(
      `<rect class="frame-inner" x="${x - FRAME / 2}" y="${y - FRAME / 2}" width="${CELL + FRAME}" height="${CELL + FRAME}" rx="8" />`,
    );
    squares.push(rect(`sq ${shade}${clickable}`, index, `data-index="${index}"`));

    if (castleSquares.has(index)) {
      // each castle flies the colours of the side that starts beside it
      const owner = view.castles.top.includes(index) ? 'black' : 'white';
      squares.push(
        `<use class="castle-icon ${owner}" href="#castle" x="${x}" y="${y}" width="${CELL}" height="${CELL}" />`,
      );
    }
    if (lastSquares.has(index)) {
      highlights.push(rect('hl last', index));
    }
    if (pathSquares.has(index)) {
      highlights.push(rect('hl path', index));
    }
    if (view.movable.has(index)) {
      const inset = 6;
      highlights.push(
        `<rect class="hl movable" x="${x + inset}" y="${y + inset}" width="${CELL - 2 * inset}" height="${CELL - 2 * inset}" rx="10" />`,
      );
    }
    if (index === view.opponentHover) {
      highlights.push(rect('hl opp-hover', index));
    }
  }

  // pieces: while a move is being built the moving piece is drawn where it is heading
  const capturedSquares = new Set(captured);
  const origin = hasPath ? path[0] : null;

  const drawPiece = (index, piece, className = '') => {
    const { x, y } = at(index);
    return `<use class="piece ${owner(piece)} ${className}" href="#piece-${kind(piece)}" x="${x}" y="${y}" width="${CELL}" height="${CELL}" />`;
  };

  board.forEach((piece, index) => {
    if (!piece || index === origin) {
      return;
    }
    if (capturedSquares.has(index)) {
      const { x, y } = at(index);
      pieces.push(drawPiece(index, piece, 'captured'));
      pieces.push(
        `<path class="capture-mark" d="M${x + 24} ${y + 24} L${x + 76} ${y + 76} M${x + 76} ${y + 24} L${x + 24} ${y + 76}" />`,
      );
      return;
    }
    pieces.push(drawPiece(index, piece));
  });

  if (hasPath) {
    pieces.push(drawPiece(path.at(-1), board[origin], 'moving'));
  } else if (path.length === 1) {
    highlights.push(rect('hl path', path[0]));
  }

  for (const [index, { capture }] of view.candidates) {
    const { cx, cy } = at(index);
    markers.push(
      capture
        ? `<circle class="cand capture" cx="${cx}" cy="${cy}" r="34" />`
        : `<circle class="cand" cx="${cx}" cy="${cy}" r="15" />`,
    );
  }

  const route = (squaresOnRoute, className) => {
    if (squaresOnRoute.length < 2) {
      return '';
    }
    const points = squaresOnRoute.map((index) => {
      const { cx, cy } = at(index);
      return `${cx},${cy}`;
    });
    return `<polyline class="route ${className}" points="${points.join(' ')}" />`;
  };

  const lines = [route(path, '')];
  if (opponentPath.length >= 2) {
    lines.push(route(opponentPath, 'theirs'));
    const { cx, cy } = at(opponentPath.at(-1));
    lines.push(`<circle class="route-end" cx="${cx}" cy="${cy}" r="16" />`);
  }

  return [
    frame.join(''),
    inner.join(''),
    squares.join(''),
    highlights.join(''),
    pieces.join(''),
    lines.join(''),
    markers.join(''),
    labels(geometry, side),
  ].join('');
}

function labels({ rows, cols }, side) {
  const out = [];
  for (let col = 0; col < cols; col++) {
    const { col: shown } = displayCell(col, { rows, cols }, side);
    const x = shown * CELL + CELL / 2;
    out.push(`<text x="${x}" y="${rows * CELL + 48}">${FILES[col]}</text>`);
  }
  for (let row = 0; row < rows; row++) {
    const { row: shown } = displayCell(row * cols, { rows, cols }, side);
    const y = shown * CELL + CELL / 2;
    out.push(`<text x="-48" y="${y}">${rows - row}</text>`);
  }
  return out.join('');
}

/**
 * Attaches the board to an <svg> element. `onSquare(index)` is called for clicks
 * and `onHover(index | null)` as the pointer moves between squares.
 */
export function createBoardView(svg, { onSquare, onHover }) {
  let hovered = null;

  const squareOf = (event) => {
    const target = event.target.closest?.('[data-index]');
    return target ? Number(target.dataset.index) : null;
  };

  svg.addEventListener('click', (event) => {
    const index = squareOf(event);
    if (index !== null) {
      onSquare(index);
    }
  });

  svg.addEventListener('pointerover', (event) => {
    const index = squareOf(event);
    if (index !== hovered) {
      hovered = index;
      onHover(index);
    }
  });

  svg.addEventListener('pointerleave', () => {
    if (hovered !== null) {
      hovered = null;
      onHover(null);
    }
  });

  return {
    render(view) {
      const width = view.cols * CELL + 2 * MARGIN;
      const height = view.rows * CELL + 2 * MARGIN;
      svg.setAttribute('viewBox', `${-MARGIN} ${-MARGIN} ${width} ${height}`);
      svg.innerHTML = boardMarkup(view);
    },
  };
}
