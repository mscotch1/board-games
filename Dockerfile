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

COPY app.py game.py lobby.py rules.py ./
COPY --from=client /client/dist ./client/dist

EXPOSE 5000

# Game state lives in process memory, so this must stay a single worker.
# Concurrency comes from threads; simple-websocket handles websocket upgrades.
CMD ["gunicorn", "--workers", "1", "--threads", "100", "--bind", "0.0.0.0:5000", "app:app"]
