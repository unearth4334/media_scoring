#!/bin/bash

# Example: Complete workflow using the mining tool with the web application

echo "🗂️  Media Archive Data Mining & Web App Integration Example"
echo "========================================================="
echo ""

# Check if we have a test directory
if [[ ! -d "./media" ]]; then
    echo "❌ Error: ./media directory not found"
    echo "This example needs the sample media directory"
    exit 1
fi

echo "📁 Step 1: Test the archive with dry run"
echo "---------------------------------------"
./scripts/mine_archive.sh test ./media
echo ""

echo "💾 Step 2: Mine the archive data into database"
echo "---------------------------------------------"
./scripts/mine_archive.sh mine ./media
echo ""

echo "📊 Step 3: Check what was stored in the database"
echo "-----------------------------------------------"
source .venv/bin/activate
python -c "
from pathlib import Path
from app.database.engine import init_database
from app.database.service import DatabaseService

# Connect to the database created by the mining tool
init_database('sqlite:///media/.scores/media.db')

with DatabaseService() as db:
    stats = db.get_stats()
    print('Database Statistics:')
    print('=' * 30)
    for key, value in stats.items():
        print(f'{key:.<25} {value}')
    
    print('\nSample file records:')
    print('=' * 30)
    files = db.get_media_files_by_directory(Path('media'))[:3]
    for file in files:
        print(f'{file.filename} (score: {file.score}, type: {file.file_type})')
        
        # Show keywords for this file
        keywords = db.get_keywords_for_file(Path(file.file_path))
        if keywords:
            kw_list = [kw.keyword for kw in keywords]
            print(f'  Keywords: {kw_list}')
        print()
"
echo ""

echo "🌐 Step 4: Start the web application (will use the same database)"
echo "----------------------------------------------------------------"
echo "You can now run:"
echo "  python run.py --dir ./media --enable-database --port 7862"
echo ""
echo "Then visit: http://127.0.0.1:7862"
echo ""
echo "The web application will use the metadata and keywords extracted by the mining tool!"
echo "You can search for files using the /api/search/files endpoint or the web interface."
echo ""
echo "✅ Mining workflow complete!"
echo "Your archive data is now available for the Media Scoring application."