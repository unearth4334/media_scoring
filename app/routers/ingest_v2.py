"""Enhanced Ingest router with workflow-based processing."""

import asyncio
import json
import logging
import tempfile
import uuid
from datetime import datetime
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
from ..utils.hashing import compute_media_file_id, compute_perceptual_hash
from ..services.ingestion_state import IngestionState, SessionState


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# Persistent state manager
ingestion_state_manager = IngestionState()

# In-memory storage for processing sessions (kept for backward compatibility)
processing_sessions: Dict[str, Dict] = {}


class IngestParameters(BaseModel):
    """Parameters for the ingestion process."""
    directory: str = Field(..., description="Directory to process")
    pattern: str = Field("*.mp4|*.png|*.jpg", description="File pattern to match")
    enable_nsfw_detection: bool = Field(True, description="Enable NSFW detection")
    nsfw_threshold: float = Field(0.5, description="NSFW threshold (0.0-1.0)")
    extract_metadata: bool = Field(True, description="Extract file metadata")
    extract_keywords: bool = Field(True, description="Extract keywords from metadata")
    import_scores: bool = Field(True, description="Import existing score files")
    max_files: Optional[int] = Field(None, description="Maximum files to process (for testing)")


class ProcessRequest(BaseModel):
    """Request to start processing."""
    parameters: IngestParameters


class ResumeRequest(BaseModel):
    """Request to resume a processing session."""
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


@router.get("/api/ingest/directories")
async def list_directories_tree(path: str = ""):
    """List directories with file counts for tree view."""
    try:
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
        
        # Get subdirectories and file counts
        subdirs = []
        file_counts = {}
        
        try:
            for item in sorted(target_path.iterdir(), key=lambda x: x.name.lower()):
                if item.is_dir() and not item.name.startswith('.'):
                    subdirs.append({
                        "name": item.name,
                        "path": str(item),
                        "has_children": any(subitem.is_dir() and not subitem.name.startswith('.') 
                                           for subitem in item.iterdir())
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
        
        return {
            "path": str(target_path),
            "parent": parent_path,
            "directories": subdirs,
            "file_summary": ", ".join(file_summary) if file_summary else "No files"
        }
    except Exception as e:
        raise HTTPException(500, f"Failed to list directories: {str(e)}")


@router.post("/api/ingest/process")
async def start_processing(request: ProcessRequest, background_tasks: BackgroundTasks):
    """Start the sequential processing with immediate commits."""
    
    # Check if database is available
    state = get_state()
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled. Sequential processing requires database.")
    
    # Generate session ID
    session_id = str(uuid.uuid4())
    
    # Validate directory
    directory = Path(request.parameters.directory).expanduser().resolve()
    if not directory.exists() or not directory.is_dir():
        raise HTTPException(400, f"Directory not found: {directory}")
    
    # Discover files
    try:
        files = discover_files(directory, request.parameters.pattern)
        if request.parameters.max_files:
            files = files[:request.parameters.max_files]
    except Exception as e:
        raise HTTPException(500, f"Failed to discover files: {str(e)}")
    
    if not files:
        raise HTTPException(400, "No files found matching the specified pattern")
    
    # Create session state
    session_state = SessionState(
        session_id=session_id,
        parameters=request.parameters.dict(),
        files=[str(f) for f in files]
    )
    session_state.status = "processing"
    
    # Save initial state to disk
    ingestion_state_manager.save_state(session_id, session_state.to_dict())
    
    # Also keep in memory for quick access
    processing_sessions[session_id] = session_state.to_dict()
    
    # Start background processing
    background_tasks.add_task(process_files_sequential, session_id)
    
    return {
        "session_id": session_id,
        "total_files": len(files),
        "status": "started"
    }
    }


@router.get("/api/ingest/status/{session_id}")
async def get_processing_status(session_id: str):
    """Get the current processing status with persistent state support."""
    # Try memory first for performance
    if session_id in processing_sessions:
        session = processing_sessions[session_id]
    else:
        # Try loading from disk
        state_dict = ingestion_state_manager.load_state(session_id)
        if state_dict:
            session = state_dict
            # Update memory cache
            processing_sessions[session_id] = session
        else:
            raise HTTPException(404, "Session not found")
    
    # Calculate current progress
    total = session.get("total_files", 0)
    processed_count = session.get("stats", {}).get("processed_files", 0)
    progress = int((processed_count / total) * 100) if total > 0 else 0
    
    return {
        "session_id": session_id,
        "status": session.get("status", "unknown"),
        "progress": progress,
        "total_files": total,
        "current_file": session.get("current_file"),
        "processed_files": processed_count,
        "stats": session.get("stats", {}),
        "errors": session.get("errors", [])[-10:],  # Last 10 errors
        "start_time": session.get("start_time"),
        "end_time": session.get("end_time")
    }


@router.post("/api/ingest/resume")
async def resume_processing(request: ResumeRequest, background_tasks: BackgroundTasks):
    """Resume a paused or interrupted processing session."""
    
    # Load session state
    state_dict = ingestion_state_manager.load_state(request.session_id)
    if not state_dict:
        raise HTTPException(404, "Session not found or already completed")
    
    # Recreate session state
    session_state = SessionState.from_dict(state_dict)
    
    # Check if already completed
    if session_state.status == "completed":
        return {
            "session_id": request.session_id,
            "status": "already_completed",
            "message": "This session has already completed processing"
        }
    
    # Resume processing
    session_state.status = "processing"
    ingestion_state_manager.save_state(request.session_id, session_state.to_dict())
    processing_sessions[request.session_id] = session_state.to_dict()
    
    # Start background processing
    background_tasks.add_task(process_files_sequential, request.session_id)
    
    return {
        "session_id": request.session_id,
        "status": "resumed",
        "processed_files": len(session_state.processed_files),
        "total_files": session_state.total_files
    }


@router.delete("/api/ingest/session/{session_id}")
async def cleanup_session(session_id: str):
    """Clean up a processing session."""
    # Remove from memory
    if session_id in processing_sessions:
        del processing_sessions[session_id]
    
    # Remove persistent state
    ingestion_state_manager.delete_state(session_id)
    
    # Clean up any temporary files
    temp_dir = Path(tempfile.gettempdir()) / "media_scoring_reports"
    if temp_dir.exists():
        for report_file in temp_dir.glob(f"ingest_report_{session_id}*"):
            try:
                report_file.unlink()
            except:
                pass
    
    return {"status": "cleaned_up"}
    if session_id in processing_sessions:
        del processing_sessions[session_id]
    
    # Remove persistent state
    ingestion_state_manager.delete_state(session_id)
    
    # Clean up any temporary files
    temp_dir = Path(tempfile.gettempdir()) / "media_scoring_reports"
    if temp_dir.exists():
        for report_file in temp_dir.glob(f"ingest_report_{session_id}*"):
            try:
                report_file.unlink()
            except:
                pass
    
    return {"status": "cleaned_up"}


async def process_files_sequential(session_id: str):
    """Process files sequentially with immediate database commits."""
    # Load session state
    state_dict = ingestion_state_manager.load_state(session_id)
    if not state_dict:
        logging.error(f"Session {session_id} not found")
        return
    
    session_state = SessionState.from_dict(state_dict)
    
    try:
        session_state.status = "processing"
        
        # Process each file one by one
        while True:
            next_file = session_state.get_next_file()
            if next_file is None:
                # All files processed
                break
            
            file_path = Path(next_file)
            session_state.current_file_index += 1
            
            # Update current file in session
            state_dict = session_state.to_dict()
            state_dict["current_file"] = file_path.name
            ingestion_state_manager.save_state(session_id, state_dict)
            processing_sessions[session_id] = state_dict
            
            try:
                # Process the file
                file_data = await process_single_file(
                    file_path, 
                    IngestParameters(**session_state.parameters)
                )
                
                # Immediately commit to database
                await commit_single_file_to_database(file_path, file_data, session_state.parameters)
                
                # Update stats
                session_state.stats["committed_files"] += 1
                if file_data.get("metadata"):
                    session_state.stats["metadata_extracted"] += 1
                if file_data.get("keywords"):
                    session_state.stats["keywords_added"] += len(file_data["keywords"])
                if file_data.get("score") is not None:
                    session_state.stats["scores_imported"] += 1
                if file_data.get("nsfw_label"):
                    session_state.stats["nsfw_detected"] += 1
                
                # Mark as processed
                session_state.mark_file_processed(next_file, success=True)
                
            except Exception as e:
                error_msg = f"Error processing {file_path.name}: {str(e)}"
                logging.error(error_msg)
                session_state.mark_file_processed(next_file, success=False, error=error_msg)
            
            # Save state after each file
            state_dict = session_state.to_dict()
            state_dict["current_file"] = None  # Clear current file after completion
            ingestion_state_manager.save_state(session_id, state_dict)
            processing_sessions[session_id] = state_dict
        
        # All files processed
        session_state.status = "completed"
        session_state.end_time = datetime.now().isoformat()
        
    except Exception as e:
        session_state.status = "error"
        session_state.end_time = datetime.now().isoformat()
        error_msg = f"Processing failed: {str(e)}"
        session_state.errors.append(error_msg)
        logging.error(f"Session {session_id} failed: {e}")
    
    # Final state save
    final_dict = session_state.to_dict()
    ingestion_state_manager.save_state(session_id, final_dict)
    processing_sessions[session_id] = final_dict


async def commit_single_file_to_database(file_path: Path, file_data: Dict[str, Any], 
                                         parameters: Dict) -> None:
    """Commit a single file's data to the database immediately.
    
    Args:
        file_path: Path to the media file
        file_data: Processed file data
        parameters: Ingestion parameters
    """
    try:
        with DatabaseService() as db:
            # Create or update media file
            media_file = db.get_or_create_media_file(file_path)
            
            # Update file attributes
            if "score" in file_data:
                media_file.score = file_data["score"]
            
            # Handle NSFW detection results
            if "nsfw_score" in file_data and file_data["nsfw_score"] is not None:
                media_file.nsfw_score = file_data["nsfw_score"]
                media_file.nsfw_label = file_data["nsfw_label"] == "nsfw" if file_data["nsfw_label"] else False
                media_file.nsfw = file_data["nsfw_label"] == "nsfw" if file_data["nsfw_label"] else False
                media_file.nsfw_model = "Marqo/nsfw-image-detection-384"
                media_file.nsfw_model_version = "1.0"
                media_file.nsfw_threshold = parameters.get("nsfw_threshold", 0.5)
            else:
                # Set default values for files without NSFW detection
                media_file.nsfw = False
                media_file.nsfw_score = None
                media_file.nsfw_label = None
            
            if "media_file_id" in file_data:
                media_file.media_file_id = file_data["media_file_id"]
            if "phash" in file_data:
                media_file.phash = file_data["phash"]
            
            # Store metadata
            if "metadata" in file_data:
                db.store_media_metadata(file_path, file_data["metadata"])
            
            # Store keywords
            if "keywords" in file_data:
                for keyword in file_data["keywords"]:
                    db.add_keyword_to_file(file_path, keyword)
            
    except Exception as e:
        logging.error(f"Failed to commit {file_path} to database: {e}")
        raise



async def process_single_file(file_path: Path, parameters: IngestParameters) -> Dict[str, Any]:
    """Process a single file and return its data."""
    file_data = {
        "file_path": str(file_path),
        "filename": file_path.name,
        "file_size": file_path.stat().st_size,
        "file_type": "image" if file_path.suffix.lower() in ['.png', '.jpg', '.jpeg'] else "video",
        "extension": file_path.suffix.lower()
    }
    
    # Import score if enabled
    if parameters.import_scores:
        score = read_score(file_path)
        if score is not None:
            file_data["score"] = score
    
    # Extract metadata if enabled
    if parameters.extract_metadata:
        try:
            metadata = extract_metadata(file_path)
            if metadata:
                file_data["metadata"] = metadata
                
                # Extract keywords from metadata if enabled
                if parameters.extract_keywords:
                    keywords = extract_keywords_from_metadata(metadata)
                    if keywords:
                        file_data["keywords"] = keywords
        except Exception as e:
            logging.warning(f"Failed to extract metadata from {file_path}: {e}")
    
    # NSFW detection if enabled and it's an image
    if (parameters.enable_nsfw_detection and 
        file_data["file_type"] == "image" and 
        is_nsfw_detection_available()):
        try:
            nsfw_score, nsfw_label = detect_image_nsfw(file_path)
            if nsfw_score is not None:
                file_data["nsfw_score"] = nsfw_score
                file_data["nsfw_label"] = nsfw_label
        except Exception as e:
            logging.warning(f"Failed NSFW detection for {file_path}: {e}")
    
    # Generate file ID and perceptual hash for images
    if file_data["file_type"] == "image":
        try:
            file_data["media_file_id"] = compute_media_file_id(file_path)
            file_data["phash"] = compute_perceptual_hash(file_path)
        except Exception as e:
            logging.warning(f"Failed to compute hashes for {file_path}: {e}")
    
    return file_data