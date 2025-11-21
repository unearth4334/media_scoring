#!/usr/bin/env python3
"""
Test for buffer clearing on startup and refresh.
"""

import sys
import tempfile
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_buffer_clear_on_startup():
    """Test that buffers are cleared on application startup."""
    print("\n🔬 Test: Buffer Clear on Startup")
    print("=" * 70)
    
    # Create temporary database
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        db_path = tmppath / "test.db"
        
        # Initialize database
        from app.database.engine import init_database
        init_database(str(db_path))
        
        # Create a buffer service and add some test buffers
        from app.database.buffer_service import BufferService
        buffer_service = BufferService(str(db_path))
        
        # Create a test buffer by directly inserting into registry
        with buffer_service.engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("""
                INSERT INTO buffer_registry 
                (filter_hash, buffer_table_name, item_count, size_bytes, created_at, last_accessed_at, filter_criteria)
                VALUES ('test_hash_1', 'buffer_test1', 10, 5000, datetime('now'), datetime('now'), '{}')
            """))
            conn.execute(text("""
                CREATE TABLE buffer_test1 (
                    id INTEGER PRIMARY KEY,
                    filename TEXT
                )
            """))
        
        # Verify buffer exists
        with buffer_service.session_factory() as session:
            from sqlalchemy import text
            result = session.execute(
                text("SELECT COUNT(*) FROM buffer_registry")
            ).scalar()
            assert result == 1, f"Should have 1 buffer, got {result}"
            print("  ✓ Test buffer created")
        
        # Simulate startup - clear all buffers
        buffer_service.clear_all_buffers()
        
        # Verify buffers were cleared
        with buffer_service.session_factory() as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM buffer_registry")
            ).scalar()
            assert result == 0, f"Should have 0 buffers after clear, got {result}"
            print("  ✓ Buffers cleared successfully")
        
        # Verify table was dropped
        from sqlalchemy import inspect
        inspector = inspect(buffer_service.engine)
        tables = inspector.get_table_names()
        assert 'buffer_test1' not in tables, "Buffer table should be dropped"
        print("  ✓ Buffer table dropped")
        
        print("  ✅ Buffer clear on startup test passed")


def test_buffer_clear_on_refresh():
    """Test that buffers are cleared when refresh button is used."""
    print("\n🔬 Test: Buffer Clear on Refresh")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        db_path = tmppath / "test.db"
        media_dir = tmppath / "media"
        media_dir.mkdir()
        
        # Initialize database
        from app.database.engine import init_database
        init_database(str(db_path))
        
        # Create a buffer service and add some test buffers
        from app.database.buffer_service import BufferService, FilterCriteria
        from app.database.service import DatabaseService
        
        buffer_service = BufferService(str(db_path))
        
        # Create a test buffer
        with buffer_service.engine.begin() as conn:
            from sqlalchemy import text
            conn.execute(text("""
                INSERT INTO buffer_registry 
                (filter_hash, buffer_table_name, item_count, size_bytes, created_at, last_accessed_at, filter_criteria)
                VALUES ('old_hash_1', 'buffer_old1', 5, 2500, datetime('now'), datetime('now'), '{}')
            """))
            conn.execute(text("""
                CREATE TABLE buffer_old1 (
                    id INTEGER PRIMARY KEY,
                    filename TEXT
                )
            """))
        
        # Verify old buffer exists
        with buffer_service.session_factory() as session:
            from sqlalchemy import text
            result = session.execute(
                text("SELECT COUNT(*) FROM buffer_registry")
            ).scalar()
            assert result == 1, f"Should have 1 old buffer, got {result}"
            print("  ✓ Old buffer exists")
        
        # Simulate refresh - clear all buffers then create new one
        buffer_service.clear_all_buffers()
        print("  ✓ Old buffers cleared")
        
        # Verify old buffers were cleared
        with buffer_service.session_factory() as session:
            result = session.execute(
                text("SELECT COUNT(*) FROM buffer_registry")
            ).scalar()
            assert result == 0, f"Should have 0 buffers after clear, got {result}"
            print("  ✓ Buffer registry empty")
        
        print("  ✅ Buffer clear on refresh test passed")


def test_buffer_isolation():
    """Test that clearing buffers doesn't affect other data."""
    print("\n🔬 Test: Buffer Isolation")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        db_path = tmppath / "test.db"
        media_dir = tmppath / "media"
        media_dir.mkdir()
        
        # Create a test image
        from PIL import Image
        img = Image.new('RGB', (100, 100), color=(100, 100, 150))
        img_path = media_dir / "test.jpg"
        img.save(img_path, 'JPEG')
        
        # Initialize database
        from app.database.engine import init_database
        init_database(str(db_path))
        
        # Add media file to database
        from app.database.service import DatabaseService
        with DatabaseService(str(db_path)) as db:
            media_file = db.get_or_create_media_file(img_path)
            assert media_file is not None
            media_file_id = media_file.id
            print(f"  ✓ Media file added: {media_file_id}")
        
        # Create and clear buffers
        from app.database.buffer_service import BufferService
        buffer_service = BufferService(str(db_path))
        buffer_service.clear_all_buffers()
        
        # Verify media file still exists
        with DatabaseService(str(db_path)) as db:
            media_file = db.get_media_file_by_id(media_file_id)
            assert media_file is not None, "Media file should still exist"
            print(f"  ✓ Media file still exists after buffer clear")
        
        print("  ✅ Buffer isolation test passed")


def run_all_tests():
    """Run all buffer clearing tests."""
    print("\n" + "=" * 70)
    print("🚀 BUFFER CLEARING TEST SUITE")
    print("=" * 70)
    
    try:
        test_buffer_clear_on_startup()
        test_buffer_clear_on_refresh()
        test_buffer_isolation()
        
        print("\n" + "=" * 70)
        print("✅ ALL TESTS PASSED!")
        print("=" * 70)
        return True
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
