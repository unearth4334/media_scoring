"""Application state management."""

import logging
from pathlib import Path
from typing import List, Optional

from .settings import Settings


class ApplicationState:
    """Manages in-memory application state."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.video_dir: Path = settings.dir
        self.file_list: List[Path] = []
        self.file_pattern: str = settings.pattern
        self.logger: logging.Logger = logging.getLogger("video_scorer_fastapi")
        self.media_db = None  # Will be initialized when directory is scanned
        
        # Thumbnail generation progress tracking
        self.thumbnail_progress = {
            "generating": False,
            "current": 0,
            "total": 0,
            "current_file": ""
        }
        
    def update_directory(self, new_dir: Path, pattern: Optional[str] = None):
        """Update current directory and pattern."""
        self.video_dir = new_dir
        if pattern:
            self.file_pattern = pattern
        
    def get_scores_dir(self) -> Path:
        """Get the scores directory for current video directory."""
        return self.video_dir / ".scores"
        
    def get_thumbnails_dir(self) -> Path:
        """Get the thumbnails directory for current video directory."""
        return self.video_dir / ".thumbnails"


# Global state instance - will be initialized in main.py
app_state: Optional[ApplicationState] = None


def get_state() -> ApplicationState:
    """Get the global application state."""
    if app_state is None:
        raise RuntimeError("Application state not initialized")
    return app_state


def init_state(settings: Settings) -> ApplicationState:
    """Initialize the global application state."""
    global app_state
    app_state = ApplicationState(settings)
    return app_state