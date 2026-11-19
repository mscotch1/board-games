import { describe, expect, it } from 'vitest';
import { describeVersion, formatBuild, mountFooters } from './footer.js';

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

  it('follows the reader\'s language for the date', () => {
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

describe('mounting footers', () => {
  const fakeFooter = () => ({
    classList: { added: [], add(name) { this.added.push(name); } },
    textContent: '',
    title: '',
  });

  it('fills every footer on the page', () => {
    const footers = [fakeFooter(), fakeFooter()];
    const root = { querySelectorAll: () => footers };
    mountFooters(root, { version: '1.2.0', commit: 'a1b2c3d4', built: '2026-11-19T15:30:00Z' }, 'en-GB');

    for (const footer of footers) {
      expect(footer.textContent).toBe('Monka Games · v1.2.0 · a1b2c3d · built 19 Nov 2026');
      expect(footer.classList.added).toEqual(['site-footer']);
      expect(footer.title).toContain('Version: v1.2.0');
    }
  });

  it('drops the parts it doesn\'t know', () => {
    const footer = fakeFooter();
    mountFooters({ querySelectorAll: () => [footer] }, { version: 'dev', commit: '', built: '' }, 'en-GB');
    expect(footer.textContent).toBe('Monka Games · dev build');
  });
});
