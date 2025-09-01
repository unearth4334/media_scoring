"""Thumbnail generation utilities"""
import subprocess
import threading
from pathlib import Path
from typing import List, Dict, Any

try:
    from PIL import Image
except ImportError:
    Image = None


# Thumbnail progress tracking
THUMBNAIL_PROGRESS = {
    "generating": False,
    "current": 0,
    "total": 0,
    "current_file": ""
}


def thumbnails_dir_for(directory: Path) -> Path:
    """Get thumbnails directory for a media directory"""
    thumb_dir = directory / ".thumbnails"
    thumb_dir.mkdir(exist_ok=True, parents=True)
    return thumb_dir


def thumbnail_path_for(media_path: Path) -> Path:
    """Get thumbnail path for a media file"""
    thumb_dir = thumbnails_dir_for(media_path.parent)
    return thumb_dir / f"{media_path.stem}_thumbnail.jpg"


def generate_thumbnail_for_image(image_path: Path, output_path: Path, height: int = 64) -> bool:
    """Generate thumbnail for an image file"""
    if Image is None:
        return False
    try:
        with Image.open(image_path) as img:
            # Calculate width maintaining aspect ratio
            aspect_ratio = img.width / img.height
            width = int(height * aspect_ratio)
            img.thumbnail((width, height), Image.Resampling.LANCZOS)
            img.save(output_path, "JPEG", quality=85)
        return True
    except Exception:
        return False


def generate_thumbnail_for_video(video_path: Path, output_path: Path, height: int = 64) -> bool:
    """Generate thumbnail for a video file using ffmpeg"""
    try:
        # Use ffmpeg to extract a frame and resize it
        cmd = [
            "ffmpeg", "-y", "-i", str(video_path),
            "-vf", f"thumbnail,scale=-1:{height}",
            "-frames:v", "1",
            "-q:v", "2",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        return result.returncode == 0
    except Exception:
        return False


def generate_thumbnail(media_path: Path, height: int = 64) -> bool:
    """Generate thumbnail for a media file (image or video)"""
    if not media_path.exists():
        return False
    
    thumb_path = thumbnail_path_for(media_path)
    if thumb_path.exists():
        return True  # Already exists
    
    ext = media_path.suffix.lower()
    if ext in ['.jpg', '.jpeg', '.png']:
        return generate_thumbnail_for_image(media_path, thumb_path, height)
    elif ext in ['.mp4']:
        return generate_thumbnail_for_video(media_path, thumb_path, height)
    return False


def generate_thumbnails_for_directory(directory: Path, file_list: List[Path], height: int = 64) -> None:
    """Generate thumbnails for all files in directory (background task)"""
    global THUMBNAIL_PROGRESS
    
    THUMBNAIL_PROGRESS["generating"] = True
    THUMBNAIL_PROGRESS["current"] = 0
    THUMBNAIL_PROGRESS["total"] = len(file_list)
    
    try:
        for i, media_path in enumerate(file_list):
            THUMBNAIL_PROGRESS["current"] = i + 1
            THUMBNAIL_PROGRESS["current_file"] = media_path.name
            generate_thumbnail(media_path, height)
    finally:
        THUMBNAIL_PROGRESS["generating"] = False
        THUMBNAIL_PROGRESS["current_file"] = ""