import { describe, expect, it } from 'vitest';
import { initThemeToggle, resolveTheme, STORAGE_KEY } from './theme.js';

describe('resolving the theme', () => {
  it('uses a stored pick over the system', () => {
    expect(resolveTheme('dark', true)).toBe('dark');
    expect(resolveTheme('light', false)).toBe('light');
  });

  it('follows the system without a pick', () => {
    expect(resolveTheme(null, true)).toBe('light');
    expect(resolveTheme(null, false)).toBe('dark');
  });

  it('ignores junk in storage', () => {
    expect(resolveTheme('purple', true)).toBe('light');
    expect(resolveTheme('', false)).toBe('dark');
  });
});

describe('the toggle', () => {
  const setup = ({ stored = null, prefersLight = false, storage } = {}) => {
    const data = new Map(stored ? [[STORAGE_KEY, stored]] : []);
    const fakeStorage = storage ?? {
      getItem: (key) => data.get(key) ?? null,
      setItem: (key, value) => data.set(key, value),
    };

    const listeners = {};
    const button = {
      title: '',
      attributes: {},
      addEventListener: (type, fn) => (listeners[type] = fn),
      setAttribute(name, value) {
        this.attributes[name] = value;
      },
    };
    const mediaListeners = [];
    const media = { matches: prefersLight, addEventListener: (_type, fn) => mediaListeners.push(fn) };
    const root = { dataset: {} };

    initThemeToggle(button, { root, storage: fakeStorage, media });
    return { button, listeners, media, mediaListeners, root, data };
  };

  it('starts on the system theme without pinning it', () => {
    const { root, button } = setup({ prefersLight: true });
    expect(root.dataset).toEqual({ effective: 'light' });
    expect(button.attributes['aria-label']).toBe('Switch to dark theme');
  });

  it('starts on a remembered pick', () => {
    const { root } = setup({ stored: 'dark', prefersLight: true });
    expect(root.dataset).toEqual({ theme: 'dark', effective: 'dark' });
  });

  it('switches to the other theme and remembers it', () => {
    const { root, listeners, data, button } = setup({ prefersLight: false });
    listeners.click();
    expect(root.dataset).toEqual({ theme: 'light', effective: 'light' });
    expect(data.get(STORAGE_KEY)).toBe('light');
    expect(button.title).toBe('Switch to dark theme');

    listeners.click();
    expect(root.dataset).toEqual({ theme: 'dark', effective: 'dark' });
    expect(data.get(STORAGE_KEY)).toBe('dark');
  });

  it('follows the system while nothing is picked, but not afterwards', () => {
    const { root, media, mediaListeners, listeners } = setup({ prefersLight: false });
    media.matches = true;
    mediaListeners.forEach((fn) => fn());
    expect(root.dataset.effective).toBe('light');

    listeners.click(); // picks dark
    media.matches = false;
    mediaListeners.forEach((fn) => fn());
    expect(root.dataset).toEqual({ theme: 'dark', effective: 'dark' });
    media.matches = true;
    mediaListeners.forEach((fn) => fn());
    expect(root.dataset.effective).toBe('dark');
  });

  it('still works when storage is blocked', () => {
    const blocked = {
      getItem() {
        throw new Error('denied');
      },
      setItem() {
        throw new Error('denied');
      },
    };
    const { root, listeners } = setup({ storage: blocked, prefersLight: true });
    expect(root.dataset.effective).toBe('light');
    listeners.click();
    expect(root.dataset).toEqual({ theme: 'dark', effective: 'dark' });
  });
});
