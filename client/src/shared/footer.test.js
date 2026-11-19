import { describe, expect, it } from 'vitest';
import { commitUrl, describeVersion, footerItems, formatBuild, issueUrl, mountFooters, releaseUrl } from './footer.js';

const REPO = 'https://github.com/example/board-games';

describe('describing a version', () => {
  it('writes release numbers as tags', () => {
    expect(describeVersion('1.2.0')).toBe('v1.2.0');
    expect(describeVersion('v1.2.0')).toBe('v1.2.0');
  });

  it('calls a build with no version a dev build', () => {
    expect(describeVersion('dev')).toBe('dev build');
    expect(describeVersion('')).toBe('dev build');
    expect(describeVersion(undefined)).toBe('dev build');
  });

  it('leaves other versions, like git describe output, alone', () => {
    expect(describeVersion('v1.2.0-3-gabc1234-dirty')).toBe('v1.2.0-3-gabc1234-dirty');
    expect(describeVersion('abc1234')).toBe('abc1234');
  });
});

describe('formatting a build', () => {
  const release = { version: 'v1.2.0', commit: 'a1b2c3d4e5f60718293a4b5c6d7e8f9012345678', built: '2026-11-19T15:30:00Z' };

  it('shortens the commit and formats the date', () => {
    const { version, commit, date } = formatBuild(release, 'en-US');
    expect(version).toBe('v1.2.0');
    expect(commit).toBe('a1b2c3d');
    expect(date).toBe('built Nov 19, 2026');
  });

  it("follows the reader's language for the date", () => {
    expect(formatBuild(release, 'en-GB').date).toBe('built 19 Nov 2026');
  });

  it('keeps the full details for a tooltip', () => {
    expect(formatBuild(release, 'en-US').title).toBe(
      'Version: v1.2.0\nCommit: a1b2c3d4e5f60718293a4b5c6d7e8f9012345678\nBuilt: 2026-11-19T15:30:00Z',
    );
  });

  it('copes with a build that knows nothing', () => {
    const unknown = formatBuild({ version: 'dev', commit: '', built: '' }, 'en-US');
    expect(unknown).toEqual({ version: 'dev build', commit: '', date: '', title: 'Version: dev build' });
  });

  it('ignores a date it cannot read', () => {
    expect(formatBuild({ version: 'v1', commit: 'abc1234', built: 'yesterday' }, 'en-US').date).toBe('');
  });

  it('does not repeat a commit already in the version', () => {
    const described = { version: 'v1.2.0-3-ga1b2c3d', commit: 'a1b2c3d4e5f6', built: '2026-11-19T15:30:00Z' };
    expect(formatBuild(described, 'en-US').commit).toBe('');
    expect(formatBuild({ ...described, version: 'v1.2.0' }, 'en-US').commit).toBe('a1b2c3d');
  });
});

describe('linking to a release', () => {
  it('works for an exact release tag', () => {
    expect(releaseUrl(REPO, 'v1.2.0')).toBe(`${REPO}/releases/tag/v1.2.0`);
    expect(releaseUrl(REPO, '1.2.0')).toBe(`${REPO}/releases/tag/v1.2.0`);
    expect(releaseUrl(REPO, 'v1.2.0-rc.1')).toBe(`${REPO}/releases/tag/v1.2.0-rc.1`);
  });

  it('does not invent a release for anything else', () => {
    expect(releaseUrl(REPO, 'v1.2.0-3-gabc1234-dirty')).toBeNull();
    expect(releaseUrl(REPO, 'abc1234')).toBeNull();
    expect(releaseUrl(REPO, 'dev')).toBeNull();
    expect(releaseUrl(REPO, undefined)).toBeNull();
  });

  it('needs a repository', () => {
    expect(releaseUrl('', 'v1.2.0')).toBeNull();
  });
});

describe('linking to a commit', () => {
  it('uses the full commit', () => {
    expect(commitUrl(REPO, 'a1b2c3d4e5f6')).toBe(`${REPO}/commit/a1b2c3d4e5f6`);
  });

  it('needs both a repository and a commit', () => {
    expect(commitUrl('', 'a1b2c3d')).toBeNull();
    expect(commitUrl(REPO, '')).toBeNull();
  });
});

describe('the issue link', () => {
  const link = issueUrl(REPO, {
    version: 'v1.2.0',
    commit: 'a1b2c3d4e5f60718',
    page: '/games/camelot/',
    userAgent: 'Mozilla/5.0 (Test)',
  });
  const body = decodeURIComponent(new URL(link).searchParams.get('body'));

  it('opens a new issue in the repository', () => {
    expect(link.startsWith(`${REPO}/issues/new?body=`)).toBe(true);
  });

  it('fills in what a bug report needs', () => {
    expect(body).toContain('**What happened?**');
    expect(body).toContain('Version: v1.2.0 (a1b2c3d)');
    expect(body).toContain('Page: /games/camelot/');
    expect(body).toContain('Browser: Mozilla/5.0 (Test)');
  });

  it('copes with details it does not have', () => {
    const bare = decodeURIComponent(new URL(issueUrl(REPO, { version: 'dev build' })).searchParams.get('body'));
    expect(bare).toContain('Version: dev build');
    expect(bare).not.toContain('Page:');
    expect(bare).not.toContain('Browser:');
    expect(bare).not.toContain('undefined');
  });

  it('is safe to put in a link whatever the browser says', () => {
    const odd = issueUrl(REPO, { version: 'v1', userAgent: 'a&b=c#d "quoted" <tag>' });
    expect(new URL(odd).searchParams.get('body')).toContain('Browser: a&b=c#d "quoted" <tag>');
    expect(new URL(odd).hash).toBe('');
  });
});

describe('the footer items', () => {
  const build = { version: 'v1.2.0', commit: 'a1b2c3d4e5f60718293a4b5c6d7e8f9012345678', built: '2026-11-19T15:30:00Z' };
  const options = { locale: 'en-GB', repo: REPO, page: '/', userAgent: 'UA' };

  it('say the build, with links where they lead somewhere', () => {
    const items = footerItems(build, options);
    expect(items.map((i) => i.text)).toEqual(['Monka Games', 'v1.2.0', 'a1b2c3d', 'built 19 Nov 2026', 'Source', 'Report an issue']);
    expect(items.find((i) => i.text === 'v1.2.0').href).toBe(`${REPO}/releases/tag/v1.2.0`);
    expect(items.find((i) => i.text === 'a1b2c3d').href).toBe(`${REPO}/commit/${build.commit}`);
    expect(items.find((i) => i.text === 'Source').href).toBe(REPO);
    expect(items.find((i) => i.text === 'Report an issue').href).toContain('/issues/new?body=');
  });

  it('leave a dev build unlinked to a release', () => {
    const items = footerItems({ version: 'dev', commit: '', built: '' }, options);
    expect(items.map((i) => i.text)).toEqual(['Monka Games', 'dev build', 'Source', 'Report an issue']);
    expect(items[1].href).toBeUndefined();
  });

  it('are just the build when there is no repository', () => {
    const items = footerItems(build, { ...options, repo: '' });
    expect(items.map((i) => i.text)).toEqual(['Monka Games', 'v1.2.0', 'a1b2c3d', 'built 19 Nov 2026']);
    expect(items.every((i) => i.href === undefined)).toBe(true);
  });
});

describe('mounting', () => {
  const element = (tag) => ({
    tag,
    textContent: '',
    classList: { added: [], add(name) { this.added.push(name); } },
  });

  const fakeDocument = ({ footers = [], repoLinks = [] } = {}) => ({
    createElement: element,
    querySelectorAll: (selector) => (selector === '[data-site-footer]' ? footers : repoLinks),
  });
  const footer = () => ({ ...element('footer'), children: [], replaceChildren(...kids) { this.children = kids; } });

  const build = { version: 'v1.2.0', commit: 'a1b2c3d4', built: '2026-11-19T15:30:00Z' };
  const options = { locale: 'en-GB', repo: REPO, page: '/', userAgent: 'UA' };

  it('fills every footer, with links that open in a new tab safely', () => {
    const footers = [footer(), footer()];
    mountFooters(fakeDocument({ footers }), build, options);

    for (const f of footers) {
      expect(f.classList.added).toEqual(['site-footer']);
      expect(f.title).toContain('Version: v1.2.0');
      expect(f.children.map((c) => c.textContent)).toEqual(['Monka Games', 'v1.2.0', 'a1b2c3d', 'built 19 Nov 2026', 'Source', 'Report an issue']);
      const links = f.children.filter((c) => c.tag === 'a');
      expect(links.length).toBe(4);
      expect(links.every((l) => l.target === '_blank' && l.rel === 'noopener noreferrer')).toBe(true);
      expect(f.children[0].tag).toBe('span');
    }
  });

  it('points links in the page into the repository', () => {
    const link = { dataset: { repo: '/blob/HEAD/LICENSE' }, hidden: false, href: '' };
    mountFooters(fakeDocument({ repoLinks: [link] }), build, options);
    expect(link.href).toBe(`${REPO}/blob/HEAD/LICENSE`);
    expect(link.hidden).toBe(false);
  });

  it('hides those links when there is no repository', () => {
    const link = { dataset: { repo: '/blob/HEAD/LICENSE' }, hidden: false, href: '' };
    mountFooters(fakeDocument({ repoLinks: [link] }), build, { ...options, repo: '' });
    expect(link.hidden).toBe(true);
  });
});

describe('telling a release from a build after it', () => {
  it('links a real pre-release but not git describe output', () => {
    expect(releaseUrl(REPO, 'v1.2.0-rc.1')).not.toBeNull();
    expect(releaseUrl(REPO, 'v1.2.0-beta.2')).not.toBeNull();
    expect(releaseUrl(REPO, 'v1.2.0-3-ga1b2c3d')).toBeNull();
    expect(releaseUrl(REPO, 'v1.2.0-3-ga1b2c3d-dirty')).toBeNull();
    expect(releaseUrl(REPO, 'v1.2.0-dirty')).toBeNull();
  });
});
