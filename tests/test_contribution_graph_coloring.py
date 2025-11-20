#!/usr/bin/env python3
"""
Test the contribution graph coloring logic.
This validates that the color range applies from the lowest non-zero tally to the highest,
and that cells with zero tally are black (level 0).
"""

def test_get_activity_level_logic():
    """Test the JavaScript getActivityLevel logic in Python equivalent."""
    
    def get_activity_level(count, min_non_zero_count, max_count):
        """
        Python equivalent of the JavaScript getActivityLevel function.
        
        Args:
            count: The count for this day
            min_non_zero_count: The minimum non-zero count across all days
            max_count: The maximum count across all days
            
        Returns:
            Activity level from 0 (zero count/black) to 4 (highest)
        """
        # Zero count gets level 0 (will be styled as black)
        if count == 0:
            return 0
        
        # Handle edge case where all non-zero values are the same
        if min_non_zero_count == max_count:
            return 4
        
        # Calculate percentage within the non-zero range
        percentage = (count - min_non_zero_count) / (max_count - min_non_zero_count)
        
        # Distribute levels 1-4 based on percentage within non-zero range
        if percentage >= 0.75:
            return 4
        if percentage >= 0.50:
            return 3
        if percentage >= 0.25:
            return 2
        return 1
    
    # Test 1: Mixed values with zeros
    print("Test 1: Mixed values with zeros")
    data = [0, 0, 1, 5, 10]
    non_zero = [c for c in data if c > 0]
    min_nz = min(non_zero)
    max_val = max(data)
    
    assert get_activity_level(0, min_nz, max_val) == 0, "Zero should be level 0 (black)"
    assert get_activity_level(1, min_nz, max_val) == 1, "Min non-zero (1) should be level 1"
    assert get_activity_level(10, min_nz, max_val) == 4, "Max (10) should be level 4"
    print("  ✓ Passed")
    
    # Test 2: All same non-zero value
    print("Test 2: All same non-zero value")
    data = [0, 0, 5, 5, 5]
    non_zero = [c for c in data if c > 0]
    min_nz = min(non_zero)
    max_val = max(data)
    
    assert get_activity_level(0, min_nz, max_val) == 0, "Zero should be level 0"
    assert get_activity_level(5, min_nz, max_val) == 4, "All non-zero should be level 4"
    print("  ✓ Passed")
    
    # Test 3: Wide range
    print("Test 3: Wide range")
    data = [0, 1, 10, 50, 100]
    non_zero = [c for c in data if c > 0]
    min_nz = min(non_zero)
    max_val = max(data)
    
    assert get_activity_level(0, min_nz, max_val) == 0, "Zero should be level 0"
    assert get_activity_level(1, min_nz, max_val) == 1, "Min non-zero (1) should be level 1"
    assert get_activity_level(100, min_nz, max_val) == 4, "Max (100) should be level 4"
    
    # Mid-range value (50) should be level 2 (between 25% and 50%)
    # percentage = (50-1)/(100-1) = 49/99 = 0.494... which is >= 0.25 but < 0.50
    assert get_activity_level(50, min_nz, max_val) == 2, "Mid-range should be level 2"
    print("  ✓ Passed")
    
    # Test 4: Verify zero is always black
    print("Test 4: Zero always gets level 0 (black)")
    assert get_activity_level(0, 1, 10) == 0
    assert get_activity_level(0, 5, 100) == 0
    assert get_activity_level(0, 1, 1) == 0
    print("  ✓ Passed")
    
    # Test 5: Edge case - range of 2 values
    print("Test 5: Range with only 2 different non-zero values")
    data = [0, 0, 1, 1, 10, 10]
    non_zero = [c for c in data if c > 0]
    min_nz = min(non_zero)
    max_val = max(data)
    
    assert get_activity_level(0, min_nz, max_val) == 0, "Zero should be level 0"
    assert get_activity_level(1, min_nz, max_val) == 1, "Min (1) should be level 1"
    assert get_activity_level(10, min_nz, max_val) == 4, "Max (10) should be level 4"
    print("  ✓ Passed")
    
    print("\n✅ All tests passed!")


if __name__ == "__main__":
    test_get_activity_level_logic()
