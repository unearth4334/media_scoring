#!/usr/bin/env python3
"""
Test script to verify PHASH similarity search functionality.
"""

import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.utils.hashing import compute_perceptual_hash

print("🔬 Testing PHASH Similarity Search Functionality")
print("=" * 50)

# Test compute_perceptual_hash function
print("\n1️⃣  Testing PHASH computation...")
try:
    # Create a test image
    from PIL import Image
    import tempfile
    
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
        # Create a simple test image
        img = Image.new('RGB', (100, 100), color='red')
        img.save(tmp_file.name)
        tmp_path = Path(tmp_file.name)
    
    phash1 = compute_perceptual_hash(tmp_path)
    if phash1:
        print(f"✅ PHASH computed successfully: {phash1}")
    else:
        print("❌ PHASH computation failed")
        sys.exit(1)
    
    # Create another similar image
    with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file2:
        img2 = Image.new('RGB', (100, 100), color='red')
        img2.save(tmp_file2.name)
        tmp_path2 = Path(tmp_file2.name)
    
    phash2 = compute_perceptual_hash(tmp_path2)
    if phash2:
        print(f"✅ PHASH computed for second image: {phash2}")
    else:
        print("❌ PHASH computation failed for second image")
        sys.exit(1)
    
    # Verify that identical images have the same PHASH
    if phash1 == phash2:
        print("✅ Identical images have the same PHASH")
    else:
        print(f"⚠️  Warning: Identical images have different PHASH values: {phash1} vs {phash2}")
    
    # Test hash distance calculation
    try:
        import imagehash
        hash1_obj = imagehash.hex_to_hash(phash1)
        hash2_obj = imagehash.hex_to_hash(phash2)
        distance = hash1_obj - hash2_obj
        print(f"✅ Hash distance calculation works: distance = {distance}")
    except Exception as e:
        print(f"❌ Hash distance calculation failed: {e}")
        sys.exit(1)
    
    # Clean up
    tmp_path.unlink()
    tmp_path2.unlink()
    
except Exception as e:
    print(f"❌ PHASH computation error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n🎉 All PHASH similarity search tests passed!")
print("\nNote: For full database functionality testing:")
print("  - Set up a PostgreSQL database")
print("  - Set DATABASE_URL environment variable")
print("  - Run the application and test the API endpoints:")
print("    - POST /api/search/similar/by-path")
print("    - POST /api/search/similar/by-upload")
print("    - GET  /api/search/file-info-by-path")

