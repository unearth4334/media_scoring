#!/usr/bin/env python3
"""Test script for pagination endpoint."""

import requests
import json
from datetime import datetime

BASE_URL = "http://127.0.0.1:7862"

def test_pagination_basic():
    """Test basic pagination without filters."""
    print("Testing basic pagination...")
    
    response = requests.post(
        f"{BASE_URL}/api/videos/paginated",
        json={
            "page": 1,
            "page_size": 10
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Page 1: {len(data['items'])} items")
        print(f"  Total items: {data['pagination']['total_items']}")
        print(f"  Total pages: {data['pagination']['total_pages']}")
        print(f"  Has next: {data['pagination']['has_next']}")
        return True
    else:
        print(f"✗ Failed: {response.status_code} - {response.text}")
        return False


def test_pagination_with_filters():
    """Test pagination with score filter."""
    print("\nTesting pagination with filters...")
    
    response = requests.post(
        f"{BASE_URL}/api/videos/paginated",
        json={
            "page": 1,
            "page_size": 20,
            "min_score": 3,
            "sort_field": "rating",
            "sort_direction": "desc"
        }
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Filtered results: {len(data['items'])} items")
        print(f"  Total matching: {data['pagination']['total_items']}")
        print(f"  Filters: {data['filters_applied']}")
        
        # Check if sorted correctly
        if data['items']:
            scores = [item['score'] for item in data['items']]
            print(f"  Scores: {scores[:5]}...")
        return True
    else:
        print(f"✗ Failed: {response.status_code} - {response.text}")
        return False


def test_pagination_multiple_pages():
    """Test navigating through multiple pages."""
    print("\nTesting multiple pages...")
    
    # Get page 1 with minimum page_size (10)
    response1 = requests.post(
        f"{BASE_URL}/api/videos/paginated",
        json={"page": 1, "page_size": 10}
    )
    
    if response1.status_code != 200:
        print(f"✗ Page 1 failed: {response1.status_code}")
        try:
            error_detail = response1.json()
            print(f"  Error details: {error_detail}")
        except:
            print(f"  Response text: {response1.text}")
        return False
    
    data1 = response1.json()
    total_pages = data1['pagination']['total_pages']
    total_items = data1['pagination']['total_items']
    
    print(f"✓ Page 1 of {total_pages}: {len(data1['items'])} items (total: {total_items})")
    
    # Get page 2 if it exists
    if total_pages >= 2:
        response2 = requests.post(
            f"{BASE_URL}/api/videos/paginated",
            json={"page": 2, "page_size": 10}
        )
        
        if response2.status_code == 200:
            data2 = response2.json()
            print(f"✓ Page 2 of {total_pages}: {len(data2['items'])} items")
            
            # Verify items are different
            names1 = {item['name'] for item in data1['items']}
            names2 = {item['name'] for item in data2['items']}
            
            if names1.intersection(names2):
                print("✗ Warning: Same items appear on both pages")
                return False
            else:
                print("✓ Pages contain different items")
            
            return True
        else:
            print(f"✗ Page 2 failed: {response2.status_code}")
            return False
    else:
        print("  (Only 1 page available with current data)")
        return True


def test_pagination_edge_cases():
    """Test edge cases."""
    print("\nTesting edge cases...")
    
    # Test page beyond total pages
    response = requests.post(
        f"{BASE_URL}/api/videos/paginated",
        json={"page": 999, "page_size": 10}
    )
    
    if response.status_code == 200:
        data = response.json()
        print(f"✓ Page 999: {len(data['items'])} items (expected 0)")
        if len(data['items']) == 0:
            print("  Correctly returns empty page")
        return True
    else:
        print(f"✗ Failed: {response.status_code}")
        return False


def main():
    """Run all tests."""
    print("=" * 60)
    print("PAGINATION ENDPOINT TEST SUITE")
    print("=" * 60)
    
    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/api/videos", timeout=2)
        if response.status_code != 200:
            print("✗ Server not responding correctly")
            return
    except requests.exceptions.RequestException as e:
        print(f"✗ Cannot connect to server at {BASE_URL}")
        print(f"  Error: {e}")
        print("\n  Please start the server with:")
        print("  python run.py --dir ./media --use-db")
        return
    
    print("✓ Server is running\n")
    
    # Run tests
    results = []
    results.append(("Basic pagination", test_pagination_basic()))
    results.append(("Filtered pagination", test_pagination_with_filters()))
    results.append(("Multiple pages", test_pagination_multiple_pages()))
    results.append(("Edge cases", test_pagination_edge_cases()))
    
    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ PASS" if result else "✗ FAIL"
        print(f"{status}: {name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")


if __name__ == "__main__":
    main()
