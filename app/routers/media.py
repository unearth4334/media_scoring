"""Media router for handling file listing, serving, scoring, and metadata."""

import json
import subprocess
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..state import get_state
from ..services.files import read_score, write_score, switch_directory
from ..services.thumbnails import start_thumbnail_generation
from ..utils.png_chunks import read_png_parameters_text

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
        "database_enabled": state.database_enabled
    }


@router.post("/filter")
async def filter_videos(req: Request):
    """Filter media files based on criteria."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    data = await req.json()
    
    # Extract filter parameters
    min_score = data.get("min_score")
    max_score = data.get("max_score") 
    file_types = data.get("file_types")
    start_date = data.get("start_date")
    end_date = data.get("end_date")
    
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
        with state.get_database_service() as db:
            media_files = db.get_all_media_files(
                min_score=min_score,
                max_score=max_score,
                file_types=file_types,
                start_date=start_date_obj,
                end_date=end_date_obj
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
                    "extension": media_file.extension
                })
            
            return {
                "videos": items,
                "count": len(items),
                "filters_applied": {
                    "min_score": min_score,
                    "max_score": max_score,
                    "file_types": file_types,
                    "start_date": start_date,
                    "end_date": end_date
                }
            }
    
    except Exception as e:
        state.logger.error(f"Filter failed: {e}")
        # Fallback to filesystem if database fails
        state.logger.info("Falling back to filesystem due to database error")
        
        # Get files from filesystem and apply client-side filtering
        filesystem_items = _get_files_from_filesystem(state)
        
        # Apply basic filtering to filesystem results
        filtered_items = filesystem_items
        
        # Apply score filters if specified
        if min_score is not None:
            filtered_items = [item for item in filtered_items if (item.get('score') or 0) >= min_score]
        if max_score is not None:
            filtered_items = [item for item in filtered_items if (item.get('score') or 0) <= max_score]
        
        # Apply file type filters if specified
        if file_types:
            file_exts = [f".{ext}" if not ext.startswith('.') else ext for ext in file_types]
            filtered_items = [item for item in filtered_items if item.get('extension') in file_exts]
        
        return {
            "videos": filtered_items,
            "count": len(filtered_items),
            "filters_applied": {
                "min_score": min_score,
                "max_score": max_score,
                "file_types": file_types,
                "start_date": start_date,
                "end_date": end_date
            },
            "fallback_used": True  # Indicate that filesystem fallback was used
        }


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
        with state.get_database_service() as db:
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
    target = state.video_dir / name
    
    if not target.exists() or target not in state.file_list:
        raise HTTPException(404, "File not found")
    
    write_score(target, score)
    state.logger.info(f"SCORE file={name} score={score}")
    return {"ok": True}


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