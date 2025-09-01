"""Scanning and directory management API endpoints"""
from fastapi import APIRouter, HTTPException, Request
from pathlib import Path

from ..core.state import state
from ..core.config import config

router = APIRouter()


@router.post("/api/scan")
async def api_scan(req: Request):
    """Scan a new directory for media files"""
    data = await req.json()
    new_dir_str = str(data.get("dir", "")).strip()
    pattern = str(data.get("pattern", "")).strip()
    
    if not new_dir_str:
        raise HTTPException(400, "dir required")
    
    try:
        new_dir = Path(new_dir_str).expanduser().resolve()
        if not new_dir.exists() or not new_dir.is_dir():
            raise HTTPException(400, f"Directory not found: {new_dir}")
        
        state.switch_directory(new_dir, pattern or state.file_pattern)
        return {"ok": True, "message": f"Switched to {new_dir}"}
        
    except Exception as e:
        raise HTTPException(500, f"Failed to switch directory: {str(e)}")


@router.get("/api/sibling-directories")
def api_sibling_directories():
    """Get list of sibling directories for navigation"""
    try:
        target_path = state.video_dir
        parent_path = target_path.parent
        
        directories = []
        try:
            for item in parent_path.iterdir():
                if item.is_dir() and not item.name.startswith('.'):
                    directories.append({
                        "name": item.name,
                        "path": str(item),
                        "is_current": item.resolve() == target_path.resolve()
                    })
        except PermissionError:
            pass
        
        # Sort directories alphabetically
        directories.sort(key=lambda x: x["name"].lower(), reverse=config.directory_sort_desc)
        
        return {
            "directories": directories, 
            "current_path": str(target_path), 
            "parent_path": str(parent_path)
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to list sibling directories: {str(e)}")