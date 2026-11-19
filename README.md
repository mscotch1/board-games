# Monka Games

Two-player board games played in the browser. Right now there is one game, Camelot.

A Flask + Socket.IO server owns each game (it knows the rules and validates every
move); the client is a small Vite-built page that draws the board and sends moves.

## Camelot rules

Each side has 10 men and 4 knights. White moves first; the creator of a game picks
a side (or leaves it random), and *Play again* swaps colours.

- **Plain move:** one step to an adjacent empty square.
- **Canter:** jump over an adjacent friendly piece. Cantered pieces stay on the board, and
  a piece can't canter over the same friend twice in a turn.
- **Jump:** jump over an adjacent enemy piece to capture it. **Capturing is mandatory**, and a
  chain of jumps must be completed while the piece can still jump. If several captures are
  possible you may choose between them.
- **Knight's charge:** a knight may canter (any number of times) and then jump. Men can chain
  canters or chain jumps, but not mix them.
- **Castles:** the two squares at each end. You can't make a plain move or canter into your own
  castle (a jump may land there), and a piece inside the enemy castle can only leave it by jumping.
- **Winning:** occupy both squares of the enemy castle, capture every enemy piece, or leave your
  opponent with no legal move.

## Development

Server (Python 3.10+):

```sh
pip install -r requirements-dev.txt
pytest
python app.py          # http://localhost:5000
```

Client (Node 24):

```sh
cd client
npm ci
npm test
npm run dev            # http://localhost:5173, proxies the socket to python app.py
npm run build          # writes client/dist, which app.py serves
```

## Running with Docker

Pushing a `v*` tag runs the tests and publishes `ghcr.io/mscotch1/board-games` with the tags
`1.2.3`, `1.2` and `latest`. With docker compose:

```yaml
services:
  board-games:
    image: ghcr.io/mscotch1/board-games:latest
    restart: unless-stopped
    ports:
      - "5000:5000"
    # environment:
    #   CORS_ALLOWED_ORIGINS: https://games.example.com   # only if a proxy rewrites the Host header
```

(If the package is private, `docker login ghcr.io` first.) The container serves everything on
port 5000 and has a `/healthz` endpoint.

Games live in memory, so the server **must run as a single worker** (the Dockerfile already does:
one gunicorn worker with 100 threads), and a restart ends every game in progress.

| Variable               | Purpose                                                                 |
| ---------------------- | ----------------------------------------------------------------------- |
| `CORS_ALLOWED_ORIGINS` | Comma separated origins allowed to open a socket, or `*`. Defaults to same-origin. |
| `STATIC_DIR`           | Where the built client is. Defaults to `client/dist`.                    |
