#!/usr/bin/env python3
"""
Test script to verify PostgreSQL database connectivity and functionality.
"""

import os
import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

def test_postgresql_connection():
    """Test PostgreSQL connection using DATABASE_URL."""
    db_url = os.getenv('DATABASE_URL')
    if not db_url or not db_url.startswith('postgresql://'):
        print("⏭️  PostgreSQL test skipped (no DATABASE_URL set)")
        print("     Set DATABASE_URL environment variable to test PostgreSQL connection")
        return False
    
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
    print("==" * 25)
    
    try:
        test_postgresql_connection()
        print()
        print("🎉 Database test completed!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        sys.exit(1)