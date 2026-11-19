// Sets the theme before the first paint, so a page never flashes the wrong one while the
// rest of the scripts load (shared/theme.js keeps it up to date afterwards). This is a
// plain file, not an inline script, so the Content-Security-Policy can forbid inline scripts.
try {
  var root = document.documentElement;
  var saved = localStorage.getItem('theme');
  if (saved !== 'light' && saved !== 'dark') {
    saved = matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  } else {
    root.dataset.theme = saved;
  }
  root.dataset.effective = saved;
} catch (e) {
  // storage or matchMedia unavailable: the stylesheet's own defaults apply
}
