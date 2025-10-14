"""Media router for handling file listing, serving, scoring, and metadata."""

import json
import subprocess
from datetime import datetime
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
    nsfw_filter: Optional[str] = Field(None, description="NSFW filter: 'all', 'sfw', or 'nsfw'")
    
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
                nsfw_filter=request.nsfw_filter,
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
                    "original_created_at": media_file.original_created_at.isoformat() if media_file.original_created_at else None,
                    "file_type": media_file.file_type,
                    "extension": media_file.extension,
                    "file_size": media_file.file_size or 0,
                    "nsfw": media_file.nsfw or False,
                    "media_file_id": media_file.media_file_id  # Add unique identifier
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
                    "nsfw_filter": request.nsfw_filter,
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
        # Get file modification time as best approximation of creation date
        try:
            stat = p.stat()
            original_created_at = datetime.fromtimestamp(stat.st_mtime).isoformat()
        except (OSError, ValueError):
            original_created_at = None
            
        items.append({
            "name": p.name,
            "url": f"/media/{p.name}",
            "score": read_score(p) if read_score(p) is not None else 0,
            "path": str(p),  # Full path
            "created_at": None,  # Not available from filesystem
            "original_created_at": original_created_at,  # Use file modification time
            "file_type": "video" if p.suffix.lower() == ".mp4" else "image",
            "extension": p.suffix.lower(),
            "nsfw": False  # Not available from filesystem
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
                    "original_created_at": media_file.original_created_at.isoformat() if media_file.original_created_at else None,
                    "file_type": media_file.file_type,
                    "extension": media_file.extension,
                    "nsfw": media_file.nsfw or False,
                    "media_file_id": media_file.media_file_id  # Add unique identifier
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


@router.get("/meta/by-id/{media_file_id}")
def get_media_metadata_by_id(media_file_id: str):
    """Get metadata for a media file by its media_file_id (SHA256 hash)."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality required for media_file_id lookup")
    
    try:
        with state.get_database_service() as db:
            db_metadata = db.get_media_metadata_by_id(media_file_id)
            if not db_metadata:
                raise HTTPException(404, "Media file not found")
            
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
    except HTTPException:
        raise
    except Exception as e:
        state.logger.error(f"Failed to get metadata by ID: {e}")
        raise HTTPException(500, f"Failed to retrieve metadata: {str(e)}")


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


@router.get("/media/info/by-id/{media_file_id}")
def get_media_info_by_id(media_file_id: str):
    """Get comprehensive information about a media file by its media_file_id."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality required for media_file_id lookup")
    
    try:
        with state.get_database_service() as db:
            media_file = db.get_media_file_by_id(media_file_id)
            if not media_file:
                raise HTTPException(404, "Media file not found")
            
            # Get the file path and construct info
            target = Path(media_file.file_path)
            
            if not target.exists() or not target.is_file():
                raise HTTPException(404, "File not found on disk")
            
            # Get file stats
            stat = target.stat()
            
            # Initialize response
            info = {
                "filename": target.name,
                "file_size": stat.st_size,
                "file_path": str(target),
                "file_type": target.suffix.lstrip('.').upper() or "Unknown",
                "creation_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "score": media_file.score,
                "dimensions": None,
                "duration": None,
                "resolution": None,
                "aspect_ratio": None,
                "frame_rate": None,
                "bitrate": None,
                "codec": None,
                "metadata": {}
            }
            
            # Get metadata from database
            db_metadata = db.get_media_metadata_by_id(media_file_id)
            if db_metadata:
                if db_metadata.width and db_metadata.height:
                    info["dimensions"] = {"width": db_metadata.width, "height": db_metadata.height}
                    info["resolution"] = db_metadata.width * db_metadata.height
                    # Calculate aspect ratio
                    from math import gcd
                    g = gcd(db_metadata.width, db_metadata.height)
                    info["aspect_ratio"] = f"{db_metadata.width//g}:{db_metadata.height//g}"
                
                if db_metadata.duration:
                    info["duration"] = db_metadata.duration
                
                if db_metadata.frame_rate:
                    info["frame_rate"] = db_metadata.frame_rate
                
                # Add metadata fields
                if db_metadata.png_text:
                    try:
                        info["metadata"]["png_text"] = json.loads(db_metadata.png_text)
                    except json.JSONDecodeError:
                        info["metadata"]["png_text"] = db_metadata.png_text
                
                # Add AI generation parameters
                generation_params = {}
                for field in ["prompt", "negative_prompt", "model_name", "sampler", "steps", "cfg_scale", "seed"]:
                    value = getattr(db_metadata, field, None)
                    if value:
                        generation_params[field] = value
                
                if generation_params:
                    info["metadata"]["generation_params"] = generation_params
            
            return info
    except HTTPException:
        raise
    except Exception as e:
        state.logger.error(f"Failed to get media info by ID: {e}")
        raise HTTPException(500, f"Failed to retrieve media info: {str(e)}")


@router.get("/media/info/{name:path}")
def get_media_info(name: str):
    """Get comprehensive information about a media file for the info pane."""
    return _get_media_info_impl(name)


@router.get("/media/{name:path}/info")
def get_media_info_legacy(name: str):
    """Legacy endpoint for backward compatibility. Get comprehensive information about a media file for the info pane."""
    return _get_media_info_impl(name)


def _get_media_info_impl(name: str):
    """Implementation for getting media info."""
    state = get_state()
    target = (state.video_dir / name).resolve()
    
    try:
        target.relative_to(state.video_dir)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
    
    # Get file stats
    stat = target.stat()
    
    # Initialize response
    info = {
        "filename": target.name,
        "file_size": stat.st_size,
        "file_path": str(target),
        "file_type": target.suffix.lstrip('.').upper() or "Unknown",
        "creation_date": datetime.fromtimestamp(stat.st_ctime).isoformat(),
        "modified_date": datetime.fromtimestamp(stat.st_mtime).isoformat(),
        "score": None,
        "dimensions": None,
        "duration": None,
        "resolution": None,
        "aspect_ratio": None,
        "frame_rate": None,
        "bitrate": None,
        "codec": None,
        "metadata": {}
    }
    
    # Get score
    score_val = read_score(target)
    if score_val != 0:
        info["score"] = score_val
    
    # Get metadata from database if available
    if state.database_enabled:
        try:
            with state.get_database_service() as db:
                db_metadata = db.get_media_metadata(target)
                if db_metadata:
                    if db_metadata.width and db_metadata.height:
                        info["dimensions"] = {"width": db_metadata.width, "height": db_metadata.height}
                        info["resolution"] = db_metadata.width * db_metadata.height
                        # Calculate aspect ratio
                        from math import gcd
                        g = gcd(db_metadata.width, db_metadata.height)
                        info["aspect_ratio"] = f"{db_metadata.width//g}:{db_metadata.height//g}"
                    
                    if db_metadata.duration:
                        info["duration"] = db_metadata.duration
                    
                    if db_metadata.frame_rate:
                        info["frame_rate"] = db_metadata.frame_rate
                    
                    # Add metadata fields
                    if db_metadata.png_text:
                        try:
                            info["metadata"]["png_text"] = json.loads(db_metadata.png_text)
                        except json.JSONDecodeError:
                            info["metadata"]["png_text"] = db_metadata.png_text
                    
                    # Add AI generation parameters
                    generation_params = {}
                    for field in ["prompt", "negative_prompt", "model_name", "sampler", "steps", "cfg_scale", "seed"]:
                        value = getattr(db_metadata, field, None)
                        if value:
                            generation_params[field] = value
                    
                    if generation_params:
                        info["metadata"]["generation_params"] = generation_params
        except Exception as e:
            state.logger.error(f"Failed to get metadata from database: {e}")
    
    # Fallback: Extract metadata directly from file if not in database
    ext = target.suffix.lower()
    if ext == ".mp4" and not info["dimensions"]:
        try:
            # Get video metadata using ffprobe
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "video:0",
                "-show_entries", "stream=width,height,duration,r_frame_rate,bit_rate,codec_name",
                "-of", "json", str(target)
            ]
            cp = subprocess.run(cmd, capture_output=True, text=True, check=True)
            ffprobe_info = json.loads(cp.stdout or "{}")
            
            if isinstance(ffprobe_info, dict) and ffprobe_info.get("streams"):
                stream = ffprobe_info["streams"][0]
                
                w = stream.get("width")
                h = stream.get("height")
                if w and h:
                    info["dimensions"] = {"width": int(w), "height": int(h)}
                    info["resolution"] = int(w) * int(h)
                    from math import gcd
                    g = gcd(int(w), int(h))
                    info["aspect_ratio"] = f"{int(w)//g}:{int(h)//g}"
                
                duration = stream.get("duration")
                if duration:
                    info["duration"] = float(duration)
                
                frame_rate = stream.get("r_frame_rate")
                if frame_rate and "/" in frame_rate:
                    num, denom = frame_rate.split("/")
                    info["frame_rate"] = float(num) / float(denom)
                
                bitrate = stream.get("bit_rate")
                if bitrate:
                    info["bitrate"] = int(bitrate)
                
                codec = stream.get("codec_name")
                if codec:
                    info["codec"] = codec
        except Exception as e:
            state.logger.error(f"Failed to extract video metadata: {e}")
    
    elif ext in {".png", ".jpg", ".jpeg"} and not info["dimensions"]:
        try:
            if Image is None:
                state.logger.warning("Pillow not installed, cannot extract image metadata")
            else:
                with Image.open(target) as im:
                    info["dimensions"] = {"width": int(im.width), "height": int(im.height)}
                    info["resolution"] = int(im.width) * int(im.height)
                    from math import gcd
                    g = gcd(int(im.width), int(im.height))
                    info["aspect_ratio"] = f"{int(im.width)//g}:{int(im.height)//g}"
                    
                    # Get EXIF data if available
                    if hasattr(im, '_getexif') and im._getexif():
                        exif_data = {}
                        for tag_id, value in im._getexif().items():
                            # Convert tag ID to name
                            if hasattr(Image, 'ExifTags'):
                                from PIL.ExifTags import TAGS
                                tag_name = TAGS.get(tag_id, tag_id)
                                exif_data[tag_name] = str(value)
                        if exif_data:
                            info["metadata"]["exif"] = exif_data
            
            # For PNG files, try to get parameters text
            if ext == ".png":
                txt = read_png_parameters_text(target)
                if txt and "png_text" not in info["metadata"]:
                    info["metadata"]["png_text"] = txt
        except Exception as e:
            state.logger.error(f"Failed to extract image metadata: {e}")
    
    return info


@router.post("/score")
async def update_score(req: Request):
    """Update score for a media file."""
    state = get_state()
    data = await req.json()
    name = data.get("name")
    media_file_id = data.get("media_file_id")  # New: support media_file_id
    score = int(data.get("score", 0))
    
    # Initialize variables for database mode
    media_file = None
    db_path = None
    
    # If database is enabled, find the file by its media_file_id or filename in the database
    if state.database_enabled:
        try:
            db_service = state.get_database_service()
            if db_service:
                with db_service as db:
                    # Prefer media_file_id lookup if available
                    if media_file_id:
                        media_file = db.session.query(MediaFile).filter(
                            MediaFile.media_file_id == media_file_id
                        ).first()
                        if not media_file:
                            state.logger.error(f"File with media_file_id '{media_file_id}' not found in database")
                            raise HTTPException(404, f"File with media_file_id not found in database")
                    else:
                        # Fallback to filename lookup
                        media_file = db.session.query(MediaFile).filter(
                            MediaFile.filename == name
                        ).first()
                        if not media_file:
                            state.logger.error(f"File '{name}' not found in database")
                            raise HTTPException(404, f"File '{name}' not found in database")
                    
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


@router.post("/nsfw")
async def update_nsfw(req: Request):
    """Update NSFW status for a media file."""
    state = get_state()
    data = await req.json()
    name = data.get("name")
    media_file_id = data.get("media_file_id")  # New: support media_file_id
    nsfw = bool(data.get("nsfw", False))
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is required for NSFW updates")
    
    try:
        db_service = state.get_database_service()
        if db_service is None:
            raise HTTPException(503, "Database service not available")
            
        with db_service as db:
            # Prefer media_file_id lookup if available
            if media_file_id:
                media_file = db.session.query(MediaFile).filter(
                    MediaFile.media_file_id == media_file_id
                ).first()
                if not media_file:
                    raise HTTPException(404, f"File with media_file_id not found in database")
            else:
                # Fallback to filename lookup
                media_file = db.session.query(MediaFile).filter(
                    MediaFile.filename == name
                ).first()
                if not media_file:
                    raise HTTPException(404, f"File '{name}' not found in database")
            
            # Update NSFW status
            media_file.nsfw = nsfw
            media_file.nsfw_label = nsfw
            db.session.commit()
            
            state.logger.info(f"NSFW UPDATE SUCCESS: file={name or media_file_id} nsfw={nsfw}")
            return {"ok": True, "nsfw": nsfw}
            
    except HTTPException:
        raise
    except Exception as e:
        state.logger.error(f"NSFW UPDATE FAILED: file={name or media_file_id} nsfw={nsfw} error={e}")
        raise HTTPException(500, f"Failed to update NSFW status: {str(e)}")


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