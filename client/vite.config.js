import { resolve } from 'node:path';
import { defineConfig } from 'vite';

export default defineConfig({
  build: {
    rollupOptions: {
      // every game is its own page; add new games here
      input: {
        main: resolve(import.meta.dirname, 'index.html'),
        camelot: resolve(import.meta.dirname, 'games/camelot/index.html'),
      },
    },
  },
  server: {
    // run `python app.py` next to `npm run dev`; the page talks to it through here
    proxy: {
      '/socket.io': { target: 'http://localhost:5000', ws: true },
      '/healthz': 'http://localhost:5000',
    },
  },
  test: {
    include: ['src/**/*.test.js'],
  },
});
