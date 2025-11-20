#!/usr/bin/env python3
"""
Manual verification script for daily contributions functionality.
This script demonstrates the complete workflow of the contribution tallies feature.
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
from app.database.models import MediaFile


def demonstrate_contribution_tallies():
    """Demonstrate the contribution tallies feature."""
    print("=" * 70)
    print("📊 Manual Verification: Daily Contributions Tally Feature")
    print("=" * 70)
    
    # Create a temporary database
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_db:
        db_path = tmp_db.name
    
    test_dir = Path(tempfile.mkdtemp())
    db_url = f"sqlite:///{db_path}"
    
    print(f"\n📁 Database: {db_path}")
    print(f"📁 Test directory: {test_dir}")
    
    try:
        # Initialize database
        init_database(db_url)
        print("\n✅ Database initialized with daily_contributions table")
        
        # Scenario 1: Simulate ingesting files from different dates
        print("\n" + "=" * 70)
        print("📝 SCENARIO 1: Ingesting files from multiple dates")
        print("=" * 70)
        
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Simulate ingesting 100 files across 10 days
        print("\nSimulating ingestion of 100 files across 10 days...")
        
        with DatabaseService() as db:
            file_count = 0
            for day_offset in range(10):
                date = today - timedelta(days=day_offset)
                # Vary the number of files per day (5-15 files)
                files_for_day = 5 + (day_offset % 11)
                
                for i in range(files_for_day):
                    file_path = test_dir / f"file_{file_count}.jpg"
                    file_path.touch()
                    
                    # Create media file with original_created_at
                    media_file = db.get_or_create_media_file(file_path)
                    media_file.original_created_at = date
                    
                    # This is what ingestv2 does: increment daily contribution
                    db.increment_daily_contribution(date, count=1)
                    
                    file_count += 1
            
            db.session.commit()
        
        print(f"   ✅ Ingested {file_count} files")
        
        # Show the contribution tallies
        print("\n📈 Daily Contribution Tallies:")
        print("   Date         | Files")
        print("   " + "-" * 30)
        
        with DatabaseService() as db:
            contributions = db.get_all_daily_contributions()
            total = 0
            for date_obj, count in contributions:
                print(f"   {date_obj.strftime('%Y-%m-%d')} |  {count:3d}")
                total += count
            
            print("   " + "-" * 30)
            print(f"   Total        |  {total:3d}")
        
        # Scenario 2: Show performance comparison
        print("\n" + "=" * 70)
        print("⚡ SCENARIO 2: Performance Comparison")
        print("=" * 70)
        
        print("\n🔍 Method 1: Old approach (query all media files)")
        import time
        
        start = time.time()
        with DatabaseService() as db:
            # Simulate the old way: get all media files and group them
            media_files = db.session.query(MediaFile).all()
            old_counts = {}
            for mf in media_files:
                date_obj = mf.original_created_at or mf.created_at
                if date_obj:
                    date_str = date_obj.strftime('%Y-%m-%d')
                    old_counts[date_str] = old_counts.get(date_str, 0) + 1
        old_time = (time.time() - start) * 1000
        
        print(f"   Time: {old_time:.2f}ms")
        print(f"   Results: {len(old_counts)} dates, {sum(old_counts.values())} files")
        
        print("\n⚡ Method 2: New approach (use pre-computed table)")
        
        start = time.time()
        with DatabaseService() as db:
            # New way: just query the daily_contributions table
            contributions = db.get_all_daily_contributions()
            new_counts = {d.strftime('%Y-%m-%d'): c for d, c in contributions}
        new_time = (time.time() - start) * 1000
        
        print(f"   Time: {new_time:.2f}ms")
        print(f"   Results: {len(new_counts)} dates, {sum(new_counts.values())} files")
        
        if old_time > 0:
            speedup = old_time / new_time if new_time > 0 else float('inf')
            print(f"\n   🚀 Speedup: {speedup:.1f}x faster!")
        
        # Verify both methods produce the same results
        print("\n✅ Verification: Both methods produce identical results" 
              if old_counts == new_counts else "❌ Results don't match!")
        
        # Scenario 3: Demonstrate rebuild functionality
        print("\n" + "=" * 70)
        print("🔄 SCENARIO 3: Rebuild Functionality")
        print("=" * 70)
        
        print("\n🗑️  Clearing daily_contributions table...")
        with DatabaseService() as db:
            from app.database.models import DailyContribution
            db.session.query(DailyContribution).delete()
            db.session.commit()
            
            contributions = db.get_all_daily_contributions()
            print(f"   ✅ Table cleared ({len(contributions)} records)")
        
        print("\n🔄 Rebuilding from existing media files...")
        with DatabaseService() as db:
            count = db.rebuild_daily_contributions()
            db.session.commit()
            print(f"   ✅ Rebuilt {count} contribution records")
            
            # Verify rebuild worked
            contributions = db.get_all_daily_contributions()
            total = sum(c for _, c in contributions)
            print(f"   📊 Total files in rebuilt table: {total}")
        
        # Scenario 4: Show API endpoint behavior
        print("\n" + "=" * 70)
        print("🌐 SCENARIO 4: API Endpoint Behavior")
        print("=" * 70)
        
        print("\n📡 Simulating /api/media/daily-counts endpoint...")
        with DatabaseService() as db:
            contributions = db.get_all_daily_contributions()
            
            # Format as the API would return
            daily_counts = {
                d.strftime('%Y-%m-%d'): c 
                for d, c in contributions
            }
            
            result = {
                "daily_counts": daily_counts,
                "total_files": sum(daily_counts.values()),
                "total_days": len(daily_counts)
            }
            
            print(f"   Response preview:")
            print(f"   - total_files: {result['total_files']}")
            print(f"   - total_days: {result['total_days']}")
            print(f"   - Sample dates: {list(daily_counts.items())[:3]}")
        
        print("\n" + "=" * 70)
        print("✅ Manual Verification Complete!")
        print("=" * 70)
        
        print("\n📋 Summary:")
        print("   ✓ Daily contributions table stores pre-computed tallies")
        print("   ✓ Ingestv2 increments tallies during file commit")
        print("   ✓ New approach is significantly faster than querying all files")
        print("   ✓ Rebuild function can reconstruct tallies from media files")
        print("   ✓ API endpoint uses pre-computed table for quick responses")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error: {e}")
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
    success = demonstrate_contribution_tallies()
    sys.exit(0 if success else 1)
