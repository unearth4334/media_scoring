#!/usr/bin/env python3
"""Test database state initialization."""

import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.settings import Settings
from app.state import ApplicationState

def test_database_state():
    """Test database initialization in application state."""
    
    print("=== Testing Database State Initialization ===\n")
    
    # Check environment variables
    print("Environment variables:")
    db_url = os.getenv('DATABASE_URL') or os.getenv('MEDIA_DB_URL')
    print(f"  DATABASE_URL: {db_url}")
    print(f"  MEDIA_DB_URL: {os.getenv('MEDIA_DB_URL')}")
    print()
    
    # Test direct database URL
    test_url = "postgresql://media_user:media_password@postgres:5432/media_scoring"
    print(f"Test database URL: {test_url}")
    
    # Create settings with database URL
    config_data = {
        'dir': Path('/media'),
        'enable_database': True,
        'database_url': test_url
    }
    
    print(f"Creating settings with config: {config_data}")
    settings = Settings(**config_data)
    print(f"  Settings.enable_database: {settings.enable_database}")
    print(f"  Settings.database_url: {settings.database_url}")
    print()
    
    # Initialize application state
    print("Initializing application state...")
    try:
        state = ApplicationState(settings)
        print(f"  State.database_requested: {state.database_requested}")
        print(f"  State.database_enabled: {state.database_enabled}")
        
        # Test database service
        print("Testing database service...")
        db_service = state.get_database_service()
        print(f"  Database service: {db_service}")
        
        if db_service:
            print("  ✅ Database service created successfully")
        else:
            print("  ❌ Database service is None")
            
    except Exception as e:
        print(f"  ❌ Failed to initialize state: {e}")
        import traceback
        traceback.print_exc()
    
    # Test database connectivity
    print("\nTesting database connectivity...")
    try:
        from app.database.engine import get_session
        with get_session() as session:
            result = session.execute("SELECT 1 as test").fetchone()
            print(f"  ✅ Database query successful: {result}")
    except Exception as e:
        print(f"  ❌ Database query failed: {e}")

if __name__ == "__main__":
    test_database_state()
