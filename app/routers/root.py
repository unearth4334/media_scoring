"""Root-level routes for media serving, downloads, and thumbnails."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..state import get_state
from ..services.thumbnails import (
    get_thumbnail_path_for, 
    generate_thumbnail_for_image, 
    generate_thumbnail_for_video
)

try:
    from PIL import Image
except ImportError:
    Image = None


router = APIRouter()


@router.get("/media/{name:path}")
def serve_media(name: str):
    """Serve media files."""
    state = get_state()
    target = (state.video_dir / name).resolve()
    
    # Security: ensure the resolved path is within video directory
    try:
        target.relative_to(state.video_dir)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
    
    ext = target.suffix.lower()
    if ext == ".mp4":
        mime = "video/mp4"
    elif ext == ".png":
        mime = "image/png"
    elif ext in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    else:
        mime = "application/octet-stream"
    
    return FileResponse(target, media_type=mime)


@router.get("/download/{name:path}")
def download_media(name: str):
    """Download a media file."""
    state = get_state()
    target = (state.video_dir / name).resolve()
    
    try:
        target.relative_to(state.video_dir)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
    
    # Force download via Content-Disposition
    return FileResponse(target, media_type="application/octet-stream", filename=name)


@router.get("/thumbnail/{name:path}")
def serve_thumbnail(name: str):
    """Serve thumbnail image for a media file."""
    state = get_state()
    
    if not state.settings.generate_thumbnails:
        raise HTTPException(404, "Thumbnails not enabled")
    
    # Find the original media file
    target = (state.video_dir / name).resolve()
    try:
        target.relative_to(state.video_dir)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "Media file not found")
    
    # Get thumbnail path
    thumb_path = get_thumbnail_path_for(target)
    
    if not thumb_path.exists():
        # Try to generate thumbnail on demand
        name_lower = target.name.lower()
        if name_lower.endswith(('.png', '.jpg', '.jpeg')):
            generate_thumbnail_for_image(target, thumb_path)
        elif name_lower.endswith('.mp4'):
            generate_thumbnail_for_video(target, thumb_path)
    
    if not thumb_path.exists():
        raise HTTPException(404, "Thumbnail not available")
    
    return FileResponse(thumb_path, media_type="image/jpeg")