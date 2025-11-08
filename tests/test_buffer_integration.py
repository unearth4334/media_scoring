#!/usr/bin/env python3
"""Integration test for buffer service with actual database."""

import sys
import tempfile
from pathlib import Path
from datetime import datetime

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.buffer_service import BufferService, FilterCriteria
from app.database.service import DatabaseService
from app.database.engine import init_database
from app.database.models import MediaFile


def create_test_database():
    """Create a test database with sample data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Initialize SQLite database
        db_path = tmppath / "test.db"
        db_url = f"sqlite:///{db_path}"
        
        print(f"Creating test database at {db_path}")
        init_database(db_url)
        
        # Create sample media files
        with DatabaseService() as db:
            for i in range(100):
                file_path = tmppath / f"test_image_{i:03d}.jpg"
                file_path.touch()  # Create empty file
                
                media_file = db.get_or_create_media_file(file_path)
                media_file.score = (i % 6)  # Scores 0-5
                media_file.file_type = "image"
                media_file.extension = ".jpg"
                media_file.file_size = 1024 * (i + 1)
                
                # Add some keywords
                if i % 3 == 0:
                    db.add_keywords(file_path, ["cat"], keyword_type="auto")
                if i % 5 == 0:
                    db.add_keywords(file_path, ["dog"], keyword_type="auto")
                if i % 7 == 0:
                    db.add_keywords(file_path, ["bird"], keyword_type="auto")
        
        print(f"✅ Created test database with 100 sample files")
        
        return tmppath, db_url


def test_buffer_integration():
    """Test full buffer service integration."""
    print("\n🔬 Testing Buffer Service Integration")
    print("=" * 50)
    
    tmppath, db_url = create_test_database()
    
    # Initialize buffer service
    buffer_db_path = tmppath / "buffer.db"
    buffer_service = BufferService(buffer_db_path)
    
    print("\nTest 1: Create buffer with score filter")
    print("-" * 50)
    
    # Create filter for high-scoring files
    filters = FilterCriteria(
        min_score=3,
        max_score=5,
        sort_field="date",
        sort_direction="desc"
    )
    
    with DatabaseService() as db:
        filter_hash, item_count = buffer_service.get_or_create_buffer(filters, db)
    
    print(f"✅ Buffer created: {filter_hash[:16]}")
    print(f"   Items in buffer: {item_count}")
    assert item_count > 0, "Should have items in buffer"
    
    print("\nTest 2: Reuse existing buffer")
    print("-" * 50)
    
    # Request same filter again - should reuse buffer
    with DatabaseService() as db:
        filter_hash2, item_count2 = buffer_service.get_or_create_buffer(filters, db)
    
    assert filter_hash == filter_hash2, "Filter hash should be the same"
    assert item_count == item_count2, "Item count should be the same"
    print(f"✅ Buffer reused successfully")
    
    print("\nTest 3: Keyset pagination")
    print("-" * 50)
    
    # Get first page
    page1, cursor1 = buffer_service.get_page(filter_hash, cursor=None, limit=10)
    print(f"   Page 1: {len(page1)} items")
    assert len(page1) == 10, "First page should have 10 items"
    assert cursor1 is not None, "Should have cursor for next page"
    
    # Get second page
    page2, cursor2 = buffer_service.get_page(filter_hash, cursor=cursor1, limit=10)
    print(f"   Page 2: {len(page2)} items")
    assert len(page2) == 10, "Second page should have 10 items"
    
    # Verify no duplicate items
    page1_ids = [item["id"] for item in page1]
    page2_ids = [item["id"] for item in page2]
    assert len(set(page1_ids) & set(page2_ids)) == 0, "Pages should not have duplicate items"
    print(f"✅ Pagination working correctly")
    
    print("\nTest 4: UI state persistence")
    print("-" * 50)
    
    # Save UI state
    buffer_service.save_ui_state("active_filter", {
        "filter_hash": filter_hash,
        "filters": filters.to_dict()
    })
    
    # Retrieve UI state
    active_state = buffer_service.get_ui_state("active_filter")
    assert active_state is not None, "Should retrieve UI state"
    assert active_state["filter_hash"] == filter_hash, "Filter hash should match"
    print(f"✅ UI state persisted and retrieved")
    
    print("\nTest 5: Buffer with keywords")
    print("-" * 50)
    
    # Create filter with keyword search
    keyword_filters = FilterCriteria(
        keywords=["cat"],
        sort_field="date"
    )
    
    with DatabaseService() as db:
        kw_hash, kw_count = buffer_service.get_or_create_buffer(keyword_filters, db)
    
    print(f"   Buffer created for keyword 'cat': {kw_count} items")
    assert kw_count > 0, "Should find files with 'cat' keyword"
    print(f"✅ Keyword filtering working")
    
    print("\nTest 6: Buffer statistics")
    print("-" * 50)
    
    stats = buffer_service.get_buffer_stats()
    print(f"   Total buffers: {stats['buffer_count']}")
    print(f"   Total items: {stats['total_items']}")
    print(f"   Total size: {stats['total_size_mb']:.2f} MB")
    assert stats['buffer_count'] == 2, "Should have 2 buffers"
    print(f"✅ Buffer statistics retrieved")
    
    print("\nTest 7: Buffer deletion")
    print("-" * 50)
    
    # Delete one buffer
    buffer_service.delete_buffer(filter_hash)
    
    stats_after = buffer_service.get_buffer_stats()
    assert stats_after['buffer_count'] == 1, "Should have 1 buffer after deletion"
    print(f"✅ Buffer deleted successfully")
    
    print("\nTest 8: Clear all buffers")
    print("-" * 50)
    
    buffer_service.clear_all_buffers()
    
    stats_final = buffer_service.get_buffer_stats()
    assert stats_final['buffer_count'] == 0, "Should have 0 buffers after clearing"
    print(f"✅ All buffers cleared")
    
    print("\n" + "=" * 50)
    print("🎉 All integration tests passed!")


if __name__ == "__main__":
    try:
        test_buffer_integration()
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
