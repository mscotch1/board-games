import { describe, expect, it } from 'vitest';
import { choiceFor, initThemePickers, pickerMarkup, resolveTheme, STORAGE_KEY } from './theme.js';

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

describe('choices', () => {
  it('maps what is stored to a choice', () => {
    expect(choiceFor('light')).toBe('light');
    expect(choiceFor('dark')).toBe('dark');
    expect(choiceFor(null)).toBe('system');
    expect(choiceFor('system')).toBe('system');
    expect(choiceFor('purple')).toBe('system');
  });

  it('offers light, system and dark buttons', () => {
    const markup = pickerMarkup();
    for (const value of ['light', 'system', 'dark']) {
      expect(markup).toContain(`data-theme-choice="${value}"`);
    }
  });
});

describe('the picker', () => {
  const setup = ({ stored = null, prefersLight = false, storage, pickerCount = 1 } = {}) => {
    const data = new Map(stored ? [[STORAGE_KEY, stored]] : []);
    const fakeStorage = storage ?? {
      getItem: (key) => data.get(key) ?? null,
      setItem: (key, value) => data.set(key, value),
      removeItem: (key) => data.delete(key),
    };

    const makePicker = () => {
      const buttons = ['light', 'system', 'dark'].map((choice) => ({
        dataset: { themeChoice: choice },
        pressed: null,
        setAttribute(name, value) {
          if (name === 'aria-pressed') this.pressed = value;
        },
      }));
      const listeners = {};
      const container = {
        querySelectorAll: () => buttons,
        addEventListener: (type, fn) => (listeners[type] = fn),
      };
      const pick = (choice) => {
        const button = buttons.find((b) => b.dataset.themeChoice === choice);
        listeners.click({ target: { closest: () => button } });
      };
      const pressed = () => buttons.filter((b) => b.pressed === 'true').map((b) => b.dataset.themeChoice);
      return { container, listeners, pick, pressed };
    };
    const pickers = Array.from({ length: pickerCount }, makePicker);
    const { pick, pressed, listeners } = pickers[0];

    const mediaListeners = [];
    const media = { matches: prefersLight, addEventListener: (_type, fn) => mediaListeners.push(fn) };
    const systemChanges = (prefersLightNow) => {
      media.matches = prefersLightNow;
      mediaListeners.forEach((fn) => fn());
    };
    const root = { dataset: {} };

    initThemePickers(pickers.map((p) => p.container), { root, storage: fakeStorage, media });
    return { pick, pressed, pickers, root, data, systemChanges, listeners };
  };

  it('starts on "system" without pinning a theme', () => {
    const { root, pressed } = setup({ prefersLight: true });
    expect(root.dataset).toEqual({ effective: 'light' });
    expect(pressed()).toEqual(['system']);
  });

  it('starts on a remembered pick', () => {
    const { root, pressed } = setup({ stored: 'dark', prefersLight: true });
    expect(root.dataset).toEqual({ theme: 'dark', effective: 'dark' });
    expect(pressed()).toEqual(['dark']);
  });

  it('pins and remembers light and dark', () => {
    const { pick, root, data, pressed } = setup({ prefersLight: false });
    pick('light');
    expect(root.dataset).toEqual({ theme: 'light', effective: 'light' });
    expect(data.get(STORAGE_KEY)).toBe('light');
    expect(pressed()).toEqual(['light']);

    pick('dark');
    expect(root.dataset).toEqual({ theme: 'dark', effective: 'dark' });
    expect(data.get(STORAGE_KEY)).toBe('dark');
    expect(pressed()).toEqual(['dark']);
  });

  it('goes back to following the system, and forgets the pick', () => {
    const { pick, root, data, pressed } = setup({ stored: 'dark', prefersLight: true });
    pick('system');
    expect(root.dataset).toEqual({ effective: 'light' });
    expect(data.has(STORAGE_KEY)).toBe(false);
    expect(pressed()).toEqual(['system']);
  });

  it('tracks the system while on "system", and ignores it once pinned', () => {
    const { pick, root, systemChanges } = setup({ prefersLight: false });
    systemChanges(true);
    expect(root.dataset.effective).toBe('light');

    pick('dark');
    systemChanges(false);
    systemChanges(true);
    expect(root.dataset).toEqual({ theme: 'dark', effective: 'dark' });

    pick('system');
    expect(root.dataset).toEqual({ effective: 'light' });
    systemChanges(false);
    expect(root.dataset.effective).toBe('dark');
  });

  it('keeps several pickers in step, so an old one can not undo a choice', () => {
    const { pickers, root, systemChanges } = setup({ prefersLight: false, pickerCount: 2 });
    pickers[0].pick('dark');
    expect(pickers[1].pressed()).toEqual(['dark']);

    systemChanges(true);
    expect(root.dataset).toEqual({ theme: 'dark', effective: 'dark' });

    pickers[1].pick('system');
    expect(pickers[0].pressed()).toEqual(['system']);
    expect(root.dataset).toEqual({ effective: 'light' });
  });

  it('ignores clicks that are not on a choice', () => {
    const { listeners, root } = setup({ prefersLight: false });
    listeners.click({ target: { closest: () => null } });
    expect(root.dataset).toEqual({ effective: 'dark' });
  });

  it('still works when storage is blocked', () => {
    const blocked = {
      getItem() {
        throw new Error('denied');
      },
      setItem() {
        throw new Error('denied');
      },
      removeItem() {
        throw new Error('denied');
      },
    };
    const { pick, root } = setup({ storage: blocked, prefersLight: true });
    expect(root.dataset.effective).toBe('light');
    pick('dark');
    expect(root.dataset).toEqual({ theme: 'dark', effective: 'dark' });
    pick('system');
    expect(root.dataset).toEqual({ effective: 'light' });
  });
});
