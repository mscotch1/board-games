# Build the client with Vite
FROM node:24-slim AS client
WORKDIR /client
COPY client/package.json client/package-lock.json ./
RUN npm ci
COPY client/ ./
RUN npm run build

# The server, with the built client
FROM python:3.12-slim
WORKDIR /app

# Install dependencies first so they are cached between code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py ./
COPY --from=client /client/dist ./client/dist

# Games are saved here so they survive a restart; mount a volume on it to keep them
# across container replacements.
ENV DATA_DIR=/data
RUN mkdir -p /data
VOLUME /data

EXPOSE 5000

# Games are held in this process (and saved to DATA_DIR), so this must stay a single worker.
# Concurrency comes from threads; simple-websocket handles websocket upgrades.
CMD ["gunicorn", "--workers", "1", "--threads", "100", "--bind", "0.0.0.0:5000", "app:app"]
