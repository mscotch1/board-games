# Build the client with Vite
FROM node:24-slim AS client
WORKDIR /client
COPY client/package.json client/package-lock.json ./
RUN npm ci
COPY client/ ./

# What the footer says about this build. The release workflow passes these in; without
# them the footer says "dev build". They come after `npm ci` so the dependency layer stays cached.
ARG APP_VERSION=dev
ARG APP_COMMIT=
ARG APP_BUILT=
RUN npm run build

# The server, with the built client
FROM python:3.12-slim
WORKDIR /app

# Install dependencies first so they are cached between code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY --from=client /client/dist ./client/dist

# The same build details, for the /version and /healthz endpoints
ARG APP_VERSION=dev
ARG APP_COMMIT=
ARG APP_BUILT=
ENV APP_VERSION=${APP_VERSION} APP_COMMIT=${APP_COMMIT} APP_BUILT=${APP_BUILT}

# Games are saved here so they survive a restart; mount a volume on it to keep them
# across container replacements. Backups go in /data/backups unless BACKUP_DIR says otherwise.
ENV DATA_DIR=/data

# Run as an unprivileged user. The directory belongs to it, so a new named volume mounted
# on /data is writable; a bind-mounted host directory must be made writable for uid 10001.
RUN useradd --system --uid 10001 --no-create-home --shell /usr/sbin/nologin app \
 && mkdir -p /data \
 && chown app:app /data
VOLUME /data
USER app

EXPOSE 5000

# Healthy when the server answers and can read its saved games (python:slim has no curl)
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
  CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/healthz', timeout=4)"]

# Games are held in this process (and saved to DATA_DIR), so this must stay a single worker.
# Concurrency comes from threads; simple-websocket handles websocket upgrades.
# (gunicorn's heartbeat files go in /dev/shm, which is memory-backed and needs no extra permissions.)
CMD ["gunicorn", "--workers", "1", "--threads", "100", "--worker-tmp-dir", "/dev/shm", "--bind", "0.0.0.0:5000", "app:app"]
