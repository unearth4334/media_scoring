#!/bin/bash

# =========================================================
# Media Archive Data Ingesting & Web App Integration Example
# =========================================================
#
# Usage:
#   ./injest.sh <media_dir> [--database-url <url>] [--pattern "<pat>"] [--no-view] [--verbose]
#       Run the full interactive workflow using the given media directory.
#       Optionally specify a PostgreSQL database URL for use outside containers.
#
#   ./injest.sh --help
#       Show this usage information.
#
# Examples:
#   ./injest.sh ./media
#   ./injest.sh /absolute/path/to/media
#   ./injest.sh ./media --database-url "postgresql://user:pass@host/db"
#   ./injest.sh ./media --pattern "*.mp4|*.png"
#   ./injest.sh ./media --no-view
#
# Requirements:
#   - A Python virtual environment in ".venv" alongside this script.
#   - The "ingest_archive.sh" helper script in the same directory.
#   - For PostgreSQL: A running PostgreSQL server and valid connection URL.
#
# Workflow Steps:
#   1. Test the archive (dry run) with results saved in ./results
#   2. Ingest the archive data into PostgreSQL database
#   3. Query the database and display statistics + sample records
#   4. Instructions to launch the web application
#
# =========================================================

set -euo pipefail

## Resolve script directory regardless of caller's CWD
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/../.venv"
INGESTER="$SCRIPT_DIR/ingest_archive.sh"

## Parse CLI arguments
MEDIA_DIR=""
DATABASE_URL=""
INGESTING_ARGS=()

while [[ $# -gt 0 ]]; do
    case "$1" in
        --database-url)
            [[ $# -ge 2 ]] || { echo "❌ --database-url requires a value"; exit 1; }
            DATABASE_URL="$2"
            INGESTING_ARGS+=("--database-url" "$2")
            shift 2
            ;;
        --pattern)
            [[ $# -ge 2 ]] || { echo "❌ --pattern requires a value"; exit 1; }
            INGESTING_ARGS+=("--pattern" "$2")
            shift 2
            ;;
        --no-view)
            INGESTING_ARGS+=("--no-view")
            shift
            ;;
        --verbose|-v)
            INGESTING_ARGS+=("--verbose")
            shift
            ;;
        --help|-h)
            sed -n '3,29p' "$0" | sed 's/^# //'
            exit 0
            ;;
        -*)
            echo "❌ Error: Unknown option: $1"
            echo "Run './injest.sh --help' for usage."
            exit 1
            ;;
        *)
            if [[ -z "$MEDIA_DIR" ]]; then
                MEDIA_DIR="$1"
                shift
            else
                echo "❌ Error: Multiple directories specified: '$MEDIA_DIR' and '$1'"
                echo "Run './injest.sh --help' for usage."
                exit 1
            fi
            ;;
    esac
done

# Require media dir as CLI argument
if [[ -z "$MEDIA_DIR" ]]; then
    echo "❌ Error: Missing required argument <media_dir>"
    echo "Run './injest.sh --help' for usage."
    exit 1
fi

# Normalize media dir (absolute path)
MEDIA_DIR="$(realpath "$MEDIA_DIR")"

# Check if media directory exists
if [[ ! -d "$MEDIA_DIR" ]]; then
    echo "❌ Error: $MEDIA_DIR directory not found"
    exit 1
fi

echo "🗂️  Media Archive Data Ingesting & Web App Integration"
echo "========================================================="
echo "Using media directory: $MEDIA_DIR"
if [[ -n "$DATABASE_URL" ]]; then
  echo "Database URL: (provided)"
fi
echo ""

read -p "📁 Step 1: Test the archive with dry run. Continue? (y/n): " yn
case $yn in
    [Yy]* ) 
        echo "---------------------------------------"
        # Save test artifacts under ./results
        "$INGESTER" test "$MEDIA_DIR" --test-output-dir "$SCRIPT_DIR/results" "${INGESTING_ARGS[@]}"
        echo ""
        ;;
    * ) echo "Skipped Step 1."; exit 0;;
esac

read -p "💾 Step 2: Ingest the archive data into database. Continue? (y/n): " yn
case $yn in
    [Yy]* ) 
        echo "---------------------------------------------"
        "$INGESTER" ingest "$MEDIA_DIR" "${INGESTING_ARGS[@]}"
        echo ""
        ;;
    * ) echo "Skipped Step 2."; exit 0;;
esac

read -p "📊 Step 3: Check what was stored in the database. Continue? (y/n): " yn
case $yn in
    [Yy]* ) 
        echo "-----------------------------------------------"
        # Activate venv if present (keeps parity with ingest scripts)
        if [[ -d "$VENV_DIR" ]]; then
          # shellcheck disable=SC1091
          source "$VENV_DIR/bin/activate"
        fi
        python - <<EOF
from pathlib import Path
from app.database.engine import init_database
from app.database.service import DatabaseService
import os, sys

media_dir = Path("$MEDIA_DIR")
database_url = "$DATABASE_URL"

# Determine database URL to use
if database_url:
    print(f"Using provided database URL: {database_url}")
    db_url = database_url
else:
    env_db_url = os.getenv('DATABASE_URL') or os.getenv('MEDIA_DB_URL')
    if env_db_url:
        print(f"Using database URL from environment: {env_db_url}")
        db_url = env_db_url
    else:
        print("❌ Error: No database URL provided.")
        print("Please provide --database-url or set DATABASE_URL environment variable.")
        print("PostgreSQL database is required for this workflow.")
        sys.exit(1)

# Connect to the database created by the ingesting tool
try:
    init_database(db_url)
    print(f"✅ Connected to database successfully")
except Exception as e:
    print(f"❌ Failed to connect to database: {e}")
    sys.exit(1)

with DatabaseService() as db:
    # High-level stats
    try:
        stats = db.get_stats()
    except Exception as e:
        print(f"⚠️  Could not read stats: {e}")
        stats = {}

    print('Database Statistics:')
    print('=' * 30)
    for key, value in (stats or {}).items():
        print(f'{key:.<25} {value}')

    # Sample records by directory (robust to missing caches)
    print('\\nSample file records:')
    print('=' * 30)
    files = []
    try:
        files = (db.get_media_files_by_directory(media_dir) or [])[:3]
    except Exception as e:
        print(f"⚠️  Skipping file sample: {e}")
        files = []

    for file in files:
        try:
            print(f'{file.filename} (score: {getattr(file, "score", None)}, type: {getattr(file, "file_type", None)})')
            try:
                keywords = db.get_keywords_for_file(Path(file.file_path)) or []
            except Exception:
                keywords = []
            if keywords:
                kw_list = [getattr(kw, "keyword", str(kw)) for kw in keywords]
                print(f'  Keywords: {kw_list}')
        except Exception as e:
            print(f"  ⚠️  Error printing record: {e}")
        print()
EOF
        echo ""
        ;;
    * ) echo "Skipped Step 3."; exit 0;;
esac

echo "🌐 Step 4: Start the web application (will use the same database)"
echo "----------------------------------------------------------------"
echo "You can now run:"
if [[ -n "$DATABASE_URL" ]]; then
    echo "  DATABASE_URL=\"$DATABASE_URL\" python run.py --dir \"$MEDIA_DIR\" --enable-database --port 7862"
else
    echo "  python run.py --dir \"$MEDIA_DIR\" --enable-database --port 7862"
fi
echo ""
echo "Then visit: http://127.0.0.1:7862"
echo ""
echo "The web application will use the metadata and keywords extracted by the ingesting tool!"
echo "You can search for files using the /api/search/files endpoint or the web interface."
echo ""
echo "✅ Ingest workflow complete!"
echo "========================================================="