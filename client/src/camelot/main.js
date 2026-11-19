import { connect } from '../shared/connection.js';
import { forgetGame, getGame, newToken, resumableGames, saveGame } from '../shared/saved-games.js';
import { mountFooters } from '../shared/footer.js';
import { mountThemePickers } from '../shared/theme.js';
import { boardRatio, createBoardView } from './board-view.js';
import './camelot.css';
import { describeMove, ghostsOf, positionAfter, replayFrames, undoMove } from './history.js';
import { rematchCode } from './rematch.js';
import { installSprite } from './sprite.js';
import { exactTurn, isFinished, mustCapture, nextSquares, startSquares, capturedSoFar } from './selection.js';

const $ = (id) => document.getElementById(id);

installSprite();
mountThemePickers(document.querySelectorAll('[data-theme-picker]'));
mountFooters();

// Leaving a game doesn't end it: it can be resumed from the menu. Closing the socket
// properly, rather than just navigating away, tells the opponent straight away.
document.querySelectorAll('[data-leaves-game]').forEach((link) => {
  link.addEventListener('click', () => connection?.close());
});

const SIDE_NAMES = { white: 'White', black: 'Black' };
const VARIANT_NAMES = { camelot: 'Camelot', cam: 'Cam' };
const otherSide = (side) => (side === 'white' ? 'black' : 'white');

const pieceOwner = (piece) => (piece <= 2 ? 'white' : 'black');

/** Whether a game has been won or drawn. */
const isOver = (state) => Boolean(state.winner || state.draw);

let connection = null;
let currentCode = null;
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

/** Keep the game's code in the address bar, so reloading or bookmarking the page returns to it. */
function keepInAddressBar(code) {
  history.replaceState(null, '', `${location.pathname}?${new URLSearchParams({ gamecode: code })}`);
}

const COMPUTER_LEVELS = ['easy', 'medium', 'hard'];
const levelName = (level) => level.charAt(0).toUpperCase() + level.slice(1);

function start(code, side, variant, computer) {
  currentCode = code;
  keepInAddressBar(code);

  // Remember who we are before anything is sent: a reload before the server has answered
  // must come back as the same player. The entry stays pending until the server confirms it.
  if (!getGame(code)) {
    saveGame(code, { token: newToken(), side, variant, computer: computer ?? null, pending: true });
  }
  const { token } = getGame(code);

  // The invite card is only for a game that is waiting for a friend, and the server says when that is. Until it
  // answers (which is at once, for a computer game or one being resumed) there is just a quiet message, so the
  // card with the link doesn't flash up and vanish.
  $('menu').hidden = true;
  $('waiting').hidden = true;
  $('connecting').hidden = false;
  $('invite-link').textContent = inviteLink(code);
  $('game-code').textContent = code;

  // The token is how the server knows who we are, including after a reload or a restart.
  // `resume` says we have been in this game before, so a game that has gone is an error
  // and not a new game; it is only set once the server has confirmed the game to us.
  // (a computer opponent is only asked for when the game is being made, which is while it is pending)
  connection = connect(() => {
    const saved = getGame(code);
    const auth = { code, token, resume: Boolean(saved) && !saved.pending, side, variant };
    if (saved?.pending && saved.computer) {
      auth.computer = saved.computer;
    }
    return auth;
  });

  connection.onRefused((reason, reasonCode) => {
    if (reasonCode === 'not-found' || getGame(code)?.pending) {
      forgetGame(code); // nothing to come back to
    }
    $('connecting').hidden = true;
    showProblem(reasonCode === 'not-found' ? reason : `Could not join the game: ${reason}.`);
  });
  connection.onStatus((connected) => {
    $('connection-banner').hidden = connected;
  });

  connection.on('waiting', () => {
    saveGame(code, { token, variant, pending: false });
    $('connecting').hidden = true;
    $('waiting').hidden = false;
  });
  connection.on('game-ready', ({ side: yourSide, state, chat, opponentConnected, computer: level, history }) => {
    saveGame(code, {
      token,
      side: yourSide,
      variant: state.variant,
      computer: level ?? null,
      over: isOver(state),
      pending: false,
    });
    begin(code, yourSide, state, chat, opponentConnected, level ?? null, history ?? []);
    if (isOver(state)) {
      showResult(); // coming back to a finished game shows how it ended
    }
  });
  connection.on('game-state', ({ state }) => applyState(state));
  connection.on('opponent-status', ({ connected }) => {
    if (session) {
      session.opponentConnected = connected;
      renderPlayers();
    }
  });
  connection.on('game-cancelled', () => {
    forgetGame(code);
    location.href = location.pathname;
  });
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
  connection.on('action-rejected', ({ error }) => {
    $('notice').textContent = error;
  });
  connection.on('draw-rejected', ({ error }) => {
    $('notice').textContent = error;
  });
  connection.on('draw-declined', () => {
    $('notice').textContent = 'Your opponent declined the draw.';
  });
  connection.on('chat', ({ text }) => addChat(text, false));
}

$('new-game').addEventListener('submit', (event) => {
  event.preventDefault();
  const form = new FormData(event.target);
  const opponent = form.get('opponent');
  start(newGameCode(), form.get('side'), form.get('variant'), COMPUTER_LEVELS.includes(opponent) ? opponent : undefined);
});

$('join-game').addEventListener('submit', (event) => {
  event.preventDefault();
  const code = new FormData(event.target).get('gamecode').trim();
  if (code) {
    start(code, 'random');
  }
});

$('cancel').addEventListener('click', () => {
  connection?.send('cancel-game');
  forgetGame(currentCode);
  // give the message a moment to leave before the page goes
  setTimeout(() => (location.href = location.pathname), 150);
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

function begin(code, side, state, chat = [], opponentConnected = true, computer = null, history = []) {
  session = {
    code,
    side,
    state,
    computer,
    path: [],
    pending: false,
    opponentPath: [],
    opponentHover: null,
    opponentConnected,
    history, // the turns played, oldest first (see history.js)
    review: null, // the number of turns whose position is being shown, or null for the live game
    replay: null, // a turn being played back on the board
  };
  $('notice').textContent = '';
  $('chat-log').replaceChildren();
  chat.forEach((message) => addChat(message.text, message.side === side));
  // the computer doesn't chat, so there is no chat box; the move list gets the room instead
  $('chat-panel').hidden = Boolean(computer);
  document.querySelector('.side').classList.toggle('no-chat', Boolean(computer));
  // the game on the other end decides which game this is, whatever the lobby said
  $('brand-name').textContent = state.variantName;
  $('rules-link').href = `rules/#${state.variant}`;
  $('lobby').hidden = true;
  $('game').hidden = false;
  render();
}

function applyState(state) {
  stopReplay();
  session.review = null;
  const turnsBefore = session.state.moveCount;
  session.state = state;
  session.path = [];
  session.pending = false;
  session.opponentPath = [];
  $('notice').textContent = '';

  // keep our copy of the history in step with the server's
  const { history } = session;
  if (state.lastMove && state.moveCount === history.length + 1) {
    history.push(state.lastMove);
  } else if (state.moveCount !== history.length) {
    session.history = state.lastMove ? [state.lastMove] : []; // missed some turns: carry on from this one
  }
  render();

  // the opponent's turn is played back on the board, so a quick move or a long chain of hops can be followed
  const latest = session.history.at(-1);
  if (latest && latest.player !== session.side && state.moveCount > turnsBefore && autoReplayOn()) {
    startReplay(latest, undoMove(state.board, latest));
  }

  if (isOver(state)) {
    saveGame(session.code, { over: true });
    // let a final move finish playing back before the result covers the board
    const wait = session.replay ? (session.replay.frames.length - 1) * STEP_MS + HOLD_MS + 150 : 0;
    setTimeout(showResult, wait);
  }
}

function setPath(path) {
  session.path = path;
  connection.send('preview', { moves: path });
  render();
}

function isMyTurn() {
  const { state, side, pending } = session;
  return state.turn === side && !isOver(state) && !pending;
}

function handleSquare(index) {
  if (session.review !== null) {
    stopReview(); // clicking the board goes back to the game
    return;
  }
  stopReplay(); // and skips a replay that is still playing
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

$('resign').addEventListener('click', () => {
  if (confirm('Resign this game? Your opponent will win.')) {
    connection.send('resign');
  }
});
$('offer-draw').addEventListener('click', () => connection.send('offer-draw'));
$('claim-draw').addEventListener('click', () => connection.send('claim-draw'));
$('accept-draw').addEventListener('click', () => connection.send('respond-draw', { accept: true }));
$('decline-draw').addEventListener('click', () => connection.send('respond-draw', { accept: false }));

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

  const live = !session.replay && session.review === null;
  if (myTurn && live) {
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

  // what the board shows: the live game, an earlier position (with the turn that led to it
  // marked), or a turn being played back from the position before it
  const { history } = session;
  const count = session.review ?? history.length;
  const entry = count > 0 ? history[count - 1] : null;
  let shown = {
    board: positionAfter(state.board, history, count),
    lastTurn: entry ? { moves: entry.moves } : null,
    // while a move is being built the marks of the last one would only be in the way
    trail: path.length === 0 && entry ? entry.moves : [],
    // the live board only marks where pieces were taken, to keep the pieces still in play easy to see;
    // looking at a past move shows the taken pieces themselves
    ghosts: path.length === 0 && entry && session.review !== null ? ghostsOf(entry) : [],
    marks: path.length === 0 && entry && session.review === null ? entry.captured.map(([square]) => square) : [],
    path,
    captured: live ? capturedSoFar(state.legal, path) : [],
  };
  if (session.replay) {
    const { before, frames, step } = session.replay;
    shown = { board: before, lastTurn: null, trail: [], ghosts: [], ...frames[step] };
  }

  view.render({
    rows: state.rows,
    cols: state.cols,
    mask: state.mask,
    castles: state.castles,
    side,
    clickable,
    movable,
    candidates,
    opponentPath: session.opponentPath,
    opponentHover: session.opponentHover,
    ...shown,
  });

  renderStatus(myTurn);
  renderPlayers();
  renderControls(myTurn);
  renderHistory();
}

// --- history ----------------------------------------------------------------

const STEP_MS = 480; // how long each hop of a replay is shown
const HOLD_MS = 350;
const AUTO_REPLAY_KEY = 'monka.autoReplay';

/**
 * Whether the opponent's turns are played back automatically: the player's choice if they have
 * made one, otherwise yes, unless the system asks for less motion. (The Replay button always works.)
 */
function autoReplayOn() {
  try {
    const saved = localStorage.getItem(AUTO_REPLAY_KEY);
    if (saved !== null) {
      return saved === '1';
    }
  } catch {
    // no storage: use the default
  }
  return !window.matchMedia?.('(prefers-reduced-motion: reduce)').matches;
}

/** Plays `entry` back on the board, starting from `before` (the position it was played from). */
function startReplay(entry, before) {
  stopReplay();
  if (entry.moves.length < 2) {
    return;
  }
  session.replay = { before, frames: replayFrames(entry), step: 0, timer: null };
  stepReplay();
}

function stepReplay() {
  const replay = session.replay;
  if (!replay) {
    return;
  }
  render();
  if (replay.step < replay.frames.length - 1) {
    replay.step += 1;
    replay.timer = setTimeout(stepReplay, STEP_MS);
  } else {
    replay.timer = setTimeout(stopReplay, HOLD_MS);
  }
}

function stopReplay() {
  if (session?.replay) {
    clearTimeout(session.replay.timer);
    session.replay = null;
    render();
  }
}

/** The earliest position that can be shown: the start, unless the history is missing its first turns. */
function firstReviewable() {
  return session.state.moveCount === session.history.length ? 0 : 1;
}

function reviewTurn(count) {
  const length = session.history.length;
  const target = Math.min(Math.max(count, firstReviewable()), length);
  stopReplay();
  session.review = target === length ? null : target;
  render();
}

function stopReview() {
  reviewTurn(session.history.length);
}

function renderHistory() {
  const { history, state } = session;
  const geometry = { rows: state.rows, cols: state.cols };
  const offset = state.moveCount - history.length; // turns before the first one we have
  const shownCount = session.review ?? history.length;

  const list = $('history-list');
  const items = history.map((entry, i) => {
    const item = document.createElement('li');
    const button = document.createElement('button');
    button.type = 'button';
    button.className = `hist-item${i + 1 === shownCount ? ' active' : ''}`;

    const number = document.createElement('span');
    number.className = 'hist-num';
    number.textContent = String(offset + i + 1);
    const dot = document.createElement('span');
    dot.className = `hist-dot ${entry.player}`;
    dot.title = SIDE_NAMES[entry.player];
    const notation = document.createElement('span');
    notation.className = 'hist-move';
    notation.textContent = describeMove(entry, geometry);
    button.append(number, dot, notation);
    if (entry.captured.length > 0) {
      const taken = document.createElement('span');
      taken.className = 'hist-taken';
      taken.textContent = `${entry.captured.length} taken`;
      button.append(taken);
    }
    button.setAttribute('aria-label', `Move ${offset + i + 1}, ${SIDE_NAMES[entry.player]}: ${notation.textContent}`);
    button.setAttribute('aria-current', i + 1 === shownCount ? 'step' : 'false');
    button.addEventListener('click', () => reviewTurn(i + 1));
    item.append(button);
    return item;
  });
  if (items.length === 0) {
    const empty = document.createElement('li');
    empty.className = 'hist-empty';
    empty.textContent = 'No moves yet.';
    items.push(empty);
  }
  list.replaceChildren(...items);

  // follow the game while it is live; otherwise keep the turn being looked at in view
  const active = list.querySelector('.hist-item.active');
  if (session.review === null || !active) {
    list.scrollTop = list.scrollHeight;
  } else {
    active.scrollIntoView({ block: 'nearest' });
  }

  $('history-prev').disabled = shownCount <= firstReviewable();
  $('history-next').disabled = session.review === null;
  $('history-replay').disabled = shownCount === 0;

  const viewing = session.review !== null;
  $('history-viewing').hidden = !viewing;
  if (viewing) {
    $('history-viewing-text').textContent =
      shownCount === 0 ? 'Viewing the start' : `Viewing move ${offset + shownCount}`;
  }
}

$('history-prev').addEventListener('click', () => reviewTurn((session.review ?? session.history.length) - 1));
$('history-next').addEventListener('click', () => reviewTurn((session.review ?? session.history.length) + 1));
$('history-live').addEventListener('click', stopReview);
$('history-auto').checked = autoReplayOn();
$('history-auto').addEventListener('change', (event) => {
  try {
    localStorage.setItem(AUTO_REPLAY_KEY, event.target.checked ? '1' : '0');
  } catch {
    // it just won't be remembered
  }
});
$('history-replay').addEventListener('click', () => {
  const { history, state } = session;
  const count = session.review ?? history.length;
  if (count === 0) {
    return;
  }
  const entry = history[count - 1];
  stopReplay();
  session.replay = {
    before: positionAfter(state.board, history, count - 1),
    frames: replayFrames(entry),
    step: 0,
    timer: null,
  };
  stepReplay();
});

document.addEventListener('keydown', (event) => {
  const typing = event.target instanceof HTMLElement && event.target.matches('input, textarea, select');
  if (!session || typing || event.altKey || event.ctrlKey || event.metaKey || $('game').hidden) {
    return;
  }
  if (event.key === 'ArrowLeft') {
    $('history-prev').click();
    event.preventDefault();
  } else if (event.key === 'ArrowRight') {
    $('history-next').click();
    event.preventDefault();
  }
});

function renderStatus(myTurn) {
  const { state, side } = session;
  const status = $('status');

  if (state.draw) {
    status.textContent = 'Drawn game';
    status.className = 'status';
  } else if (state.winner) {
    status.textContent = state.winner === side ? 'You won' : 'You lost';
    status.className = 'status';
  } else if (state.turn === side) {
    status.textContent = `Your move (${SIDE_NAMES[side]})`;
    status.className = 'status yours';
  } else {
    status.textContent = `${session.computer ? "Computer's" : "Opponent's"} move (${SIDE_NAMES[state.turn]})`;
    status.className = 'status theirs';
  }

  document.title = myTurn ? `Your move | ${state.variantName}` : `${state.variantName} | Monka Games`;
}

function renderPlayers() {
  const { state, side } = session;
  const counts = { white: 0, black: 0 };
  state.board.forEach((piece) => piece && counts[pieceOwner(piece)]++);

  const away = '<span class="away" title="Not connected right now. The game waits for them.">away</span>';
  const row = (who, owner, isAway = false) => `
    <div class="player${state.turn === owner && !isOver(state) ? ' active' : ''}">
      <svg class="shield" viewBox="0 0 100 120" aria-hidden="true"><use href="#shield-${owner}" /></svg>
      <span class="who"><strong>${who}${isAway ? away : ''}</strong><small>${SIDE_NAMES[owner]}</small></span>
      <span class="count" title="Pieces left">${counts[owner]}</span>
    </div>`;

  const them = session.computer ? `Computer (${levelName(session.computer)})` : 'Opponent';
  $('players').innerHTML = row('You', side) + row(them, otherSide(side), !session.opponentConnected);
}

function renderControls(myTurn) {
  const { state, path } = session;
  $('turn-actions').classList.toggle('idle', !myTurn);
  const complete = myTurn && exactTurn(state.legal, path) !== null;

  $('undo').disabled = !myTurn || path.length === 0;
  $('end-turn').disabled = !complete;
  $('end-turn').classList.toggle('ready', complete && isFinished(state.legal, path));

  renderDrawControls();

  let hint;
  if (isOver(state)) {
    hint = 'The game is over.';
  } else if (!myTurn) {
    hint = session.pending
      ? 'Sending your move…'
      : session.computer
        ? 'The computer is thinking…'
        : 'Waiting for your opponent to move.';
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

/** The offer, claim and answer buttons for variants where the game can be drawn. */
function renderDrawControls() {
  const { state, side } = session;
  const open = state.drawsAllowed && !isOver(state);
  const offerFromThem = open && state.drawOffer && state.drawOffer !== side;
  const claimable = state.claimable.repetition || state.claimable.fiftyMoves;

  $('actions-row').hidden = isOver(state);
  $('offer-draw').hidden = !state.drawsAllowed;
  $('draw-offer').hidden = !offerFromThem;
  $('claim-draw').hidden = !claimable;
  $('claim-draw').textContent = state.claimable.repetition ? 'Claim a draw (repetition)' : 'Claim a draw (50 moves)';

  const offered = state.drawOffer === side;
  $('offer-draw').disabled = offered;
  $('offer-draw').textContent = offered ? 'Draw offered' : 'Offer a draw';
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
  const drawn = Boolean(state.draw);

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
    resignation: won ? 'Your opponent has resigned the field.' : 'You resigned the game.',
  };

  const draws = {
    'lone-pieces': 'Each side is down to a single piece, so neither can win.',
    stalemate: 'A player has no legal move, but the other has fewer than two pieces left to win with.',
    agreed: 'You both agreed to a draw.',
    repetition: 'The same position came up three times.',
    'fifty-moves': 'Fifty moves each passed without a capture or a piece reaching a castle.',
  };

  $('over-title').textContent = drawn ? 'A draw' : won ? 'Victory!' : 'Alas, defeat';
  $('over-text').textContent = (drawn ? draws[state.draw] : reasons[state.winReason]) ?? '';

  // the next game swaps colours: whoever clicks first creates it and asks for the other side
  $('play-again').onclick = () => {
    connection.close();
    forgetGame(code);
    const next = new URLSearchParams({ gamecode: rematchCode(code), side: otherSide(side), variant: state.variant });
    if (session.computer) {
      next.set('computer', session.computer);
    }
    location.href = `${location.pathname}?${next}`;
  };

  if (!$('over').open) {
    $('over').showModal();
  }
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

// --- games to come back to --------------------------------------------------

function renderResumeList() {
  const games = resumableGames();
  $('resume').hidden = games.length === 0;

  $('resume-list').replaceChildren(
    ...games.map((game) => {
      const item = document.createElement('li');

      const info = document.createElement('span');
      info.className = 'resume-info';
      const name = document.createElement('strong');
      name.textContent = VARIANT_NAMES[game.variant] ?? 'Game';
      const detail = document.createElement('small');
      const versus = game.computer ? `Computer (${levelName(game.computer)}) · ` : '';
      detail.textContent = `${versus}${game.side ? `As ${SIDE_NAMES[game.side]}` : 'Waiting for an opponent'} · ${game.code}`;
      info.append(name, detail);

      const resume = document.createElement('button');
      resume.className = 'btn';
      resume.type = 'button';
      resume.textContent = 'Resume';
      resume.addEventListener('click', () => start(game.code, game.side, game.variant, game.computer ?? undefined));

      const forget = document.createElement('button');
      forget.className = 'forget';
      forget.type = 'button';
      forget.textContent = '✕';
      forget.title = 'Forget this game';
      forget.setAttribute('aria-label', `Forget the game ${game.code}`);
      forget.addEventListener('click', () => {
        forgetGame(game.code);
        renderResumeList();
      });

      item.append(info, resume, forget);
      return item;
    }),
  );
}

// --- go ---------------------------------------------------------------------

const params = new URLSearchParams(location.search);
const wantedVariant = params.get('variant') ?? undefined;
if (params.get('gamecode')) {
  const level = params.get('computer');
  start(params.get('gamecode'), params.get('side') ?? 'random', wantedVariant, COMPUTER_LEVELS.includes(level) ? level : undefined);
} else {
  renderResumeList();
  if (wantedVariant) {
    // a link from the front page to one of the games
    const radio = document.querySelector(`input[name=variant][value="${wantedVariant}"]`);
    if (radio) {
      radio.checked = true;
    }
  }
}
