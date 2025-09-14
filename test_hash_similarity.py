#!/usr/bin/env python3
"""
Test script for perceptual hash similarity detection.
"""

import sys
from pathlib import Path

# Add the app directory to the Python path
sys.path.insert(0, str(Path(__file__).parent))

from app.utils.hashing import compute_perceptual_hash
from app.settings import Settings
from app.database.engine import init_database
from app.database.service import DatabaseService
from PIL import Image, ImageDraw
import random

def create_complex_image(path: Path, size=(200, 200), pattern="gradient"):
    """Create more complex test images for similarity testing."""
    img = Image.new('RGB', size, (255, 255, 255))
    draw = ImageDraw.Draw(img)
    
    if pattern == "gradient":
        # Create a gradient
        for y in range(size[1]):
            color_value = int(255 * y / size[1])
            draw.rectangle([0, y, size[0], y+1], fill=(color_value, 0, 255-color_value))
    
    elif pattern == "circles":
        # Create random circles
        for _ in range(5):
            x = random.randint(0, size[0])
            y = random.randint(0, size[1])
            r = random.randint(10, 50)
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            draw.ellipse([x-r, y-r, x+r, y+r], fill=color)
    
    elif pattern == "lines":
        # Create random lines
        for _ in range(10):
            x1 = random.randint(0, size[0])
            y1 = random.randint(0, size[1])
            x2 = random.randint(0, size[0])
            y2 = random.randint(0, size[1])
            color = (random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
            draw.line([x1, y1, x2, y2], fill=color, width=3)
    
    img.save(path)
    return path

def test_similarity_detection():
    """Test perceptual hash similarity detection."""
    print("Testing perceptual hash similarity detection...")
    
    test_dir = Path("./media")
    test_dir.mkdir(exist_ok=True)
    
    # Set random seed for reproducible results
    random.seed(42)
    
    # Create test images
    img1 = create_complex_image(test_dir / "complex1.png", pattern="gradient")
    img2 = create_complex_image(test_dir / "complex2.png", pattern="circles") 
    img3 = create_complex_image(test_dir / "complex3.png", pattern="lines")
    
    # Create a slightly modified version of img1 (should be similar)
    original = Image.open(img1)
    similar = original.copy()
    # Add slight noise
    draw = ImageDraw.Draw(similar)
    for _ in range(20):
        x = random.randint(0, similar.width-1)
        y = random.randint(0, similar.height-1)
        draw.point([x, y], fill=(255, 255, 255))
    similar.save(test_dir / "complex1_similar.png")
    
    # Compute hashes
    hash1 = compute_perceptual_hash(img1)
    hash2 = compute_perceptual_hash(img2)
    hash3 = compute_perceptual_hash(img3)
    hash_similar = compute_perceptual_hash(test_dir / "complex1_similar.png")
    
    print(f"Complex image 1 hash: {hash1}")
    print(f"Complex image 2 hash: {hash2}")
    print(f"Complex image 3 hash: {hash3}")
    print(f"Similar image hash: {hash_similar}")
    
    # Test database similarity search
    settings = Settings(dir=test_dir, enable_database=True)
    db_url = settings.get_database_url()
    init_database(db_url)
    
    with DatabaseService() as db:
        # Add files to database (this computes hashes automatically)
        for img_path in [img1, img2, img3, test_dir / "complex1_similar.png"]:
            db.get_or_create_media_file(img_path)
        
        # Test similarity search
        if hash1:
            print(f"\nSearching for files similar to {img1.name}...")
            similar_files = db.find_similar_files_by_hash(hash1, threshold=10)
            print(f"Found {len(similar_files)} similar files:")
            for file in similar_files:
                print(f"  - {file.filename} (hash: {file.phash})")
    
    # Clean up
    for img_path in [img1, img2, img3, test_dir / "complex1_similar.png"]:
        img_path.unlink()
    
    print("✅ Similarity detection test completed!")

def test_exact_duplicate_detection():
    """Test exact duplicate detection using content hash."""
    print("\nTesting exact duplicate detection...")
    
    test_dir = Path("./media")
    
    # Create an image
    original_path = test_dir / "original.png"
    create_complex_image(original_path, pattern="gradient")
    
    # Create an exact copy (same pixel data)
    duplicate_path = test_dir / "duplicate.png" 
    original = Image.open(original_path)
    original.save(duplicate_path)
    
    # Create a similar but different image (save as different format)
    different_path = test_dir / "different.jpg"
    original.save(different_path, format='JPEG', quality=95)  # JPEG compression makes it different
    
    # Test with database
    settings = Settings(dir=test_dir, enable_database=True)
    db_url = settings.get_database_url()
    init_database(db_url)
    
    with DatabaseService() as db:
        # Add files to database
        original_file = db.get_or_create_media_file(original_path)
        duplicate_file = db.get_or_create_media_file(duplicate_path)
        different_file = db.get_or_create_media_file(different_path)
        
        print(f"Original hash: {original_file.media_file_id}")
        print(f"Duplicate hash: {duplicate_file.media_file_id}")
        print(f"Different hash: {different_file.media_file_id}")
        
        # Exact duplicates should have identical content hashes
        assert original_file.media_file_id == duplicate_file.media_file_id, "Exact duplicates should have identical content hashes"
        assert original_file.media_file_id != different_file.media_file_id, "Different files should have different content hashes"
        
        print("✅ Exact duplicate detection working correctly!")
    
    # Clean up
    for path in [original_path, duplicate_path, different_path]:
        if path.exists():
            path.unlink()

if __name__ == "__main__":
    print("🔍 Testing Hash-Based Similarity and Duplicate Detection")
    print("=" * 60)
    
    try:
        test_similarity_detection()
        test_exact_duplicate_detection()
        print("\n🎉 All similarity detection tests passed!")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)