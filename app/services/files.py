"""File management service for media discovery, scoring, and logging."""

import datetime as dt
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

from ..state import get_state


def get_scores_dir_for(directory: Path) -> Path:
    """Get and create scores directory for a given directory."""
    sdir = directory / ".scores"
    sdir.mkdir(exist_ok=True, parents=True)
    (sdir / ".log").mkdir(exist_ok=True, parents=True)
    return sdir


def get_sidecar_path_for(video_path: Path) -> Path:
    """Get sidecar file path for a media file."""
    return get_scores_dir_for(video_path.parent) / f"{video_path.name}.json"


def read_score(video_path: Path) -> Optional[int]:
    """Read score from sidecar file."""
    scp = get_sidecar_path_for(video_path)
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
    """Write score to sidecar file."""
    scp = get_sidecar_path_for(video_path)
    payload = {
        "file": video_path.name,
        "score": int(score),
        "updated": dt.datetime.now().isoformat(timespec="seconds"),
    }
    scp.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def match_union_pattern(directory: Path, pattern: str) -> List[Path]:
    """Match files using union glob pattern (e.g., '*.mp4|*.png|*.jpg')."""
    pats = [p.strip() for p in (pattern or "").split("|") if p.strip()]
    if not pats:
        pats = ["*.mp4"]
    seen: Dict[Path, Path] = {}
    for pat in pats:
        for p in directory.glob(pat):
            if p.is_file():
                seen[p.resolve()] = p
    return sorted(seen.values())


def discover_files(directory: Path, pattern: str) -> List[Path]:
    """Discover media files in directory matching pattern."""
    return match_union_pattern(directory, pattern)


def setup_logging(directory: Path) -> logging.Logger:
    """Setup logging for the application."""
    logger = logging.getLogger("video_scorer_fastapi")
    logger.setLevel(logging.DEBUG)
    
    # Remove existing handlers
    for h in list(logger.handlers):
        logger.removeHandler(h)
    
    # Create file handler
    log_dir = get_scores_dir_for(directory) / ".log"
    log_file = log_dir / "video_scorer.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    
    # Create formatter
    fmt = logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s")
    fh.setFormatter(fmt)
    
    logger.addHandler(fh)
    logger.info(f"Logger initialized. dir={directory}")
    
    return logger


def switch_directory(new_dir: Path, pattern: Optional[str] = None) -> List[Path]:
    """Switch to a new directory and discover files."""
    state = get_state()
    
    # Update state
    state.update_directory(new_dir, pattern)
    
    # Setup logging for new directory
    setup_logging(new_dir)
    
    # Discover files
    file_list = discover_files(new_dir, state.file_pattern)
    state.file_list = file_list
    
    state.logger.info(f"SCAN dir={new_dir} pattern={state.file_pattern} files={len(file_list)}")
    
    return file_list