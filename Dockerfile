# Base image
FROM python:3.12-slim

# Set working directory
WORKDIR /app

# Copy application code
COPY bot.py /app/
COPY ollama_access.py /app/

# Install dependencies
RUN pip install telethon aiohttp

# Expose volumes for logs and config
VOLUME ["/app/logs", "/app/config"]

# Start the bot
CMD ["python", "bot.py"]