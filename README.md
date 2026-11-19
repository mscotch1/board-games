# Monka Games

Two-player board games played in the browser: Camelot, and its pocket cousin Cam.

A Flask + Socket.IO server owns each game (it knows the rules and validates every
move); the client is a small Vite-built page that draws the board and sends moves.

## Camelot rules

Camelot follows the [World Camelot Federation's official rules](http://www.worldcamelotfederation.com/Camelot_Rules.htm).
Each side has 10 men and 4 knights on a 160-square board. White moves first; the creator of a game picks
a side (or leaves it random), and *Play again* swaps colours.

- **Plain move:** one step to an adjacent empty square.
- **Canter:** jump over an adjacent friendly piece, which stays on the board. A canter can't begin and
  end on the same square.
- **Jump:** jump over an adjacent enemy piece to capture it. **Capturing is mandatory**, and a chain of
  jumps must be completed while the piece can still jump (except as noted for castles). If several captures
  are possible you may choose between them.
- **Knight's charge:** a knight may canter (any number of times) and then jump. Men can chain canters or
  chain jumps, but not mix them.
- **Your own castle:** you can't plain-move or canter into it, but you can jump into it. A piece that jumps
  in and can't jump on must leave on your next turn, ahead of any other move, and must jump out if it can.
- **The enemy castle:** a piece that enters it ends its turn there and can never come out. Each player may
  move a piece from one castle square to the other twice in the whole game.
- **Winning:** move two pieces into the enemy castle; or capture every enemy piece while keeping at least
  two of your own; or leave your opponent with no legal move while you have at least two pieces.
- **Draws:** by agreement (offer and accept in the game panel); automatically when both sides are down to
  one piece or fewer; and either player can claim one when the same position has come up for the third
  time with the same player to move, or when fifty moves each have passed with no capture and no piece
  reaching a castle.

## Cam rules

Cam is Parker Brothers' 1949 miniature of Camelot (rules from the
[World Camelot Federation](http://www.worldcamelotfederation.com/Cam_Rules.htm)). Moves, canters, jumps,
knight's charges and mandatory capture are the same as in Camelot. What differs:

- **Board:** 67 squares (7 files, 13 ranks) with a single castle square at each end, D1 and D13.
- **Pieces:** 2 knights and 5 men a side.
- **Winning:** move any one piece into the enemy castle (the turn ends the moment it gets there), or
  capture every enemy piece.
- **Your own castle:** you can't plain-move or canter into it, but you can jump into it. A piece that
  jumps in and can't jump on must leave on your next turn, ahead of any other move (jumping out if it can).

## Adding a variant

Boards, starting positions and the few rule options live in `variants.py`; the rules engine in `rules.py`
takes a `Variant` and nothing else is board-specific, so the client draws whatever board the server sends.
A new variant is a `Variant(...)` entry plus tests, and a choice in the lobby.

## Interpretation choices

Where the official text leaves room, these are the calls made:

- A piece can't canter over the same friendly piece twice in one turn. The rules don't say, but without a
  limit a canter could loop forever.
- "Twice during the game" for castle moves is counted per player, not per piece.
- If a player has no legal move and the other has fewer than two pieces, the game is drawn (the rules give
  neither a win nor a draw for that case).
- Position repetition compares the board and whose turn it is, and either player may claim at any time
  while the position stands.
- Cam, per its rules, has no draws, and a blocked player simply loses.

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
