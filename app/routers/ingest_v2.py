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


router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

# In-memory storage for processing sessions
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
    """Start the processing phase (preview mode)."""
    
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
    
    # Initialize processing session
    processing_sessions[session_id] = {
        "session_id": session_id,
        "parameters": request.parameters.dict(),
        "status": "starting",
        "progress": 0,
        "total_files": len(files),
        "current_file": None,
        "processed_files": 0,
        "start_time": datetime.now().isoformat(),
        "files": [str(f) for f in files],
        "processed_data": [],
        "errors": [],
        "stats": {
            "total_files": len(files),
            "processed_files": 0,
            "metadata_extracted": 0,
            "keywords_added": 0,
            "scores_imported": 0,
            "nsfw_detected": 0,
            "errors": 0
        }
    }
    
    # Start background processing
    background_tasks.add_task(process_files_background, session_id, files, request.parameters)
    
    return {
        "session_id": session_id,
        "total_files": len(files),
        "status": "started"
    }


@router.get("/api/ingest/status/{session_id}")
async def get_processing_status(session_id: str):
    """Get the current processing status."""
    if session_id not in processing_sessions:
        raise HTTPException(404, "Session not found")
    
    session = processing_sessions[session_id]
    
    return {
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


@router.get("/api/ingest/report/{session_id}")
async def get_preview_report(session_id: str):
    """Generate and serve the HTML preview report."""
    if session_id not in processing_sessions:
        raise HTTPException(404, "Session not found")
    
    session = processing_sessions[session_id]
    
    if session["status"] not in ["completed", "error"]:
        raise HTTPException(400, "Processing not completed yet")
    
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
    
    # Start background commit
    session["status"] = "committing"
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
        raise HTTPException(404, "Session not found")
    
    session = processing_sessions[session_id]
    
    return {
        "session_id": session_id,
        "status": session["status"],
        "commit_progress": session.get("commit_progress", 0),
        "commit_errors": session.get("commit_errors", [])[-10:]  # Last 10 errors
    }


@router.delete("/api/ingest/session/{session_id}")
async def cleanup_session(session_id: str):
    """Clean up a processing session."""
    if session_id in processing_sessions:
        del processing_sessions[session_id]
    
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
        session["status"] = "processing"
        
        for i, file_path in enumerate(files):
            session["current_file"] = file_path.name
            
            try:
                # Process single file
                file_data = await process_single_file(file_path, parameters)
                session["processed_data"].append(file_data)
                session["processed_files"] += 1
                session["stats"]["processed_files"] += 1
                
                # Update stats based on what was processed
                if file_data.get("metadata"):
                    session["stats"]["metadata_extracted"] += 1
                if file_data.get("keywords"):
                    session["stats"]["keywords_added"] += len(file_data["keywords"])
                if file_data.get("score") is not None:
                    session["stats"]["scores_imported"] += 1
                if file_data.get("nsfw_label"):
                    session["stats"]["nsfw_detected"] += 1
                
                # Update progress after processing the file
                session["progress"] = int(((i + 1) / len(files)) * 100)
                    
            except Exception as e:
                error_msg = f"Error processing {file_path.name}: {str(e)}"
                session["errors"].append(error_msg)
                session["stats"]["errors"] += 1
                logging.error(error_msg)
                
                # Update progress even on error
                session["progress"] = int(((i + 1) / len(files)) * 100)
        
        session["status"] = "completed"
        session["progress"] = 100
        session["end_time"] = datetime.now().isoformat()
        
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        session["end_time"] = datetime.now().isoformat()
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


async def commit_data_background(session_id: str):
    """Background task to commit processed data to database."""
    session = processing_sessions[session_id]
    
    try:
        session["commit_errors"] = []
        processed_data = session["processed_data"]
        parameters = session["parameters"]
        
        with DatabaseService() as db:
            for i, file_data in enumerate(processed_data):
                session["commit_progress"] = int((i / len(processed_data)) * 100)
                
                try:
                    # Create or update media file
                    file_path = Path(file_data["file_path"])
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
                        media_file.nsfw_threshold = parameters["nsfw_threshold"]
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
                    error_msg = f"Error committing {file_data['filename']}: {str(e)}"
                    session["commit_errors"].append(error_msg)
                    logging.error(error_msg)
        
        session["status"] = "committed"
        session["commit_progress"] = 100
        
    except Exception as e:
        session["status"] = "commit_error"
        session["commit_error"] = str(e)
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