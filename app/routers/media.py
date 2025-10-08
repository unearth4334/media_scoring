"""Media router for handling file listing, serving, scoring, and metadata."""

import json
import subprocess
from pathlib import Path
from typing import Optional, List
from enum import Enum

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from ..state import get_state
from ..services.files import read_score, write_score, switch_directory
from ..services.thumbnails import start_thumbnail_generation
from ..utils.png_chunks import read_png_parameters_text
from ..database.models import MediaFile


class SortField(str, Enum):
    """Valid sort fields for media files."""
    NAME = "name"
    DATE = "date"
    SIZE = "size"
    RATING = "rating"


class SortDirection(str, Enum):
    """Valid sort directions."""
    ASC = "asc"
    DESC = "desc"


class FilterRequest(BaseModel):
    """Request model for filtering media files."""
    # Filtering parameters
    min_score: Optional[int] = Field(None, ge=0, le=5)
    max_score: Optional[int] = Field(None, ge=0, le=5)
    file_types: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    # Sorting parameters
    sort_field: SortField = Field(SortField.NAME, description="Field to sort by")
    sort_direction: SortDirection = Field(SortDirection.ASC, description="Sort direction")
    
    # Pagination parameters (optional)
    offset: Optional[int] = Field(None, ge=0)
    limit: Optional[int] = Field(None, ge=1, le=10000)


try:
    from PIL import Image
except ImportError:
    Image = None


router = APIRouter(prefix="/api")


@router.get("/videos")
def list_videos():
    """Return list of media files with scores and configuration."""
    state = get_state()
    
    # Use database if enabled, otherwise fallback to file system
    items = []
    if state.database_enabled:
        # Get all media files from database
        items = _get_files_from_database(state)
    else:
        # Original file system behavior - load all files
        items = _get_files_from_filesystem(state)
    
    return {
        "dir": str(state.video_dir), 
        "pattern": state.file_pattern, 
        "videos": items,
        "thumbnails_enabled": state.settings.generate_thumbnails,
        "thumbnail_height": state.settings.thumbnail_height,
        "toggle_extensions": state.settings.toggle_extensions,
        "database_enabled": state.database_enabled,
        "user_path_prefix": state.settings.user_path_prefix
    }


@router.post("/filter")
async def filter_videos(request: FilterRequest):
    """Filter media files based on criteria with sorting."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    # Extract filter parameters from Pydantic model
    min_score = request.min_score
    max_score = request.max_score 
    file_types = request.file_types
    start_date = request.start_date
    end_date = request.end_date
    
    # Convert date strings to datetime objects if provided
    from datetime import datetime
    start_date_obj = None
    end_date_obj = None
    
    if start_date:
        try:
            start_date_obj = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
        except ValueError:
            pass
    
    if end_date:
        try:
            end_date_obj = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
        except ValueError:
            pass
    
    try:
        db_service = state.get_database_service()
        if db_service is None:
            raise HTTPException(503, "Database service is not available")
            
        with db_service as db:
            media_files = db.get_all_media_files(
                min_score=min_score,
                max_score=max_score,
                file_types=file_types,
                start_date=start_date_obj,
                end_date=end_date_obj,
                sort_field=request.sort_field.value,
                sort_direction=request.sort_direction.value,
                offset=request.offset,
                limit=request.limit
            )
            
            items = []
            for media_file in media_files:
                file_path = Path(media_file.file_path)
                relative_path = file_path.name
                
                items.append({
                    "name": media_file.filename,
                    "url": f"/media/{relative_path}",
                    "score": media_file.score or 0,
                    "path": media_file.file_path,
                    "created_at": media_file.created_at.isoformat() if media_file.created_at else None,
                    "file_type": media_file.file_type,
                    "extension": media_file.extension,
                    "file_size": media_file.file_size or 0
                })
            
            return {
                "videos": items,
                "count": len(items),
                "filters_applied": {
                    "min_score": min_score,
                    "max_score": max_score,
                    "file_types": file_types,
                    "start_date": start_date,
                    "end_date": end_date,
                    "sort_field": request.sort_field.value,
                    "sort_direction": request.sort_direction.value,
                    "offset": request.offset,
                    "limit": request.limit
                }
            }
    
    except Exception as e:
        state.logger.error(f"Filter failed: {e}")
        raise HTTPException(500, f"Filter failed: {str(e)}")


def _get_files_from_filesystem(state):
    """Get media files from file system (original behavior)."""
    items = []
    for p in state.file_list:
        items.append({
            "name": p.name,
            "url": f"/media/{p.name}",
            "score": read_score(p) if read_score(p) is not None else 0,
            "path": str(p),  # Full path
            "created_at": None,  # Not available from filesystem
            "file_type": "video" if p.suffix.lower() == ".mp4" else "image",
            "extension": p.suffix.lower()
        })
    return items


def _get_files_from_database(state):
    """Get media files from database."""
    items = []
    try:
        db_service = state.get_database_service()
        if db_service is None:
            state.logger.error("Database service is not available")
            return _get_files_from_filesystem(state)
            
        with db_service as db:
            media_files = db.get_all_media_files()
            
            for media_file in media_files:
                file_path = Path(media_file.file_path)
                relative_path = file_path.name
                
                items.append({
                    "name": media_file.filename,
                    "url": f"/media/{relative_path}",
                    "score": media_file.score or 0,
                    "path": media_file.file_path,
                    "created_at": media_file.created_at.isoformat() if media_file.created_at else None,
                    "file_type": media_file.file_type,
                    "extension": media_file.extension
                })
    except Exception as e:
        state.logger.error(f"Failed to get media files from database: {e}")
        # Fallback to filesystem if database fails
        items = _get_files_from_filesystem(state)
    
    return items


@router.post("/scan")
async def scan_directory(req: Request):
    """Scan a new directory for media files."""
    data = await req.json()
    new_dir = Path(str(data.get("dir",""))).expanduser().resolve()
    pattern = str(data.get("pattern","")).strip() or None
    
    if not new_dir.exists() or not new_dir.is_dir():
        raise HTTPException(400, f"Directory not found: {new_dir}")
    
    file_list = switch_directory(new_dir, pattern)
    
    # Start thumbnail generation if enabled
    start_thumbnail_generation(new_dir, file_list)
    
    state = get_state()
    return {
        "ok": True, 
        "dir": str(state.video_dir), 
        "pattern": state.file_pattern, 
        "count": len(file_list)
    }


@router.get("/meta/{name:path}")
def get_media_metadata(name: str):
    """Get metadata for a media file."""
    state = get_state()
    target = (state.video_dir / name).resolve()
    
    try:
        target.relative_to(state.video_dir)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")

    # First check if we have metadata in database
    metadata = {}
    if state.database_enabled:
        try:
            with state.get_database_service() as db:
                db_metadata = db.get_media_metadata(target)
                if db_metadata:
                    # Convert database metadata to response format
                    metadata = {
                        "width": db_metadata.width,
                        "height": db_metadata.height,
                        "duration": db_metadata.duration,
                        "frame_rate": db_metadata.frame_rate,
                        "color_mode": db_metadata.color_mode,
                        "has_alpha": db_metadata.has_alpha,
                    }
                    
                    # Add PNG text if available
                    if db_metadata.png_text:
                        try:
                            metadata["png_text"] = json.loads(db_metadata.png_text)
                        except json.JSONDecodeError:
                            pass
                    
                    # Add AI parameters if available
                    for field in ["prompt", "negative_prompt", "model_name", "sampler", "steps", "cfg_scale", "seed"]:
                        value = getattr(db_metadata, field, None)
                        if value:
                            metadata[field] = value
                    
                    return metadata
        except Exception as e:
            state.logger.error(f"Failed to get metadata from database: {e}")

    # Fallback to on-demand extraction (original behavior)
    ext = target.suffix.lower()
    if ext == ".mp4":
        # Use ffprobe to retrieve width/height
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "video:0",
                "-show_entries", "stream=width,height",
                "-of", "json", str(target)
            ]
            cp = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(cp.stdout or "{}")
            if isinstance(info, dict) and info.get("streams"):
                st = info["streams"][0]
                w = st.get("width")
                h = st.get("height")
                if w and h:
                    metadata = {"width": int(w), "height": int(h)}
        except Exception as e:
            return {"error": str(e)}
    elif ext in {".png", ".jpg", ".jpeg"}:
        try:
            if Image is None:
                metadata = {"error": "Pillow not installed"}
            else:
                with Image.open(target) as im:
                    metadata = {"width": int(im.width), "height": int(im.height)}
            if ext == ".png":
                txt = read_png_parameters_text(target)
                if txt:
                    metadata["png_text"] = txt
        except Exception as e:
            return {"error": str(e)}
    
    # Store extracted metadata in database for future use
    if metadata and state.database_enabled:
        try:
            from ..services.metadata import extract_and_store_metadata
            extract_and_store_metadata(target)
        except Exception as e:
            state.logger.error(f"Failed to store metadata in database: {e}")
    
    return metadata


@router.post("/score")
async def update_score(req: Request):
    """Update score for a media file."""
    state = get_state()
    data = await req.json()
    name = data.get("name")
    score = int(data.get("score", 0))
    
    # Initialize variables for database mode
    media_file = None
    db_path = None
    
    # If database is enabled, find the file by its filename in the database
    if state.database_enabled:
        try:
            db_service = state.get_database_service()
            if db_service:
                with db_service as db:
                    # Find the media file by filename
                    media_file = db.session.query(MediaFile).filter(
                        MediaFile.filename == name
                    ).first()
                    
                    if media_file:
                        # Translate database path (host path) to container path
                        db_path = media_file.file_path
                        
                        # Check if we need to translate from host path to container path
                        if hasattr(state.settings, 'user_path_prefix') and state.settings.user_path_prefix:
                            # Replace host path prefix with container path
                            if db_path.startswith(state.settings.user_path_prefix):
                                container_path = db_path.replace(state.settings.user_path_prefix, "/media", 1)
                                target = Path(container_path)
                            else:
                                target = Path(db_path)
                        else:
                            target = Path(db_path)
                        
                        state.logger.info(f"Found file in database: {db_path} -> {target}")
                    else:
                        state.logger.error(f"File '{name}' not found in database")
                        raise HTTPException(404, f"File '{name}' not found in database")
            else:
                raise HTTPException(503, "Database service not available")
        except Exception as e:
            state.logger.error(f"Database error when looking up file: {e}")
            raise HTTPException(500, f"Database error: {str(e)}")
    else:
        # Original filesystem behavior
        target = state.video_dir / name
        if not target.exists() or target not in state.file_list:
            raise HTTPException(404, "File not found")
    
    if not target.exists():
        state.logger.error(f"File not found on filesystem: {target}")
        raise HTTPException(404, f"File not found on filesystem: {target}")
    
    state.logger.info(f"Updating score: file={name} score={score} path={target}")
    
    try:
        # For database mode, we need to pass the original database path to write_score
        # so the database update uses the correct path for lookup
        if state.database_enabled and media_file:
            # Use the original database path for write_score to avoid duplicates
            score_path = Path(db_path)
        else:
            # Use the translated/filesystem path for non-database mode
            score_path = target
            
        write_score(score_path, score)
        state.logger.info(f"SCORE UPDATE SUCCESS: file={name} score={score} path={target} db_path={score_path}")
        return {"ok": True}
    except Exception as e:
        state.logger.error(f"SCORE UPDATE FAILED: file={name} score={score} error={e}")
        raise HTTPException(500, f"Failed to update score: {str(e)}")


@router.post("/key")
async def log_key_press(req: Request):
    """Log key press for analytics."""
    state = get_state()
    data = await req.json()
    key = str(data.get("key"))
    fname = str(data.get("name"))
    state.logger.info(f"KEY key={key} file={fname}")
    return {"ok": True}


@router.get("/directories")
async def list_directories(path: str = ""):
    """List directories in the given path, excluding dot folders."""
    state = get_state()
    
    try:
        if not path:
            target_path = state.video_dir
        else:
            target_path = Path(path).expanduser().resolve()
        
        # Security check: ensure we're not accessing forbidden paths
        if not target_path.exists() or not target_path.is_dir():
            raise HTTPException(404, "Directory not found")
        
        directories = []
        for item in target_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                directories.append({
                    "name": item.name,
                    "path": str(item)
                })
        
        # Sort directories alphabetically
        directories.sort(key=lambda x: x["name"].lower(), reverse=state.settings.directory_sort_desc)
        
        return {"directories": directories, "current_path": str(target_path)}
    except Exception as e:
        raise HTTPException(500, f"Failed to list directories: {str(e)}")


@router.get("/sibling-directories")
async def list_sibling_directories(path: str = ""):
    """List sibling directories (directories at the same level), excluding dot folders."""
    state = get_state()
    
    try:
        if not path:
            target_path = state.video_dir
        else:
            target_path = Path(path).expanduser().resolve()
        
        # Security check: ensure we're not accessing forbidden paths
        if not target_path.exists() or not target_path.is_dir():
            raise HTTPException(404, "Directory not found")
        
        # Get parent directory
        parent_path = target_path.parent
        if not parent_path.exists() or not parent_path.is_dir():
            return {"directories": [], "current_path": str(target_path), "parent_path": str(parent_path)}
        
        directories = []
        for item in parent_path.iterdir():
            if item.is_dir() and not item.name.startswith('.') and item != target_path:
                directories.append({
                    "name": item.name,
                    "path": str(item)
                })
        
        # Sort directories alphabetically
        directories.sort(key=lambda x: x["name"].lower(), reverse=state.settings.directory_sort_desc)
        
        return {"directories": directories, "current_path": str(target_path), "parent_path": str(parent_path)}
    except Exception as e:
        raise HTTPException(500, f"Failed to list sibling directories: {str(e)}")