import { describe, expect, it } from 'vitest';
import { forgetGame, getGame, MAX_AGE_MS, newToken, resumableGames, saveGame } from './saved-games.js';

const memoryStorage = (initial = {}) => {
  const data = new Map(Object.entries(initial));
  return {
    getItem: (key) => data.get(key) ?? null,
    setItem: (key, value) => data.set(key, value),
    data,
  };
};

const blockedStorage = {
  getItem() {
    throw new Error('denied');
  },
  setItem() {
    throw new Error('denied');
  },
};

describe('saved games', () => {
  it('remembers a game by its code', () => {
    const storage = memoryStorage();
    saveGame('abc', { token: 't1', side: 'white', variant: 'cam' }, storage, 1000);
    expect(getGame('abc', storage)).toEqual({ token: 't1', side: 'white', variant: 'cam', savedAt: 1000 });
    expect(getGame('other', storage)).toBeNull();
  });

  it('updates an entry without losing what it already knew', () => {
    const storage = memoryStorage();
    saveGame('abc', { token: 't1', variant: 'cam' }, storage, 1000);
    saveGame('abc', { side: 'black' }, storage, 2000);
    expect(getGame('abc', storage)).toEqual({ token: 't1', variant: 'cam', side: 'black', savedAt: 2000 });
  });

  it('forgets games', () => {
    const storage = memoryStorage();
    saveGame('abc', { token: 't1' }, storage);
    saveGame('def', { token: 't2' }, storage);
    forgetGame('abc', storage);
    forgetGame('never-saved', storage);
    expect(getGame('abc', storage)).toBeNull();
    expect(getGame('def', storage)).not.toBeNull();
  });

  it('copes with storage that is empty, corrupt, or blocked', () => {
    expect(getGame('abc', memoryStorage())).toBeNull();
    expect(getGame('abc', memoryStorage({ 'monka-games:v1': 'not json' }))).toBeNull();
    expect(getGame('abc', memoryStorage({ 'monka-games:v1': '[1,2]' }))).toBeNull();
    expect(getGame('abc', blockedStorage)).toBeNull();
    expect(() => saveGame('abc', { token: 't' }, blockedStorage)).not.toThrow();
    expect(() => forgetGame('abc', blockedStorage)).not.toThrow();
    expect(resumableGames(blockedStorage)).toEqual([]);
  });

  it('ignores entries without a token', () => {
    const storage = memoryStorage({ 'monka-games:v1': JSON.stringify({ abc: { side: 'white' } }) });
    expect(getGame('abc', storage)).toBeNull();
  });
});

describe('games to resume', () => {
  it('lists unfinished games, newest first', () => {
    const storage = memoryStorage();
    saveGame('old', { token: 'a', variant: 'camelot' }, storage, 1000);
    saveGame('new', { token: 'b', variant: 'cam' }, storage, 3000);
    saveGame('mid', { token: 'c' }, storage, 2000);
    expect(resumableGames(storage, 4000).map((g) => g.code)).toEqual(['new', 'mid', 'old']);
  });

  it('leaves out games that are over', () => {
    const storage = memoryStorage();
    saveGame('going', { token: 'a' }, storage, 1000);
    saveGame('done', { token: 'b', over: true }, storage, 2000);
    expect(resumableGames(storage, 3000).map((g) => g.code)).toEqual(['going']);
    expect(getGame('done', storage)).not.toBeNull(); // still there to look at the result
  });

  it('leaves out games the server has not confirmed yet', () => {
    const storage = memoryStorage();
    saveGame('confirmed', { token: 'a' }, storage, 1000);
    saveGame('unconfirmed', { token: 'b', pending: true }, storage, 2000);
    expect(resumableGames(storage, 3000).map((g) => g.code)).toEqual(['confirmed']);
    saveGame('unconfirmed', { pending: false }, storage, 3000);
    expect(resumableGames(storage, 4000).map((g) => g.code)).toEqual(['unconfirmed', 'confirmed']);
  });

  it('drops games that are far too old', () => {
    const storage = memoryStorage();
    saveGame('ancient', { token: 'a' }, storage, 0);
    saveGame('recent', { token: 'b' }, storage, MAX_AGE_MS);
    expect(resumableGames(storage, MAX_AGE_MS + 1).map((g) => g.code)).toEqual(['recent']);
    expect(getGame('ancient', storage)).toBeNull();
  });
});

describe('tokens', () => {
  it('are 22 url-safe characters, which the server accepts', () => {
    for (let i = 0; i < 50; i++) {
      expect(newToken()).toMatch(/^[A-Za-z0-9_-]{22}$/);
    }
  });

  it('are different every time', () => {
    expect(new Set(Array.from({ length: 100 }, () => newToken())).size).toBe(100);
  });

  it('come from the random source given', () => {
    const fixed = { getRandomValues: (bytes) => bytes.fill(255) };
    expect(newToken(fixed)).toBe('_____________________w');
  });
});
