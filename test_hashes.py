#!/usr/bin/env python3
"""
Test script for media file hash computation functionality.
"""

import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.hashing import compute_media_file_id, compute_perceptual_hash
from PIL import Image
import numpy as np

def create_test_image(path: Path, size=(100, 100), color=(255, 0, 0)):
    """Create a simple test image."""
    # Create a simple colored image
    img = Image.new('RGB', size, color)
    img.save(path)
    return path

def test_image_hashes():
    """Test hash computation for images."""
    print("Testing image hash computation...")
    
    # Create test images
    test_dir = Path("./media")
    test_dir.mkdir(exist_ok=True)
    
    # Create two identical images
    img1_path = create_test_image(test_dir / "test1.png", (100, 100), (255, 0, 0))  # Red
    img2_path = create_test_image(test_dir / "test2.png", (100, 100), (255, 0, 0))  # Red (identical)
    img3_path = create_test_image(test_dir / "test3.png", (100, 100), (0, 255, 0))  # Green (different)
    
    # Test content hash computation
    hash1 = compute_media_file_id(img1_path)
    hash2 = compute_media_file_id(img2_path)
    hash3 = compute_media_file_id(img3_path)
    
    print(f"Image 1 content hash: {hash1}")
    print(f"Image 2 content hash: {hash2}")
    print(f"Image 3 content hash: {hash3}")
    
    # Identical images should have identical content hashes
    assert hash1 == hash2, "Identical images should have identical content hashes"
    assert hash1 != hash3, "Different images should have different content hashes"
    print("✅ Content hash test passed!")
    
    # Test perceptual hash computation
    phash1 = compute_perceptual_hash(img1_path)
    phash2 = compute_perceptual_hash(img2_path)
    phash3 = compute_perceptual_hash(img3_path)
    
    print(f"Image 1 perceptual hash: {phash1}")
    print(f"Image 2 perceptual hash: {phash2}")
    print(f"Image 3 perceptual hash: {phash3}")
    
    # Similar images should have similar perceptual hashes
    assert phash1 == phash2, "Identical images should have identical perceptual hashes"
    print("✅ Perceptual hash test passed!")
    
    # Clean up
    img1_path.unlink()
    img2_path.unlink()
    img3_path.unlink()
    
    return True

def test_database_integration():
    """Test database integration with hash computation."""
    print("\nTesting database integration...")
    
    from app.settings import Settings
    from app.database.engine import init_database
    from app.database.service import DatabaseService
    
    # Create settings and initialize database
    settings = Settings(dir=Path("./media"), enable_database=True)
    db_url = settings.get_database_url()
    init_database(db_url)
    
    # Create a test image
    test_dir = Path("./media")
    test_img = create_test_image(test_dir / "hash_test.png", (50, 50), (128, 128, 128))
    
    try:
        # Test database service with hash computation
        with DatabaseService() as db:
            # Create media file (should compute hashes automatically)
            media_file = db.get_or_create_media_file(test_img)
            print(f"Created media file: {media_file.filename}")
            print(f"Content hash: {media_file.media_file_id}")
            print(f"Perceptual hash: {media_file.phash}")
            
            assert media_file.media_file_id is not None, "Content hash should be computed"
            assert media_file.phash is not None, "Perceptual hash should be computed"
            assert len(media_file.media_file_id) == 64, "SHA256 hash should be 64 characters"
            
            print("✅ Database integration test passed!")
            
            # Test hash update method
            original_hash = media_file.media_file_id
            success = db.update_media_file_hashes(test_img)
            assert success, "Hash update should succeed"
            
            # Verify hash is the same (since file didn't change)
            updated_media_file = db.get_or_create_media_file(test_img)
            assert updated_media_file.media_file_id == original_hash, "Hash should remain the same for unchanged file"
            print("✅ Hash update test passed!")
    
    finally:
        # Clean up
        test_img.unlink()

if __name__ == "__main__":
    print("🧪 Testing Media File Hash Computation")
    print("=" * 50)
    
    try:
        test_image_hashes()
        test_database_integration()
        print("\n🎉 All tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        sys.exit(1)