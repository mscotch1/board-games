// The line at the foot of every page: which build this is, where the source is (the AGPL asks
// that users of a modified site can get it), and a way to report a problem. The build details
// and the repository address are set when the site is built (see vite.config.js), so what a
// visitor sees is exactly what was deployed.

/** How to show a version: tags read as "v1.2.0", anything else (a commit, a dev build) as it is. */
export function describeVersion(version) {
  if (!version || version === 'dev') {
    return 'dev build';
  }
  return /^\d/.test(version) ? `v${version}` : version;
}

/**
 * The parts of the build for display: `{ version, commit, date, title }`. Empty parts are
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

const RELEASE_TAG = /^v?\d+\.\d+\.\d+(-[0-9A-Za-z.-]+)?$/;
// what `git describe` adds after a tag when the build is not exactly that tag
const AFTER_THE_TAG = /-\d+-g[0-9a-f]+(-dirty)?$|-dirty$/;

/** The GitHub release page for a version that is exactly a release tag, or null for anything else. */
export function releaseUrl(repo, version) {
  if (!repo || !RELEASE_TAG.test(version ?? '') || AFTER_THE_TAG.test(version)) {
    return null;
  }
  const tag = version.startsWith('v') ? version : `v${version}`;
  return `${repo}/releases/tag/${tag}`;
}

/** The page for a commit, or null when it isn't known. */
export function commitUrl(repo, commit) {
  return repo && commit ? `${repo}/commit/${commit}` : null;
}

/**
 * A link that starts a new issue with the details a bug report needs already filled in: the
 * version, the page and the browser. It never includes the game's code or anything else
 * from the address bar, and the reporter sees all of it on GitHub before sending.
 */
export function issueUrl(repo, { version, commit, page, userAgent }) {
  const body = [
    '**What happened?**',
    '',
    '',
    '**What did you expect to happen?**',
    '',
    '',
    '---',
    `Version: ${[version, commit && `(${commit.slice(0, 7)})`].filter(Boolean).join(' ')}`,
    page && `Page: ${page}`,
    userAgent && `Browser: ${userAgent}`,
  ]
    .filter((line) => line !== undefined && line !== null && line !== false)
    .join('\n');
  return `${repo}/issues/new?body=${encodeURIComponent(body)}`;
}

/**
 * What the footer says, as a list of `{ text, href?, title? }`. Without a repository address
 * the links are left out and only the build details remain.
 */
export function footerItems(build, { locale, repo = '', page = '', userAgent = '' } = {}) {
  const { version, commit, date } = formatBuild(build, locale);
  const items = [{ text: 'Monka Games' }];

  items.push({ text: version, href: releaseUrl(repo, build.version) ?? undefined });
  if (commit) {
    items.push({ text: commit, href: commitUrl(repo, build.commit) ?? undefined });
  }
  if (date) {
    items.push({ text: date });
  }
  if (repo) {
    items.push({ text: 'Source', href: repo, title: 'The source code, under the GNU Affero General Public License' });
    items.push({
      text: 'Report an issue',
      href: issueUrl(repo, { version, commit: build.commit, page, userAgent }),
      title: 'Opens a new issue on GitHub, with your version and browser filled in',
    });
  }
  return items;
}

/** Fills every `[data-site-footer]` element, and points every `a[data-repo]` link into the repository. */
export function mountFooters(
  root = document,
  build = __BUILD__,
  { locale = navigator.language, repo = __REPO__, page = location.pathname, userAgent = navigator.userAgent } = {},
) {
  const { title } = formatBuild(build, locale);
  const items = footerItems(build, { locale, repo, page, userAgent });

  root.querySelectorAll('[data-site-footer]').forEach((footer) => {
    footer.classList.add('site-footer');
    footer.title = title;
    footer.replaceChildren(
      ...items.map((item) => {
        const element = root.createElement(item.href ? 'a' : 'span');
        element.textContent = item.text;
        if (item.href) {
          element.href = item.href;
          element.target = '_blank';
          element.rel = 'noopener noreferrer';
        }
        if (item.title) {
          element.title = item.title;
        }
        return element;
      }),
    );
  });

  // links in the page text that point into the repository, e.g. <a data-repo="/blob/HEAD/LICENSE">
  root.querySelectorAll('a[data-repo]').forEach((link) => {
    if (repo) {
      link.href = repo + link.dataset.repo;
    } else {
      link.hidden = true;
    }
  });
}
