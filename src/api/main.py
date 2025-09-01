"""Main API routes for Media Scorer"""
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse, FileResponse
from pathlib import Path

from ..core.state import state
from ..core.scoring import read_score
from ..core.config import config
from .templates import get_main_template

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index():
    """Serve the main web interface"""
    return HTMLResponse(get_main_template())


@router.get("/api/videos")
def api_videos():
    """Get list of videos/images with scores"""
    items = []
    for p in state.file_list:
        items.append({
            "name": p.name,
            "url": f"/media/{p.name}",
            "score": read_score(p) if read_score(p) is not None else 0
        })
    return {
        "dir": str(state.video_dir), 
        "pattern": state.file_pattern, 
        "videos": items,
        "thumbnails_enabled": config.generate_thumbnails,
        "thumbnail_height": config.thumbnail_height,
        "toggle_extensions": config.toggle_extensions
    }


@router.get("/media/{name:path}")
def serve_media(name: str):
    """Serve media files"""
    media_path = (state.video_dir / name).resolve()
    try:
        media_path.relative_to(state.video_dir)
    except ValueError:
        raise HTTPException(404, "File not found")
    
    if not media_path.exists() or not media_path.is_file():
        raise HTTPException(404, "File not found")
    
    return FileResponse(media_path)