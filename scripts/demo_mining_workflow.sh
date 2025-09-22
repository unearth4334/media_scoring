#!/bin/bash

# =========================================================
# Media Archive Data Mining & Web App Integration Example
# =========================================================
#
# Usage:
#   ./workflow.sh <media_dir>
#       Run the full interactive workflow using the given media directory.
#
#   ./workflow.sh --help
#       Show this usage information.
#
# Examples:
#   ./workflow.sh ./media
#   ./workflow.sh /absolute/path/to/media
#
# Requirements:
#   - A Python virtual environment in ".venv" alongside this script.
#   - The "mine_archive.sh" helper script in the same directory.
#
# Workflow Steps:
#   1. Test the archive (dry run) with results saved in ./results
#   2. Mine the archive data into an SQLite database
#   3. Query the database and display statistics + sample records
#   4. Instructions to launch the web application
#
# =========================================================

# --- Resolve script directory regardless of caller's CWD ---
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/../.venv"
MINER="$SCRIPT_DIR/mine_archive.sh"

# --- Handle --help option ---
if [[ "$1" == "--help" || "$1" == "-h" ]]; then
    grep "^# " "$0" | sed 's/^# //'
    exit 0
fi

# --- Require media dir as CLI argument ---
if [[ -z "$1" ]]; then
    echo "❌ Error: Missing required argument <media_dir>"
    echo "Run './workflow.sh --help' for usage."
    exit 1
fi

# Normalize media dir (absolute path)
MEDIA_DIR="$(realpath "$1")"

# Check if media directory exists
if [[ ! -d "$MEDIA_DIR" ]]; then
    echo "❌ Error: $MEDIA_DIR directory not found"
    exit 1
fi

echo "🗂️  Media Archive Data Mining & Web App Integration Example"
echo "========================================================="
echo "Using media directory: $MEDIA_DIR"
echo ""

read -p "📁 Step 1: Test the archive with dry run. Continue? (y/n): " yn
case $yn in
    [Yy]* ) 
        echo "---------------------------------------"
        "$MINER" test "$MEDIA_DIR" --test-output-dir "$SCRIPT_DIR/results"
        echo ""
        ;;
    * ) echo "Skipped Step 1."; exit 0;;
esac

read -p "💾 Step 2: Mine the archive data into database. Continue? (y/n): " yn
case $yn in
    [Yy]* ) 
        echo "---------------------------------------------"
        "$MINER" mine "$MEDIA_DIR"
        echo ""
        ;;
    * ) echo "Skipped Step 2."; exit 0;;
esac

read -p "📊 Step 3: Check what was stored in the database. Continue? (y/n): " yn
case $yn in
    [Yy]* ) 
        echo "-----------------------------------------------"
        source "$VENV_DIR/bin/activate"
        python - <<EOF
from pathlib import Path
from app.database.engine import init_database
from app.database.service import DatabaseService
from app.settings import Settings
import os, sys

media_dir = Path("$MEDIA_DIR")

# Use the same database configuration logic as the application
settings = Settings.load_from_yaml()
settings.dir = media_dir

# Get the database URL using the same logic as the mining tool
db_url = settings.get_database_url()
print(f"Connecting to database: {db_url}")

# Connect to the database created by the mining tool
init_database(db_url)

with DatabaseService() as db:
    stats = db.get_stats()
    print('Database Statistics:')
    print('=' * 30)
    for key, value in stats.items():
        print(f'{key:.<25} {value}')
    
    print('\nSample file records:')
    print('=' * 30)
    files = db.get_media_files_by_directory(media_dir)[:3]
    for file in files:
        print(f'{file.filename} (score: {file.score}, type: {file.file_type})')
        
        keywords = db.get_keywords_for_file(Path(file.file_path))
        if keywords:
            kw_list = [kw.keyword for kw in keywords]
            print(f'  Keywords: {kw_list}')
        print()
EOF
        echo ""
        ;;
    * ) echo "Skipped Step 3."; exit 0;;
esac

echo "🌐 Step 4: Start the web application (will use the same database)"
echo "----------------------------------------------------------------"
echo "You can now run:"
echo "  python run.py --dir \"$MEDIA_DIR\" --enable-database --port 7862"
echo ""
echo "Then visit: http://127.0.0.1:7862"
echo ""
echo "The web application will use the metadata and keywords extracted by the mining tool!"
echo "You can search for files using the /api/search/files endpoint or the web interface."
echo ""
echo "✅ Mining workflow complete!"
echo "Your archive data is now available for the Media Scoring application."
echo "========================================================="
