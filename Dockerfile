FROM python:3.13-slim-bookworm

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Docker CLI/daemon for Manim container renders; ffmpeg not required in the bot image.
RUN apt-get update && apt-get install -y --no-install-recommends \
    docker.io \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
COPY discordmanimator ./discordmanimator

RUN pip install --no-cache-dir .

COPY scripts/zeabur-entrypoint.sh /usr/local/bin/zeabur-entrypoint.sh
RUN chmod +x /usr/local/bin/zeabur-entrypoint.sh

# Zeabur injects PORT at runtime; the bot binds there for health checks.
ENV PORT=8080
EXPOSE 8080

ENTRYPOINT ["/usr/local/bin/zeabur-entrypoint.sh"]
