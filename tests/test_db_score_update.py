#!/usr/bin/env python3
"""Test database score updates directly."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.state import ApplicationState
from app.settings import Settings
from app.services.files import write_score

def test_database_score_update():
    """Test the complete score update workflow."""
    
    print("=== Testing Database Score Update ===\n")
    
    # Create settings
    settings = Settings(
        dir=Path('/media'),
        enable_database=True,
        database_url="postgresql://media_user:media_password@postgres:5432/media_scoring"
    )
    
    # Initialize state
    from app.state import init_state
    state = init_state(settings)
    print(f"Database enabled: {state.database_enabled}")
    
    if not state.database_enabled:
        print("❌ Database is not enabled!")
        return
    
    # Test file path (use a known file from API)
    test_filename = "00009-102810426.png"
    
    # First, find the file in the database
    try:
        with state.get_database_service() as db:
            from app.database.models import MediaFile
            media_file = db.session.query(MediaFile).filter(
                MediaFile.filename == test_filename
            ).first()
            
            if not media_file:
                print(f"❌ File '{test_filename}' not found in database")
                return
                
            print(f"Found file: {media_file.file_path}")
            print(f"Current score: {media_file.score}")
            
            # Test the update process
            test_score = 3
            file_path = Path(media_file.file_path)
            
            print(f"\nTesting write_score({file_path}, {test_score})...")
            
            # Call write_score function (this should update both sidecar and database)
            write_score(file_path, test_score)
            
            print("✅ write_score completed")
            
    except Exception as e:
        print(f"❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Now check if the score was actually updated
    try:
        with state.get_database_service() as db:
            from app.database.models import MediaFile
            updated_file = db.session.query(MediaFile).filter(
                MediaFile.filename == test_filename
            ).first()
            
            if updated_file:
                print(f"\nAfter update:")
                print(f"  Score in database: {updated_file.score}")
                print(f"  Expected score: {test_score}")
                
                if updated_file.score == test_score:
                    print("✅ Score update successful!")
                else:
                    print(f"❌ Score mismatch! Expected {test_score}, got {updated_file.score}")
            else:
                print("❌ File not found after update")
                
    except Exception as e:
        print(f"❌ Error checking updated score: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_database_score_update()
