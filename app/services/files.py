"""File management services."""

import json
import datetime as dt
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional

try:
    from PIL import Image
except ImportError:
    Image = None

from ..state import get_state
from ..utils.png_chunks import extract_png_metadata
from ..models.media_file import MediaFile, GenerationParameters, MediaFileDatabase


def scores_dir_for(directory: Path) -> Path:
    """Get the scores directory for a media directory."""
    sdir = directory / ".scores"
    sdir.mkdir(exist_ok=True, parents=True)
    (sdir / ".log").mkdir(exist_ok=True, parents=True)
    return sdir


def database_path_for(directory: Path) -> Path:
    """Get the database path for a media directory."""
    scores_dir = scores_dir_for(directory)
    return scores_dir / "media_files.db"


def sidecar_path_for(video_path: Path) -> Path:
    """Get the sidecar file path for a media file (legacy format)."""
    return scores_dir_for(video_path.parent) / f"{video_path.name}.json"


def read_score(video_path: Path) -> Optional[int]:
    """Read score from database first, fall back to legacy sidecar file."""
    state = get_state()
    
    # Try to get from database first
    if hasattr(state, 'media_db') and state.media_db:
        relative_path = str(video_path.relative_to(state.video_dir))
        media_file = state.media_db.get_media_file(relative_path)
        if media_file and media_file.score is not None:
            return media_file.score
    
    # Fall back to legacy sidecar file
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
    """Write score to database and legacy sidecar file."""
    state = get_state()
    
    # Write to database if available
    if hasattr(state, 'media_db') and state.media_db:
        try:
            relative_path = str(video_path.relative_to(state.video_dir))
            state.media_db.update_score(relative_path, score)
        except Exception as e:
            state.logger.error(f"Failed to update score in database: {e}")
    
    # Also write to legacy sidecar file for backwards compatibility
    scp = sidecar_path_for(video_path)
    payload = {
        "file": video_path.name,
        "score": int(score),
        "updated": dt.datetime.now().isoformat(timespec="seconds"),
    }
    scp.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _match_union(directory: Path, pattern: str) -> List[Path]:
    """Find files matching pattern union."""
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
    """Discover media files matching pattern."""
    return _match_union(directory, pattern)


def extract_media_metadata(file_path: Path, media_dir: Path) -> MediaFile:
    """Extract comprehensive metadata from a media file."""
    relative_path = str(file_path.relative_to(media_dir))
    
    # Get file stats
    stat = file_path.stat()
    
    # Create base MediaFile object
    media_file = MediaFile(
        filename=file_path.name,
        filepath=relative_path,
        file_size=stat.st_size,
        created_date=dt.datetime.fromtimestamp(stat.st_ctime),
        modified_date=dt.datetime.fromtimestamp(stat.st_mtime)
    )
    
    # Get existing score
    score = read_score(file_path)
    if score is not None:
        media_file.score = score
    
    # Extract image metadata
    if file_path.suffix.lower() in {'.png', '.jpg', '.jpeg'}:
        try:
            if Image:
                with Image.open(file_path) as img:
                    media_file.width = img.width
                    media_file.height = img.height
            
            # Extract generation parameters from PNG
            if file_path.suffix.lower() == '.png':
                generation_params = extract_png_metadata(file_path)
                if generation_params:
                    media_file.generation_params = generation_params
                    
        except Exception as e:
            logging.warning(f"Failed to extract metadata from {file_path}: {e}")
    
    # Extract video metadata (basic dimensions)
    elif file_path.suffix.lower() == '.mp4':
        try:
            import subprocess
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "video:0",
                "-show_entries", "stream=width,height",
                "-of", "json", str(file_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(result.stdout or "{}")
            if isinstance(info, dict) and info.get("streams"):
                st = info["streams"][0]
                w = st.get("width")
                h = st.get("height")
                if w and h:
                    media_file.width = int(w)
                    media_file.height = int(h)
        except Exception as e:
            logging.warning(f"Failed to extract video metadata from {file_path}: {e}")
    
    return media_file


def scan_directory_to_database(directory: Path, pattern: str) -> List[Path]:
    """Scan directory and populate database with media file metadata."""
    state = get_state()
    
    # Initialize database
    db_path = database_path_for(directory)
    media_db = MediaFileDatabase(db_path)
    state.media_db = media_db
    
    # Discover files
    file_list = discover_files(directory, pattern)
    
    # Process each file and store in database
    relative_paths = []
    for file_path in file_list:
        try:
            # Extract comprehensive metadata
            media_file = extract_media_metadata(file_path, directory)
            
            # Store in database
            media_db.upsert_media_file(media_file)
            relative_paths.append(media_file.filepath)
            
        except Exception as e:
            state.logger.error(f"Failed to process {file_path}: {e}")
    
    # Clean up database - remove entries for files that no longer exist
    try:
        removed_count = media_db.cleanup_missing_files(relative_paths)
        if removed_count > 0:
            state.logger.info(f"Cleaned up {removed_count} missing files from database")
    except Exception as e:
        state.logger.error(f"Failed to cleanup database: {e}")
    
    state.logger.info(f"Scanned {len(file_list)} files, updated database")
    
    return file_list


def switch_directory(new_dir: Path, pattern: Optional[str] = None):
    """Switch to a new directory and scan files."""
    state = get_state()
    
    # Update state
    state.video_dir = new_dir
    if pattern is not None and pattern.strip():
        state.file_pattern = pattern.strip()
    
    # Setup logging
    setup_logging(new_dir)
    
    # Scan directory and populate database
    file_list = scan_directory_to_database(new_dir, state.file_pattern)
    state.file_list = file_list
    
    state.logger.info(f"SCAN dir={new_dir} pattern={state.file_pattern} files={len(file_list)}")
    
    return file_list


def setup_logging(directory: Path):
    """Setup logging for the given directory."""
    state = get_state()
    
    # Remove existing handlers
    for handler in state.logger.handlers[:]:
        state.logger.removeHandler(handler)
    
    # Setup file logging
    log_dir = scores_dir_for(directory) / ".log"
    log_file = log_dir / "video_scorer.log"
    
    handler = logging.FileHandler(log_file, encoding="utf-8")
    handler.setLevel(logging.DEBUG)
    
    formatter = logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s")
    handler.setFormatter(formatter)
    
    state.logger.addHandler(handler)
    state.logger.setLevel(logging.DEBUG)
    
    state.logger.info(f"Logger initialized. dir={directory}")