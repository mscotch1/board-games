// Tags that need the site's public address, added to every page at build time.
//
// Link previews (Open Graph, Twitter cards) and canonical links only work with absolute
// URLs, and the address isn't known until the site is deployed. So when the SITE_URL
// build setting is given (e.g. https://games.example.com) these tags are added; without it
// they are simply left out, and the pages work the same, just with plainer link previews.

/** The origin of `siteUrl` with nothing after it, or null if there isn't one. Throws for an unusable value. */
export function normalizeSiteUrl(siteUrl) {
  if (!siteUrl) {
    return null;
  }
  let url;
  try {
    url = new URL(siteUrl);
  } catch {
    throw new Error(`SITE_URL must be a full address like https://games.example.com, not "${siteUrl}"`);
  }
  if (url.protocol !== 'https:' && url.protocol !== 'http:') {
    throw new Error(`SITE_URL must start with https:// (or http://), not "${siteUrl}"`);
  }
  return url.origin;
}

/** The public address of a built page, e.g. "/games/camelot/index.html" -> "https://site/games/camelot/". */
export function pageUrl(origin, htmlPath) {
  return origin + htmlPath.replace(/index\.html$/, '');
}

/** The head tags (in Vite's tag format) for one page. */
export function siteMetaTags(origin, htmlPath) {
  const url = pageUrl(origin, htmlPath);
  const image = `${origin}/og-image.png`;
  return [
    { tag: 'link', attrs: { rel: 'canonical', href: url }, injectTo: 'head' },
    { tag: 'meta', attrs: { property: 'og:url', content: url }, injectTo: 'head' },
    { tag: 'meta', attrs: { property: 'og:image', content: image }, injectTo: 'head' },
    { tag: 'meta', attrs: { property: 'og:image:width', content: '1200' }, injectTo: 'head' },
    { tag: 'meta', attrs: { property: 'og:image:height', content: '630' }, injectTo: 'head' },
    { tag: 'meta', attrs: { name: 'twitter:image', content: image }, injectTo: 'head' },
  ];
}

/** A Vite plugin that adds those tags to every page (but not to the 404 page, which shouldn't be linked). */
export function siteMetaPlugin(siteUrl) {
  const origin = normalizeSiteUrl(siteUrl);
  return {
    name: 'site-meta',
    transformIndexHtml(html, context) {
      if (!origin || context.path === '/404.html') {
        return html;
      }
      return { html, tags: siteMetaTags(origin, context.path) };
    },
  };
}
