"""Enhanced Ingest router with workflow-based processing."""

import asyncio
import json
import logging
import tempfile
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import shutil

from fastapi import APIRouter, Request, HTTPException, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from ..state import get_state
from ..database.service import DatabaseService
from ..services.files import discover_files, read_score
from ..services.metadata import extract_metadata, extract_keywords_from_metadata
from ..services.nsfw_detection import detect_image_nsfw, is_nsfw_detection_available
from ..services.thumbnails import (
    get_thumbnail_path_for,
    generate_thumbnail_for_image,
    generate_thumbnail_for_video
)
from ..utils.hashing import compute_media_file_id, compute_perceptual_hash
from ..utils.sanitization import sanitize_file_data


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# In-memory storage for processing sessions
processing_sessions: Dict[str, Dict] = {}

# Session persistence directory
SESSION_DIR = Path(tempfile.gettempdir()) / "media_scoring_sessions"
SESSION_DIR.mkdir(exist_ok=True)

# Session status constants
STATUS_STARTING = "starting"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_ERROR = "error"
STATUS_COMMITTING = "committing"
STATUS_COMMITTED = "committed"
STATUS_COMMIT_ERROR = "commit_error"

# Status groups for filtering active sessions
ACTIVE_PROCESSING_STATUSES = [STATUS_STARTING, STATUS_PROCESSING, STATUS_COMMITTING]
PERSISTENT_STATUSES = [STATUS_COMPLETED, STATUS_COMMITTED, STATUS_COMMIT_ERROR]
ALL_ACTIVE_STATUSES = ACTIVE_PROCESSING_STATUSES + PERSISTENT_STATUSES


def validate_session_id(session_id: str) -> str:
    """Validate and sanitize session_id to prevent path traversal.
    
    Args:
        session_id: The session ID to validate
        
    Returns:
        The validated session_id
        
    Raises:
        HTTPException: If session_id is not a valid UUID
    """
    try:
        # Validate it's a proper UUID
        uuid.UUID(session_id)
        # Return only the string representation (no path components)
        return session_id
    except ValueError:
        raise HTTPException(400, "Invalid session ID format")



async def save_session_to_disk(session_id: str, session_data: Dict):
    """Save session to disk for persistence across page refreshes."""
    def _save():
        try:
            session_file = SESSION_DIR / f"{session_id}.json"
            # Create a serializable copy (exclude processed_data for size)
            save_data = {
                "session_id": session_id,
                "status": session_data.get("status"),
                "progress": session_data.get("progress"),
                "total_files": session_data.get("total_files"),
                "current_file": session_data.get("current_file"),
                "processed_files": session_data.get("processed_files"),
                "stats": session_data.get("stats"),
                "errors": session_data.get("errors", []),
                "start_time": session_data.get("start_time"),
                "end_time": session_data.get("end_time"),
                "parameters": session_data.get("parameters"),
                "commit_progress": session_data.get("commit_progress"),
                "commit_errors": session_data.get("commit_errors", []),
                "commit_error": session_data.get("commit_error")  # Main error message
            }
            with open(session_file, 'w') as f:
                json.dump(save_data, f)
            
            # Save processed_data separately if status is completed (needed for commit)
            if session_data.get("status") == "completed" and session_data.get("processed_data"):
                data_file = SESSION_DIR / f"{session_id}_data.json"
                with open(data_file, 'w') as f:
                    json.dump(session_data["processed_data"], f)
        except Exception as e:
            logging.error(f"Failed to save session {session_id} to disk: {e}")
    
    # Run file I/O in thread to avoid blocking event loop
    await asyncio.to_thread(_save)


def load_session_from_disk(session_id: str) -> Optional[Dict]:
    """Load session from disk."""
    try:
        session_id = validate_session_id(session_id)  # Validate to prevent path traversal
        session_file = SESSION_DIR / f"{session_id}.json"
        if session_file.exists():
            with open(session_file, 'r') as f:
                return json.load(f)
    except HTTPException:
        # Invalid session_id format
        return None
    except Exception as e:
        logging.error(f"Failed to load session {session_id} from disk: {e}")
    return None


def load_processed_data_from_disk(session_id: str) -> Optional[List[Dict]]:
    """Load processed data from disk for a completed session.
    
    Returns:
        List of dictionaries containing processed file data, or None if not found.
        Each dictionary contains file metadata, scores, keywords, etc.
    """
    try:
        session_id = validate_session_id(session_id)  # Validate to prevent path traversal
        data_file = SESSION_DIR / f"{session_id}_data.json"
        if data_file.exists():
            with open(data_file, 'r') as f:
                return json.load(f)
    except HTTPException:
        # Invalid session_id format
        return None
    except Exception as e:
        logging.error(f"Failed to load processed data for {session_id} from disk: {e}")
    return None


def ensure_processed_data_loaded(session: Dict, session_id: str) -> None:
    """Ensure processed_data is loaded in session, loading from disk if needed.
    
    Args:
        session: The session dictionary to check/update
        session_id: The session ID to use for loading data from disk
        
    Raises:
        HTTPException: If processed data cannot be found
    """
    if not session.get("processed_data"):
        processed_data = load_processed_data_from_disk(session_id)
        if processed_data:
            session["processed_data"] = processed_data
        else:
            raise HTTPException(500, "Processed data not found. Please reprocess the files.")


def delete_session_file(file_path: Path, file_type: str = "file") -> None:
    """Helper to safely delete a session file.
    
    Args:
        file_path: Path to the file to delete
        file_type: Description of the file type for logging
    """
    if file_path.exists():
        try:
            file_path.unlink()
        except Exception as e:
            logging.error(f"Failed to delete {file_type} {file_path.name}: {e}")


def get_active_sessions() -> List[str]:
    """Get list of active session IDs from disk."""
    try:
        session_files = SESSION_DIR.glob("*.json")
        return [f.stem for f in session_files]
    except Exception as e:
        logging.error(f"Failed to list active sessions: {e}")
        return []


def cleanup_old_sessions():
    """Remove session files older than 24 hours."""
    try:
        if not SESSION_DIR.exists():
            return
        
        cutoff_time = datetime.now() - timedelta(hours=24)
        for session_file in SESSION_DIR.glob("*.json"):
            try:
                file_mtime = datetime.fromtimestamp(session_file.stat().st_mtime)
                if file_mtime < cutoff_time:
                    session_file.unlink()
            except:
                pass
    except Exception as e:
        logging.error(f"Failed to cleanup old sessions: {e}")


def filter_existing_files(files: List[Path], db: DatabaseService) -> tuple[List[Path], int]:
    """Filter out files that already exist in the database.
    
    Returns:
        Tuple of (new_files, skipped_count)
    """
    new_files = []
    skipped_count = 0
    
    for file_path in files:
        if db.media_file_exists(file_path):
            skipped_count += 1
        else:
            new_files.append(file_path)
    
    return new_files, skipped_count


class IngestParameters(BaseModel):
    """Parameters for the ingestion process."""
    directory: Optional[str] = Field(None, description="Single directory to process (deprecated, use directories)")
    directories: Optional[List[str]] = Field(None, description="Multiple directories to process")
    pattern: str = Field("*.mp4|*.png|*.jpg", description="File pattern to match")
    enable_nsfw_detection: bool = Field(True, description="Enable NSFW detection")
    nsfw_threshold: float = Field(0.5, description="NSFW threshold (0.0-1.0)")
    extract_metadata: bool = Field(True, description="Extract file metadata")
    extract_keywords: bool = Field(True, description="Extract keywords from metadata")
    import_scores: bool = Field(True, description="Import existing score files")
    skip_existing: bool = Field(True, description="Skip files already in database")
    max_files: Optional[int] = Field(None, description="Maximum files to process (for testing)")


class ProcessRequest(BaseModel):
    """Request to start processing."""
    parameters: IngestParameters


class CommitRequest(BaseModel):
    """Request to commit processed data to database."""
    session_id: str


@router.get("/ingest-v2", response_class=HTMLResponse)
async def ingest_v2_page(request: Request):
    """Serve the enhanced ingest tool page."""
    state = get_state()
    return templates.TemplateResponse(
        "ingest_v2.html",
        {
            "request": request,
            "settings": state.settings,
            "nsfw_detection_available": is_nsfw_detection_available()
        }
    )


@router.post("/api/ingest/file-types")
async def get_file_types_in_directories(directories: List[str]):
    """Get available file types in the selected directories."""
    try:
        file_types = set()
        media_root = Path("/media").resolve()
        
        for dir_path in directories:
            directory = Path(dir_path).expanduser().resolve()
            
            # Security check: ensure path is within /media/ to prevent path traversal
            try:
                directory.relative_to(media_root)
            except ValueError:
                # Path is outside /media/, skip it
                continue
            
            if not directory.exists() or not directory.is_dir():
                continue
            
            try:
                for item in directory.iterdir():
                    if item.is_file():
                        ext = item.suffix.lower()
                        if ext in ['.mp4', '.png', '.jpg', '.jpeg']:
                            file_types.add(ext)
            except PermissionError:
                pass
        
        # Return as sorted list of extensions without the dot
        return {
            "file_types": sorted([ext[1:] for ext in file_types])
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to get file types: {str(e)}")


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
        
        # Get subdirectories and file counts
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
                    ext = item.suffix.lower()
                    file_counts[ext] = file_counts.get(ext, 0) + 1
        except PermissionError:
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
        
        # Return with no-cache headers to ensure fresh data
        response_data = {
            "path": str(target_path),
            "parent": parent_path,
            "directories": subdirs,
            "file_summary": ", ".join(file_summary) if file_summary else "No files"
        }
        
        return JSONResponse(
            content=response_data,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0"
            }
        )
    except Exception as e:
        raise HTTPException(500, f"Failed to list directories: {str(e)}")


@router.post("/api/ingest/process")
async def start_processing(request: ProcessRequest, background_tasks: BackgroundTasks):
    """Start the processing phase (preview mode)."""
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Get directories list (support both old single directory and new multiple directories)
    directories_to_process = []
    if request.parameters.directories:
        directories_to_process = request.parameters.directories
    elif request.parameters.directory:
        directories_to_process = [request.parameters.directory]
    else:
        raise HTTPException(400, "No directories specified")
    
    # Validate all directories
    validated_dirs = []
    for dir_path in directories_to_process:
        directory = Path(dir_path).expanduser().resolve()
        if not directory.exists() or not directory.is_dir():
            raise HTTPException(400, f"Directory not found: {directory}")
        validated_dirs.append(directory)
    
    # Discover files from all directories
    try:
        files = []
        for directory in validated_dirs:
            dir_files = discover_files(directory, request.parameters.pattern)
            files.extend(dir_files)
        
        if request.parameters.max_files:
            files = files[:request.parameters.max_files]
    except Exception as e:
        raise HTTPException(500, f"Failed to discover files: {str(e)}")
    
    if not files:
        raise HTTPException(400, "No files found matching the specified pattern")
    
    # Filter out already-ingested files if skip_existing is enabled
    skipped_count = 0
    total_discovered = len(files)
    if request.parameters.skip_existing:
        state = get_state()
        if state.database_enabled:
            try:
                with DatabaseService() as db:
                    # Run filtering in thread to avoid blocking
                    files, skipped_count = await asyncio.to_thread(filter_existing_files, files, db)
                    logging.info(f"Filtered files: {len(files)} new, {skipped_count} already in database")
            except Exception as e:
                logging.warning(f"Failed to filter existing files, processing all: {e}")
        else:
            logging.info("Database disabled, skip_existing has no effect")
    
    if not files:
        raise HTTPException(400, f"No new files to process (found {total_discovered}, skipped {skipped_count} already ingested)")
    
    # Initialize processing session
    processing_sessions[session_id] = {
        "session_id": session_id,
        "parameters": request.parameters.dict(),
        "status": STATUS_STARTING,
        "progress": 0,
        "total_files": len(files),
        "total_discovered": total_discovered,
        "skipped_existing": skipped_count,
        "current_file": None,
        "processed_files": 0,
        "start_time": datetime.now().isoformat(),
        "files": [str(f) for f in files],
        "processed_data": [],
        "errors": [],
        "stats": {
            "total_files": len(files),
            "total_discovered": total_discovered,
            "skipped_existing": skipped_count,
            "processed_files": 0,
            "metadata_extracted": 0,
            "keywords_added": 0,
            "scores_imported": 0,
            "nsfw_detected": 0,
            "errors": 0
        }
    }
    
    # Save session to disk for persistence (non-blocking)
    asyncio.create_task(save_session_to_disk(session_id, processing_sessions[session_id]))
    
    # Cleanup old sessions (older than 24 hours)
    cleanup_old_sessions()
    
    # Start background processing
    background_tasks.add_task(process_files_background, session_id, files, request.parameters)
    
    return {
        "session_id": session_id,
        "total_files": len(files),
        "total_discovered": total_discovered,
        "skipped_existing": skipped_count,
        "status": "started"
    }


@router.get("/api/ingest/active-session")
async def get_active_session():
    """Get the most recent active or in-progress session."""
    most_recent_session = None
    most_recent_time = None
    
    # Check in-memory sessions for active ones
    for session_id, session in processing_sessions.items():
        if session["status"] in ALL_ACTIVE_STATUSES:
            start_time = datetime.fromisoformat(session["start_time"])
            if most_recent_time is None or start_time > most_recent_time:
                most_recent_session = {"session_id": session_id, "status": session["status"]}
                most_recent_time = start_time
    
    # If found an active session, return it
    if most_recent_session:
        return most_recent_session
    
    # Check disk for recent sessions
    active_session_ids = get_active_sessions()
    for session_id in active_session_ids:
        session_data = load_session_from_disk(session_id)
        if not session_data:
            continue
            
        try:
            start_time = datetime.fromisoformat(session_data["start_time"])
        except:
            continue
        
        # Prioritize in-progress sessions
        if session_data.get("status") in ACTIVE_PROCESSING_STATUSES:
            if most_recent_time is None or start_time > most_recent_time:
                # Restore to memory
                processing_sessions[session_id] = {
                    **session_data,
                    "files": [],  # Don't restore file list
                    "processed_data": []  # Don't restore processed data
                }
                most_recent_session = {"session_id": session_id, "status": session_data["status"]}
                most_recent_time = start_time
        # Return most recent completed/committed/error sessions (persist until cleared)
        elif session_data.get("status") in PERSISTENT_STATUSES:
            if most_recent_time is None or start_time > most_recent_time:
                # Restore to memory for viewing
                processing_sessions[session_id] = {
                    **session_data,
                    "files": [],
                    "processed_data": []
                }
                most_recent_session = {"session_id": session_id, "status": session_data["status"]}
                most_recent_time = start_time
    
    if most_recent_session:
        return most_recent_session
    
    return {"session_id": None, "status": None}


@router.get("/api/ingest/status/{session_id}")
async def get_processing_status(session_id: str):
    """Get the current processing status."""
    # Check in-memory first
    if session_id not in processing_sessions:
        # Try loading from disk
        session_data = load_session_from_disk(session_id)
        if session_data:
            processing_sessions[session_id] = {
                **session_data,
                "files": [],
                "processed_data": []
            }
        else:
            raise HTTPException(404, "Session not found")
    
    session = processing_sessions[session_id]
    
    response_data = {
        "session_id": session_id,
        "status": session["status"],
        "progress": session["progress"],
        "total_files": session["total_files"],
        "current_file": session["current_file"],
        "processed_files": session["processed_files"],
        "stats": session["stats"],
        "errors": session["errors"][-10:],  # Last 10 errors
        "start_time": session["start_time"],
        "end_time": session.get("end_time")
    }
    
    # Log periodically to avoid spam
    if session["processed_files"] % 5 == 0 or session["status"] in ["completed", "error"]:
        logging.info(f"Status request for {session_id}: processed={session['processed_files']}/{session['total_files']}, stats={session['stats']}")
    
    return response_data


@router.get("/api/ingest/report/{session_id}")
async def get_preview_report(session_id: str):
    """Generate and serve the HTML preview report."""
    if session_id not in processing_sessions:
        raise HTTPException(404, "Session not found")
    
    session = processing_sessions[session_id]
    
    if session["status"] not in ["completed", "error"]:
        raise HTTPException(400, "Processing not completed yet")
    
    # Load processed_data from disk if not in memory
    ensure_processed_data_loaded(session, session_id)
    
    # Generate HTML report
    report_html = generate_html_report(session)
    
    # Save to temporary file
    temp_dir = Path(tempfile.gettempdir()) / "media_scoring_reports"
    temp_dir.mkdir(exist_ok=True)
    
    report_file = temp_dir / f"ingest_report_{session_id}.html"
    with open(report_file, 'w', encoding='utf-8') as f:
        f.write(report_html)
    
    return FileResponse(
        path=str(report_file),
        filename=f"ingest_report_{session_id}.html",
        media_type="text/html"
    )


@router.post("/api/ingest/commit")
async def commit_to_database(request: CommitRequest, background_tasks: BackgroundTasks):
    """Commit the processed data to the database."""
    if request.session_id not in processing_sessions:
        raise HTTPException(404, "Session not found")
    
    session = processing_sessions[request.session_id]
    
    if session["status"] != "completed":
        raise HTTPException(400, "Processing not completed successfully")
    
    # Check if database is available
    state = get_state()
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    # Load processed_data from disk if not in memory
    ensure_processed_data_loaded(session, request.session_id)
    
    # Start background commit
    session["status"] = STATUS_COMMITTING
    session["commit_progress"] = 0
    background_tasks.add_task(commit_data_background, request.session_id)
    
    return {
        "session_id": request.session_id,
        "status": "commit_started"
    }


@router.get("/api/ingest/commit-status/{session_id}")
async def get_commit_status(session_id: str):
    """Get the current commit status."""
    if session_id not in processing_sessions:
        # Try loading from disk
        session_data = load_session_from_disk(session_id)
        if session_data:
            processing_sessions[session_id] = {
                **session_data,
                "files": [],
                "processed_data": []
            }
        else:
            raise HTTPException(404, "Session not found")
    
    session = processing_sessions[session_id]
    
    return {
        "session_id": session_id,
        "status": session["status"],
        "commit_progress": session.get("commit_progress", 0),
        "commit_errors": session.get("commit_errors", [])[-10:],  # Last 10 errors
        "commit_error": session.get("commit_error")  # Main error message for commit_error status
    }


@router.delete("/api/ingest/session/{session_id}")
async def cleanup_session(session_id: str):
    """Clean up a processing session."""
    session_id = validate_session_id(session_id)  # Validate to prevent path traversal
    
    if session_id in processing_sessions:
        del processing_sessions[session_id]
    
    # Remove session files from disk
    delete_session_file(SESSION_DIR / f"{session_id}.json", "session file")
    delete_session_file(SESSION_DIR / f"{session_id}_data.json", "data file")
    
    # Clean up any temporary files
    temp_dir = Path(tempfile.gettempdir()) / "media_scoring_reports"
    if temp_dir.exists():
        for report_file in temp_dir.glob(f"ingest_report_{session_id}*"):
            try:
                report_file.unlink()
            except:
                pass
    
    return {"status": "cleaned_up"}


async def process_files_background(session_id: str, files: List[Path], parameters: IngestParameters):
    """Background task to process files."""
    session = processing_sessions[session_id]
    
    try:
        session["status"] = STATUS_PROCESSING
        await save_session_to_disk(session_id, session)  # Save initial state
        logging.info(f"Starting background processing for session {session_id} with {len(files)} files")
        
        for i, file_path in enumerate(files):
            # Update current file immediately
            session["current_file"] = file_path.name
            session["progress"] = int((i / len(files)) * 100)
            
            try:
                # Process single file
                file_data = await process_single_file(file_path, parameters)
                session["processed_data"].append(file_data)
                
                # Update processed count immediately
                session["processed_files"] = i + 1
                session["stats"]["processed_files"] = i + 1
                
                # Update stats based on what was processed
                if file_data.get("metadata"):
                    session["stats"]["metadata_extracted"] += 1
                if file_data.get("keywords"):
                    session["stats"]["keywords_added"] += len(file_data["keywords"])
                if file_data.get("score") is not None:
                    session["stats"]["scores_imported"] += 1
                if file_data.get("nsfw_label"):
                    session["stats"]["nsfw_detected"] += 1
                
                # Update progress after processing file (more accurate)
                session["progress"] = int(((i + 1) / len(files)) * 100)
                
                # Save to disk periodically (every 10 files) - non-blocking
                if (i + 1) % 10 == 0:
                    asyncio.create_task(save_session_to_disk(session_id, session))
                
                # Log progress periodically
                if (i + 1) % 5 == 0 or (i + 1) == len(files):
                    logging.info(f"Progress [{i+1}/{len(files)}]: stats={session['stats']}")
                    
            except Exception as e:
                error_msg = f"Error processing {file_path.name}: {str(e)}"
                session["errors"].append(error_msg)
                session["stats"]["errors"] += 1
                logging.error(error_msg)
        
        session["status"] = STATUS_COMPLETED
        session["progress"] = 100
        session["end_time"] = datetime.now().isoformat()
        await save_session_to_disk(session_id, session)  # Save final state
        logging.info(f"Completed processing for session {session_id}. Final stats: {session['stats']}")
        
    except Exception as e:
        session["status"] = STATUS_ERROR
        session["error"] = str(e)
        session["end_time"] = datetime.now().isoformat()
        await save_session_to_disk(session_id, session)  # Save error state
        logging.error(f"Processing failed for session {session_id}: {e}")


async def process_single_file(file_path: Path, parameters: IngestParameters) -> Dict[str, Any]:
    """Process a single file and return its data."""
    file_data = {
        "file_path": str(file_path),
        "filename": file_path.name,
        "file_size": file_path.stat().st_size,
        "file_type": "image" if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg'] else "video",
        "extension": file_path.suffix.lower()
    }
    
    # Import score if enabled (run in thread to avoid blocking)
    if parameters.import_scores:
        score = await asyncio.to_thread(read_score, file_path)
        if score is not None:
            file_data["score"] = score
    
    # Extract metadata if enabled (run in thread to avoid blocking)
    if parameters.extract_metadata:
        try:
            metadata = await asyncio.to_thread(extract_metadata, file_path)
            if metadata:
                file_data["metadata"] = metadata
                
                # Extract keywords from metadata if enabled
                if parameters.extract_keywords:
                    keywords = await asyncio.to_thread(extract_keywords_from_metadata, metadata)
                    if keywords:
                        file_data["keywords"] = keywords
        except Exception as e:
            logging.warning(f"Failed to extract metadata from {file_path}: {e}")
    
    # NSFW detection if enabled and it's an image (run in thread to avoid blocking)
    if (parameters.enable_nsfw_detection and 
        file_data["file_type"] == "image" and 
        is_nsfw_detection_available()):
        try:
            nsfw_score, nsfw_label = await asyncio.to_thread(detect_image_nsfw, file_path)
            if nsfw_score is not None:
                file_data["nsfw_score"] = nsfw_score
                file_data["nsfw_label"] = nsfw_label
        except Exception as e:
            logging.warning(f"Failed NSFW detection for {file_path}: {e}")
    
    # Generate file ID and perceptual hash for images (run in thread to avoid blocking)
    if file_data["file_type"] == "image":
        try:
            file_data["media_file_id"] = await asyncio.to_thread(compute_media_file_id, file_path)
            file_data["phash"] = await asyncio.to_thread(compute_perceptual_hash, file_path)
        except Exception as e:
            logging.warning(f"Failed to compute hashes for {file_path}: {e}")
    
    return file_data


def _commit_single_file(db: DatabaseService, file_data: Dict, parameters: Dict) -> Optional[str]:
    """Synchronous helper to commit a single file to database (runs in thread pool).
    
    Returns error message if failed, None if successful.
    """
    try:
        # Sanitize file data to remove NUL characters that would cause database errors
        sanitized_data = sanitize_file_data(file_data)
        
        # Create or update media file
        file_path = Path(sanitized_data["file_path"])
        media_file = db.get_or_create_media_file(file_path)
        
        # Update file attributes
        if "score" in sanitized_data:
            media_file.score = sanitized_data["score"]
        
        # Handle NSFW detection results
        if "nsfw_score" in sanitized_data and sanitized_data["nsfw_score"] is not None:
            media_file.nsfw_score = sanitized_data["nsfw_score"]
            media_file.nsfw_label = sanitized_data["nsfw_label"] == "nsfw" if sanitized_data["nsfw_label"] else False
            media_file.nsfw = sanitized_data["nsfw_label"] == "nsfw" if sanitized_data["nsfw_label"] else False
            media_file.nsfw_model = "Marqo/nsfw-image-detection-384"
            media_file.nsfw_model_version = "1.0"
            media_file.nsfw_threshold = parameters["nsfw_threshold"]
        else:
            # Set default values for files without NSFW detection
            media_file.nsfw = False
            media_file.nsfw_score = None
            media_file.nsfw_label = None
        if "media_file_id" in sanitized_data:
            media_file.media_file_id = sanitized_data["media_file_id"]
        if "phash" in sanitized_data:
            media_file.phash = sanitized_data["phash"]
        
        # Flush changes to detect any database errors early
        db.session.flush()
        
        # Store metadata
        if "metadata" in sanitized_data:
            db.store_media_metadata(file_path, sanitized_data["metadata"])
            db.session.flush()
        
        # Store keywords
        if "keywords" in sanitized_data and sanitized_data["keywords"]:
            db.add_keywords(file_path, sanitized_data["keywords"], keyword_type='extracted', source='comfyui')
            db.session.flush()
        
        # Update daily contribution tally based on file creation date
        # Use original_created_at if available from metadata, otherwise fall back to created_at
        contribution_date = media_file.original_created_at or media_file.created_at
        if contribution_date:
            db.increment_daily_contribution(contribution_date, count=1)
            db.session.flush()
        
        # Generate thumbnails if enabled
        state = get_state()
        if state.settings.generate_thumbnails:
            try:
                # Generate regular thumbnail (64px default)
                thumb_path = get_thumbnail_path_for(file_path, large=False)
                if not thumb_path.exists():
                    name_lower = file_path.name.lower()
                    if name_lower.endswith(('.png', '.jpg', '.jpeg')):
                        generate_thumbnail_for_image(file_path, thumb_path, height=state.settings.thumbnail_height)
                    elif name_lower.endswith('.mp4'):
                        generate_thumbnail_for_video(file_path, thumb_path, height=state.settings.thumbnail_height)
                
                # Generate large thumbnail (256px default)
                large_thumb_path = get_thumbnail_path_for(file_path, large=True)
                if not large_thumb_path.exists():
                    name_lower = file_path.name.lower()
                    if name_lower.endswith(('.png', '.jpg', '.jpeg')):
                        generate_thumbnail_for_image(file_path, large_thumb_path, height=state.settings.large_thumbnail_height)
                    elif name_lower.endswith('.mp4'):
                        generate_thumbnail_for_video(file_path, large_thumb_path, height=state.settings.large_thumbnail_height)
            except Exception as e:
                # Log thumbnail generation errors but don't fail the commit
                logging.warning(f"Failed to generate thumbnails for {file_path.name}: {e}")
        
        return None  # Success
        
    except Exception as e:
        # If there's an error, rollback this transaction
        if db.session:
            db.session.rollback()
        error_msg = f"Error committing {file_data.get('filename', 'unknown')}: {str(e)}"
        logging.error(error_msg)
        return error_msg


async def commit_data_background(session_id: str):
    """Background task to commit processed data to database.
    
    Note: This function processes all files in a single database transaction.
    For very large batches (>1000 files), consider processing in smaller chunks
    to avoid connection timeouts. Individual file errors are handled gracefully
    via rollback in _commit_single_file, allowing the batch to continue.
    """
    session = processing_sessions[session_id]
    
    try:
        session["commit_errors"] = []
        session["status"] = STATUS_COMMITTING
        await save_session_to_disk(session_id, session)  # Save committing state
        
        processed_data = session["processed_data"]
        parameters = session["parameters"]
        successful_commits = 0
        failed_commits = 0
        
        with DatabaseService() as db:
            for i, file_data in enumerate(processed_data):
                session["commit_progress"] = int((i / len(processed_data)) * 100)
                
                # Save progress periodically - non-blocking
                if i % 10 == 0:
                    asyncio.create_task(save_session_to_disk(session_id, session))
                
                # Run database operations in thread pool to prevent blocking
                error_msg = await asyncio.to_thread(_commit_single_file, db, file_data, parameters)
                
                if error_msg:
                    session["commit_errors"].append(error_msg)
                    failed_commits += 1
                    logging.error(error_msg)
                else:
                    successful_commits += 1
                    
                    # Log progress periodically
                    if successful_commits % 10 == 0:
                        logging.info(f"Successfully processed {successful_commits} files so far")
            
            # The context manager will automatically commit all successful changes when exiting
        
        # Log final statistics
        logging.info(f"Commit completed: {successful_commits} successful, {failed_commits} failed")
        
        session["status"] = STATUS_COMMITTED
        session["commit_progress"] = 100
        await save_session_to_disk(session_id, session)  # Save final committed state
        
    except Exception as e:
        session["status"] = STATUS_COMMIT_ERROR
        session["commit_error"] = str(e)
        await save_session_to_disk(session_id, session)  # Save error state
        logging.error(f"Commit failed for session {session_id}: {e}")


def generate_html_report(session: Dict) -> str:
    """Generate an HTML preview report for the processing session."""
    
    processed_data = session["processed_data"]
    stats = session["stats"]
    parameters = session["parameters"]
    
    # Sample data for display
    sample_files = processed_data[:10]  # First 10 files
    
    # NSFW statistics
    nsfw_files = [f for f in processed_data if f.get("nsfw_label") == "nsfw"]
    sfw_files = [f for f in processed_data if f.get("nsfw_label") == "sfw"]
    
    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Ingestion Preview Report - {session["session_id"][:8]}</title>
        <style>
            body {{ font-family: Arial, sans-serif; margin: 20px; line-height: 1.6; }}
            .header {{ background: #f4f4f4; padding: 20px; border-radius: 5px; margin-bottom: 20px; }}
            .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin: 20px 0; }}
            .stat-card {{ background: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 5px; text-align: center; }}
            .stat-number {{ font-size: 2em; font-weight: bold; color: #4a90e2; }}
            .stat-label {{ color: #666; font-size: 0.9em; }}
            .file-list {{ max-height: 400px; overflow-y: auto; border: 1px solid #ddd; }}
            .file-item {{ padding: 10px; border-bottom: 1px solid #eee; display: flex; justify-content: space-between; align-items: center; }}
            .file-item:nth-child(even) {{ background: #f9f9f9; }}
            .nsfw-tag {{ background: #ff4444; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; }}
            .sfw-tag {{ background: #44aa44; color: white; padding: 2px 6px; border-radius: 3px; font-size: 0.8em; }}
            .error-list {{ background: #fff5f5; border: 1px solid #fed7d7; padding: 15px; border-radius: 5px; }}
            .error-item {{ color: #c53030; margin: 5px 0; }}
            table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
            th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
            th {{ background: #f4f4f4; }}
        </style>
    </head>
    <body>
        <div class="header">
            <h1>🎬 Ingestion Preview Report</h1>
            <p><strong>Session ID:</strong> {session["session_id"]}</p>
            <p><strong>Directory:</strong> {parameters["directory"]}</p>
            <p><strong>Pattern:</strong> {parameters["pattern"]}</p>
            <p><strong>Processing Time:</strong> {session["start_time"]} - {session.get("end_time", "In Progress")}</p>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{stats["total_files"]}</div>
                <div class="stat-label">Total Files</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats["processed_files"]}</div>
                <div class="stat-label">Processed</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats["metadata_extracted"]}</div>
                <div class="stat-label">Metadata Extracted</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats["keywords_added"]}</div>
                <div class="stat-label">Keywords Added</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{stats["scores_imported"]}</div>
                <div class="stat-label">Scores Imported</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{len(nsfw_files)}</div>
                <div class="stat-label">NSFW Detected</div>
            </div>
        </div>
        
        <h2>📊 Processing Summary</h2>
        <table>
            <tr><th>Parameter</th><th>Value</th></tr>
            <tr><td>Enable NSFW Detection</td><td>{"Yes" if parameters["enable_nsfw_detection"] else "No"}</td></tr>
            <tr><td>NSFW Threshold</td><td>{parameters["nsfw_threshold"]}</td></tr>
            <tr><td>Extract Metadata</td><td>{"Yes" if parameters["extract_metadata"] else "No"}</td></tr>
            <tr><td>Extract Keywords</td><td>{"Yes" if parameters["extract_keywords"] else "No"}</td></tr>
            <tr><td>Import Scores</td><td>{"Yes" if parameters["import_scores"] else "No"}</td></tr>
        </table>
        
        <h2>📁 Sample Files Preview (First 10)</h2>
        <div class="file-list">
    """
    
    for file_data in sample_files:
        nsfw_tag = ""
        if file_data.get("nsfw_label"):
            tag_class = "nsfw-tag" if file_data["nsfw_label"] == "nsfw" else "sfw-tag"
            nsfw_score = file_data.get("nsfw_score", 0)
            nsfw_tag = f'<span class="{tag_class}">{file_data["nsfw_label"].upper()} ({nsfw_score:.2f})</span>'
        
        score_text = f"★{file_data['score']}" if file_data.get("score") is not None else "No score"
        keywords_text = ", ".join(file_data.get("keywords", [])[:3]) if file_data.get("keywords") else "No keywords"
        if len(file_data.get("keywords", [])) > 3:
            keywords_text += f" (+{len(file_data['keywords']) - 3} more)"
            
        html += f"""
            <div class="file-item">
                <div>
                    <strong>{file_data["filename"]}</strong><br>
                    <small>{file_data["file_type"]} • {file_data["file_size"]} bytes • {score_text}</small><br>
                    <small>Keywords: {keywords_text}</small>
                </div>
                <div>{nsfw_tag}</div>
            </div>
        """
    
    html += "</div>"
    
    # Add errors section if there are any
    if session["errors"]:
        html += f"""
        <h2>⚠️ Errors ({len(session["errors"])})</h2>
        <div class="error-list">
        """
        for error in session["errors"][-20:]:  # Show last 20 errors
            html += f'<div class="error-item">{error}</div>'
        html += "</div>"
    
    # NSFW breakdown
    if nsfw_files or sfw_files:
        html += f"""
        <h2>🔞 NSFW Analysis</h2>
        <table>
            <tr><th>Classification</th><th>Count</th><th>Percentage</th></tr>
            <tr><td>Safe for Work (SFW)</td><td>{len(sfw_files)}</td><td>{len(sfw_files)/len(processed_data)*100:.1f}%</td></tr>
            <tr><td>Not Safe for Work (NSFW)</td><td>{len(nsfw_files)}</td><td>{len(nsfw_files)/len(processed_data)*100:.1f}%</td></tr>
            <tr><td>Not Analyzed</td><td>{len(processed_data) - len(nsfw_files) - len(sfw_files)}</td><td>{(len(processed_data) - len(nsfw_files) - len(sfw_files))/len(processed_data)*100:.1f}%</td></tr>
        </table>
        """
    
    html += """
        <div style="margin-top: 40px; padding: 20px; background: #f0f8ff; border-radius: 5px;">
            <h3>Next Steps</h3>
            <p>Review the processed data above. If everything looks correct, you can commit this data to the database.</p>
            <p><strong>Note:</strong> Committing will permanently store this information in your database.</p>
        </div>
    </body>
    </html>
    """
    
    return html