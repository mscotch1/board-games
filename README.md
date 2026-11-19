# Monka Games

Two-player board games played in the browser: Camelot, and its pocket cousin Cam.

A Flask + Socket.IO server owns each game (it knows the rules, validates every
move and saves the game); the client is a small Vite-built page that draws the board and sends moves.

The rules are also on the site, with diagrams and links to further reading, at `/games/camelot/rules/`
(linked from the front page, the lobby and the game header).

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

## Leaving and coming back

Games are saved after every move, so nothing is lost to a reload, a dropped connection or a server restart.

- **Who you are:** the browser makes a secret token for each game and keeps it in `localStorage`; the server
  recognises it and puts you back in your seat, with the board, the chat and whose turn it is. The address
  bar keeps the game's code, so reloading or bookmarking the page returns to the game, and the menu lists
  your unfinished games with a *Resume* button. Two tabs can play the same seat at once.
- **Leaving doesn't end a game.** Your opponent just sees you as *away* and the game waits. If you want to
  quit, *Resign* (the opponent wins). There are no clocks.
- **Dropped connections** show a "reconnecting" banner and recover on their own.
- **Expiry:** a game nobody has touched for a while is deleted: 24 hours if still waiting for an opponent,
  7 days once started, and 24 hours after it finishes (so a result can still be looked at). A game with
  someone connected is never deleted. A creator can cancel a game nobody has joined.

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
    volumes:
      - board-games-data:/data   # saved games; without it a new container starts empty
    # environment:
    #   CORS_ALLOWED_ORIGINS: https://games.example.com   # only if a proxy rewrites the Host header

volumes:
  board-games-data:
```

(If the package is private, `docker login ghcr.io` first.) The container serves everything on
port 5000 and has a `/healthz` endpoint.

Games are held in the server's memory and saved to a SQLite file in `DATA_DIR` (`/data` in the image), so the
server **must run as a single worker** (the Dockerfile already does: one gunicorn worker with 100 threads).
Restarting or replacing the container keeps every game, as long as `/data` is a volume.

| Variable               | Purpose                                                                 |
| ---------------------- | ----------------------------------------------------------------------- |
| `CORS_ALLOWED_ORIGINS` | Comma separated origins allowed to open a socket, or `*`. Defaults to same-origin. |
| `STATIC_DIR`           | Where the built client is. Defaults to `client/dist`.                    |
| `DATA_DIR`             | Where games are saved. Defaults to `./data`; set it empty to keep games in memory only. |
| `WAITING_TTL_HOURS`    | Hours before a game nobody has joined is deleted. Default 24.            |
| `GAME_TTL_DAYS`        | Days of inactivity before a game in progress is deleted. Default 7.      |
| `FINISHED_TTL_HOURS`   | Hours a finished game is kept. Default 24.                               |
| `BACKUP_INTERVAL_HOURS` | Hours between backups of the saved games. Default 24; 0 turns backups off. |
| `BACKUP_KEEP`          | How many backups to keep (the newest). Default 7; 0 keeps them all.      |
| `BACKUP_DIR`           | Where backups go. Defaults to `backups/` inside `DATA_DIR`.               |
| `NEW_GAMES_PER_HOUR`   | How many new games one client address may start per hour (in bursts of up to 10). Default 30; 0 turns it off. |
| `MAX_GAMES`            | The most games kept at once; beyond that new games are turned away. Default 5000; 0 turns it off. |
| `CLIENT_IP_HEADER`     | The header holding the real client address when behind a proxy, e.g. `CF-Connecting-IP`. Only set it when the proxy is trusted to set it. |
| `HSTS_MAX_AGE`         | Seconds for a `Strict-Transport-Security` header. Off by default; turn it on once the site is served over HTTPS. |

## Backups

The saved games are backed up automatically, once a day by default: a complete, consistent copy of the database,
taken while the server runs, named by when it was made (`games-20261119-083000.sqlite3`), keeping the newest seven.
They go to `/data/backups`, which protects against corruption and mistakes but not against losing the volume itself, so
for real safety point `BACKUP_DIR` at a different disk (`BACKUP_DIR=/backups` with a second volume mounted there), or
sync the folder somewhere else. `/healthz` reports `lastBackup`, so a monitor can alert if backups stop.

To restore, stop the container, copy the backup over the live database, and start it again:

```sh
docker compose stop board-games
docker run --rm -v board-games-data:/data -v "$PWD":/from alpine \
  sh -c 'cp /from/games-20261119-083000.sqlite3 /data/games.sqlite3 && rm -f /data/games.sqlite3-wal /data/games.sqlite3-shm && chown 10001 /data/games.sqlite3'
docker compose start board-games
```

Players' tokens are in the saved games, so everyone can come back to their games as they were at the time of the backup.

## Security

- **Strict Content-Security-Policy** on every response: only this site's own scripts, styles, fonts and images,
  sockets back to the same host, no inline scripts or styles, no framing. Along with `X-Content-Type-Options`,
  `X-Frame-Options` and `Referrer-Policy`. (This is why the theme is set by a small file, `theme-init.js`, and not an
  inline script: don't add inline scripts or styles to the pages.)
- **Runs as an unprivileged user** (uid 10001) in the container. A named volume on `/data` just works; a bind-mounted
  host directory has to be writable by that uid (`chown 10001 ./data`). If it isn't, the server stops at startup and
  says so.
- **Limits** keep a public instance from being filled with junk: new games per client address per hour, a cap on the
  total games kept, and a cap on messages per connection per second (excess is ignored).

## Releasing

```sh
git tag v1.0.0
git push origin v1.0.0
```

The workflow tests the code, builds the image and publishes it to GHCR. The build is stamped with the tag, the
commit and the time (the `APP_VERSION`, `APP_COMMIT` and `APP_BUILT` build arguments), and that stamp appears:

- in the footer of every page: `Monka Games · v1.0.0 · a1b2c3d · built 19 Nov 2026` (hover for the full commit and time);
- at `/version`, as JSON, so you can check what a deployment is actually running;
- in `/healthz`, which also reports `status`, `uptimeSeconds`, the number of games by status and how many
  players are connected. It returns 503 if the saved games can't be read, and the image's `HEALTHCHECK` uses it,
  so `docker ps` shows `healthy` or `unhealthy`.

A build outside the release workflow (`npm run build`, a local `docker build`) says `dev build`, or uses
`git describe` when there is a repository.
