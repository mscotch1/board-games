import { execSync } from 'node:child_process';
import { resolve } from 'node:path';
import { defineConfig } from 'vite';

/** The output of a git command, or '' when git (or a repository) isn't there, as in the Docker build. */
function git(args) {
  try {
    return execSync(`git ${args}`, { stdio: ['ignore', 'pipe', 'ignore'] }).toString().trim();
  } catch {
    return '';
  }
}

// What the footer says about this build. The Docker build has no git history, so
// the release workflow hands these in as APP_VERSION, APP_COMMIT and APP_BUILT;
// anywhere else they come from git, or fall back to "dev".
const build = {
  version: process.env.APP_VERSION || git('describe --tags --always --dirty') || 'dev',
  commit: process.env.APP_COMMIT || git('rev-parse HEAD'),
  built: process.env.APP_BUILT || new Date().toISOString(),
};

export default defineConfig({
  define: {
    __BUILD__: JSON.stringify(build),
  },
  build: {
    rollupOptions: {
      // every game is its own page; add new games here
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        camelot: resolve(import.meta.dirname, 'games/camelot/index.html'),
        rules: resolve(import.meta.dirname, 'games/camelot/rules/index.html'),
      },
    },
  },
  server: {
    // run `python app.py` next to `npm run dev`; the page talks to it through here
    proxy: {
      '/socket.io': { target: 'http://localhost:5000', ws: true },
      '/healthz': 'http://localhost:5000',
      '/version': 'http://localhost:5000',
    },
  },
  test: {
    include: ['src/**/*.test.js'],
  },
});
