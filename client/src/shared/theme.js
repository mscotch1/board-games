// Light/dark theme. Until the player picks one, the theme follows the system;
// a pick is remembered. Colours live in theme.css and switch on the
// `data-theme` attribute of <html> (set only for an explicit pick), while
// `data-effective` always holds the theme in use so the toggle can show the
// right icon. Each page also sets both in an inline script in its <head> so the
// page doesn't flash the wrong theme while this module loads.

export const STORAGE_KEY = 'theme';

/** The theme in use, given a stored pick (if any) and whether the system prefers light. */
export function resolveTheme(stored, prefersLight) {
  if (stored === 'light' || stored === 'dark') {
    return stored;
  }
  return prefersLight ? 'light' : 'dark';
}

function readStored(storage) {
  try {
    return storage.getItem(STORAGE_KEY);
  } catch {
    return null; // storage can be blocked
  }
}

function writeStored(storage, value) {
  try {
    storage.setItem(STORAGE_KEY, value);
  } catch {
    // the choice then only lasts for this visit
  }
}

/**
 * Makes `button` switch between light and dark. `root` is the <html> element,
 * `media` the "prefers light" media query list.
 */
export function initThemeToggle(
  button,
  { root = document.documentElement, storage = localStorage, media = matchMedia('(prefers-color-scheme: light)') } = {},
) {
  let stored = readStored(storage);

  const apply = () => {
    const effective = resolveTheme(stored, media.matches);
    if (stored === 'light' || stored === 'dark') {
      root.dataset.theme = effective;
    } else {
      delete root.dataset.theme;
    }
    root.dataset.effective = effective;

    const next = effective === 'dark' ? 'light' : 'dark';
    button.setAttribute('aria-label', `Switch to ${next} theme`);
    button.title = `Switch to ${next} theme`;
  };

  button.addEventListener('click', () => {
    stored = resolveTheme(stored, media.matches) === 'dark' ? 'light' : 'dark';
    writeStored(storage, stored);
    apply();
  });

  // follow the system until a theme has been picked
  media.addEventListener('change', apply);

  apply();
}
