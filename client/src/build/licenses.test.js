import { describe, expect, it } from 'vitest';
import { findLicenseFile, formatNotices, productionPackages } from './licenses.js';

const lock = {
  packages: {
    '': { name: 'the-app', version: '1.0.0' },
    'node_modules/socket.io-client': { version: '4.8.4', license: 'MIT' },
    'node_modules/@fontsource/medievalsharp': { version: '5.3.0', license: 'OFL-1.1' },
    'node_modules/socket.io-client/node_modules/debug': { version: '4.4.3', license: 'MIT' },
    'node_modules/xmlhttprequest-ssl': { version: '2.1.2' },
    'node_modules/vite': { version: '8.0.0', license: 'MIT', dev: true },
    'node_modules/vitest': { version: '5.0.0', license: 'MIT', dev: true, peer: true },
    'node_modules/odd': { version: '1.0.0', license: { type: 'MIT' } },
  },
};

describe('the production packages', () => {
  const packages = productionPackages(lock);

  it('leave out the project itself and the development tools', () => {
    const names = packages.map((p) => p.name);
    expect(names).not.toContain('vite');
    expect(names).not.toContain('vitest');
    expect(names).not.toContain('');
  });

  it('are sorted by name, with scoped and nested packages named properly', () => {
    expect(packages.map((p) => p.name)).toEqual([
      '@fontsource/medievalsharp',
      'debug',
      'odd',
      'socket.io-client',
      'xmlhttprequest-ssl',
    ]);
  });

  it('carry their versions and licenses', () => {
    const byName = Object.fromEntries(packages.map((p) => [p.name, p]));
    expect(byName['socket.io-client']).toMatchObject({ version: '4.8.4', license: 'MIT' });
    expect(byName['@fontsource/medievalsharp'].license).toBe('OFL-1.1');
  });

  it('say nothing when a license isn\'t a plain string', () => {
    const byName = Object.fromEntries(packages.map((p) => [p.name, p]));
    expect(byName['xmlhttprequest-ssl'].license).toBeUndefined();
    expect(byName.odd.license).toBeUndefined();
  });

  it('cope with a lockfile that has no packages', () => {
    expect(productionPackages({})).toEqual([]);
  });
});

describe('finding a license file', () => {
  it('matches the usual names in any case', () => {
    for (const name of ['LICENSE', 'license', 'LICENSE.md', 'License.txt', 'LICENCE', 'COPYING']) {
      expect(findLicenseFile(['package.json', 'index.js', name])).toBe(name);
    }
  });

  it('ignores files that merely mention it', () => {
    expect(findLicenseFile(['package.json', 'license-checker.js', 'README.md', 'LICENSE-NOTES'])).toBeNull();
  });
});

describe('the notices file', () => {
  const packages = productionPackages(lock);
  const texts = { 'socket.io-client': 'The MIT License\n\nPermission is hereby granted...\n', debug: 'MIT again' };
  const notices = formatNotices(packages, (p) => texts[p.name] ?? null, 'Third-party software\n');

  it('starts with the header', () => {
    expect(notices.startsWith('Third-party software\n')).toBe(true);
  });

  it('has a section for every package, with its version and license', () => {
    expect(notices).toContain('socket.io-client 4.8.4\nLicense: MIT');
    expect(notices).toContain('@fontsource/medievalsharp 5.3.0\nLicense: OFL-1.1');
    expect(notices.split('='.repeat(78)).length - 1).toBe(packages.length * 2);
  });

  it('includes the license text', () => {
    expect(notices).toContain('Permission is hereby granted...');
  });

  it('is honest about a package that brought no license text', () => {
    expect(notices).toContain('xmlhttprequest-ssl 2.1.2\nLicense: not stated in the package');
    expect(notices).toContain('did not include a license file');
  });

  it('ends with a newline', () => {
    expect(notices.endsWith('\n')).toBe(true);
  });
});
