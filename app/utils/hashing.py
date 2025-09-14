"""Hash computation utilities for media files."""

import hashlib
import logging
import subprocess
from pathlib import Path
from typing import Optional

try:
    from PIL import Image
except ImportError:
    Image = None

try:
    import imagehash
except ImportError:
    imagehash = None

logger = logging.getLogger(__name__)


def compute_media_file_id(file_path: Path) -> Optional[str]:
    """Compute SHA256 hash of exact pixel content for media file.
    
    For images: hash the raw pixel data
    For videos: hash the first frame pixel data
    """
    try:
        ext = file_path.suffix.lower()
        
        if ext in {".png", ".jpg", ".jpeg"}:
            return compute_image_content_hash(file_path)
        elif ext == ".mp4":
            return compute_video_frame_hash(file_path)
        else:
            logger.warning(f"Unsupported file type for hash computation: {ext}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to compute media_file_id for {file_path}: {e}")
        return None


def compute_perceptual_hash(file_path: Path) -> Optional[str]:
    """Compute perceptual hash for similarity detection.
    
    Uses imagehash library to create a hash that's similar for visually similar images.
    For videos, uses the first frame.
    """
    try:
        if imagehash is None:
            logger.warning("imagehash library not available")
            return None
            
        ext = file_path.suffix.lower()
        
        if ext in {".png", ".jpg", ".jpeg"}:
            return compute_image_perceptual_hash(file_path)
        elif ext == ".mp4":
            return compute_video_frame_perceptual_hash(file_path)
        else:
            logger.warning(f"Unsupported file type for perceptual hash: {ext}")
            return None
            
    except Exception as e:
        logger.error(f"Failed to compute perceptual hash for {file_path}: {e}")
        return None


def compute_image_content_hash(file_path: Path) -> Optional[str]:
    """Compute SHA256 hash of image pixel data (ignoring metadata)."""
    try:
        if Image is None:
            logger.warning("Pillow library not available")
            return None
            
        with Image.open(file_path) as img:
            # Convert to RGB to normalize color space (ignores metadata)
            rgb_img = img.convert('RGB')
            # Get raw pixel data
            pixel_data = rgb_img.tobytes()
            # Compute SHA256 hash
            return hashlib.sha256(pixel_data).hexdigest()
            
    except Exception as e:
        logger.error(f"Failed to compute image content hash for {file_path}: {e}")
        return None


def compute_image_perceptual_hash(file_path: Path) -> Optional[str]:
    """Compute perceptual hash for image."""
    try:
        if Image is None or imagehash is None:
            return None
            
        with Image.open(file_path) as img:
            # Use average hash (good balance of speed and accuracy)
            phash = imagehash.average_hash(img)
            return str(phash)
            
    except Exception as e:
        logger.error(f"Failed to compute image perceptual hash for {file_path}: {e}")
        return None


def compute_video_frame_hash(file_path: Path) -> Optional[str]:
    """Compute SHA256 hash of first video frame pixel data."""
    try:
        # Extract first frame using ffmpeg
        cmd = [
            "ffmpeg", "-i", str(file_path),
            "-vf", "select=eq(n\\,0)",  # Select first frame
            "-vframes", "1",
            "-f", "image2pipe",
            "-pix_fmt", "rgb24",
            "-c:v", "rawvideo",
            "-"
        ]
        
        cp = subprocess.run(cmd, capture_output=True, check=True)
        pixel_data = cp.stdout
        
        if pixel_data:
            return hashlib.sha256(pixel_data).hexdigest()
        else:
            logger.warning(f"No pixel data extracted from {file_path}")
            return None
            
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg failed to extract frame from {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to compute video frame hash for {file_path}: {e}")
        return None


def compute_video_frame_perceptual_hash(file_path: Path) -> Optional[str]:
    """Compute perceptual hash of first video frame."""
    try:
        if imagehash is None:
            return None
            
        # Extract first frame as PNG using ffmpeg
        cmd = [
            "ffmpeg", "-i", str(file_path),
            "-vf", "select=eq(n\\,0)",  # Select first frame
            "-vframes", "1",
            "-f", "image2pipe",
            "-c:v", "png",
            "-"
        ]
        
        cp = subprocess.run(cmd, capture_output=True, check=True)
        
        if cp.stdout and Image is not None:
            import io
            img = Image.open(io.BytesIO(cp.stdout))
            phash = imagehash.average_hash(img)
            return str(phash)
        else:
            logger.warning(f"No frame data extracted from {file_path}")
            return None
            
    except subprocess.CalledProcessError as e:
        logger.error(f"ffmpeg failed to extract frame from {file_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to compute video frame perceptual hash for {file_path}: {e}")
        return None