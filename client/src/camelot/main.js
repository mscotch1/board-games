import { connect } from '../shared/connection.js';
import { createBoardView } from './board-view.js';
import './camelot.css';
import { rematchCode } from './rematch.js';
import { exactTurn, isFinished, mustCapture, nextSquares, startSquares, capturedSoFar } from './selection.js';

const $ = (id) => document.getElementById(id);

const SIDE_NAMES = { white: 'White', black: 'Black' };
const otherSide = (side) => (side === 'white' ? 'black' : 'white');

const pieceOwner = (piece) => (piece <= 2 ? 'white' : 'black');

let connection = null;
let session = null; // set once an opponent has joined

const view = createBoardView($('board'), {
  onSquare: handleSquare,
  onHover: (index) => connection?.send('hover', { index }),
});

// --- lobby ------------------------------------------------------------------

function newGameCode() {
  return Array.from(crypto.getRandomValues(new Uint8Array(4)), (b) => b.toString(16).padStart(2, '0')).join('');
}

function inviteLink(code) {
  return `${location.origin}${location.pathname}?gamecode=${encodeURIComponent(code)}`;
}

function showProblem(text) {
  $('problem-text').textContent = text;
  if (!$('problem').open) {
    $('problem').showModal();
  }
}

function start(code, side) {
  $('menu').hidden = true;
  $('waiting').hidden = false;
  $('invite-link').textContent = inviteLink(code);
  $('game-code').textContent = code;

  connection = connect({ code, side });
  connection.onRefused((reason) => showProblem(`Could not join the game: ${reason}.`));
  connection.onLost(() => {
    if (!session?.state.winner) {
      showProblem('The connection to the server was lost.');
    }
  });

  connection.on('game-ready', ({ side: yourSide, state }) => begin(code, yourSide, state));
  connection.on('game-state', ({ state }) => applyState(state));
  connection.on('move-rejected', ({ error }) => {
    if (session) {
      session.pending = false;
      setPath([]);
      $('notice').textContent = error;
    }
  });
  connection.on('opponent-preview', ({ moves }) => {
    if (session) {
      session.opponentPath = moves;
      render();
    }
  });
  connection.on('opponent-hover', ({ index }) => {
    if (session) {
      session.opponentHover = index;
      render();
    }
  });
  connection.on('chat', ({ text }) => addChat(text, false));
  connection.on('opponent-disconnected', () => {
    if (!session?.state.winner) {
      showProblem('Your opponent disconnected.');
    }
  });
}

$('new-game').addEventListener('submit', (event) => {
  event.preventDefault();
  start(newGameCode(), new FormData(event.target).get('side'));
});

$('join-game').addEventListener('submit', (event) => {
  event.preventDefault();
  const code = new FormData(event.target).get('gamecode').trim();
  if (code) {
    start(code, 'random');
  }
});

$('cancel').addEventListener('click', () => {
  location.href = location.pathname;
});

$('copy').addEventListener('click', async () => {
  const button = $('copy');
  try {
    await navigator.clipboard.writeText($('invite-link').textContent);
    button.textContent = 'Copied!';
  } catch {
    // clipboard access can be refused; select the text so it can be copied by hand
    getSelection().selectAllChildren($('invite-link'));
    button.textContent = 'Press Ctrl+C';
  }
  setTimeout(() => (button.textContent = 'Copy'), 1800);
});

for (const dialog of document.querySelectorAll('dialog')) {
  // these only close by leaving the page
  dialog.addEventListener('cancel', (event) => event.preventDefault());
}

// --- game -------------------------------------------------------------------

function begin(code, side, state) {
  session = { code, side, state, path: [], pending: false, opponentPath: [], opponentHover: null };
  $('lobby').hidden = true;
  $('game').hidden = false;
  render();
}

function applyState(state) {
  session.state = state;
  session.path = [];
  session.pending = false;
  session.opponentPath = [];
  $('notice').textContent = '';
  render();

  if (state.winner) {
    showResult();
  }
}

function setPath(path) {
  session.path = path;
  connection.send('preview', { moves: path });
  render();
}

function isMyTurn() {
  const { state, side, pending } = session;
  return state.turn === side && !state.winner && !pending;
}

function handleSquare(index) {
  if (!isMyTurn()) {
    return;
  }

  const { state, path } = session;
  $('notice').textContent = '';

  if (path.length === 0) {
    if (startSquares(state.legal).has(index)) {
      setPath([index]);
    }
  } else if (path.length === 1 && index === path[0]) {
    setPath([]);
  } else if (nextSquares(state.legal, path).has(index)) {
    setPath([...path, index]);
  } else if (path.length === 1 && startSquares(state.legal).has(index)) {
    // changed their mind about which piece to move
    setPath([index]);
  }
}

$('undo').addEventListener('click', () => {
  if (session && isMyTurn() && session.path.length > 0) {
    setPath(session.path.length === 1 ? [] : session.path.slice(0, -1));
  }
});

$('end-turn').addEventListener('click', () => {
  if (!session || !isMyTurn() || !exactTurn(session.state.legal, session.path)) {
    return;
  }
  session.pending = true;
  connection.send('end-turn', { moves: session.path });
  render();
});

function render() {
  const { state, side, path } = session;
  const myTurn = isMyTurn();

  const clickable = new Set();
  let movable = new Set();
  let candidates = new Map();

  if (myTurn) {
    candidates = nextSquares(state.legal, path);
    candidates.forEach((_, square) => clickable.add(square));
    if (path.length <= 1) {
      startSquares(state.legal).forEach((square) => clickable.add(square));
    }
    if (path.length === 0) {
      movable = startSquares(state.legal);
    }
    if (path.length === 1) {
      clickable.add(path[0]);
    }
  }

  view.render({
    rows: state.rows,
    cols: state.cols,
    mask: state.mask,
    board: state.board,
    castles: state.castles,
    side,
    lastTurn: state.lastTurn,
    clickable,
    movable,
    candidates,
    path,
    captured: capturedSoFar(state.legal, path),
    opponentPath: session.opponentPath,
    opponentHover: session.opponentHover,
  });

  renderStatus(myTurn);
  renderPlayers();
  renderControls(myTurn);
}

function renderStatus(myTurn) {
  const { state, side } = session;
  const status = $('status');

  if (state.winner) {
    status.textContent = state.winner === side ? 'You won' : 'You lost';
    status.className = 'status';
  } else if (state.turn === side) {
    status.textContent = `Your move (${SIDE_NAMES[side]})`;
    status.className = 'status yours';
  } else {
    status.textContent = `Opponent's move (${SIDE_NAMES[state.turn]})`;
    status.className = 'status theirs';
  }

  document.title = myTurn ? 'Your move | Camelot' : 'Camelot | Monka Games';
}

function renderPlayers() {
  const { state, side } = session;
  const counts = { white: 0, black: 0 };
  state.board.forEach((piece) => piece && counts[pieceOwner(piece)]++);

  const row = (who, owner) => `
    <div class="player${state.turn === owner && !state.winner ? ' active' : ''}">
      <span class="swatch ${owner}"></span>
      <span class="who"><strong>${who}</strong><small>${SIDE_NAMES[owner]}</small></span>
      <span class="count" title="Pieces left">${counts[owner]}</span>
    </div>`;

  $('players').innerHTML = row('You', side) + row('Opponent', otherSide(side));
}

function renderControls(myTurn) {
  const { state, path } = session;
  const complete = myTurn && exactTurn(state.legal, path) !== null;

  $('undo').disabled = !myTurn || path.length === 0;
  $('end-turn').disabled = !complete;
  $('end-turn').classList.toggle('ready', complete && isFinished(state.legal, path));

  let hint;
  if (state.winner) {
    hint = 'The game is over.';
  } else if (!myTurn) {
    hint = session.pending ? 'Sending your move…' : 'Waiting for your opponent to move.';
  } else if (path.length === 0) {
    hint = mustCapture(state.legal)
      ? 'You must capture. Pick one of the highlighted pieces.'
      : 'Pick one of the highlighted pieces to move.';
  } else if (!complete) {
    hint = 'Keep going: pick the next square.';
  } else if (nextSquares(state.legal, path).size > 0) {
    hint = 'You can end your turn here, or keep going.';
  } else {
    hint = 'Press End turn to confirm your move.';
  }
  $('hint').textContent = hint;
}

// --- result -----------------------------------------------------------------

function showResult() {
  const { state, side, code } = session;
  const won = state.winner === side;

  const reasons = {
    castle: won ? 'You occupied both squares of the enemy castle.' : 'Your opponent occupied both squares of the castle.',
    capture: won ? 'You captured every enemy piece.' : 'Your opponent captured every one of your pieces.',
    blocked: won ? 'Your opponent has no legal move.' : 'You have no legal move.',
  };

  $('over-title').textContent = won ? 'Victory!' : 'Defeat';
  $('over-text').textContent = reasons[state.winReason] ?? '';

  // the next game swaps colours: whoever clicks first creates it and asks for the other side
  $('play-again').onclick = () => {
    connection.close();
    location.href = `${location.pathname}?gamecode=${encodeURIComponent(rematchCode(code))}&side=${otherSide(side)}`;
  };

  $('over').showModal();
}

// --- chat -------------------------------------------------------------------

function addChat(text, mine) {
  const item = document.createElement('li');
  item.className = mine ? 'mine' : '';
  item.textContent = text;
  const log = $('chat-log');
  log.append(item);
  log.scrollTop = log.scrollHeight;
}

$('chat-form').addEventListener('submit', (event) => {
  event.preventDefault();
  const text = new FormData(event.target).get('text').trim();
  if (text && connection) {
    connection.send('chat', { text });
    addChat(text, true);
    event.target.reset();
  }
});

// --- go ---------------------------------------------------------------------

const params = new URLSearchParams(location.search);
if (params.get('gamecode')) {
  start(params.get('gamecode'), params.get('side') ?? 'random');
}
