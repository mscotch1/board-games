import { connect } from '../shared/connection.js';
import { mountThemePickers } from '../shared/theme.js';
import { boardRatio, createBoardView } from './board-view.js';
import './camelot.css';
import { rematchCode } from './rematch.js';
import { installSprite } from './sprite.js';
import { exactTurn, isFinished, mustCapture, nextSquares, startSquares, capturedSoFar } from './selection.js';

const $ = (id) => document.getElementById(id);

installSprite();
mountThemePickers(document.querySelectorAll('[data-theme-picker]'));

// leaving a game that is still going ends it for the opponent too, so check first
document.querySelectorAll('[data-leaves-game]').forEach((link) => {
  link.addEventListener('click', (event) => {
    if (!session || session.state.winner) {
      return;
    }
    if (confirm('Leave this game? Your opponent will be disconnected.')) {
      // say goodbye properly, so the opponent finds out straight away
      connection.close();
    } else {
      event.preventDefault();
    }
  });
});

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

function start(code, side, variant) {
  $('menu').hidden = true;
  $('waiting').hidden = false;
  $('invite-link').textContent = inviteLink(code);
  $('game-code').textContent = code;

  connection = connect({ code, side, variant });
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
  const form = new FormData(event.target);
  start(newGameCode(), form.get('side'), form.get('variant'));
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
  // the game on the other end decides which game this is, whatever the lobby said
  $('brand-name').textContent = state.variantName;
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

  $('board').parentElement.style.setProperty('--board-ratio', boardRatio(state));

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

  document.title = myTurn ? `Your move | ${state.variantName}` : `${state.variantName} | Monka Games`;
}

function renderPlayers() {
  const { state, side } = session;
  const counts = { white: 0, black: 0 };
  state.board.forEach((piece) => piece && counts[pieceOwner(piece)]++);

  const row = (who, owner) => `
    <div class="player${state.turn === owner && !state.winner ? ' active' : ''}">
      <svg class="shield" viewBox="0 0 100 120" aria-hidden="true"><use href="#shield-${owner}" /></svg>
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
    if (mustCapture(state.legal)) {
      hint = 'You must capture. Pick one of the highlighted pieces.';
    } else if (pieceInOwnCastle()) {
      hint = 'The piece in your castle must leave it. Pick it to move.';
    } else {
      hint = 'Pick one of the highlighted pieces to move.';
    }
  } else if (!complete) {
    hint = 'Keep going: pick the next square.';
  } else if (nextSquares(state.legal, path).size > 0) {
    hint = 'You can end your turn here, or keep going.';
  } else {
    hint = 'Press End turn to confirm your move.';
  }
  $('hint').textContent = hint;
}

/** Whether one of the player's pieces is standing in the castle it started beside. */
function pieceInOwnCastle() {
  const { state, side } = session;
  const home = side === 'white' ? state.castles.bottom : state.castles.top;
  return home.some((square) => state.board[square] && pieceOwner(state.board[square]) === side);
}

// --- result -----------------------------------------------------------------

function showResult() {
  const { state, side, code } = session;
  const won = state.winner === side;

  const bothTowers = state.castleToWin > 1;
  const castle = bothTowers
    ? won
      ? 'Huzzah! Both towers of the enemy castle fly your colours.'
      : 'Your opponent has taken both towers of the castle.'
    : won
      ? 'Huzzah! One of your pieces has reached the enemy castle.'
      : 'An enemy piece has reached your castle.';
  const reasons = {
    castle,
    capture: won ? 'Huzzah! Not a single enemy piece is left standing.' : 'Not a single one of your pieces is left standing.',
    blocked: won ? 'Huzzah! Your opponent is hemmed in with no move to make.' : 'You are hemmed in with no move to make.',
  };

  $('over-title').textContent = won ? 'Victory!' : 'Alas, defeat';
  $('over-text').textContent = reasons[state.winReason] ?? '';

  // the next game swaps colours: whoever clicks first creates it and asks for the other side
  $('play-again').onclick = () => {
    connection.close();
    const next = new URLSearchParams({ gamecode: rematchCode(code), side: otherSide(side), variant: state.variant });
    location.href = `${location.pathname}?${next}`;
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
const wantedVariant = params.get('variant') ?? undefined;
if (params.get('gamecode')) {
  start(params.get('gamecode'), params.get('side') ?? 'random', wantedVariant);
} else if (wantedVariant) {
  // a link from the front page to one of the games
  const radio = document.querySelector(`input[name=variant][value="${wantedVariant}"]`);
  if (radio) {
    radio.checked = true;
  }
}
