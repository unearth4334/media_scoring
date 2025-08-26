# Docker Deployment Guide

This guide explains how to deploy the Video & Image Scorer in a Docker container, specifically configured for QNAP NAS deployment.

## Quick Start

1. **Clone the repository** to your QNAP NAS or local machine:
   ```bash
   git clone https://github.com/unearth4334/media_scoring.git
   cd media_scoring
   ```

2. **Copy and configure environment file**:
   ```bash
   cp .env.example .env
   ```
   
3. **Edit `.env` file** to match your setup:
   ```bash
   # Path to your media files on the NAS
   MEDIA_PATH=/share/sd/SecretFolder
   
   # Port to expose (default: 7862)
   HOST_PORT=7862
   
   # User/Group IDs for NAS file access (usually 0 for admin access)
   PUID=0
   PGID=0
   
   # Media patterns to scan
   MEDIA_PATTERN="*.mp4|*.png|*.jpg"
   
   # Enable thumbnail generation
   GENERATE_THUMBNAILS=true
   ```

4. **Build and start the container**:
   ```bash
   docker-compose up -d
   ```

5. **Access the web interface**:
   Open your browser and navigate to `http://your-nas-ip:7862`

## Docker Files Explanation

### Dockerfile
- Based on Python 3.11 slim image
- Installs system dependencies: `ffmpeg` for video processing, `curl` for health checks
- Installs Python dependencies from `requirements.txt`
- Exposes port 7862
- Sets up proper permissions for NAS access

### docker-compose.yml
Basic deployment configuration with:
- Volume mapping for media files: `/share/sd/SecretFolder:/media`
- PUID/PGID environment variables for file permissions
- Named volumes for application data (scores, thumbnails, workflows)
- Auto-restart policy

### docker-compose.override.yml
Advanced configuration with environment variable support:
- Configurable media path via `MEDIA_PATH`
- Configurable host port via `HOST_PORT` 
- All settings can be overridden via `.env` file

## Volume Mappings

| Host Path | Container Path | Purpose |
|-----------|----------------|---------|
| `/share/sd/SecretFolder` | `/media` | Your media files |
| `./config` | `/app/config` | Configuration files (optional) |
| `scores_data` | `/app/.scores` | Score data and logs |
| `thumbnails_data` | `/app/.thumbnails` | Generated thumbnails |
| `workflows_data` | `/app/workflows` | Extracted workflows |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | `0` | User ID for file permissions |
| `PGID` | `0` | Group ID for file permissions |
| `MEDIA_PATH` | `/share/sd/SecretFolder` | Path to media files on host |
| `HOST_PORT` | `7862` | Port to expose on host |
| `MEDIA_PATTERN` | `*.mp4\|*.png\|*.jpg` | File patterns to scan |
| `GENERATE_THUMBNAILS` | `true` | Enable thumbnail generation |

## QNAP NAS Specific Setup

### File Permissions
On QNAP NAS systems, you typically need root-level access to read files from shared folders. The configuration uses:
```yaml
environment:
  - PUID=0  # Root user
  - PGID=0  # Root group
```

### Media Path
Update the media path in your `.env` file to match your NAS share structure:
```bash
# Example QNAP paths:
MEDIA_PATH=/share/CACHEDEV1_DATA/Multimedia
MEDIA_PATH=/share/HDA_DATA/Videos
MEDIA_PATH=/share/sd/SecretFolder  # Your specific path
```

### Network Access
Ensure the Docker container can be accessed from your network:
- The service binds to `0.0.0.0:7862` inside the container
- Access via `http://your-nas-ip:7862` from other devices
- Configure QNAP firewall if needed to allow port 7862

## Manual Docker Commands

If you prefer not to use docker-compose:

```bash
# Build the image
docker build -t media-scorer .

# Run the container
docker run -d \
  --name media-scorer \
  -p 7862:7862 \
  -v /share/sd/SecretFolder:/media \
  -v scores_data:/app/.scores \
  -v thumbnails_data:/app/.thumbnails \
  -v workflows_data:/app/workflows \
  -e PUID=0 \
  -e PGID=0 \
  --restart unless-stopped \
  media-scorer
```

## Troubleshooting

### Permission Issues
If you encounter permission errors accessing files:
1. Verify PUID/PGID settings match your NAS user
2. Check that the media path exists and is readable
3. For QNAP, you may need PUID=0 and PGID=0 for admin access

### Port Conflicts
If port 7862 is already in use:
1. Change `HOST_PORT` in your `.env` file
2. Update firewall rules if necessary
3. Restart the container with `docker-compose restart`

### Container Logs
View container logs for debugging:
```bash
docker-compose logs -f media-scorer
```

### Container Shell Access
Access the container for debugging:
```bash
docker exec -it media-scorer /bin/bash
```

## Updating

To update the application:
```bash
git pull
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Data Persistence

Application data is stored in named Docker volumes:
- **scores_data**: Contains `.scores/` directory with rating data and logs
- **thumbnails_data**: Contains `.thumbnails/` directory with generated preview images  
- **workflows_data**: Contains `workflows/` directory with extracted ComfyUI workflow JSONs

These volumes persist even when the container is removed, ensuring your data is safe during updates.