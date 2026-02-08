# Docker Deployment Guide

This guide provides detailed instructions for deploying the Discord Music Bot using Docker.

## 📋 Table of Contents

- [Prerequisites](#prerequisites)
- [Quick Start](#quick-start)
- [Configuration](#configuration)
- [Advanced Usage](#advanced-usage)
- [Production Deployment](#production-deployment)
- [Maintenance](#maintenance)
- [Troubleshooting](#troubleshooting)

## Prerequisites

### Required Software

- **Docker**: Version 20.10 or higher
  - [Install Docker on Windows](https://docs.docker.com/desktop/install/windows-install/)
  - [Install Docker on macOS](https://docs.docker.com/desktop/install/mac-install/)
  - [Install Docker on Linux](https://docs.docker.com/engine/install/)
  
- **Docker Compose**: Version 2.0 or higher
  - Included with Docker Desktop (Windows/macOS)
  - [Install on Linux](https://docs.docker.com/compose/install/)

### Required Credentials

- **Discord Bot Token** (Required)
  - Create at [Discord Developer Portal](https://discord.com/developers/applications)
  - Enable "Message Content Intent" under Bot settings
  
- **Spotify Credentials** (Optional)
  - Create at [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
  - Required only for Spotify playlist support

## Quick Start

### 1. Clone the Repository

```bash
git clone https://github.com/Amit-Kumar-Keshri/Music-DC-bot.git
cd Music-DC-bot
```

### 2. Configure Environment Variables

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your credentials
# Windows: notepad .env
# macOS/Linux: nano .env
```

**Minimum Required Configuration (.env)**:
```env
DISCORD_TOKEN=your_actual_discord_bot_token_here
```

**Full Configuration with Spotify (.env)**:
```env
DISCORD_TOKEN=your_discord_bot_token
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
SPOTIPY_REDIRECT_URI=http://localhost:8888/callback
DEFAULT_PREFIX=!
DEFAULT_VOLUME=0.5
```

### 3. Start the Bot

```bash
# Start in background
docker-compose up -d

# View logs
docker-compose logs -f
```

### 4. Verify Services

```bash
# Check service status
docker-compose ps

# Expected output:
# NAME                    STATUS              PORTS
# discord-music-bot       Up (healthy)        
# music-bot-dashboard     Up (healthy)        0.0.0.0:5000->5000/tcp
```

### 5. Access Dashboard

Open your browser to: `http://localhost:5000`

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DISCORD_TOKEN` | ✅ Yes | - | Your Discord bot token |
| `SPOTIPY_CLIENT_ID` | ❌ No | - | Spotify API client ID |
| `SPOTIPY_CLIENT_SECRET` | ❌ No | - | Spotify API client secret |
| `SPOTIPY_REDIRECT_URI` | ❌ No | `http://localhost:8888/callback` | Spotify OAuth redirect |
| `DEFAULT_PREFIX` | ❌ No | `!` | Command prefix |
| `DEFAULT_VOLUME` | ❌ No | `0.5` | Default playback volume (0.1-2.0) |
| `IDLE_TIMEOUT` | ❌ No | `300` | Idle timeout in seconds |
| `ALONE_TIMEOUT` | ❌ No | `60` | Auto-leave timeout when alone |

### Volume Configuration

The docker-compose setup creates three persistent volumes:

| Volume | Purpose | Can Delete? |
|--------|---------|-------------|
| `bot-logs` | Error and info logs | Yes (regenerates) |
| `bot-stats` | Usage statistics | No (data loss) |
| `bot-cache` | Audio file cache | Yes (performance impact) |

**View volumes**:
```bash
docker volume ls | grep music-dc-bot
```

**Inspect volume**:
```bash
docker volume inspect music-dc-bot_bot-stats
```

## Advanced Usage

### Development Mode

Enable hot-reload for code changes without rebuilding:

1. Uncomment volume mounts in `docker-compose.yml`:
```yaml
volumes:
  - ./bot.py:/app/bot.py:ro
  - ./commands:/app/commands:ro
  - ./audio:/app/audio:ro
  - ./utils:/app/utils:ro
```

2. Restart services:
```bash
docker-compose up -d
```

### Custom Port Mapping

Change the dashboard port in `docker-compose.yml`:

```yaml
ports:
  - "8080:5000"  # Access at http://localhost:8080
```

### Resource Limits

Default limits are configured in `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '1.0'        # 1 CPU core max
      memory: 512M       # 512MB RAM max
    reservations:
      memory: 256M       # 256MB guaranteed
```

Adjust based on your server capacity.

### Building Custom Image

```bash
# Build with custom tag
docker build -t my-music-bot:v1.0 .

# Build with no cache (clean build)
docker build --no-cache -t music-bot:latest .

# Build for specific platform
docker build --platform linux/amd64 -t music-bot:latest .
```

## Production Deployment

### Option 1: VPS with Docker

**Recommended for**: Full control, custom domains

```bash
# On your VPS
git clone https://github.com/Amit-Kumar-Keshri/Music-DC-bot.git
cd Music-DC-bot

# Configure environment
cp .env.example .env
nano .env  # Add your tokens

# Start services
docker-compose up -d

# Enable auto-start on boot
# Create systemd service or use docker restart policy (already configured)
```

**Expose Dashboard with Reverse Proxy (Nginx)**:

```nginx
server {
    listen 80;
    server_name bot.yourdomain.com;
    
    location / {
        proxy_pass http://localhost:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

### Option 2: Cloud Platforms

#### Railway

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login and deploy
railway login
railway init
railway up
```

#### DigitalOcean App Platform

1. Connect GitHub repository
2. Select "Dockerfile" as build method
3. Add environment variables in dashboard
4. Deploy

#### AWS ECS/Fargate

```bash
# Push image to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account>.dkr.ecr.us-east-1.amazonaws.com
docker tag music-bot:latest <account>.dkr.ecr.us-east-1.amazonaws.com/music-bot:latest
docker push <account>.dkr.ecr.us-east-1.amazonaws.com/music-bot:latest

# Deploy via ECS console or CLI
```

### Option 3: Kubernetes

Create deployment manifests:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: music-bot
spec:
  replicas: 1
  selector:
    matchLabels:
      app: music-bot
  template:
    metadata:
      labels:
        app: music-bot
    spec:
      containers:
      - name: bot
        image: music-bot:latest
        env:
        - name: DISCORD_TOKEN
          valueFrom:
            secretKeyRef:
              name: bot-secrets
              key: discord-token
```

## Maintenance

### Updating the Bot

```bash
# Pull latest code
git pull origin main

# Rebuild and restart
docker-compose build
docker-compose up -d

# View new logs
docker-compose logs -f
```

### Backup Data

```bash
# Backup stats volume
docker run --rm \
  -v music-dc-bot_bot-stats:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/stats-backup-$(date +%Y%m%d).tar.gz -C /data .

# Backup logs
docker run --rm \
  -v music-dc-bot_bot-logs:/data \
  -v $(pwd):/backup \
  alpine tar czf /backup/logs-backup-$(date +%Y%m%d).tar.gz -C /data .
```

### Restore Data

```bash
# Restore stats
docker run --rm \
  -v music-dc-bot_bot-stats:/data \
  -v $(pwd):/backup \
  alpine sh -c "cd /data && tar xzf /backup/stats-backup-20260209.tar.gz"
```

### Clean Up Old Data

```bash
# Remove cache volume (frees space)
docker-compose down
docker volume rm music-dc-bot_bot-cache
docker-compose up -d

# Remove old logs
docker exec discord-music-bot sh -c "find /app/logs -name '*.log' -mtime +30 -delete"
```

### Monitoring

**Check resource usage**:
```bash
docker stats discord-music-bot music-bot-dashboard
```

**Health checks**:
```bash
# Service status
docker-compose ps

# Health check logs
docker inspect discord-music-bot --format='{{json .State.Health}}' | jq
```

## Troubleshooting

### Bot Not Starting

**Check logs first**:
```bash
docker-compose logs bot
```

**Common issues**:

1. **Invalid Token**:
   ```
   Error: Improper token has been passed
   ```
   - Verify `DISCORD_TOKEN` in `.env`
   - Ensure no extra spaces or quotes

2. **Missing Dependencies**:
   ```bash
   # Rebuild with no cache
   docker-compose build --no-cache
   docker-compose up -d
   ```

3. **Permission Errors**:
   ```bash
   # Check file ownership
   ls -la .env
   
   # Fix permissions
   chmod 644 .env
   ```

### Dashboard Not Accessible

**Check if port is in use**:
```bash
# Windows
netstat -ano | findstr :5000

# macOS/Linux
lsof -i :5000
```

**Try different port**:
```yaml
# In docker-compose.yml
ports:
  - "5001:5000"
```

**Force recreate**:
```bash
docker-compose up -d --force-recreate dashboard
```

### Audio Playback Issues

**FFmpeg errors**:
```bash
# Verify FFmpeg installation
docker exec discord-music-bot ffmpeg -version

# If missing, rebuild
docker-compose build --no-cache
```

**yt-dlp update**:
```bash
# Update yt-dlp in running container
docker exec discord-music-bot pip install --upgrade yt-dlp

# For permanent fix, rebuild image
```

**Clear cache**:
```bash
docker volume rm music-dc-bot_bot-cache
docker-compose up -d
```

### High Memory Usage

**Check stats**:
```bash
docker stats discord-music-bot --no-stream
```

**Reduce resource usage**:
```yaml
# In docker-compose.yml
deploy:
  resources:
    limits:
      memory: 256M  # Reduce from 512M
```

**Restart services**:
```bash
docker-compose restart
```

### Network Issues

**DNS problems**:
```bash
# Test connectivity
docker exec discord-music-bot ping -c 3 discord.com
docker exec discord-music-bot ping -c 3 youtube.com
```

**Update DNS**:
```yaml
# In docker-compose.yml, add to bot service:
dns:
  - 8.8.8.8
  - 8.8.4.4
```

### Volume Corruption

**Reset volumes**:
```bash
# WARNING: This deletes all data!
docker-compose down -v
docker-compose up -d
```

**Selective reset**:
```bash
# Only reset cache
docker volume rm music-dc-bot_bot-cache
```

## Getting Help

- **GitHub Issues**: [Report bugs or request features](https://github.com/Amit-Kumar-Keshri/Music-DC-bot/issues)
- **Docker Docs**: [Official Docker documentation](https://docs.docker.com/)
- **Discord.py Docs**: [Discord.py documentation](https://discordpy.readthedocs.io/)

## Performance Tips

1. **Use SSD storage** for volumes
2. **Allocate sufficient RAM** (512MB minimum recommended)
3. **Keep Docker updated** to latest stable version
4. **Enable BuildKit** for faster builds:
   ```bash
   export DOCKER_BUILDKIT=1
   docker-compose build
   ```
5. **Prune unused data** regularly:
   ```bash
   docker system prune -a --volumes
   ```
