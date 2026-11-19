# Use an official Python runtime as a base image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Install dependencies first so they are cached between code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application files
COPY . .

# Expose the port the server listens on
EXPOSE 5000

# Game state lives in process memory, so this must stay a single worker.
# Concurrency comes from threads; simple-websocket handles websocket upgrades.
CMD ["gunicorn", "--workers", "1", "--threads", "100", "--bind", "0.0.0.0:5000", "app:app"]
