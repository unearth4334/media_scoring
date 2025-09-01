"""Scoring system for media files"""
import json
import datetime as dt
from pathlib import Path
from typing import Optional


def scores_dir_for(directory: Path) -> Path:
    """Get or create scores directory for media directory"""
    sdir = directory / ".scores"
    sdir.mkdir(exist_ok=True, parents=True)
    (sdir / ".log").mkdir(exist_ok=True, parents=True)
    return sdir


def sidecar_path_for(video_path: Path) -> Path:
    """Get sidecar score file path for media file"""
    return scores_dir_for(video_path.parent) / f"{video_path.name}.json"


def read_score(video_path: Path) -> Optional[int]:
    """Read score for media file from sidecar file"""
    scp = sidecar_path_for(video_path)
    if not scp.exists():
        return None
    try:
        data = json.loads(scp.read_text(encoding="utf-8"))
        val = int(data.get("score", 0))
        if val < -1 or val > 5:
            return 0
        return val
    except Exception:
        return None


def write_score(video_path: Path, score: int) -> None:
    """Write score for media file to sidecar file"""
    scp = sidecar_path_for(video_path)
    payload = {
        "file": video_path.name,
        "score": int(score),
        "updated": dt.datetime.now().isoformat(timespec="seconds"),
    }
    scp.write_text(json.dumps(payload, indent=2), encoding="utf-8")