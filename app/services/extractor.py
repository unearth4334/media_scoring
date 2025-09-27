"""Workflow extraction service using extract_comfyui_workflow.py."""

import subprocess
import sys
from pathlib import Path
from typing import Dict

from ..state import get_state


def get_extractor_script_path() -> Path:
    """Get path to the external extractor script."""
    # Look for script in project root (parent of app directory)
    project_root = Path(__file__).resolve().parent.parent.parent
    return project_root / "extract_comfyui_workflow.py"


def ensure_workflows_dir(for_video: Path) -> Path:
    """Ensure workflows directory exists for video file."""
    wf_dir = for_video.parent / ".workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    return wf_dir


def extract_workflow_for(video_path: Path) -> Dict[str, str]:
    """
    Run the external extractor for a single mp4 and write:
    ./.workflows/<filename_without_ext>_workflow.json
    Returns a dict with status and paths.
    """
    state = get_state()
    
    if not video_path.exists():
        return {"name": video_path.name, "status": "error", "error": "file_not_found"}
    
    script = get_extractor_script_path()
    if not script.exists():
        return {"name": video_path.name, "status": "error", "error": "missing_extractor"}
    
    out_path = ensure_workflows_dir(video_path) / f"{video_path.stem}_workflow.json"
    cmd = [sys.executable, str(script), str(video_path), "-o", str(out_path)]
    
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if cp.returncode == 0:
            state.logger.info(f"EXTRACT success file={video_path.name} out={out_path}")
            return {"name": video_path.name, "status": "ok", "output": str(out_path)}
        else:
            state.logger.warning(f"EXTRACT failed file={video_path.name} rc={cp.returncode} stderr={cp.stderr.strip()}")
            return {"name": video_path.name, "status": "error", "error": f"rc={cp.returncode}", "stderr": cp.stderr}
    except FileNotFoundError:
        return {"name": video_path.name, "status": "error", "error": "python_not_found"}