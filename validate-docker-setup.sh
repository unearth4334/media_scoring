#!/bin/bash
# Docker setup validation script for QNAP NAS deployment

set -e

echo "🔍 Validating Docker setup for Media Scorer..."

# Check if Docker is available
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed or not in PATH"
    exit 1
fi

# Check if Docker Compose is available  
if ! command -v docker compose &> /dev/null && ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not available"
    exit 1
fi

echo "✅ Docker and Docker Compose are available"

# Validate Docker Compose configuration
echo "🔧 Validating Docker Compose configuration..."
if docker compose config --quiet; then
    echo "✅ Docker Compose configuration is valid"
else
    echo "❌ Docker Compose configuration has errors"
    exit 1
fi

# Check if .env file exists
if [ -f ".env" ]; then
    echo "✅ Environment file (.env) found"
    source .env
    echo "   📁 Media path: ${MEDIA_PATH:-/share/sd/SecretFolder}"
    echo "   🔌 Host port: ${HOST_PORT:-7862}"
    echo "   👤 PUID: ${PUID:-0}, PGID: ${PGID:-0}"
else
    echo "⚠️  No .env file found. Using defaults."
    echo "   💡 Consider copying .env.example to .env and customizing it"
fi

# Check if media directory exists (for local testing)
if [ -d "${MEDIA_PATH:-/share/sd/SecretFolder}" ]; then
    echo "✅ Media directory exists: ${MEDIA_PATH:-/share/sd/SecretFolder}"
else
    echo "⚠️  Media directory not found: ${MEDIA_PATH:-/share/sd/SecretFolder}"
    echo "   💡 This is normal if running on a different machine than your NAS"
fi

echo ""
echo "🚀 Ready to deploy! Run:"
echo "   docker compose up -d"
echo ""
echo "📖 For complete instructions, see DOCKER.md"