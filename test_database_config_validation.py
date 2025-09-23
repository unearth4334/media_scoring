#!/usr/bin/env python3
"""
Test script to validate database configuration behavior without requiring actual database servers.
This test verifies that the correct database URLs are generated but doesn't attempt connections.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add the app directory to Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.settings import Settings
from tools.mine_data import DataMiner


def test_sqlite_fallback_when_no_env_vars():
    """Test that SQLite is used as fallback when no environment variables are set."""
    print("🧪 Testing SQLite fallback behavior...")
    
    # Clear any database environment variables
    old_db_url = os.environ.pop('DATABASE_URL', None)
    old_media_db_url = os.environ.pop('MEDIA_DB_URL', None)
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test Settings class
            settings = Settings.load_from_yaml()
            settings.dir = temp_path
            result_url = settings.get_database_url()
            
            expected = f"sqlite:///{temp_path}/.scores/media.db"
            if result_url == expected:
                print("✅ Settings correctly falls back to SQLite")
            else:
                print(f"❌ Settings fallback failed: expected {expected}, got {result_url}")
                return False
                
            # Test DataMiner class
            import logging
            logger = logging.getLogger('test')
            miner = DataMiner(settings, logger)
            miner_url = miner._get_database_url(temp_path)
            
            if miner_url == expected:
                print("✅ DataMiner correctly falls back to SQLite")
            else:
                print(f"❌ DataMiner fallback failed: expected {expected}, got {miner_url}")
                return False
                
    finally:
        # Restore original values
        if old_db_url:
            os.environ['DATABASE_URL'] = old_db_url
        if old_media_db_url:
            os.environ['MEDIA_DB_URL'] = old_media_db_url
    
    return True


def test_postgresql_config_from_database_url():
    """Test that PostgreSQL URL is used when DATABASE_URL is set."""
    print("🧪 Testing PostgreSQL configuration from DATABASE_URL...")
    
    test_url = "postgresql://testuser:testpass@testhost:5432/testdb"
    old_db_url = os.environ.get('DATABASE_URL')
    old_media_db_url = os.environ.pop('MEDIA_DB_URL', None)
    
    os.environ['DATABASE_URL'] = test_url
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test Settings class
            settings = Settings.load_from_yaml()
            settings.dir = temp_path
            result_url = settings.get_database_url()
            
            if result_url == test_url:
                print("✅ Settings correctly uses DATABASE_URL")
            else:
                print(f"❌ Settings failed: expected {test_url}, got {result_url}")
                return False
                
            # Test DataMiner class
            import logging
            logger = logging.getLogger('test')
            miner = DataMiner(settings, logger)
            miner_url = miner._get_database_url(temp_path)
            
            if miner_url == test_url:
                print("✅ DataMiner correctly uses DATABASE_URL")
            else:
                print(f"❌ DataMiner failed: expected {test_url}, got {miner_url}")
                return False
                
    finally:
        # Restore original values
        if old_db_url:
            os.environ['DATABASE_URL'] = old_db_url
        else:
            os.environ.pop('DATABASE_URL', None)
        if old_media_db_url:
            os.environ['MEDIA_DB_URL'] = old_media_db_url
    
    return True


def test_postgresql_config_from_media_db_url():
    """Test that PostgreSQL URL is used when MEDIA_DB_URL is set."""
    print("🧪 Testing PostgreSQL configuration from MEDIA_DB_URL...")
    
    test_url = "postgresql://mediauser:mediapass@mediahost:5432/mediadb"
    old_db_url = os.environ.pop('DATABASE_URL', None)
    old_media_db_url = os.environ.get('MEDIA_DB_URL')
    
    os.environ['MEDIA_DB_URL'] = test_url
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test Settings class
            settings = Settings.load_from_yaml()
            settings.dir = temp_path
            result_url = settings.get_database_url()
            
            if result_url == test_url:
                print("✅ Settings correctly uses MEDIA_DB_URL")
            else:
                print(f"❌ Settings failed: expected {test_url}, got {result_url}")
                return False
                
            # Test DataMiner class
            import logging
            logger = logging.getLogger('test')
            miner = DataMiner(settings, logger)
            miner_url = miner._get_database_url(temp_path)
            
            if miner_url == test_url:
                print("✅ DataMiner correctly uses MEDIA_DB_URL")
            else:
                print(f"❌ DataMiner failed: expected {test_url}, got {miner_url}")
                return False
                
    finally:
        # Restore original values
        if old_db_url:
            os.environ['DATABASE_URL'] = old_db_url
        if old_media_db_url:
            os.environ['MEDIA_DB_URL'] = old_media_db_url
        else:
            os.environ.pop('MEDIA_DB_URL', None)
    
    return True


def test_database_url_precedence_over_media_db_url():
    """Test that DATABASE_URL takes precedence over MEDIA_DB_URL."""
    print("🧪 Testing DATABASE_URL precedence over MEDIA_DB_URL...")
    
    primary_url = "postgresql://primary:pass@primary.host:5432/primary"
    secondary_url = "postgresql://secondary:pass@secondary.host:5432/secondary"
    
    old_db_url = os.environ.get('DATABASE_URL')
    old_media_db_url = os.environ.get('MEDIA_DB_URL')
    
    os.environ['DATABASE_URL'] = primary_url
    os.environ['MEDIA_DB_URL'] = secondary_url
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test Settings class
            settings = Settings.load_from_yaml()
            settings.dir = temp_path
            result_url = settings.get_database_url()
            
            if result_url == primary_url:
                print("✅ Settings correctly prioritizes DATABASE_URL")
            else:
                print(f"❌ Settings precedence failed: expected {primary_url}, got {result_url}")
                return False
                
            # Test DataMiner class
            import logging
            logger = logging.getLogger('test')
            miner = DataMiner(settings, logger)
            miner_url = miner._get_database_url(temp_path)
            
            if miner_url == primary_url:
                print("✅ DataMiner correctly prioritizes DATABASE_URL")
            else:
                print(f"❌ DataMiner precedence failed: expected {primary_url}, got {miner_url}")
                return False
                
    finally:
        # Restore original values
        if old_db_url:
            os.environ['DATABASE_URL'] = old_db_url
        else:
            os.environ.pop('DATABASE_URL', None)
        if old_media_db_url:
            os.environ['MEDIA_DB_URL'] = old_media_db_url
        else:
            os.environ.pop('MEDIA_DB_URL', None)
    
    return True


def test_cli_args_override_env_vars():
    """Test that CLI arguments override environment variables."""
    print("🧪 Testing CLI argument override behavior...")
    
    env_url = "postgresql://env:pass@env.host:5432/envdb"
    cli_url = "postgresql://cli:pass@cli.host:5432/clidb"
    
    old_db_url = os.environ.get('DATABASE_URL')
    os.environ['DATABASE_URL'] = env_url
    
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            
            # Test Settings class with CLI override
            settings = Settings.load_from_yaml()
            settings.dir = temp_path
            settings.database_url = cli_url  # Simulate CLI override
            result_url = settings.get_database_url()
            
            if result_url == cli_url:
                print("✅ Settings correctly prioritizes CLI argument over env var")
            else:
                print(f"❌ Settings CLI override failed: expected {cli_url}, got {result_url}")
                return False
                
            # Test DataMiner class
            import logging
            logger = logging.getLogger('test')
            miner = DataMiner(settings, logger)
            miner_url = miner._get_database_url(temp_path)
            
            if miner_url == cli_url:
                print("✅ DataMiner correctly prioritizes CLI argument over env var")
            else:
                print(f"❌ DataMiner CLI override failed: expected {cli_url}, got {miner_url}")
                return False
                
    finally:
        # Restore original values
        if old_db_url:
            os.environ['DATABASE_URL'] = old_db_url
        else:
            os.environ.pop('DATABASE_URL', None)
    
    return True


def main():
    """Run all tests."""
    print("🔬 Testing Database Configuration Logic (No Connections)")
    print("=" * 60)
    
    tests = [
        test_sqlite_fallback_when_no_env_vars,
        test_postgresql_config_from_database_url,
        test_postgresql_config_from_media_db_url,
        test_database_url_precedence_over_media_db_url,
        test_cli_args_override_env_vars,
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
        print("🎉 All database configuration tests passed!")
        return 0
    else:
        print(f"❌ {len(tests) - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())