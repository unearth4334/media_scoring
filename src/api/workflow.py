"""Workflow extraction and export API endpoints"""
import tempfile
import zipfile
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pathlib import Path

from ..core.state import state
from ..core.workflow import extract_workflow_for

router = APIRouter()


@router.post("/api/extract")
async def api_extract(req: Request):
    """Extract ComfyUI workflow JSON for one or more files"""
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


@router.post("/api/export-filtered")
async def api_export_filtered(req: Request):
    """Export all filtered files as a zip archive for download"""
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


@router.get("/download/{name:path}")
def download_media(name: str):
    """Download a single media file"""
    media_path = (state.video_dir / name).resolve()
    try:
        media_path.relative_to(state.video_dir)
    except ValueError:
        raise HTTPException(404, "File not found")
    
    if not media_path.exists() or not media_path.is_file():
        raise HTTPException(404, "File not found")
    
    return FileResponse(
        media_path,
        filename=media_path.name,
        headers={"Content-Disposition": f"attachment; filename={media_path.name}"}
    )