// The games this browser is part of. A player is identified to the server by a
// secret token, and the token for each game is kept here (in localStorage) so a
// reload, a dropped connection or a server restart can pick the game up again.
//
// Entries: code -> { token, side, variant, over, pending, savedAt }. An entry is
// saved as `pending` before the first connection, so a reload before the server
// has answered still remembers who we are; once the server has confirmed the game
// the entry stops being pending, which is also what tells the client that the next
// connection is a return rather than a new game.

const KEY = 'monka-games:v1';
export const MAX_AGE_MS = 30 * 24 * 60 * 60 * 1000; // the server forgets games long before this

function read(storage) {
  try {
    const parsed = JSON.parse(storage.getItem(KEY));
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed : {};
  } catch {
    return {}; // nothing saved, unreadable, or storage blocked
  }
}

function write(storage, games) {
  try {
    storage.setItem(KEY, JSON.stringify(games));
  } catch {
    // the game just won't be resumable after the page closes
  }
}

export function getGame(code, storage = localStorage) {
  const entry = read(storage)[code];
  return entry && typeof entry.token === 'string' ? entry : null;
}

/** Records (or updates) a game. Fields not given are kept from the earlier entry. */
export function saveGame(code, fields, storage = localStorage, now = Date.now()) {
  const games = read(storage);
  games[code] = { ...games[code], ...fields, savedAt: now };
  write(storage, games);
}

export function forgetGame(code, storage = localStorage) {
  const games = read(storage);
  if (code in games) {
    delete games[code];
    write(storage, games);
  }
}

/** The games still going and confirmed by the server, newest first; far-too-old ones are dropped (and deleted). */
export function resumableGames(storage = localStorage, now = Date.now()) {
  const games = read(storage);
  let changed = false;

  for (const [code, entry] of Object.entries(games)) {
    if (!entry || typeof entry.token !== 'string' || now - entry.savedAt > MAX_AGE_MS) {
      delete games[code];
      changed = true;
    }
  }
  if (changed) {
    write(storage, games);
  }

  return Object.entries(games)
    .filter(([, entry]) => !entry.over && !entry.pending)
    .map(([code, entry]) => ({ code, ...entry }))
    .sort((a, b) => b.savedAt - a.savedAt);
}

/** A new secret for a player: 16 random bytes as 22 url-safe characters. */
export function newToken(random = crypto) {
  const bytes = random.getRandomValues(new Uint8Array(16));
  return btoa(String.fromCharCode(...bytes))
    .replaceAll('+', '-')
    .replaceAll('/', '_')
    .replaceAll('=', '');
}
