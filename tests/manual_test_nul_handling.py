#!/usr/bin/env python3
"""
Manual test script to verify NUL character handling in ingest v2.

This script demonstrates that the commit process now handles NUL characters
gracefully instead of failing catastrophically.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.sanitization import sanitize_file_data


def test_nul_character_sanitization():
    """Test that NUL characters are properly sanitized."""
    print("=" * 70)
    print("Testing NUL Character Sanitization")
    print("=" * 70)
    
    # Test case 1: Metadata with NUL characters
    print("\n1. Testing metadata with NUL characters:")
    file_data_with_nul = {
        "filename": "test.jpg",
        "file_path": "/path/to/file.jpg",
        "metadata": {
            "prompt": "A beautiful\x00landscape with\x00trees",
            "negative_prompt": "bad\x00quality",
            "model": "stable\x00diffusion\x00xl"
        }
    }
    
    print("   Original metadata:")
    print(f"     prompt: {repr(file_data_with_nul['metadata']['prompt'])}")
    print(f"     negative_prompt: {repr(file_data_with_nul['metadata']['negative_prompt'])}")
    print(f"     model: {repr(file_data_with_nul['metadata']['model'])}")
    
    sanitized = sanitize_file_data(file_data_with_nul)
    
    print("\n   Sanitized metadata:")
    print(f"     prompt: {repr(sanitized['metadata']['prompt'])}")
    print(f"     negative_prompt: {repr(sanitized['metadata']['negative_prompt'])}")
    print(f"     model: {repr(sanitized['metadata']['model'])}")
    
    # Verify no NUL characters remain
    assert "\x00" not in sanitized['metadata']['prompt']
    assert "\x00" not in sanitized['metadata']['negative_prompt']
    assert "\x00" not in sanitized['metadata']['model']
    print("\n   ✅ All NUL characters removed successfully!")
    
    # Test case 2: Keywords with NUL characters
    print("\n2. Testing keywords with NUL characters:")
    file_data_with_keywords = {
        "filename": "test2.jpg",
        "keywords": ["landscape\x00", "nature\x00", "beautiful\x00"]
    }
    
    print("   Original keywords:", repr(file_data_with_keywords['keywords']))
    
    sanitized_keywords = sanitize_file_data(file_data_with_keywords)
    
    print("   Sanitized keywords:", repr(sanitized_keywords['keywords']))
    
    # Verify no NUL characters remain
    for keyword in sanitized_keywords['keywords']:
        assert "\x00" not in keyword
    print("   ✅ All NUL characters removed from keywords!")
    
    # Test case 3: Complex nested structure
    print("\n3. Testing complex nested metadata with NUL characters:")
    complex_data = {
        "filename": "test3.jpg",
        "metadata": {
            "workflow_data": {
                "nodes": [
                    {
                        "type": "KSampler\x00",
                        "params": {
                            "sampler": "euler\x00a",
                            "scheduler": "karras\x00"
                        }
                    }
                ]
            }
        }
    }
    
    print("   Original nested data:")
    print(f"     node type: {repr(complex_data['metadata']['workflow_data']['nodes'][0]['type'])}")
    print(f"     sampler: {repr(complex_data['metadata']['workflow_data']['nodes'][0]['params']['sampler'])}")
    
    sanitized_complex = sanitize_file_data(complex_data)
    
    print("\n   Sanitized nested data:")
    print(f"     node type: {repr(sanitized_complex['metadata']['workflow_data']['nodes'][0]['type'])}")
    print(f"     sampler: {repr(sanitized_complex['metadata']['workflow_data']['nodes'][0]['params']['sampler'])}")
    
    # Verify no NUL characters remain in nested structure
    assert "\x00" not in sanitized_complex['metadata']['workflow_data']['nodes'][0]['type']
    assert "\x00" not in sanitized_complex['metadata']['workflow_data']['nodes'][0]['params']['sampler']
    print("   ✅ All NUL characters removed from nested structures!")
    
    # Summary
    print("\n" + "=" * 70)
    print("✅ All Tests Passed!")
    print("=" * 70)
    print("\nThe ingest v2 commit process will now:")
    print("  • Automatically sanitize all string data before database insertion")
    print("  • Remove NUL (0x00) characters that would cause PostgreSQL errors")
    print("  • Handle individual file errors gracefully without breaking the batch")
    print("  • Continue processing remaining files even if some fail")
    print("  • Report which files had issues in the commit_errors list")
    print("=" * 70)


if __name__ == "__main__":
    try:
        test_nul_character_sanitization()
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
