#!/bin/bash
# Demonstration script for testing the database service functionality

set -e

echo "🧪 Demonstrating Media Scorer Database Service"
echo "=============================================="

# Test SQLite database functionality
echo ""
echo "1️⃣  Testing SQLite Database (Local Development)"
echo "--------------------------------------------"
python test_database.py

# Show the Docker Compose services
echo ""
echo "2️⃣  Docker Compose Services Configuration"
echo "--------------------------------------"
echo "PostgreSQL service will be available at:"
echo "  Host: localhost"
echo "  Port: 5432"
echo "  Database: media_scoring"
echo "  Username: media_user"
echo "  Password: media_password"

echo ""
echo "3️⃣  Docker Compose Services"
echo "-------------------------"
docker compose config --services

echo ""
echo "4️⃣  Volume Configuration"
echo "---------------------"
echo "Persistent volumes:"
echo "  • postgres_data     - PostgreSQL database files"
echo "  • scores_data       - Score sidecar files" 
echo "  • thumbnails_data   - Generated thumbnails"
echo "  • workflows_data    - Workflow extraction outputs"

echo ""
echo "🚀 To start the full application with PostgreSQL:"
echo "   docker compose up -d"
echo ""
echo "🔍 To connect to the database with external tools:"
echo "   Host: localhost"
echo "   Port: 5432"
echo "   Database: media_scoring"
echo "   Username: media_user"
echo "   Password: media_password"
echo ""
echo "📊 Example psql connection:"
echo "   psql -h localhost -p 5432 -U media_user -d media_scoring"
echo ""
echo "✅ Database service implementation complete!"