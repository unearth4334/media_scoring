#!/usr/bin/env python3
"""
Comprehensive test suite for the sidebar sorting redesign.
This script validates all the key functionality of the new sorting system.
"""

import asyncio
import json
import sys
from pathlib import Path

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent.parent))

import requests
from app.routers.media import FilterRequest, SortField, SortDirection


class SortingTestSuite:
    """Test suite for the new sorting functionality."""
    
    def __init__(self, base_url="http://127.0.0.1:7864"):
        self.base_url = base_url
        self.results = []
    
    def log_result(self, test_name, success, message=""):
        """Log a test result."""
        status = "✅ PASS" if success else "❌ FAIL"
        self.results.append((test_name, success, message))
        print(f"{status} {test_name}: {message}")
    
    def test_pydantic_models(self):
        """Test that Pydantic models work correctly."""
        test_cases = [
            {"sort_field": "name", "sort_direction": "asc"},
            {"sort_field": "rating", "sort_direction": "desc"},
            {"sort_field": "date", "sort_direction": "desc"},
            {"sort_field": "size", "sort_direction": "asc"},
        ]
        
        for case in test_cases:
            try:
                request = FilterRequest(**case)
                self.log_result(
                    f"Pydantic model: {case['sort_field']} {case['sort_direction']}", 
                    True,
                    f"field={request.sort_field.value}, direction={request.sort_direction.value}"
                )
            except Exception as e:
                self.log_result(
                    f"Pydantic model: {case['sort_field']} {case['sort_direction']}", 
                    False, 
                    str(e)
                )
    
    def test_api_endpoints(self):
        """Test that the API endpoints work with new parameters."""
        test_cases = [
            {"sort_field": "rating", "sort_direction": "desc", "description": "Rating ↓"},
            {"sort_field": "name", "sort_direction": "asc", "description": "Name ↑"},
            {"sort_field": "size", "sort_direction": "desc", "description": "Size ↓"},
            {"sort_field": "date", "sort_direction": "desc", "description": "Date ↓"},
        ]
        
        for case in test_cases:
            try:
                response = requests.post(
                    f"{self.base_url}/api/filter",
                    headers={"Content-Type": "application/json"},
                    json={
                        "sort_field": case["sort_field"],
                        "sort_direction": case["sort_direction"]
                    },
                    timeout=10
                )
                
                if response.status_code == 200:
                    data = response.json()
                    videos = data.get("videos", [])
                    filters_applied = data.get("filters_applied", {})
                    
                    # Check that sort parameters are in the response
                    has_sort_field = filters_applied.get("sort_field") == case["sort_field"]
                    has_sort_direction = filters_applied.get("sort_direction") == case["sort_direction"]
                    has_videos = len(videos) > 0
                    has_file_size = len(videos) == 0 or "file_size" in videos[0]
                    
                    success = has_sort_field and has_sort_direction and has_videos and has_file_size
                    message = f"videos={len(videos)}, sort_field={has_sort_field}, sort_direction={has_sort_direction}, file_size_field={has_file_size}"
                    
                    self.log_result(f"API {case['description']}", success, message)
                else:
                    self.log_result(f"API {case['description']}", False, f"HTTP {response.status_code}: {response.text[:100]}")
                    
            except Exception as e:
                self.log_result(f"API {case['description']}", False, str(e))
    
    def test_sorting_correctness(self):
        """Test that sorting actually works as expected."""
        # Test rating sorting (descending)
        try:
            response = requests.post(
                f"{self.base_url}/api/filter",
                headers={"Content-Type": "application/json"},
                json={"sort_field": "rating", "sort_direction": "desc"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                videos = data.get("videos", [])
                
                if len(videos) >= 2:
                    scores = [v.get("score", 0) for v in videos]
                    is_sorted_desc = all(scores[i] >= scores[i+1] for i in range(len(scores)-1))
                    self.log_result("Rating sort correctness", is_sorted_desc, f"scores: {scores[:5]}")
                else:
                    self.log_result("Rating sort correctness", True, "insufficient data for test")
            else:
                self.log_result("Rating sort correctness", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_result("Rating sort correctness", False, str(e))
        
        # Test name sorting (ascending) 
        try:
            response = requests.post(
                f"{self.base_url}/api/filter",
                headers={"Content-Type": "application/json"},
                json={"sort_field": "name", "sort_direction": "asc"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                videos = data.get("videos", [])
                
                if len(videos) >= 2:
                    names = [v.get("name", "") for v in videos]
                    is_sorted_asc = all(names[i] <= names[i+1] for i in range(len(names)-1))
                    self.log_result("Name sort correctness", is_sorted_asc, f"names: {names[:3]}")
                else:
                    self.log_result("Name sort correctness", True, "insufficient data for test")
            else:
                self.log_result("Name sort correctness", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_result("Name sort correctness", False, str(e))
    
    def test_response_format(self):
        """Test that responses include all required fields."""
        try:
            response = requests.post(
                f"{self.base_url}/api/filter",
                headers={"Content-Type": "application/json"},
                json={"sort_field": "rating", "sort_direction": "desc"},
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check top-level structure
                has_videos = "videos" in data
                has_count = "count" in data
                has_filters_applied = "filters_applied" in data
                
                # Check filters_applied structure
                filters = data.get("filters_applied", {})
                has_sort_field = "sort_field" in filters
                has_sort_direction = "sort_direction" in filters
                
                # Check video structure (if videos exist)
                videos = data.get("videos", [])
                if videos:
                    video = videos[0]
                    required_fields = ["name", "url", "score", "path", "file_size"]
                    has_required_fields = all(field in video for field in required_fields)
                else:
                    has_required_fields = True  # No videos to check
                
                success = all([has_videos, has_count, has_filters_applied, has_sort_field, has_sort_direction, has_required_fields])
                message = f"videos={has_videos}, count={has_count}, filters={has_filters_applied}, fields={has_required_fields}"
                
                self.log_result("Response format", success, message)
            else:
                self.log_result("Response format", False, f"HTTP {response.status_code}")
                
        except Exception as e:
            self.log_result("Response format", False, str(e))
    
    def run_all_tests(self):
        """Run all tests and provide a summary."""
        print("🎬 Sidebar Sorting Redesign - Comprehensive Test Suite")
        print("=" * 60)
        
        print("\n1. Testing Pydantic Models...")
        self.test_pydantic_models()
        
        print("\n2. Testing API Endpoints...")
        self.test_api_endpoints()
        
        print("\n3. Testing Sorting Correctness...")
        self.test_sorting_correctness()
        
        print("\n4. Testing Response Format...")
        self.test_response_format()
        
        # Summary
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        
        passed = sum(1 for _, success, _ in self.results if success)
        total = len(self.results)
        
        print(f"Total Tests: {total}")
        print(f"Passed: {passed}")
        print(f"Failed: {total - passed}")
        print(f"Success Rate: {passed/total*100:.1f}%")
        
        if passed == total:
            print("\n🎉 ALL TESTS PASSED! The sidebar sorting redesign is working correctly!")
        else:
            print(f"\n⚠️  {total - passed} tests failed. Review the output above for details.")
        
        return passed == total


if __name__ == "__main__":
    suite = SortingTestSuite()
    success = suite.run_all_tests()
    sys.exit(0 if success else 1)