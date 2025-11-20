#!/usr/bin/env python3
"""
Integration test for daily contributions in ingestv2 workflow.
Tests that contribution tallies are updated correctly during ingestion.
"""

import sys
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database.engine import init_database, close_database
from app.database.service import DatabaseService
from app.database.models import Base, MediaFile


def test_contribution_tallies_during_ingestion():
    """Test that contribution tallies are updated when files are added to database."""
    print("🧪 Testing Contribution Tallies During Ingestion")
    print("=" * 60)
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    # Create a temporary directory for test files
    test_dir = Path(tempfile.mkdtemp())
    
    db_url = f"sqlite:///{db_path}"
    print(f"📁 Using temporary database: {db_path}")
    print(f"📁 Using temporary test directory: {test_dir}")
    
    try:
        # Initialize database
        init_database(db_url)
        print("✅ Database initialized")
        
        # Test 1: Verify daily_contributions is empty
        print("\n📊 Test 1: Verifying initial state...")
        with DatabaseService() as db:
            contributions = db.get_all_daily_contributions()
            assert len(contributions) == 0, f"Expected empty contributions table, got {len(contributions)} records"
            print("   ✅ Daily contributions table is empty")
        
        # Test 2: Add media files with different creation dates
        print("\n📝 Test 2: Adding media files with different dates...")
        from datetime import timedelta
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        test_dates = [
            today,
            today - timedelta(days=1),
            today - timedelta(days=2),
        ]
        
        with DatabaseService() as db:
            for i, file_date in enumerate(test_dates):
                file_path = test_dir / f"test_image_{i}.jpg"
                file_path.touch()
                
                # Create media file
                media_file = db.get_or_create_media_file(file_path)
                media_file.original_created_at = file_date
                
                # Simulate what ingestv2 does: increment daily contribution
                db.increment_daily_contribution(file_date, count=1)
                
            db.session.commit()
        
        print(f"   ✅ Added {len(test_dates)} media files")
        
        # Test 3: Verify daily contributions were updated
        print("\n📈 Test 3: Verifying daily contributions were updated...")
        with DatabaseService() as db:
            contributions = db.get_all_daily_contributions()
            
            print(f"   📊 Found {len(contributions)} daily contribution records:")
            for date_obj, count in contributions:
                print(f"      {date_obj.strftime('%Y-%m-%d')}: {count} files")
            
            # Verify we have 3 different dates
            assert len(contributions) == 3, f"Expected 3 date records, got {len(contributions)}"
            
            # Verify each date has 1 file
            for date_obj, count in contributions:
                assert count == 1, f"Expected 1 file for {date_obj.strftime('%Y-%m-%d')}, got {count}"
            
            print("   ✅ Daily contributions updated correctly")
        
        # Test 4: Test incremental updates
        print("\n➕ Test 4: Testing incremental contribution updates...")
        
        # Add 3 more files for today
        with DatabaseService() as db:
            for i in range(3, 6):
                file_path = test_dir / f"test_image_{i}.jpg"
                file_path.touch()
                
                media_file = db.get_or_create_media_file(file_path)
                media_file.original_created_at = today
                
                # Increment contribution tally
                db.increment_daily_contribution(today, count=1)
            
            db.session.commit()
        
        print(f"   ✅ Added 3 more files for today")
        
        # Verify today's count increased
        with DatabaseService() as db:
            contributions = db.get_all_daily_contributions()
            
            today_count = next((c for d, c in contributions if d == today), 0)
            
            expected_count = 4  # 1 original + 3 additional
            assert today_count == expected_count, f"Expected {expected_count} files for today, got {today_count}"
            
            print(f"   ✅ Today's count correctly incremented to {today_count}")
        
        # Test 5: Test rebuild functionality
        print("\n🔄 Test 5: Testing rebuild functionality...")
        
        with DatabaseService() as db:
            # Rebuild from media files
            count = db.rebuild_daily_contributions()
            db.session.commit()
            
            print(f"   ✅ Rebuilt {count} contribution records")
            
            # Verify counts are still correct after rebuild
            contributions = db.get_all_daily_contributions()
            assert len(contributions) == 3, f"Expected 3 records after rebuild, got {len(contributions)}"
            
            today_count = next((c for d, c in contributions if d == today), 0)
            assert today_count == 4, f"Expected 4 files for today after rebuild, got {today_count}"
            
            print("   ✅ Rebuild produced correct counts")
        
        # Test 6: Verify MediaFile records
        print("\n📅 Test 6: Verifying MediaFile records...")
        with DatabaseService() as db:
            media_files = db.session.query(MediaFile).all()
            assert len(media_files) == 6, f"Expected 6 media files, got {len(media_files)}"
            
            files_with_dates = sum(1 for mf in media_files if mf.original_created_at is not None)
            assert files_with_dates == 6, f"Expected all 6 files to have original_created_at, got {files_with_dates}"
            
            print(f"   ✅ All {len(media_files)} media files have proper date fields")
        
        print("\n" + "=" * 60)
        print("✅ All integration tests passed!")
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
            close_database()
            Path(db_path).unlink()
            shutil.rmtree(test_dir)
            print(f"\n🗑️  Cleaned up test environment")
        except Exception as e:
            print(f"\n⚠️  Cleanup warning: {e}")


if __name__ == "__main__":
    success = test_contribution_tallies_during_ingestion()
    sys.exit(0 if success else 1)
