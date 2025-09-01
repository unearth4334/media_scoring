"""Thumbnail API router for thumbnail progress and serving."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..state import get_state
from ..services.thumbnails import (
    get_thumbnail_path_for, 
    generate_thumbnail_for_image, 
    generate_thumbnail_for_video
)


router = APIRouter(prefix="/api")


@router.get("/thumbnail-progress")
def get_thumbnail_progress():
    """Get current thumbnail generation progress."""
    state = get_state()
    return state.thumbnail_progress.copy()


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