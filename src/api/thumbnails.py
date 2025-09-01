"""Thumbnail API endpoints"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from ..core.state import state
from ..core.thumbnails import thumbnail_path_for, THUMBNAIL_PROGRESS

router = APIRouter()


@router.get("/api/thumbnail-progress")
def get_thumbnail_progress():
    """Get current thumbnail generation progress"""
    return THUMBNAIL_PROGRESS


@router.get("/thumbnail/{name:path}")
def serve_thumbnail(name: str):
    """Serve thumbnail image for a media file"""
    media_path = (state.video_dir / name).resolve()
    try:
        media_path.relative_to(state.video_dir)
    except ValueError:
        raise HTTPException(404, "File not found")
    
    if not media_path.exists():
        raise HTTPException(404, "File not found")
    
    thumb_path = thumbnail_path_for(media_path)
    if not thumb_path.exists():
        raise HTTPException(404, "Thumbnail not found")
    
    return FileResponse(thumb_path, media_type="image/jpeg")