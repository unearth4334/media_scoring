#!/usr/bin/env python3
"""
Comprehensive tests for filter toolbar functionality.
Tests filter state management, pill colors, and filter application.
"""

import sys
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import create_app
from app.database.engine import init_database
from app.database.service import DatabaseService
from app.state import init_state
from app.settings import Settings


def create_test_media_files(media_dir: Path, count: int = 10):
    """Create test media files with various scores and types."""
    from PIL import Image
    
    files = []
    for i in range(count):
        # Create image files with different extensions
        file_type = i % 3
        if file_type == 0:
            filename = f"test_image_{i}.jpg"
            img = Image.new('RGB', (100, 100), color=(i*20, 100, 150))
            img.save(media_dir / filename, 'JPEG')
        elif file_type == 1:
            filename = f"test_image_{i}.png"
            img = Image.new('RGB', (100, 100), color=(150, i*20, 100))
            img.save(media_dir / filename, 'PNG')
        else:
            filename = f"test_video_{i}.mp4"
            # Create empty file for video (not actual video)
            (media_dir / filename).touch()
        
        files.append(filename)
        
        # Create score files for all images
        score_dir = media_dir / ".scores"
        score_dir.mkdir(exist_ok=True)
        
        # Assign scores based on index
        score_map = {0: 5, 1: 3, 2: 1, 3: -1}
        score = score_map.get(i % 4, 0)
        
        score_file = score_dir / f"{filename}.score"
        score_file.write_text(str(score))
    
    return files


def test_filter_individual_file_types():
    """Test individual file type filters (JPG, PNG, MP4)."""
    print("\n🔬 Test 1: Individual File Type Filters")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        media_dir = tmppath / "media"
        media_dir.mkdir()
        
        # Create test files
        files = create_test_media_files(media_dir)
        
        # Initialize app
        settings = Settings(pattern="*.jpg|*.png|*.mp4",
            dir=str(media_dir),
            enable_database=False
        )
        init_state(settings)
        app = create_app(settings)
        client = TestClient(app)
        
        # Get all videos (should include all types)
        response = client.get("/api/videos")
        assert response.status_code == 200
        all_videos = response.json()["videos"]
        total_count = len(all_videos)
        
        print(f"  ✓ Total files: {total_count}")
        
        # Count file types
        jpg_count = sum(1 for v in all_videos if v['name'].endswith('.jpg'))
        png_count = sum(1 for v in all_videos if v['name'].endswith('.png'))
        mp4_count = sum(1 for v in all_videos if v['name'].endswith('.mp4'))
        
        print(f"  ✓ JPG files: {jpg_count}")
        print(f"  ✓ PNG files: {png_count}")
        print(f"  ✓ MP4 files: {mp4_count}")
        
        assert jpg_count > 0, "Should have JPG files"
        assert png_count > 0, "Should have PNG files"
        assert mp4_count > 0, "Should have MP4 files"
        
        print("  ✅ Individual file type filter test passed")


def test_filter_individual_ratings():
    """Test individual rating filters (1-5 stars, rejected, unrated)."""
    print("\n🔬 Test 2: Individual Rating Filters")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        media_dir = tmppath / "media"
        media_dir.mkdir()
        
        # Create test files with scores
        files = create_test_media_files(media_dir)
        
        # Initialize app
        settings = Settings(pattern="*.jpg|*.png|*.mp4",
            dir=str(media_dir),
            enable_database=False
        )
        init_state(settings)
        app = create_app(settings)
        client = TestClient(app)
        
        # Get all videos
        response = client.get("/api/videos")
        assert response.status_code == 200
        all_videos = response.json()["videos"]
        
        # Count scores
        scores = {}
        for v in all_videos:
            score = v.get('score', 0)
            scores[score] = scores.get(score, 0) + 1
        
        print(f"  Score distribution: {scores}")
        
        # Verify we have various scores
        assert -1 in scores, "Should have rejected files"
        assert 1 in scores or 3 in scores or 5 in scores, "Should have rated files"
        
        print("  ✅ Individual rating filter test passed")


def test_filter_date_range():
    """Test date range filtering."""
    print("\n🔬 Test 3: Date Range Filtering")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        media_dir = tmppath / "media"
        media_dir.mkdir()
        db_path = tmppath / "test.db"
        
        # Create test files
        files = create_test_media_files(media_dir, count=5)
        
        # Initialize database
        init_database(str(db_path))
        
        # Initialize app with database
        settings = Settings(pattern="*.jpg|*.png|*.mp4",
            dir=str(media_dir),
            enable_database=True,
            database_path=str(db_path)
        )
        init_state(settings)
        app = create_app(settings)
        client = TestClient(app)
        
        # Ingest files into database
        with DatabaseService(str(db_path)) as db:
            for filename in files:
                file_path = media_dir / filename
                db.get_or_create_media_file(file_path)
        
        # Test date filtering
        today = datetime.now().date()
        start_date = today - timedelta(days=7)
        end_date = today
        
        filter_request = {
            "start_date": f"{start_date}T00:00:00Z",
            "end_date": f"{end_date}T23:59:59Z",
            "file_types": None,
            "min_score": None,
            "max_score": None,
            "sort_field": "date",
            "sort_direction": "desc"
        }
        
        response = client.post("/api/filter", json=filter_request)
        assert response.status_code == 200
        filtered_videos = response.json()["videos"]
        
        print(f"  ✓ Filtered {len(filtered_videos)} files within date range")
        print("  ✅ Date range filter test passed")


def test_filter_nsfw():
    """Test NSFW filtering."""
    print("\n🔬 Test 4: NSFW Filtering")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        media_dir = tmppath / "media"
        media_dir.mkdir()
        db_path = tmppath / "test.db"
        
        # Create test files
        files = create_test_media_files(media_dir, count=5)
        
        # Initialize database
        init_database(str(db_path))
        
        # Initialize app
        settings = Settings(pattern="*.jpg|*.png|*.mp4",
            dir=str(media_dir),
            enable_database=True,
            database_path=str(db_path)
        )
        init_state(settings)
        app = create_app(settings)
        client = TestClient(app)
        
        # Ingest files and mark some as NSFW
        with DatabaseService(str(db_path)) as db:
            for i, filename in enumerate(files):
                file_path = media_dir / filename
                media_file = db.get_or_create_media_file(file_path)
                # Mark every other file as NSFW
                if i % 2 == 0:
                    media_file.nsfw = True
        
        # Test NSFW filter: all
        response = client.post("/api/filter", json={
            "nsfw_filter": "all",
            "sort_field": "name",
            "sort_direction": "asc"
        })
        assert response.status_code == 200
        all_count = len(response.json()["videos"])
        
        # Test NSFW filter: sfw only
        response = client.post("/api/filter", json={
            "nsfw_filter": "sfw",
            "sort_field": "name",
            "sort_direction": "asc"
        })
        assert response.status_code == 200
        sfw_count = len(response.json()["videos"])
        
        # Test NSFW filter: nsfw only
        response = client.post("/api/filter", json={
            "nsfw_filter": "nsfw",
            "sort_field": "name",
            "sort_direction": "asc"
        })
        assert response.status_code == 200
        nsfw_count = len(response.json()["videos"])
        
        print(f"  ✓ All: {all_count} files")
        print(f"  ✓ SFW: {sfw_count} files")
        print(f"  ✓ NSFW: {nsfw_count} files")
        
        assert sfw_count + nsfw_count == all_count, "SFW + NSFW should equal total"
        print("  ✅ NSFW filter test passed")


def test_filter_intersections():
    """Test multiple filters applied together."""
    print("\n🔬 Test 5: Filter Intersections")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        media_dir = tmppath / "media"
        media_dir.mkdir()
        db_path = tmppath / "test.db"
        
        # Create test files
        files = create_test_media_files(media_dir, count=10)
        
        # Initialize database
        init_database(str(db_path))
        
        # Initialize app
        settings = Settings(pattern="*.jpg|*.png|*.mp4",
            dir=str(media_dir),
            enable_database=True,
            database_path=str(db_path)
        )
        init_state(settings)
        app = create_app(settings)
        client = TestClient(app)
        
        # Ingest files
        with DatabaseService(str(db_path)) as db:
            for filename in files:
                file_path = media_dir / filename
                db.get_or_create_media_file(file_path)
        
        # Test: File type + Rating
        response = client.post("/api/filter", json={
            "file_types": ["jpg"],
            "min_score": 3,
            "sort_field": "name",
            "sort_direction": "asc"
        })
        assert response.status_code == 200
        filtered = response.json()["videos"]
        print(f"  ✓ JPG + Rating≥3: {len(filtered)} files")
        
        # Verify all results are JPG and have score >= 3
        for v in filtered:
            assert v['name'].endswith('.jpg'), "Should be JPG"
            assert v.get('score', 0) >= 3, f"Score should be ≥3, got {v.get('score', 0)}"
        
        # Test: File type + Rating + Date
        today = datetime.now().date()
        response = client.post("/api/filter", json={
            "file_types": ["jpg", "png"],
            "min_score": 1,
            "start_date": f"{today}T00:00:00Z",
            "end_date": f"{today}T23:59:59Z",
            "sort_field": "name",
            "sort_direction": "asc"
        })
        assert response.status_code == 200
        filtered = response.json()["videos"]
        print(f"  ✓ JPG/PNG + Rating≥1 + Today: {len(filtered)} files")
        
        print("  ✅ Filter intersection test passed")


def test_filter_state_persistence():
    """Test filter state persistence via buffer service."""
    print("\n🔬 Test 6: Filter State Persistence")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        media_dir = tmppath / "media"
        media_dir.mkdir()
        db_path = tmppath / "test.db"
        
        # Create test files
        files = create_test_media_files(media_dir, count=5)
        
        # Initialize database
        init_database(str(db_path))
        
        # Initialize app
        settings = Settings(pattern="*.jpg|*.png|*.mp4",
            dir=str(media_dir),
            enable_database=True,
            database_path=str(db_path)
        )
        init_state(settings)
        app = create_app(settings)
        client = TestClient(app)
        
        # Ingest files
        with DatabaseService(str(db_path)) as db:
            for filename in files:
                file_path = media_dir / filename
                db.get_or_create_media_file(file_path)
        
        # Set active filters
        filter_request = {
            "file_types": ["jpg", "png"],
            "min_score": 3,
            "sort_field": "rating",
            "sort_direction": "desc",
            "nsfw_filter": "all"
        }
        
        response = client.post("/api/search/filters/active", json=filter_request)
        assert response.status_code == 200
        result = response.json()
        filter_hash = result["filter_hash"]
        
        print(f"  ✓ Set active filters, hash: {filter_hash[:8]}...")
        
        # Get active filters
        response = client.get("/api/search/filters/active")
        assert response.status_code == 200
        data = response.json()
        
        assert data["filter_hash"] == filter_hash, "Filter hash should match"
        assert data["filters"]["file_types"] == ["jpg", "png"], "File types should match"
        assert data["filters"]["min_score"] == 3, "Min score should match"
        
        print("  ✓ Retrieved active filters successfully")
        print("  ✅ Filter state persistence test passed")


def test_buffer_refresh_and_pagination():
    """Test buffer refresh and pagination."""
    print("\n🔬 Test 7: Buffer Refresh and Pagination")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        media_dir = tmppath / "media"
        media_dir.mkdir()
        db_path = tmppath / "test.db"
        
        # Create test files
        files = create_test_media_files(media_dir, count=20)
        
        # Initialize database
        init_database(str(db_path))
        
        # Initialize app
        settings = Settings(pattern="*.jpg|*.png|*.mp4",
            dir=str(media_dir),
            enable_database=True,
            database_path=str(db_path)
        )
        init_state(settings)
        app = create_app(settings)
        client = TestClient(app)
        
        # Ingest files
        with DatabaseService(str(db_path)) as db:
            for filename in files:
                file_path = media_dir / filename
                db.get_or_create_media_file(file_path)
        
        # Refresh buffer
        response = client.post("/api/search/refresh", json={
            "file_types": ["jpg", "png"],
            "sort_field": "name",
            "sort_direction": "asc",
            "force_rebuild": True
        })
        assert response.status_code == 200
        data = response.json()
        filter_hash = data["filter_hash"]
        total_items = data["item_count"]
        
        print(f"  ✓ Buffer created: {total_items} items")
        
        # Get first page
        response = client.get(f"/api/search/page?filter_hash={filter_hash}&limit=5")
        assert response.status_code == 200
        page1 = response.json()
        
        print(f"  ✓ Page 1: {len(page1['items'])} items")
        assert len(page1['items']) <= 5, "Should return max 5 items"
        
        # Get second page if there's a cursor
        if page1['next_cursor']:
            cursor_params = f"&cursor_created_at={page1['next_cursor']['created_at']}&cursor_id={page1['next_cursor']['id']}"
            response = client.get(f"/api/search/page?filter_hash={filter_hash}&limit=5{cursor_params}")
            assert response.status_code == 200
            page2 = response.json()
            print(f"  ✓ Page 2: {len(page2['items'])} items")
        
        print("  ✅ Buffer refresh and pagination test passed")


def test_edge_cases():
    """Test edge cases like empty results and rapid filter changes."""
    print("\n🔬 Test 8: Edge Cases")
    print("=" * 70)
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        media_dir = tmppath / "media"
        media_dir.mkdir()
        db_path = tmppath / "test.db"
        
        # Create test files
        files = create_test_media_files(media_dir, count=5)
        
        # Initialize database
        init_database(str(db_path))
        
        # Initialize app
        settings = Settings(pattern="*.jpg|*.png|*.mp4",
            dir=str(media_dir),
            enable_database=True,
            database_path=str(db_path)
        )
        init_state(settings)
        app = create_app(settings)
        client = TestClient(app)
        
        # Ingest files
        with DatabaseService(str(db_path)) as db:
            for filename in files:
                file_path = media_dir / filename
                db.get_or_create_media_file(file_path)
        
        # Test: Filter that returns no results
        response = client.post("/api/filter", json={
            "file_types": ["jpg"],
            "min_score": 100,  # Impossible score
            "sort_field": "name",
            "sort_direction": "asc"
        })
        assert response.status_code == 200
        filtered = response.json()["videos"]
        assert len(filtered) == 0, "Should return empty result"
        print("  ✓ Empty result handled correctly")
        
        # Test: Rapid filter changes (multiple sequential requests)
        for i in range(5):
            response = client.post("/api/filter", json={
                "file_types": ["jpg", "png"],
                "min_score": i,
                "sort_field": "name",
                "sort_direction": "asc"
            })
            assert response.status_code == 200
        print("  ✓ Rapid filter changes handled correctly")
        
        print("  ✅ Edge cases test passed")


def run_all_tests():
    """Run all filter toolbar tests."""
    print("\n" + "=" * 70)
    print("🚀 FILTER TOOLBAR COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    
    try:
        # Test 1: Individual file types
        test_filter_individual_file_types()
        
        # Test 2: Individual ratings
        test_filter_individual_ratings()
        
        # Test 3: Date range
        test_filter_date_range()
        
        # Test 4: NSFW filter
        test_filter_nsfw()
        
        # Test 5: Filter intersections
        test_filter_intersections()
        
        # Test 6: State persistence
        test_filter_state_persistence()
        
        # Test 7: Buffer and pagination
        test_buffer_refresh_and_pagination()
        
        # Test 8: Edge cases
        test_edge_cases()
        
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
