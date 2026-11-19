// Draws the board as SVG. Everything is regenerated from a view model on every
// render, which is plenty fast for 160 squares and keeps this free of state.
//
// Squares are identified by their index (row * cols + col), as in the server.
// Each side sees its own pieces at the bottom, so for black the board is
// rotated half a turn when it is drawn.

const CELL = 100;
const MARGIN = 60; // room for the file and rank labels around the board

const FILES = 'abcdefghijklmnopqrstuvwxyz';

const PIECE_DEFS = `
  <symbol id="piece-man" viewBox="0 0 100 100">
    <ellipse class="piece-shade" cx="50" cy="86" rx="27" ry="7" />
    <path class="piece-body" d="M26 84 C26 68 35 60 41 53 H59 C65 60 74 68 74 84 Z" />
    <rect class="piece-body" x="34" y="45" width="32" height="9" rx="4.5" />
    <circle class="piece-body" cx="50" cy="31" r="15" />
    <circle class="piece-shine" cx="45" cy="26" r="4.5" />
  </symbol>
  <symbol id="piece-knight" viewBox="0 0 100 100">
    <ellipse class="piece-shade" cx="50" cy="87" rx="29" ry="7" />
    <path class="piece-body" d="M27 85 C27 70 33 58 43 49 L34 41 L39 24 L50 31 C55 20 63 15 72 18 C68 23 70 29 73 37 C78 50 67 60 66 70 C66 76 68 81 73 85 Z" />
    <path class="piece-rim" d="M52 29 C50 40 47 49 40 58" />
    <circle class="piece-eye" cx="59" cy="33" r="3" />
    <circle class="piece-shine" cx="63" cy="44" r="4" />
  </symbol>
  <symbol id="castle" viewBox="0 0 100 100">
    <path d="M18 80 V38 H28 V28 H38 V38 H44 V28 H56 V38 H62 V28 H72 V38 H82 V80 Z M44 80 V62 A6 6 0 0 1 56 62 V80 Z" fill-rule="evenodd" />
  </symbol>
`;

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
    squares.push(rect(`sq ${shade}${clickable}`, index, `data-index="${index}"`));

    if (castleSquares.has(index)) {
      squares.push(`<use class="castle-icon" href="#castle" x="${x}" y="${y}" width="${CELL}" height="${CELL}" />`);
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
    `<defs>${PIECE_DEFS}</defs>`,
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
    out.push(`<text x="${x}" y="${rows * CELL + 34}">${FILES[col]}</text>`);
  }
  for (let row = 0; row < rows; row++) {
    const { row: shown } = displayCell(row * cols, { rows, cols }, side);
    const y = shown * CELL + CELL / 2;
    out.push(`<text x="-34" y="${y}">${rows - row}</text>`);
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
