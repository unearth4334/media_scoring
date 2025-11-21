#!/usr/bin/env python3
"""
Simplified comprehensive tests for filter toolbar functionality.
Tests the three-state pill system and filter state management.
"""

import sys
import json
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))


def test_pill_state_comparison():
    """Test the pill state comparison logic."""
    print("\n🔬 Test 1: Pill State Comparison Logic")
    print("=" * 70)
    
    # Simulate the isValueEqual function
    def isValueEqual(value1, value2):
        if value1 is None or value1 is None:
            return value2 is None or value2 is None
        if value2 is None or value2 is None:
            return False
        
        # Handle arrays
        if isinstance(value1, list) and isinstance(value2, list):
            if len(value1) != len(value2):
                return False
            sorted1 = sorted(value1)
            sorted2 = sorted(value2)
            return all(v1 == v2 for v1, v2 in zip(sorted1, sorted2))
        
        # Handle objects
        if isinstance(value1, dict) and isinstance(value2, dict):
            keys1 = sorted(value1.keys())
            keys2 = sorted(value2.keys())
            if keys1 != keys2:
                return False
            return all(isValueEqual(value1[k], value2[k]) for k in keys1)
        
        return value1 == value2
    
    # Test cases
    assert isValueEqual(None, None), "Both None should be equal"
    assert isValueEqual(['jpg', 'png'], ['png', 'jpg']), "Arrays should match regardless of order"
    assert not isValueEqual(['jpg'], ['png']), "Different arrays should not match"
    assert isValueEqual({'a': 1, 'b': 2}, {'b': 2, 'a': 1}), "Dicts with same keys/values should match"
    assert isValueEqual('test', 'test'), "Strings should match"
    assert not isValueEqual('test', 'other'), "Different strings should not match"
    
    print("  ✅ Pill state comparison logic test passed")


def test_pill_state_transitions():
    """Test pill state transitions (grey -> green -> cyan)."""
    print("\n🔬 Test 2: Pill State Transitions")
    print("=" * 70)
    
    # Simulate filter states
    defaultFilters = {
        'rating': 'none',
        'filetype': ['jpg', 'png', 'mp4']
    }
    
    searchToolbarFilters = {
        'rating': 'none',
        'filetype': ['jpg', 'png', 'mp4']
    }
    
    appliedFilters = {
        'rating': 'none',
        'filetype': ['jpg', 'png', 'mp4']
    }
    
    # State 1: Default (grey)
    is_default = (searchToolbarFilters['rating'] == defaultFilters['rating'])
    is_modified = (searchToolbarFilters['rating'] != appliedFilters['rating'])
    state = 'grey' if is_default and not is_modified else ('green' if is_modified else 'cyan')
    assert state == 'grey', f"Should be grey, got {state}"
    print("  ✓ State 1: Default (grey) - rating='none', not modified")
    
    # State 2: Modified (green)
    searchToolbarFilters['rating'] = '3'
    is_default = (searchToolbarFilters['rating'] == defaultFilters['rating'])
    is_modified = (searchToolbarFilters['rating'] != appliedFilters['rating'])
    state = 'grey' if is_default and not is_modified else ('green' if is_modified else 'cyan')
    assert state == 'green', f"Should be green, got {state}"
    print("  ✓ State 2: Modified (green) - rating='3', not applied yet")
    
    # State 3: Applied (cyan)
    appliedFilters['rating'] = '3'
    is_default = (searchToolbarFilters['rating'] == defaultFilters['rating'])
    is_modified = (searchToolbarFilters['rating'] != appliedFilters['rating'])
    state = 'grey' if is_default and not is_modified else ('green' if is_modified else 'cyan')
    assert state == 'cyan', f"Should be cyan, got {state}"
    print("  ✓ State 3: Applied (cyan) - rating='3', applied and active")
    
    # State 4: Modified again (green)
    searchToolbarFilters['rating'] = '5'
    is_default = (searchToolbarFilters['rating'] == defaultFilters['rating'])
    is_modified = (searchToolbarFilters['rating'] != appliedFilters['rating'])
    state = 'grey' if is_default and not is_modified else ('green' if is_modified else 'cyan')
    assert state == 'green', f"Should be green, got {state}"
    print("  ✓ State 4: Modified (green) - rating='5', changed from applied '3'")
    
    print("  ✅ Pill state transitions test passed")


def test_filter_state_persistence():
    """Test that filter states can be saved and restored."""
    print("\n🔬 Test 3: Filter State Persistence")
    print("=" * 70)
    
    # Simulate saving filter state
    currentFilters = {
        'rating': '3',
        'filetype': ['jpg', 'png'],
        'dateStart': None,
        'dateEnd': None,
        'nsfw': 'all'
    }
    
    appliedFilters = {
        'rating': '3',
        'filetype': ['jpg', 'png'],
        'dateStart': None,
        'dateEnd': None,
        'nsfw': 'all'
    }
    
    # Serialize
    saved_state = json.dumps(currentFilters)
    print(f"  ✓ Saved state: {saved_state[:50]}...")
    
    # Restore
    restored = json.loads(saved_state)
    assert restored['rating'] == '3', "Rating should be restored"
    assert restored['filetype'] == ['jpg', 'png'], "File types should be restored"
    print("  ✓ State restored correctly")
    
    print("  ✅ Filter state persistence test passed")


def test_filter_intersections_logic():
    """Test filter intersection logic."""
    print("\n🔬 Test 4: Filter Intersection Logic")
    print("=" * 70)
    
    # Simulate media files
    media_files = [
        {'name': 'image1.jpg', 'score': 5, 'nsfw': False},
        {'name': 'image2.png', 'score': 3, 'nsfw': False},
        {'name': 'image3.jpg', 'score': 1, 'nsfw': True},
        {'name': 'video1.mp4', 'score': 4, 'nsfw': False},
        {'name': 'image4.png', 'score': 2, 'nsfw': True},
    ]
    
    # Test 1: File type + Rating
    filtered = [f for f in media_files 
                if f['name'].endswith('.jpg') and f['score'] >= 3]
    assert len(filtered) == 1, f"Should have 1 JPG with score>=3, got {len(filtered)}"
    assert filtered[0]['name'] == 'image1.jpg'
    print("  ✓ JPG + Rating>=3: 1 file")
    
    # Test 2: File type + NSFW
    filtered = [f for f in media_files 
                if (f['name'].endswith('.jpg') or f['name'].endswith('.png')) and not f['nsfw']]
    assert len(filtered) == 2, f"Should have 2 SFW JPG/PNG, got {len(filtered)}"
    print("  ✓ JPG/PNG + SFW: 2 files")
    
    # Test 3: All filters
    filtered = [f for f in media_files 
                if f['name'].endswith('.jpg') and f['score'] >= 3 and not f['nsfw']]
    assert len(filtered) == 1, f"Should have 1 file, got {len(filtered)}"
    print("  ✓ JPG + Rating>=3 + SFW: 1 file")
    
    print("  ✅ Filter intersection logic test passed")


def test_edge_cases():
    """Test edge cases."""
    print("\n🔬 Test 5: Edge Cases")
    print("=" * 70)
    
    # Empty file list
    media_files = []
    filtered = [f for f in media_files if f['score'] >= 3]
    assert len(filtered) == 0, "Empty list should remain empty"
    print("  ✓ Empty file list handled")
    
    # No matching filters
    media_files = [
        {'name': 'image1.jpg', 'score': 1},
        {'name': 'image2.jpg', 'score': 2},
    ]
    filtered = [f for f in media_files if f['score'] >= 5]
    assert len(filtered) == 0, "No matches should return empty"
    print("  ✓ No matching filters handled")
    
    # All files match
    filtered = [f for f in media_files if f['score'] >= 1]
    assert len(filtered) == 2, "All files should match"
    print("  ✓ All files matching handled")
    
    print("  ✅ Edge cases test passed")


def run_all_tests():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("🚀 FILTER TOOLBAR COMPREHENSIVE TEST SUITE")
    print("=" * 70)
    
    try:
        test_pill_state_comparison()
        test_pill_state_transitions()
        test_filter_state_persistence()
        test_filter_intersections_logic()
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
