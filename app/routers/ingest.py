"""Ingest router for batch data ingestion page and API."""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from ..state import get_state


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")


class IngestRequest(BaseModel):
    """Request model for ingestion."""
    directory: str
    pattern: str = "*.mp4|*.png|*.jpg"
    enable_database: bool = False
    database_url: Optional[str] = None
    verbose: bool = False


@router.get("/ingest", response_class=HTMLResponse)
async def ingest_page(request: Request):
    """Serve the ingest tool page."""
    state = get_state()
    return templates.TemplateResponse(
        "ingest.html",
        {
            "request": request,
            "settings": state.settings
        }
    )


@router.get("/api/ingest/directories")
async def list_directories_tree(path: str = ""):
    """List directories with file counts for tree view."""
    try:
        state = get_state()
        
        # Define media root directory
        media_root = Path("/media").resolve()
        
        if not path:
            # Start from /media/ instead of home directory
            target_path = media_root
        else:
            target_path = Path(path).expanduser().resolve()
        
        # Security check: prevent navigation above /media/
        try:
            target_path.relative_to(media_root)
        except ValueError:
            # Path is outside /media/, redirect to media root
            target_path = media_root
        
        if not target_path.exists() or not target_path.is_dir():
            raise HTTPException(404, "Directory not found")
        
        # Get ingestion statistics from database if enabled
        ingestion_stats = {}
        if state.database_enabled:
            try:
                db_service = state.get_database_service()
                if db_service:
                    with db_service as db:
                        # Query to get count of ingested files per directory
                        from sqlalchemy import func
                        from ..database.models import MediaFile
                        
                        results = db.session.query(
                            MediaFile.directory,
                            func.count(MediaFile.id).label('count')
                        ).group_by(MediaFile.directory).all()
                        
                        ingestion_stats = {row.directory: row.count for row in results}
            except Exception as e:
                state.logger.error(f"Failed to get ingestion stats: {e}")
        
        # Get subdirectories
        subdirs = []
        file_counts = {}
        
        try:
            for item in sorted(target_path.iterdir(), key=lambda x: x.name.lower()):
                if item.is_dir() and not item.name.startswith('.'):
                    # Count total media files in this directory
                    total_files = 0
                    ingested_files = 0
                    
                    try:
                        for subitem in item.iterdir():
                            if subitem.is_file():
                                ext = subitem.suffix.lower()
                                if ext in ['.mp4', '.png', '.jpg', '.jpeg']:
                                    total_files += 1
                    except PermissionError:
                        pass
                    
                    # Get ingested count from database
                    dir_path = str(item)
                    ingested_files = ingestion_stats.get(dir_path, 0)
                    
                    subdirs.append({
                        "name": item.name,
                        "path": str(item),
                        "has_children": any(subitem.is_dir() and not subitem.name.startswith('.') 
                                           for subitem in item.iterdir()),
                        "total_files": total_files,
                        "ingested_files": ingested_files
                    })
                elif item.is_file():
                    # Count files by extension
                    ext = item.suffix.lower()
                    file_counts[ext] = file_counts.get(ext, 0) + 1
        except PermissionError:
            # Handle permission errors gracefully
            pass
        
        # Format file count summary
        file_summary = []
        if file_counts:
            for ext, count in sorted(file_counts.items()):
                ext_name = ext[1:] if ext else "no extension"
                file_summary.append(f"{count} {ext_name}")
        
        # Only allow parent if not at media root
        parent_path = None
        if target_path != media_root and target_path.parent != target_path:
            parent_path = str(target_path.parent)
        
        return {
            "path": str(target_path),
            "parent": parent_path,
            "directories": subdirs,
            "file_summary": ", ".join(file_summary) if file_summary else "No files"
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to list directories: {str(e)}")


@router.post("/api/ingest/run")
async def run_ingest(request: IngestRequest):
    """Run the ingest process and stream progress."""
    
    async def stream_progress():
        """Stream progress updates from the ingest process."""
        import subprocess
        import sys
        
        # Build command
        cmd = [
            sys.executable,
            "tools/ingest_data.py",
            request.directory
        ]
        
        if request.pattern:
            cmd.extend(["--pattern", request.pattern])
        
        if request.enable_database:
            cmd.append("--enable-database")
        
        if request.database_url:
            cmd.extend(["--database-url", request.database_url])
        
        if request.verbose:
            cmd.append("--verbose")
        
        try:
            # Start the subprocess
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            # Stream output line by line
            if process.stdout:
                for line in process.stdout:
                    yield f"data: {line}\n\n"
            
            # Wait for completion
            process.wait()
            
            # Send completion status
            if process.returncode == 0:
                yield f"data: [COMPLETE] Ingestion completed successfully\n\n"
            else:
                yield f"data: [ERROR] Ingestion failed with exit code {process.returncode}\n\n"
                
        except Exception as e:
            yield f"data: [ERROR] {str(e)}\n\n"
    
    return StreamingResponse(
        stream_progress(),
        media_type="text/event-stream"
    )
