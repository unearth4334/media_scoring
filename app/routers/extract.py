"""Extract router for workflow extraction and file export."""

import tempfile
import zipfile
from pathlib import Path
from typing import List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

from ..state import get_state
from ..services.extractor import extract_workflow_for
from ..services.files import ensure_media_metadata


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


@router.get("/mining-test-results")
async def export_mining_test_results():
    """Export media files metadata as HTML mining test results."""
    state = get_state()
    
    # Collect all metadata for files in current directory
    all_files_metadata = []
    for file_path in state.file_list:
        metadata = ensure_media_metadata(file_path)
        all_files_metadata.append(metadata)
    
    # Generate HTML
    html_content = generate_mining_test_results_html(all_files_metadata, state.video_dir)
    
    return HTMLResponse(content=html_content, media_type="text/html")


def generate_mining_test_results_html(metadata_list: List[dict], media_dir: Path) -> str:
    """Generate HTML report for mining test results."""
    
    # Define the fields we want to include in the export
    fields = [
        'filename', 'filepath', 'score', 'steps', 'sampler', 'schedule_type', 'cfg_scale', 
        'seed', 'size', 'model', 'denoising_strength', 'hires_upscale', 'hires_upscaler',
        'hires_cfg_scale', 'dynthres_enabled', 'dynthres_mimic_scale', 
        'dynthres_threshold_percentile', 'dynthres_mimic_mode', 'dynthres_mimic_scale_min',
        'dynthres_cfg_mode', 'dynthres_cfg_scale_min', 'dynthres_sched_val',
        'dynthres_separate_feature_channels', 'dynthres_scaling_startpoint',
        'dynthres_variability_measure', 'dynthres_interpolate_phi', 'version'
    ]
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>Mining Test Results</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        table {{ border-collapse: collapse; width: 100%; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f2f2f2; }}
        .numeric {{ text-align: right; }}
        .model-info {{ font-size: 0.9em; }}
        .missing {{ color: #999; font-style: italic; }}
    </style>
</head>
<body>
    <h1>Mining Test Results</h1>
    <p>Media Directory: <code>{media_dir}</code></p>
    <p>Generated: {metadata_list[0].get('updated', 'Unknown') if metadata_list else 'N/A'}</p>
    <p>Total Files: {len(metadata_list)}</p>
    
    <table>
        <thead>
            <tr>"""
    
    # Add headers
    for field in fields:
        display_name = field.replace('_', ' ').title()
        html += f"<th>{display_name}</th>"
    
    html += """
            </tr>
        </thead>
        <tbody>"""
    
    # Add rows
    for metadata in metadata_list:
        html += "<tr>"
        for field in fields:
            value = metadata.get(field, '')
            
            # Format different field types
            if field == 'model' and isinstance(value, dict):
                model_name = value.get('name', '')
                model_hash = value.get('hash', '')
                formatted_value = f'<span class="model-info">{model_name}<br><small>{model_hash}</small></span>'
            elif field in ['cfg_scale', 'denoising_strength', 'hires_upscale', 'hires_cfg_scale'] + [f for f in fields if f.startswith('dynthres_') and f.endswith(('_scale', '_percentile', '_val', '_startpoint', '_measure', '_phi'))]:
                css_class = 'numeric'
                missing_span = '<span class="missing">-</span>'
                formatted_value = f'<span class="{css_class}">{value if value != "" else missing_span}</span>'
            elif field in ['steps', 'seed']:
                css_class = 'numeric'
                missing_span = '<span class="missing">-</span>'
                formatted_value = f'<span class="{css_class}">{value if value != "" else missing_span}</span>'
            elif field in ['dynthres_enabled', 'dynthres_separate_feature_channels']:
                formatted_value = 'Yes' if value else 'No' if value is False else '<span class="missing">-</span>'
            else:
                formatted_value = str(value) if value != '' else '<span class="missing">-</span>'
            
            html += f"<td>{formatted_value}</td>"
        html += "</tr>"
    
    html += """
        </tbody>
    </table>
</body>
</html>"""
    
    return html