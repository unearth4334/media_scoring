"""Metadata API endpoints"""
from fastapi import APIRouter, HTTPException
import subprocess
from pathlib import Path

from ..core.state import state
from ..core.png_metadata import read_png_parameters_text

try:
    from PIL import Image
except ImportError:
    Image = None

router = APIRouter()


@router.get("/api/meta/{name:path}")
def api_meta(name: str):
    """Get metadata for a media file"""
    media_path = (state.video_dir / name).resolve()
    try:
        media_path.relative_to(state.video_dir)
    except ValueError:
        raise HTTPException(404, "File not found")
    
    if not media_path.exists():
        raise HTTPException(404, "File not found")
    
    # Handle different file types
    ext = media_path.suffix.lower()
    
    if ext in ['.png', '.jpg', '.jpeg']:
        return _get_image_metadata(media_path)
    elif ext == '.mp4':
        return _get_video_metadata(media_path)
    else:
        raise HTTPException(400, "Unsupported file type")


def _get_image_metadata(image_path: Path):
    """Get metadata for image files"""
    result = {}
    
    # Get basic image info
    if Image:
        try:
            with Image.open(image_path) as img:
                result.update({
                    "width": img.width,
                    "height": img.height,
                    "format": img.format,
                    "mode": img.mode
                })
        except Exception:
            pass
    
    # For PNG files, try to extract parameters text
    if image_path.suffix.lower() == '.png':
        params = read_png_parameters_text(image_path)
        if params:
            result["parameters"] = params
    
    return result


def _get_video_metadata(video_path: Path):
    """Get metadata for video files using ffprobe"""
    try:
        cmd = [
            "ffprobe", "-v", "quiet", "-print_format", "json",
            "-show_format", "-show_streams", str(video_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        
        if result.returncode == 0:
            import json
            return json.loads(result.stdout)
        else:
            return {"error": "Failed to read video metadata"}
    except Exception as e:
        return {"error": str(e)}