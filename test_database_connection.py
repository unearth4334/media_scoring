#!/usr/bin/env python3
"""Test script to check database connection and identify issues."""

import os
import sys
import logging
from pathlib import Path

# Add the app directory to the path
sys.path.insert(0, str(Path(__file__).parent / "app"))

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

def test_database_connection():
    """Test database connection and report issues."""
    
    # Test 1: Check environment variables
    print("=== Environment Variables ===")
    database_url = os.getenv('DATABASE_URL')
    print(f"DATABASE_URL: {database_url}")
    
    if not database_url:
        print("❌ DATABASE_URL not set")
        return False
        
    # Test 2: Try to initialize database engine
    print("\n=== Database Engine Initialization ===")
    try:
        from app.database.engine import init_database
        init_database(database_url)
        print("✅ Database engine initialized successfully")
    except Exception as e:
        print(f"❌ Database engine initialization failed: {e}")
        return False
        
    # Test 3: Try to create database service
    print("\n=== Database Service Creation ===")
    try:
        from app.database.service import DatabaseService
        service = DatabaseService()
        print("✅ Database service created successfully")
    except Exception as e:
        print(f"❌ Database service creation failed: {e}")
        return False
        
    # Test 4: Try to use database service
    print("\n=== Database Service Usage ===")
    try:
        with service as db:
            media_files = db.get_all_media_files()
            print(f"✅ Database query successful, found {len(media_files)} media files")
            
            # Show some file details
            if media_files:
                print("Sample media files:")
                for i, mf in enumerate(media_files[:3]):
                    print(f"  {i+1}. {mf.filename} (score: {mf.score})")
            
    except Exception as e:
        print(f"❌ Database service usage failed: {e}")
        return False
        
    # Test 5: Check log directory
    print("\n=== Log Directory ===")
    log_dir = Path("/app/.logs")
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        test_file = log_dir / "test.log"
        test_file.write_text("test")
        test_file.unlink()
        print(f"✅ Log directory {log_dir} is writable")
    except Exception as e:
        print(f"❌ Log directory {log_dir} issue: {e}")
        
    return True

if __name__ == "__main__":
    print("Testing database connection...\n")
    success = test_database_connection()
    
    if success:
        print("\n🎉 All database tests passed!")
    else:
        print("\n❌ Database tests failed. Check the errors above.")
    
    sys.exit(0 if success else 1)
