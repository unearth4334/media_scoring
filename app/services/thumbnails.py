"""Thumbnail generation service for images and videos."""

import subprocess
import threading
from pathlib import Path
from typing import List

from ..state import get_state

try:
    from PIL import Image
except ImportError:
    Image = None


def get_thumbnails_dir_for(directory: Path) -> Path:
    """Get thumbnails directory for a media directory."""
    thumb_dir = directory / ".thumbnails"
    thumb_dir.mkdir(exist_ok=True, parents=True)
    return thumb_dir


def get_large_thumbnails_dir_for(directory: Path) -> Path:
    """Get large thumbnails directory for a media directory."""
    thumb_dir = directory / ".thumbnails_large"
    thumb_dir.mkdir(exist_ok=True, parents=True)
    return thumb_dir


def get_thumbnail_path_for(media_path: Path, large: bool = False) -> Path:
    """Get thumbnail path for a media file.
    
    Args:
        media_path: Path to the media file
        large: If True, get path for large thumbnail, otherwise regular thumbnail
    """
    if large:
        thumb_dir = get_large_thumbnails_dir_for(media_path.parent)
        return thumb_dir / f"{media_path.stem}_thumbnail_large.jpg"
    else:
        thumb_dir = get_thumbnails_dir_for(media_path.parent)
        return thumb_dir / f"{media_path.stem}_thumbnail.jpg"


def generate_thumbnail_for_image(image_path: Path, output_path: Path, height: int = None) -> bool:
    """Generate thumbnail for an image file.
    
    Args:
        image_path: Path to the source image
        output_path: Path where thumbnail will be saved
        height: Height in pixels for the thumbnail (if None, uses settings.thumbnail_height)
    """
    state = get_state()
    try:
        if Image is None:
            state.logger.warning("PIL not available, cannot generate image thumbnails")
            return False
        
        if height is None:
            height = state.settings.thumbnail_height
        
        with Image.open(image_path) as img:
            # Calculate width to maintain aspect ratio
            aspect_ratio = img.width / img.height
            width = int(height * aspect_ratio)
            
            # Resize image
            img.thumbnail((width, height), Image.Resampling.LANCZOS)
            
            # Convert to RGB if needed (for RGBA images)
            if img.mode in ('RGBA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            
            # Save as JPEG
            img.save(output_path, 'JPEG', quality=85, optimize=True)
            return True
    except Exception as e:
        state.logger.error(f"Failed to generate thumbnail for {image_path}: {e}")
        return False


def generate_thumbnail_for_video(video_path: Path, output_path: Path, height: int = None) -> bool:
    """Generate thumbnail for a video file by extracting first frame.
    
    Args:
        video_path: Path to the source video
        output_path: Path where thumbnail will be saved
        height: Height in pixels for the thumbnail (if None, uses settings.thumbnail_height)
    """
    state = get_state()
    try:
        if height is None:
            height = state.settings.thumbnail_height
            
        # Use ffmpeg to extract first frame
        cmd = [
            "ffmpeg", "-y", "-i", str(video_path), 
            "-vf", f"scale=-1:{height}",
            "-vframes", "1", "-q:v", "2",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True
        else:
            state.logger.error(f"ffmpeg failed for {video_path}: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        state.logger.error(f"ffmpeg timeout for {video_path}")
        return False
    except Exception as e:
        state.logger.error(f"Failed to generate video thumbnail for {video_path}: {e}")
        return False


def generate_thumbnails_for_directory(directory: Path, file_list: List[Path]) -> None:
    """Generate thumbnails for all media files in the directory.
    Generates both regular and large thumbnails."""
    state = get_state()
    
    if not state.settings.generate_thumbnails:
        return
    
    # Initialize progress tracking - check for both regular and large thumbnails
    files_needing_thumbnails = []
    for media_file in file_list:
        thumb_path = get_thumbnail_path_for(media_file, large=False)
        large_thumb_path = get_thumbnail_path_for(media_file, large=True)
        if not thumb_path.exists() or not large_thumb_path.exists():
            files_needing_thumbnails.append(media_file)
    
    total_files = len(files_needing_thumbnails)
    if total_files == 0:
        state.logger.info("All thumbnails already exist, no generation needed")
        return
    
    state.thumbnail_progress.update({
        "generating": True,
        "current": 0,
        "total": total_files,
        "current_file": ""
    })
    
    state.logger.info(f"Generating thumbnails for {total_files} files...")
    generated = 0
    
    try:
        for i, media_file in enumerate(files_needing_thumbnails):
            # Update progress
            state.thumbnail_progress.update({
                "current": i + 1,
                "current_file": media_file.name
            })
            
            thumb_path = get_thumbnail_path_for(media_file, large=False)
            large_thumb_path = get_thumbnail_path_for(media_file, large=True)
            
            # Generate thumbnails based on file type
            success_regular = False
            success_large = False
            name_lower = media_file.name.lower()
            
            if name_lower.endswith(('.png', '.jpg', '.jpeg')):
                # Generate regular thumbnail
                if not thumb_path.exists():
                    success_regular = generate_thumbnail_for_image(
                        media_file, thumb_path, state.settings.thumbnail_height
                    )
                else:
                    success_regular = True
                    
                # Generate large thumbnail
                if not large_thumb_path.exists():
                    success_large = generate_thumbnail_for_image(
                        media_file, large_thumb_path, state.settings.large_thumbnail_height
                    )
                else:
                    success_large = True
                    
            elif name_lower.endswith('.mp4'):
                # Generate regular thumbnail
                if not thumb_path.exists():
                    success_regular = generate_thumbnail_for_video(
                        media_file, thumb_path, state.settings.thumbnail_height
                    )
                else:
                    success_regular = True
                    
                # Generate large thumbnail
                if not large_thumb_path.exists():
                    success_large = generate_thumbnail_for_video(
                        media_file, large_thumb_path, state.settings.large_thumbnail_height
                    )
                else:
                    success_large = True
            
            if success_regular and success_large:
                generated += 1
                
    finally:
        # Reset progress tracking
        state.thumbnail_progress.update({
            "generating": False,
            "current": 0,
            "total": 0,
            "current_file": ""
        })
        
        state.logger.info(f"Thumbnail generation complete: {generated}/{total_files} generated")


def start_thumbnail_generation(directory: Path, file_list: List[Path]) -> None:
    """Start thumbnail generation in a background thread."""
    state = get_state()
    if state.settings.generate_thumbnails:
        thumbnail_thread = threading.Thread(
            target=generate_thumbnails_for_directory, 
            args=(directory, file_list),
            daemon=True
        )
        thumbnail_thread.start()