// Small board diagrams for the rules page, drawn with the same pieces and
// styles as the game. A diagram is a few squares, some pieces and an optional
// route:
//
//   cols, rows   the size of the grid
//   pieces       [{ col, row, piece }], where piece is 1 white man, 2 white knight,
//                3 black man, 4 black knight (as on the real board)
//   captured     [[col, row], ...] pieces shown as taken by the route
//   route        [[col, row], ...] the squares a piece visits, drawn as an arrow
//   dots         [[col, row], ...] squares a piece could go to, drawn as dots

const CELL = 100;
const OWNER = (piece) => (piece <= 2 ? 'white' : 'black');
const KIND = (piece) => (piece % 2 === 0 ? 'knight' : 'man');

const centre = (col, row) => [col * CELL + CELL / 2, row * CELL + CELL / 2];

export function diagramMarkup({ cols, rows, pieces = [], captured = [], route = [], dots = [], label = '' }, id = 'd') {
  const taken = new Set(captured.map(([col, row]) => `${col},${row}`));
  const parts = [];

  for (let row = 0; row < rows; row++) {
    for (let col = 0; col < cols; col++) {
      const shade = (row + col) % 2 === 0 ? 'light' : 'dark';
      parts.push(`<rect class="sq ${shade}" x="${col * CELL}" y="${row * CELL}" width="${CELL}" height="${CELL}" />`);
    }
  }

  for (const [col, row] of dots) {
    const [cx, cy] = centre(col, row);
    parts.push(`<circle class="cand" cx="${cx}" cy="${cy}" r="15" />`);
  }

  for (const { col, row, piece } of pieces) {
    const x = col * CELL;
    const y = row * CELL;
    const isTaken = taken.has(`${col},${row}`);
    parts.push(
      `<use class="piece ${OWNER(piece)}${isTaken ? ' captured' : ''}" href="#piece-${KIND(piece)}" x="${x}" y="${y}" width="${CELL}" height="${CELL}" />`,
    );
    if (isTaken) {
      parts.push(
        `<path class="capture-mark" d="M${x + 24} ${y + 24} L${x + 76} ${y + 76} M${x + 76} ${y + 24} L${x + 24} ${y + 76}" />`,
      );
    }
  }

  if (route.length >= 2) {
    const points = route.map(([col, row]) => centre(col, row).join(',')).join(' ');
    parts.push(`<polyline class="route" points="${points}" marker-end="url(#arrow-${id})" />`);
    // landing squares along the way get a dot; the last one has the arrowhead
    for (const [col, row] of route.slice(1, -1)) {
      const [cx, cy] = centre(col, row);
      parts.push(`<circle class="route-stop" cx="${cx}" cy="${cy}" r="13" />`);
    }
  }

  const defs = `<defs><marker id="arrow-${id}" viewBox="0 0 10 10" refX="6" refY="5" markerWidth="4" markerHeight="4" orient="auto"><path class="route-head" d="M0 0 L10 5 L0 10 Z" /></marker></defs>`;
  const width = cols * CELL;
  const height = rows * CELL;

  return `<svg viewBox="0 0 ${width} ${height}" role="img" aria-label="${label.replaceAll('"', '&quot;')}">${defs}${parts.join('')}</svg>`;
}

/** Fills every `[data-diagram]` element in `root` with the diagram its JSON describes. */
export function renderDiagrams(root = document) {
  root.querySelectorAll('[data-diagram]').forEach((element, index) => {
    const spec = JSON.parse(element.dataset.diagram);
    element.innerHTML = diagramMarkup(spec, String(index));
  });
}
