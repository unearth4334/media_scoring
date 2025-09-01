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