#!/usr/bin/env python3
"""
Test script to validate PostgreSQL configuration behavior.
Tests that PostgreSQL is used when DATABASE_URL environment variable is set.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.settings import Settings
from tools.ingest_data import DataIngester


def test_settings_respects_database_url():
    """Test that Settings uses DATABASE_URL when available."""
    print("🧪 Testing Settings.load_from_yaml() with DATABASE_URL...")
    
    # Test with DATABASE_URL set
    test_db_url = "postgresql://user:pass@localhost/testdb"
    os.environ['DATABASE_URL'] = test_db_url
    
    try:
        settings = Settings.load_from_yaml()
        result_url = settings.get_database_url()
        
        if result_url == test_db_url:
            print("✅ Settings correctly uses DATABASE_URL")
        else:
            print(f"❌ Settings failed: expected {test_db_url}, got {result_url}")
            return False
    finally:
        # Clean up
        os.environ.pop('DATABASE_URL', None)
    
    return True


def test_settings_respects_media_db_url():
    """Test that Settings uses MEDIA_DB_URL when available."""
    print("🧪 Testing Settings.load_from_yaml() with MEDIA_DB_URL...")
    
    # Test with MEDIA_DB_URL set
    test_db_url = "postgresql://user:pass@localhost/testdb2"
    os.environ['MEDIA_DB_URL'] = test_db_url
    
    try:
        settings = Settings.load_from_yaml()
        result_url = settings.get_database_url()
        
        if result_url == test_db_url:
            print("✅ Settings correctly uses MEDIA_DB_URL")
        else:
            print(f"❌ Settings failed: expected {test_db_url}, got {result_url}")
            return False
    finally:
        # Clean up
        os.environ.pop('MEDIA_DB_URL', None)
    
    return True


def test_database_url_precedence():
    """Test that DATABASE_URL takes precedence over MEDIA_DB_URL."""
    print("🧪 Testing DATABASE_URL precedence over MEDIA_DB_URL...")
    
    test_db_url = "postgresql://user:pass@localhost/primary"
    test_media_db_url = "postgresql://user:pass@localhost/secondary"
    
    os.environ['DATABASE_URL'] = test_db_url
    os.environ['MEDIA_DB_URL'] = test_media_db_url
    
    try:
        settings = Settings.load_from_yaml()
        result_url = settings.get_database_url()
        
        if result_url == test_db_url:
            print("✅ DATABASE_URL correctly takes precedence")
        else:
            print(f"❌ Precedence failed: expected {test_db_url}, got {result_url}")
            return False
    finally:
        # Clean up
        os.environ.pop('DATABASE_URL', None)
        os.environ.pop('MEDIA_DB_URL', None)
    
    return True


def test_ingest_data_respects_env_vars():
    """Test that DataIngester uses environment variables when no CLI args provided."""
    print("🧪 Testing DataIngester with environment variables...")
    
    test_db_url = "postgresql://user:pass@localhost/minedb"
    os.environ['DATABASE_URL'] = test_db_url
    
    try:
        # Create a temporary directory for testing
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Create settings without explicit database_url
            settings = Settings.load_from_yaml()
            settings.dir = temp_path
            settings.enable_database = True
            
            # Create a simple logger for testing
            import logging
            logger = logging.getLogger('test')
            
            # Create DataIngester instance
            ingester = DataIngester(settings, logger)
            
            # Test the _get_database_url method
            result_url = miner._get_database_url(temp_path)
            
            if result_url == test_db_url:
                print("✅ DataIngester correctly uses environment variable")
            else:
                print(f"❌ DataIngester failed: expected {test_db_url}, got {result_url}")
                return False
    finally:
        # Clean up
        os.environ.pop('DATABASE_URL', None)
    
    return True


def test_postgresql_required_without_env():
    """Test that PostgreSQL URL is required when no DATABASE_URL is set."""
    print("🧪 Testing PostgreSQL requirement behavior...")
    
    # Ensure no database environment variables are set
    os.environ.pop('DATABASE_URL', None)
    os.environ.pop('MEDIA_DB_URL', None)
    
    # Create a temporary directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create settings without explicit database_url
        settings = Settings.load_from_yaml()
        settings.dir = temp_path
        settings.enable_database = True
        
        try:
            result_url = settings.get_database_url()
            print(f"❌ Should require PostgreSQL URL but got: {result_url}")
            return False
        except ValueError as e:
            if "PostgreSQL DATABASE_URL is required" in str(e):
                print("✅ Correctly requires PostgreSQL URL when no env vars set")
            else:
                print(f"❌ Wrong error message: {e}")
                return False
    
    return True


def main():
    """Run all tests."""
    print("🔬 Testing PostgreSQL Database Configuration")
    print("=" * 50)
    
    tests = [
        test_settings_respects_database_url,
        test_settings_respects_media_db_url,
        test_database_url_precedence,
        test_ingest_data_respects_env_vars,
        test_postgresql_required_without_env,
    ]
    
    passed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            print()
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            print()
    
    print(f"Results: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed!")
        return 0
    else:
        print(f"❌ {len(tests) - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())