# ──────────────────────────────────────────────────────────────────────────────
# Discord Music Bot — Production Dockerfile
# Single-stage build on python:3.11-slim-bookworm.
# Keeps image lean while installing all native deps needed for voice audio.
# ──────────────────────────────────────────────────────────────────────────────

FROM python:3.11-slim-bookworm

# ── Build-time labels ──────────────────────────────────────────────────────
LABEL maintainer="Music Bot"
LABEL description="Discord music bot with yt-dlp, FFmpeg, and FastAPI dashboard"

# ── Environment ────────────────────────────────────────────────────────────
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    # Tells aiosqlite / stats_manager where to write the DB (override via compose)
    DB_PATH=/data/music_bot.db

# ── System dependencies ────────────────────────────────────────────────────
# ffmpeg     — audio transcoding for Discord voice
# libopus0   — Opus codec shared library (discord.py voice requirement)
# libsodium23 — NaCl/PyNaCl cryptography for voice encryption
# curl       — used by the docker-compose healthcheck
# procps     — ps/pgrep used by the Dockerfile HEALTHCHECK
# ca-certificates — needed for HTTPS calls to YouTube / Spotify APIs
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libopus0 \
        libsodium23 \
        curl \
        procps \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# ── Non-root user ──────────────────────────────────────────────────────────
RUN useradd -m -u 1000 -s /bin/bash botuser \
    && mkdir -p /app /data \
    && chown -R botuser:botuser /app /data

WORKDIR /app

# ── Python dependencies ────────────────────────────────────────────────────
# Copy requirements first so Docker can cache the pip layer independently
# from the application code.
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# ── Application code ───────────────────────────────────────────────────────
COPY --chown=botuser:botuser . .

# ── Switch to non-root ─────────────────────────────────────────────────────
USER botuser

# ── Expose dashboard port ──────────────────────────────────────────────────
EXPOSE 5000

# ── Health check ────────────────────────────────────────────────────────────
# Verifies bot.py process is running; retries 3× before marking unhealthy.
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
    CMD pgrep -f "python bot.py" > /dev/null || exit 1

# ── Default command ────────────────────────────────────────────────────────
CMD ["python", "bot.py"]
