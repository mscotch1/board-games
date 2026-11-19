import { describe, expect, it } from 'vitest';
import { normalizeSiteUrl, pageUrl, siteMetaPlugin, siteMetaTags } from './site-meta.js';

describe('the site address', () => {
  it('is reduced to its origin', () => {
    expect(normalizeSiteUrl('https://games.example.com')).toBe('https://games.example.com');
    expect(normalizeSiteUrl('https://games.example.com/')).toBe('https://games.example.com');
    expect(normalizeSiteUrl('https://games.example.com/some/path?x=1#y')).toBe('https://games.example.com');
    expect(normalizeSiteUrl('http://localhost:5000/')).toBe('http://localhost:5000');
  });

  it('is optional', () => {
    expect(normalizeSiteUrl('')).toBeNull();
    expect(normalizeSiteUrl(undefined)).toBeNull();
  });

  it('must be a real web address, or the build says so', () => {
    expect(() => normalizeSiteUrl('games.example.com')).toThrow(/full address/);
    expect(() => normalizeSiteUrl('ftp://games.example.com')).toThrow(/https/);
    expect(() => normalizeSiteUrl('javascript:alert(1)')).toThrow(/https/);
  });
});

describe('page addresses', () => {
  it('drop index.html', () => {
    expect(pageUrl('https://s.example', '/index.html')).toBe('https://s.example/');
    expect(pageUrl('https://s.example', '/games/camelot/index.html')).toBe('https://s.example/games/camelot/');
    expect(pageUrl('https://s.example', '/games/camelot/rules/index.html')).toBe('https://s.example/games/camelot/rules/');
  });
});

describe('the tags', () => {
  const tags = siteMetaTags('https://s.example', '/games/camelot/index.html');
  const byKey = Object.fromEntries(tags.map((t) => [t.attrs.property ?? t.attrs.name ?? t.attrs.rel, t.attrs.content ?? t.attrs.href]));

  it('give the page its own absolute address', () => {
    expect(byKey.canonical).toBe('https://s.example/games/camelot/');
    expect(byKey['og:url']).toBe('https://s.example/games/camelot/');
  });

  it('point previews at the share image with its size', () => {
    expect(byKey['og:image']).toBe('https://s.example/og-image.png');
    expect(byKey['twitter:image']).toBe('https://s.example/og-image.png');
    expect(byKey['og:image:width']).toBe('1200');
    expect(byKey['og:image:height']).toBe('630');
  });

  it('go in the head', () => {
    expect(tags.every((t) => t.injectTo === 'head')).toBe(true);
  });
});

describe('the plugin', () => {
  it('adds the tags to each page', () => {
    const plugin = siteMetaPlugin('https://s.example/');
    const result = plugin.transformIndexHtml('<html></html>', { path: '/index.html' });
    expect(result.html).toBe('<html></html>');
    expect(result.tags.find((t) => t.attrs.property === 'og:url').attrs.content).toBe('https://s.example/');
  });

  it('does nothing without a site address', () => {
    expect(siteMetaPlugin('').transformIndexHtml('<html></html>', { path: '/index.html' })).toBe('<html></html>');
  });

  it('leaves the 404 page alone', () => {
    const plugin = siteMetaPlugin('https://s.example');
    expect(plugin.transformIndexHtml('<html></html>', { path: '/404.html' })).toBe('<html></html>');
  });

  it('fails the build for an unusable address', () => {
    expect(() => siteMetaPlugin('nonsense')).toThrow();
  });
});
