#!/usr/bin/env python3
"""
Test script for daily contributions table functionality.
"""

import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.engine import init_database
from app.database.service import DatabaseService
from app.database.models import Base, MediaFile, DailyContribution


def test_daily_contributions():
    """Test the daily contributions table functionality."""
    print("🧪 Testing Daily Contributions Functionality")
    print("=" * 50)
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    db_url = f"sqlite:///{db_path}"
    print(f"📁 Using temporary database: {db_path}")
    
    try:
        # Initialize database
        init_database(db_url)
        print("✅ Database initialized")
        
        # Test 1: Create media files with different dates
        print("\n📝 Test 1: Creating test media files...")
        with DatabaseService() as db:
            # Create files for different dates
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            yesterday = today - timedelta(days=1)
            two_days_ago = today - timedelta(days=2)
            
            test_files = [
                ("/tmp/test1.jpg", today),
                ("/tmp/test2.jpg", today),
                ("/tmp/test3.jpg", yesterday),
                ("/tmp/test4.jpg", yesterday),
                ("/tmp/test5.jpg", two_days_ago),
            ]
            
            for file_path_str, date in test_files:
                file_path = Path(file_path_str)
                media_file = MediaFile(
                    filename=file_path.name,
                    directory=str(file_path.parent),
                    file_path=file_path_str,
                    file_size=1024,
                    file_type='image',
                    extension='.jpg',
                    original_created_at=date,
                    created_at=datetime.utcnow()
                )
                db.session.add(media_file)
            
            db.session.flush()
            print(f"   ✅ Created {len(test_files)} test media files")
        
        # Test 2: Rebuild daily contributions
        print("\n📊 Test 2: Rebuilding daily contributions table...")
        with DatabaseService() as db:
            count = db.rebuild_daily_contributions()
            print(f"   ✅ Created {count} daily contribution records")
            
            # Verify the counts
            contributions = db.get_all_daily_contributions()
            print(f"   📈 Daily contribution records:")
            for date_obj, count in contributions:
                print(f"      {date_obj.strftime('%Y-%m-%d')}: {count} files")
            
            # Verify expected counts
            assert len(contributions) == 3, f"Expected 3 date records, got {len(contributions)}"
            
            # Find today's count
            today_count = next((c for d, c in contributions if d.date() == today.date()), 0)
            assert today_count == 2, f"Expected 2 files for today, got {today_count}"
            
            yesterday_count = next((c for d, c in contributions if d.date() == yesterday.date()), 0)
            assert yesterday_count == 2, f"Expected 2 files for yesterday, got {yesterday_count}"
            
            two_days_ago_count = next((c for d, c in contributions if d.date() == two_days_ago.date()), 0)
            assert two_days_ago_count == 1, f"Expected 1 file for two days ago, got {two_days_ago_count}"
            
            print("   ✅ Counts verified correctly")
        
        # Test 3: Increment daily contributions
        print("\n➕ Test 3: Testing increment_daily_contribution...")
        with DatabaseService() as db:
            # Add more files to today
            db.increment_daily_contribution(today, count=3)
            db.session.commit()
            
            # Verify the increment
            contributions = db.get_all_daily_contributions()
            today_count = next((c for d, c in contributions if d.date() == today.date()), 0)
            assert today_count == 5, f"Expected 5 files for today after increment, got {today_count}"
            print(f"   ✅ Incremented today's count to {today_count}")
        
        # Test 4: Add new date
        print("\n📅 Test 4: Testing new date creation...")
        with DatabaseService() as db:
            three_days_ago = today - timedelta(days=3)
            db.increment_daily_contribution(three_days_ago, count=4)
            db.session.commit()
            
            # Verify the new date
            contributions = db.get_all_daily_contributions()
            assert len(contributions) == 4, f"Expected 4 date records, got {len(contributions)}"
            
            three_days_ago_count = next((c for d, c in contributions if d.date() == three_days_ago.date()), 0)
            assert three_days_ago_count == 4, f"Expected 4 files for three days ago, got {three_days_ago_count}"
            print(f"   ✅ Added new date with count {three_days_ago_count}")
        
        # Test 5: Verify time normalization
        print("\n🕐 Test 5: Testing time normalization...")
        with DatabaseService() as db:
            # Add contribution with time component (should be normalized to midnight)
            today_with_time = datetime.now().replace(hour=15, minute=30, second=45)
            db.increment_daily_contribution(today_with_time, count=1)
            db.session.commit()
            
            # Should still add to today's count
            contributions = db.get_all_daily_contributions()
            today_count = next((c for d, c in contributions if d.date() == today.date()), 0)
            assert today_count == 6, f"Expected 6 files for today after time normalization, got {today_count}"
            print(f"   ✅ Time normalization works correctly, count is now {today_count}")
        
        print("\n" + "=" * 50)
        print("✅ All tests passed!")
        return True
        
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        return False
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        # Cleanup
        try:
            Path(db_path).unlink()
            print(f"\n🗑️  Cleaned up temporary database")
        except:
            pass


if __name__ == "__main__":
    success = test_daily_contributions()
    sys.exit(0 if success else 1)
