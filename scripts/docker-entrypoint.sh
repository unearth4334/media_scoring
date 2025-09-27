#!/bin/bash
# Docker entrypoint script for Media Scorer
# Reads configuration from config.yml and environment variables
# Supports the same override hierarchy as the standalone scripts

set -e

# Change to app directory (use current dir if /app doesn't exist, for local testing)
if [ -d "/app" ]; then
    cd /app
else
    echo "Running in local mode (not in container)"
fi

# Handle thumbnail generation - check if environment variable is set
# Save the environment variable value before it gets overwritten by config reading
ENV_GENERATE_THUMBNAILS="${GENERATE_THUMBNAILS:-}"

# Read configuration from config.yml using the existing read_config.py utility
echo "Reading configuration from config.yml..."
if [ -f "config.yml" ]; then
    # Use the read_config.py script to get values in shell format
    eval "$(python tools/read_config.py --file config/config.yml --format sh)"
    echo "Config loaded: dir=$DIR, port=$PORT, host=$HOST, pattern=$PATTERN"
else
    echo "Warning: config/config.yml not found, using defaults"
    DIR="/media"
    PORT=7862
    HOST="127.0.0.1"
    PATTERN="*.mp4"
    STYLE="style_default.css"
    GENERATE_THUMBNAILS="false"
    THUMBNAIL_HEIGHT=64
fi

# Override with environment variables if they exist
# These come from docker-compose.yml which reads from .env
if [ -n "$MEDIA_PATH" ]; then
    DIR="$MEDIA_PATH"
    echo "Override: DIR=$DIR (from MEDIA_PATH env var)"
fi

if [ -n "$HOST_PORT" ]; then
    PORT="$HOST_PORT"
    echo "Override: PORT=$PORT (from HOST_PORT env var)"
fi

if [ -n "$MEDIA_PATTERN" ]; then
    PATTERN="$MEDIA_PATTERN"
    echo "Override: PATTERN=$PATTERN (from MEDIA_PATTERN env var)"
fi

# Handle thumbnail generation override from environment
if [ -n "$ENV_GENERATE_THUMBNAILS" ]; then
    # Environment variable was set
    if [ "$ENV_GENERATE_THUMBNAILS" = "true" ]; then
        THUMBNAIL_ARGS="--generate-thumbnails"
        echo "Override: thumbnail generation enabled (from env var)"
    else
        THUMBNAIL_ARGS=""
        echo "Override: thumbnail generation disabled (from env var)"
    fi
else
    # Use config.yml value
    if [ "$GENERATE_THUMBNAILS" = "true" ]; then
        THUMBNAIL_ARGS="--generate-thumbnails"
    else
        THUMBNAIL_ARGS=""
    fi
fi

# Add thumbnail height if thumbnails are enabled
if [ -n "$THUMBNAIL_ARGS" ]; then
    THUMBNAIL_ARGS="$THUMBNAIL_ARGS --thumbnail-height $THUMBNAIL_HEIGHT"
fi

# For Docker, we always bind to 0.0.0.0 to accept external connections
HOST="0.0.0.0"

# Build database arguments if DATABASE_URL is provided
DATABASE_ARGS=""
if [ -n "$DATABASE_URL" ]; then
    DATABASE_ARGS="--database-url $DATABASE_URL"
    echo "Using external database: $DATABASE_URL"
fi

# Start SSH daemon in the background
echo "Starting SSH daemon..."
/usr/sbin/sshd -D &

echo "Starting Media Scorer with:"
echo "  DIR: $DIR"
echo "  PORT: $PORT" 
echo "  HOST: $HOST"
echo "  PATTERN: $PATTERN"
echo "  STYLE: $STYLE"
echo "  THUMBNAIL_ARGS: $THUMBNAIL_ARGS"
echo "  DATABASE_ARGS: $DATABASE_ARGS"

# Start the application with the resolved configuration
exec python run.py \
    --dir "$DIR" \
    --port "$PORT" \
    --host "$HOST" \
    --pattern "$PATTERN" \
    --style "$STYLE" \
    $THUMBNAIL_ARGS \
    $DATABASE_ARGS