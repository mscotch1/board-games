// The small line at the foot of every page saying which build this is. The
// values are set when the site is built (see vite.config.js), so what a visitor
// sees is exactly what was deployed.

/** How to show a version: tags read as "v1.2.0", anything else (a commit, a dev build) as it is. */
export function describeVersion(version) {
  if (!version || version === 'dev') {
    return 'dev build';
  }
  return /^\d/.test(version) ? `v${version}` : version;
}

/**
 * The parts of the footer for a build: `{ version, commit, date, title }`. Empty parts are
 * left out of the line; `title` is the full detail, for a tooltip.
 */
export function formatBuild(build, locale) {
  const version = describeVersion(build.version);
  const fullCommit = build.commit ?? '';
  const commit = fullCommit.slice(0, 7);

  let date = '';
  const builtAt = new Date(build.built);
  if (build.built && !Number.isNaN(builtAt.getTime())) {
    date = new Intl.DateTimeFormat(locale, { dateStyle: 'medium' }).format(builtAt);
  }

  const title = [
    `Version: ${version}`,
    fullCommit && `Commit: ${fullCommit}`,
    build.built && `Built: ${build.built}`,
  ]
    .filter(Boolean)
    .join('\n');

  return {
    version,
    // `git describe` output already ends in the commit, so don't say it twice
    commit: commit && version.includes(commit) ? '' : commit,
    date: date && `built ${date}`,
    title,
  };
}

/** Fills every `[data-site-footer]` element with the build line. */
export function mountFooters(root = document, build = __BUILD__, locale = navigator.language) {
  const { version, commit, date, title } = formatBuild(build, locale);
  const parts = ['Monka Games', version, commit, date].filter(Boolean);

  root.querySelectorAll('[data-site-footer]').forEach((footer) => {
    footer.classList.add('site-footer');
    footer.textContent = parts.join(' · ');
    footer.title = title;
  });
}
