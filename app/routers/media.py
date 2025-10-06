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
    
    # Return list of entries with current score
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
        "thumbnails_enabled": state.settings.generate_thumbnails,
        "thumbnail_height": state.settings.thumbnail_height,
        "toggle_extensions": state.settings.toggle_extensions
    }


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


@router.get("/directory-tree")
async def get_directory_tree(path: str = "", max_depth: int = 3):
    """Get directory tree structure starting from the given path."""
    state = get_state()
    
    try:
        if not path:
            target_path = state.video_dir
        else:
            target_path = Path(path).expanduser().resolve()
        
        # Security check: ensure we're not accessing forbidden paths
        if not target_path.exists() or not target_path.is_dir():
            raise HTTPException(404, "Directory not found")
        
        def build_tree(dir_path: Path, current_depth: int = 0) -> dict:
            """Recursively build directory tree."""
            tree_node = {
                "name": dir_path.name if dir_path.name else str(dir_path),
                "path": str(dir_path),
                "type": "directory",
                "children": []
            }
            
            if current_depth < max_depth:
                try:
                    subdirs = []
                    for item in dir_path.iterdir():
                        if item.is_dir() and not item.name.startswith('.'):
                            subdirs.append(item)
                    
                    # Sort subdirectories
                    subdirs.sort(key=lambda x: x.name.lower(), reverse=state.settings.directory_sort_desc)
                    
                    for subdir in subdirs:
                        tree_node["children"].append(build_tree(subdir, current_depth + 1))
                        
                except PermissionError:
                    # Skip directories we can't access
                    pass
            
            return tree_node
        
        tree = build_tree(target_path)
        return {"tree": tree, "current_path": str(target_path)}
        
    except Exception as e:
        raise HTTPException(500, f"Failed to build directory tree: {str(e)}")