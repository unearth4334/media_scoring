#!/usr/bin/env python3
"""
Demonstration of buffer service functionality.

This script demonstrates the key features of the buffered search results system:
1. Creating a buffer from filtered search results
2. Fast pagination through buffered results
3. Buffer reuse for identical filters
4. UI state persistence
"""

import sys
from pathlib import Path
import tempfile
from datetime import datetime, timedelta

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.buffer_service import BufferService, FilterCriteria
from app.database.service import DatabaseService
from app.database.engine import init_database


def print_section(title):
    """Print a section header."""
    print("\n" + "=" * 70)
    print(f"  {title}")
    print("=" * 70)


def demo_buffer_service():
    """Demonstrate buffer service features."""
    print("\n🎬 Buffer Service Demonstration")
    print("This demo shows how the buffered search results improve performance\n")
    
    # Setup test environment
    print_section("1. Setup Test Environment")
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Create test database
        db_path = tmppath / "demo.db"
        db_url = f"sqlite:///{db_path}"
        init_database(db_url)
        
        # Create sample media files
        print(f"Creating 100 sample media items...")
        media_dir = tmppath / "media"
        media_dir.mkdir()
        
        with DatabaseService() as db:
            for i in range(100):
                file_path = media_dir / f"photo_{i:03d}.jpg"
                file_path.touch()
                
                media_file = db.get_or_create_media_file(file_path)
                media_file.score = (i % 6)  # Scores 0-5
                media_file.file_type = "image"
                media_file.extension = ".jpg"
                media_file.file_size = 1024 * (i + 100)
                media_file.original_created_at = datetime.utcnow() - timedelta(days=i)
                
                # Add keywords to some files
                if i % 5 == 0:
                    db.add_keywords(file_path, ["sunset"], keyword_type="auto")
                if i % 7 == 0:
                    db.add_keywords(file_path, ["beach"], keyword_type="auto")
        
        print("✅ Created 100 media items with scores, dates, and keywords\n")
        
        # Initialize buffer service
        buffer_db_path = tmppath / "buffer.db"
        buffer_service = BufferService(buffer_db_path)
        
        # Demo 1: Create buffer with score filter
        print_section("2. Create Buffer with Score Filter")
        
        print("Creating buffer for high-quality images (score >= 4)...")
        
        high_score_filter = FilterCriteria(
            min_score=4,
            max_score=5,
            sort_field="date",
            sort_direction="desc"
        )
        
        with DatabaseService() as db:
            filter_hash, item_count = buffer_service.get_or_create_buffer(
                high_score_filter, db
            )
        
        print(f"✅ Buffer created!")
        print(f"   Filter hash: {filter_hash[:16]}...")
        print(f"   Items matching filter: {item_count}")
        print(f"   (Expected ~33 items with scores 4-5)\n")
        
        # Demo 2: Pagination
        print_section("3. Paginate Through Results")
        
        print("Fetching results in pages of 10 items...")
        
        cursor = None
        page_num = 1
        total_fetched = 0
        
        while page_num <= 4:  # Get first 4 pages
            items, cursor = buffer_service.get_page(filter_hash, cursor, limit=10)
            
            if not items:
                break
            
            print(f"\nPage {page_num}:")
            for i, item in enumerate(items[:3], 1):  # Show first 3 items
                print(f"  {i}. {item['filename']} - Score: {item['score']}")
            
            if len(items) > 3:
                print(f"  ... and {len(items) - 3} more items")
            
            total_fetched += len(items)
            page_num += 1
            
            if not cursor:
                print("\n  (No more pages)")
                break
        
        print(f"\n✅ Paginated through {total_fetched} items across {page_num - 1} pages")
        
        # Demo 3: Buffer reuse
        print_section("4. Buffer Reuse (Instant)")
        
        print("Requesting same filter again (should reuse existing buffer)...")
        
        import time
        start = time.time()
        
        with DatabaseService() as db:
            reused_hash, reused_count = buffer_service.get_or_create_buffer(
                high_score_filter, db
            )
        
        reuse_time = time.time() - start
        
        print(f"✅ Buffer reused in {reuse_time*1000:.2f}ms")
        print(f"   Same filter hash: {reused_hash == filter_hash}")
        print(f"   Same item count: {reused_count == item_count}\n")
        
        # Demo 4: Different filter creates new buffer
        print_section("5. Different Filter Creates New Buffer")
        
        print("Creating buffer with keyword filter...")
        
        keyword_filter = FilterCriteria(
            keywords=["sunset"],
            sort_field="date"
        )
        
        with DatabaseService() as db:
            keyword_hash, keyword_count = buffer_service.get_or_create_buffer(
                keyword_filter, db
            )
        
        print(f"✅ New buffer created!")
        print(f"   Filter hash: {keyword_hash[:16]}...")
        print(f"   Items with 'sunset' keyword: {keyword_count}")
        print(f"   Different from previous hash: {keyword_hash != filter_hash}\n")
        
        # Demo 5: UI state persistence
        print_section("6. UI State Persistence")
        
        print("Saving active filter state...")
        
        buffer_service.save_ui_state("active_filter", {
            "filter_hash": filter_hash,
            "filters": high_score_filter.to_dict(),
            "last_page": 2,
            "scroll_position": 500
        })
        
        print("✅ State saved")
        
        print("\nRetrieving saved state (simulating browser refresh)...")
        
        restored_state = buffer_service.get_ui_state("active_filter")
        
        print(f"✅ State restored!")
        print(f"   Filter hash: {restored_state['filter_hash'][:16]}...")
        print(f"   Last page: {restored_state['last_page']}")
        print(f"   Scroll position: {restored_state['scroll_position']}px\n")
        
        # Demo 6: Buffer statistics
        print_section("7. Buffer Statistics")
        
        stats = buffer_service.get_buffer_stats()
        
        print(f"Buffer Registry:")
        print(f"  Total buffers: {stats['buffer_count']}")
        print(f"  Total items: {stats['total_items']}")
        print(f"  Storage used: {stats['total_size_mb']:.2f} MB\n")
        
        # Demo 7: Multiple filters
        print_section("8. Complex Filter Combinations")
        
        print("Creating buffers for various filter combinations...")
        
        filters = [
            ("All low scores", FilterCriteria(max_score=2)),
            ("Recent + High score", FilterCriteria(min_score=4, sort_field="date")),
            ("Sunset beach", FilterCriteria(keywords=["sunset", "beach"], match_all=True)),
        ]
        
        for name, criteria in filters:
            with DatabaseService() as db:
                fhash, fcount = buffer_service.get_or_create_buffer(criteria, db)
            print(f"  • {name}: {fcount} items (hash: {fhash[:8]}...)")
        
        final_stats = buffer_service.get_buffer_stats()
        print(f"\n✅ Now have {final_stats['buffer_count']} buffers in registry")
        
        print_section("Demo Complete!")
        
        print("""
Key Takeaways:
  ✓ Buffers materialize search results for fast access
  ✓ Identical filters reuse existing buffers (instant)
  ✓ Pagination is fast and consistent (keyset-based)
  ✓ UI state persists across sessions
  ✓ Multiple buffers coexist efficiently
  ✓ Automatic LRU eviction manages storage

Next Steps:
  • Integrate these endpoints into your UI
  • Add a "Refresh" button to trigger buffer creation
  • Use keyset pagination for infinite scroll
  • Restore UI state on page load for seamless UX
        """)


if __name__ == "__main__":
    try:
        demo_buffer_service()
    except Exception as e:
        print(f"\n❌ Demo failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
