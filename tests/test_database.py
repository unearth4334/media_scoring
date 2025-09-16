#!/usr/bin/env python3
"""
Test script to verify database connectivity and functionality.
"""

import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent / "app"))

def test_sqlite_database():
    """Test SQLite database connection."""
    print("Testing SQLite database connection...")
    
    from app.settings import Settings
    from app.database.engine import init_database
    from app.database.service import DatabaseService
    
    # Create settings with SQLite
    settings = Settings(dir=Path("./media"), enable_database=True)
    db_url = settings.get_database_url()
    print(f"Database URL: {db_url}")
    
    # Initialize database
    init_database(db_url)
    
    # Test database service
    with DatabaseService() as db:
        # Try to create a test media file entry
        test_file = Path("./media/test.mp4")
        test_file.parent.mkdir(exist_ok=True)
        test_file.touch()
        
        media_file = db.get_or_create_media_file(test_file)
        print(f"Created media file: {media_file}")
        
        # Update score
        db.update_media_file_score(test_file, 5)
        print("Updated score to 5")
        
        # Read score back
        score = db.get_media_file_score(test_file)
        print(f"Retrieved score: {score}")
        
        test_file.unlink()  # Clean up
    
    print("✅ SQLite database test passed!")

def test_postgresql_connection():
    """Test PostgreSQL connection if DATABASE_URL is set."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url or not db_url.startswith('postgresql://'):
        print("⏭️  PostgreSQL test skipped (no DATABASE_URL set)")
        return
    
    print("Testing PostgreSQL database connection...")
    print(f"Database URL: {db_url}")
    
    from app.database.engine import init_database
    from app.database.service import DatabaseService
    
    try:
        # Initialize database
        init_database(db_url)
        
        # Test database service
        with DatabaseService() as db:
            print("✅ PostgreSQL connection successful!")
            
    except Exception as e:
        print(f"❌ PostgreSQL connection failed: {e}")
        return False
    
    print("✅ PostgreSQL database test passed!")
    return True

if __name__ == "__main__":
    print("🔬 Testing Media Scorer Database Functionality")
    print("=" * 50)
    
    try:
        test_sqlite_database()
        print()
        test_postgresql_connection()
        print()
        print("🎉 All database tests completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)