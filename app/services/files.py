"""File management service for media discovery, scoring, and logging."""

import datetime as dt
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

from ..state import get_state
from ..utils.png_chunks import read_png_parameters_text
from ..utils.metadata_parser import parse_generation_metadata


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
    
    # Read existing metadata if any
    existing_data = {}
    if scp.exists():
        try:
            existing_data = json.loads(scp.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    # Update with new score
    existing_data.update({
        "file": video_path.name,
        "score": int(score),
        "updated": dt.datetime.now().isoformat(timespec="seconds"),
    })
    
    scp.write_text(json.dumps(existing_data, indent=2), encoding="utf-8")


def write_media_metadata(media_path: Path, media_dir: Optional[Path] = None) -> None:
    """Extract and write complete media metadata to sidecar file."""
    try:
        state = get_state()
        base_dir = state.video_dir
    except RuntimeError:
        # Fall back to provided media_dir or parent directory
        base_dir = media_dir or media_path.parent
    
    scp = get_sidecar_path_for(media_path)
    
    # Read existing data if any
    existing_data = {}
    if scp.exists():
        try:
            existing_data = json.loads(scp.read_text(encoding="utf-8"))
        except Exception:
            pass
    
    # Base metadata
    metadata = {
        "filename": media_path.name,
        "filepath": str(media_path.relative_to(base_dir)) if base_dir else media_path.name,
        "updated": dt.datetime.now().isoformat(timespec="seconds"),
    }
    
    # Extract generation metadata for PNG files
    if media_path.suffix.lower() == '.png':
        try:
            png_text = read_png_parameters_text(media_path)
            if png_text:
                generation_metadata = parse_generation_metadata(png_text)
                metadata.update(generation_metadata)
        except Exception as e:
            metadata["metadata_error"] = str(e)
    
    # Merge with existing data (preserve score)
    existing_data.update(metadata)
    
    scp.write_text(json.dumps(existing_data, indent=2), encoding="utf-8")


def read_media_metadata(media_path: Path) -> Dict[str, any]:
    """Read complete media metadata from sidecar file."""
    scp = get_sidecar_path_for(media_path)
    if not scp.exists():
        return {}
    
    try:
        return json.loads(scp.read_text(encoding="utf-8"))
    except Exception:
        return {}


def ensure_media_metadata(media_path: Path) -> Dict[str, any]:
    """Ensure media metadata exists and return it."""
    metadata = read_media_metadata(media_path)
    
    # If metadata doesn't exist or is incomplete, extract it
    if not metadata or "filename" not in metadata:
        write_media_metadata(media_path)
        metadata = read_media_metadata(media_path)
    
    return metadata


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