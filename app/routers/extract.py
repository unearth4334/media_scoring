"""Extract router for workflow extraction and file export."""

import tempfile
import zipfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from ..state import get_state
from ..services.extractor import extract_workflow_for
from ..services.html_export import export_mining_test_results_html


router = APIRouter(prefix="/api")


@router.post("/extract")
async def extract_workflows(req: Request):
    """
    Extract ComfyUI workflow JSON for one or more files.
    JSON body: { "names": ["file1.mp4", ...] }
    """
    state = get_state()
    data = await req.json()
    names = data.get("names") or []
    
    if not isinstance(names, list):
        raise HTTPException(400, "names must be a list of filenames")
    
    results = []
    for nm in names:
        vp = (state.video_dir / nm).resolve()
        try:
            vp.relative_to(state.video_dir)
        except Exception:
            results.append({"name": nm, "status": "error", "error": "forbidden_path"})
            continue
        results.append(extract_workflow_for(vp))
    
    return {"results": results}


@router.post("/export-filtered")
async def export_filtered_files(req: Request):
    """
    Export all filtered files as a zip archive for download.
    JSON body: { "names": ["file1.mp4", "file2.png", ...] }
    """
    state = get_state()
    data = await req.json()
    names = data.get("names") or []
    
    if not isinstance(names, list):
        raise HTTPException(400, "names must be a list of filenames")
    
    if not names:
        raise HTTPException(400, "No files to export")
    
    # Create a temporary zip file
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    temp_zip.close()
    
    try:
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zf:
            for name in names:
                file_path = (state.video_dir / name).resolve()
                try:
                    file_path.relative_to(state.video_dir)
                except Exception:
                    continue  # Skip forbidden paths
                
                if file_path.exists() and file_path.is_file():
                    # Add file to zip with just the filename (no path)
                    zf.write(file_path, name)
        
        # Return the zip file
        return FileResponse(
            temp_zip.name, 
            media_type="application/zip", 
            filename="filtered_media.zip",
            headers={"Content-Disposition": "attachment; filename=filtered_media.zip"}
        )
    except Exception as e:
        # Clean up temp file on error
        Path(temp_zip.name).unlink(missing_ok=True)
        raise HTTPException(500, f"Failed to create zip archive: {str(e)}")


@router.post("/export-html")
async def export_html_report(req: Request):
    """
    Export all media files with full metadata as an HTML report.
    JSON body: { "names": ["file1.mp4", "file2.png", ...] } (optional - if not provided, exports all files)
    """
    state = get_state()
    data = await req.json()
    names = data.get("names")  # Optional - if None, export all files
    
    # Get database instance
    if not hasattr(state, 'media_db') or not state.media_db:
        raise HTTPException(500, "Database not initialized")
    
    try:
        # Get media files to export
        if names:
            # Validate names and get corresponding media files
            if not isinstance(names, list):
                raise HTTPException(400, "names must be a list of filenames")
            
            media_files = []
            for name in names:
                # Convert filename to relative path
                file_path = state.video_dir / name
                if not file_path.exists():
                    continue
                
                relative_path = str(file_path.relative_to(state.video_dir))
                media_file = state.media_db.get_media_file(relative_path)
                if media_file:
                    media_files.append(media_file)
        else:
            # Export all files
            media_files = state.media_db.get_all_media_files()
        
        if not media_files:
            raise HTTPException(400, "No media files found to export")
        
        # Create temporary HTML file
        temp_html = tempfile.NamedTemporaryFile(delete=False, suffix='.html', mode='w', encoding='utf-8')
        temp_html.close()
        
        # Generate HTML report
        success = export_mining_test_results_html(media_files, state.video_dir, Path(temp_html.name))
        
        if not success:
            Path(temp_html.name).unlink(missing_ok=True)
            raise HTTPException(500, "Failed to generate HTML report")
        
        # Return the HTML file
        return FileResponse(
            temp_html.name,
            media_type="text/html",
            filename="mining_test_results.html",
            headers={"Content-Disposition": "attachment; filename=mining_test_results.html"}
        )
        
    except Exception as e:
        # Clean up any temp files on error
        try:
            Path(temp_html.name).unlink(missing_ok=True)
        except:
            pass
        raise HTTPException(500, f"Failed to create HTML report: {str(e)}")


@router.get("/database-info")
async def get_database_info():
    """Get information about the current database."""
    state = get_state()
    
    if not hasattr(state, 'media_db') or not state.media_db:
        return {"database_initialized": False, "total_files": 0}
    
    try:
        media_files = state.media_db.get_all_media_files()
        total_files = len(media_files)
        scored_files = len([f for f in media_files if f.score is not None and f.score > 0])
        files_with_metadata = len([f for f in media_files if f.generation_params])
        
        return {
            "database_initialized": True,
            "total_files": total_files,
            "scored_files": scored_files,
            "files_with_metadata": files_with_metadata,
            "database_path": str(state.media_db.db_path)
        }
    except Exception as e:
        return {"database_initialized": True, "error": str(e)}