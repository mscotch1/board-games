// Light/dark theme with three choices: light, dark, or follow the system. The
// choice is remembered; "follow the system" is stored as no value at all.
// Colours live in theme.css and switch on the `data-theme` attribute of <html>
// (set only for an explicit light or dark), while `data-effective` always holds
// the theme in use. Each page also sets both in an inline script in its <head>
// so it doesn't flash the wrong theme while this module loads.

export const STORAGE_KEY = 'theme';

/** The theme in use, given a stored pick (if any) and whether the system prefers light. */
export function resolveTheme(stored, prefersLight) {
  if (stored === 'light' || stored === 'dark') {
    return stored;
  }
  return prefersLight ? 'light' : 'dark';
}

/** Which of the three choices a stored value means. */
export function choiceFor(stored) {
  return stored === 'light' || stored === 'dark' ? stored : 'system';
}

function readStored(storage) {
  try {
    return storage.getItem(STORAGE_KEY);
  } catch {
    return null; // storage can be blocked
  }
}

function writeStored(storage, choice) {
  try {
    if (choice === 'system') {
      storage.removeItem(STORAGE_KEY);
    } else {
      storage.setItem(STORAGE_KEY, choice);
    }
  } catch {
    // the choice then only lasts for this visit
  }
}

const icon = (paths) =>
  `<svg viewBox="0 0 24 24" aria-hidden="true">${paths}</svg>`;

const CHOICES = [
  {
    value: 'light',
    label: 'Light theme',
    icon: icon(
      '<circle cx="12" cy="12" r="4.5" /><path d="M12 2.5v2.5M12 19v2.5M2.5 12H5M19 12h2.5M5.3 5.3l1.8 1.8M16.9 16.9l1.8 1.8M5.3 18.7l1.8-1.8M16.9 7.1l1.8-1.8" />',
    ),
  },
  {
    value: 'system',
    label: 'Follow the system theme',
    icon: icon('<rect x="3" y="4.5" width="18" height="12" rx="2" /><path d="M8.5 20h7M12 16.5V20" />'),
  },
  {
    value: 'dark',
    label: 'Dark theme',
    icon: icon('<path d="M20 14.5A8.5 8.5 0 0 1 9.5 4a8.5 8.5 0 1 0 10.5 10.5Z" />'),
  },
];

/** The buttons for a picker, to be put inside an element with role="group". */
export function pickerMarkup() {
  return CHOICES.map(
    ({ value, label, icon: svg }) =>
      `<button type="button" data-theme-choice="${value}" aria-label="${label}" title="${label}" aria-pressed="false">${svg}</button>`,
  ).join('');
}

/**
 * Fills each container with the picker's buttons and wires them up. A page can
 * have several pickers (the lobby and the game header, say); they share one
 * choice, which is why they are set up together.
 */
export function mountThemePickers(containers, options) {
  const list = [...containers];
  for (const container of list) {
    container.setAttribute('role', 'group');
    container.setAttribute('aria-label', 'Theme');
    container.innerHTML = pickerMarkup();
  }
  initThemePickers(list, options);
}

/**
 * Makes the `[data-theme-choice]` buttons in `containers` choose the theme.
 * `root` is the <html> element, `media` the "prefers light" media query list.
 */
export function initThemePickers(
  containers,
  { root = document.documentElement, storage = localStorage, media = matchMedia('(prefers-color-scheme: light)') } = {},
) {
  const buttons = containers.flatMap((container) => [...container.querySelectorAll('[data-theme-choice]')]);
  let stored = readStored(storage);

  const apply = () => {
    const effective = resolveTheme(stored, media.matches);
    if (choiceFor(stored) === 'system') {
      delete root.dataset.theme;
    } else {
      root.dataset.theme = effective;
    }
    root.dataset.effective = effective;

    for (const button of buttons) {
      button.setAttribute('aria-pressed', String(button.dataset.themeChoice === choiceFor(stored)));
    }
  };

  for (const container of containers) {
    container.addEventListener('click', (event) => {
      const choice = event.target.closest?.('[data-theme-choice]')?.dataset.themeChoice;
      if (choice) {
        stored = choice === 'system' ? null : choice;
        writeStored(storage, choice);
        apply();
      }
    });
  }

  // follow the system whenever "system" is the choice
  media.addEventListener('change', apply);

  apply();
}
