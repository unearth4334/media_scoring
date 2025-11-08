#!/usr/bin/env python3
"""Quick API test for buffer search endpoints."""

import sys
import tempfile
from pathlib import Path
import json

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi.testclient import TestClient
from app.main import create_app
from app.database.engine import init_database
from app.database.service import DatabaseService
from app.state import init_state
from app.settings import Settings


def test_buffer_api_endpoints():
    """Test buffer API endpoints with FastAPI TestClient."""
    print("\n🔬 Testing Buffer API Endpoints")
    print("=" * 70)
    
    # Create temporary directory and database
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Initialize test database
        db_path = tmppath / "test.db"
        db_url = f"sqlite:///{db_path}"
        
        print("Setting up test environment...")
        init_database(db_url)
        
        # Create test media files
        media_dir = tmppath / "media"
        media_dir.mkdir()
        
        with DatabaseService() as db:
            for i in range(50):
                file_path = media_dir / f"test_{i:03d}.jpg"
                file_path.touch()
                
                media_file = db.get_or_create_media_file(file_path)
                media_file.score = (i % 6)
                media_file.file_type = "image"
                media_file.extension = ".jpg"
        
        # Create settings
        settings = Settings(
            dir=media_dir,
            pattern="*.jpg",
            enable_database=True,
            database_url=db_url
        )
        
        # Initialize app state
        state = init_state(settings)
        
        # Create FastAPI app
        app = create_app()
        client = TestClient(app)
        
        print("✅ Test environment ready with 50 test items\n")
        
        # Test 1: Refresh endpoint
        print("Test 1: POST /api/search/refresh")
        print("-" * 70)
        
        refresh_response = client.post(
            "/api/search/refresh",
            json={
                "min_score": 3,
                "sort_field": "date",
                "sort_direction": "desc"
            }
        )
        
        assert refresh_response.status_code == 200, f"Expected 200, got {refresh_response.status_code}"
        refresh_data = refresh_response.json()
        
        print(f"✅ Status: {refresh_response.status_code}")
        print(f"   Filter hash: {refresh_data['filter_hash'][:16]}...")
        print(f"   Item count: {refresh_data['item_count']}")
        
        filter_hash = refresh_data['filter_hash']
        
        # Test 2: Page endpoint (first page)
        print("\nTest 2: GET /api/search/page (first page)")
        print("-" * 70)
        
        page_response = client.get(
            f"/api/search/page?filter_hash={filter_hash}&limit=10"
        )
        
        assert page_response.status_code == 200
        page_data = page_response.json()
        
        print(f"✅ Status: {page_response.status_code}")
        print(f"   Items returned: {page_data['count']}")
        print(f"   Has more: {page_data['has_more']}")
        
        assert page_data['count'] > 0, "Should return items"
        
        # Test 3: Page endpoint (second page with cursor)
        if page_data['next_cursor']:
            print("\nTest 3: GET /api/search/page (second page)")
            print("-" * 70)
            
            cursor = page_data['next_cursor']
            page2_response = client.get(
                f"/api/search/page?filter_hash={filter_hash}"
                f"&cursor_created_at={cursor['created_at']}"
                f"&cursor_id={cursor['id']}&limit=10"
            )
            
            assert page2_response.status_code == 200
            page2_data = page2_response.json()
            
            print(f"✅ Status: {page2_response.status_code}")
            print(f"   Items returned: {page2_data['count']}")
        
        # Test 4: Get active filters
        print("\nTest 4: GET /api/search/filters/active")
        print("-" * 70)
        
        active_response = client.get("/api/search/filters/active")
        
        assert active_response.status_code == 200
        active_data = active_response.json()
        
        print(f"✅ Status: {active_response.status_code}")
        print(f"   Has active filter: {active_data.get('filter_hash') is not None}")
        
        # Test 5: Set active filters (pending)
        print("\nTest 5: POST /api/search/filters/active")
        print("-" * 70)
        
        set_filter_response = client.post(
            "/api/search/filters/active",
            json={
                "keywords": ["test"],
                "min_score": 4
            }
        )
        
        assert set_filter_response.status_code == 200
        set_filter_data = set_filter_response.json()
        
        print(f"✅ Status: {set_filter_response.status_code}")
        print(f"   Filter hash: {set_filter_data['filter_hash'][:16]}...")
        
        # Test 6: Buffer stats
        print("\nTest 6: GET /api/search/buffer/stats")
        print("-" * 70)
        
        stats_response = client.get("/api/search/buffer/stats")
        
        assert stats_response.status_code == 200
        stats_data = stats_response.json()
        
        print(f"✅ Status: {stats_response.status_code}")
        print(f"   Buffer count: {stats_data['stats']['buffer_count']}")
        print(f"   Total items: {stats_data['stats']['total_items']}")
        print(f"   Storage: {stats_data['stats']['total_size_mb']:.2f} MB")
        
        # Test 7: Delete buffer
        print("\nTest 7: DELETE /api/search/buffer/{filter_hash}")
        print("-" * 70)
        
        delete_response = client.delete(f"/api/search/buffer/{filter_hash}")
        
        assert delete_response.status_code == 200
        delete_data = delete_response.json()
        
        print(f"✅ Status: {delete_response.status_code}")
        print(f"   Message: {delete_data['message']}")
        
        print("\n" + "=" * 70)
        print("🎉 All API endpoint tests passed!")


if __name__ == "__main__":
    try:
        # Check if fastapi and testclient are available
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            print("⏭️  Skipping API tests (requires fastapi and testclient)")
            print("    Install with: pip install fastapi httpx")
            sys.exit(0)
        
        test_buffer_api_endpoints()
        
    except AssertionError as e:
        print(f"\n❌ API test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
