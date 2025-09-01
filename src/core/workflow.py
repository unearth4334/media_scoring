"""Workflow extraction utilities for ComfyUI workflows"""
import subprocess
import sys
from pathlib import Path
from typing import Dict


def extractor_script_path() -> Path:
    """Get path to the workflow extraction script"""
    # expect the script to live next to the main app
    here = Path(__file__).resolve().parent.parent.parent
    return here / "extract_comfyui_workflow.py"


def ensure_workflows_dir(for_video: Path) -> Path:
    """Ensure workflows directory exists for video file"""
    wf_dir = for_video.parent / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    return wf_dir


def extract_workflow_for(video_path: Path) -> Dict[str, str]:
    """Extract ComfyUI workflow from video file metadata"""
    extractor = extractor_script_path()
    if not extractor.exists():
        return {"name": video_path.name, "status": "error", "error": "extractor_not_found"}
    
    wf_dir = ensure_workflows_dir(video_path)
    out_base = wf_dir / f"{video_path.stem}_workflow.json"
    
    try:
        cp = subprocess.run([
            sys.executable, str(extractor), 
            str(video_path), "--output", str(out_base)
        ], capture_output=True, text=True, timeout=60)
        
        if cp.returncode == 0:
            return {"name": video_path.name, "status": "ok", "workflow_path": str(out_base)}
        else:
            return {
                "name": video_path.name, 
                "status": "error", 
                "error": f"rc={cp.returncode}", 
                "stderr": cp.stderr
            }
    except FileNotFoundError:
        return {"name": video_path.name, "status": "error", "error": "python_not_found"}
    except subprocess.TimeoutExpired:
        return {"name": video_path.name, "status": "error", "error": "timeout"}
    except Exception as e:
        return {"name": video_path.name, "status": "error", "error": str(e)}