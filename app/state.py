"""Global application state management."""

import logging
from pathlib import Path
from typing import List, Dict, Optional

from .settings import Settings
from .database import DatabaseService
from .database.engine import init_database


class ApplicationState:
    """Manages in-memory application state."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.video_dir: Path = settings.dir
        self.file_list: List[Path] = []
        self.file_pattern: str = settings.pattern
        self.logger: logging.Logger = logging.getLogger("video_scorer_fastapi")
        
        # Initialize database if enabled
        self.database_requested = settings.enable_database  # Track if user requested database
        self.database_enabled = settings.enable_database
        if self.database_enabled:
            try:
                db_url = settings.get_database_url()
                self.logger.info(f"Attempting to initialize database with URL: {db_url}")
                init_database(db_url)
                self.logger.info(f"Database initialized successfully")
            except Exception as e:
                self.logger.error(f"Failed to initialize database: {e}", exc_info=True)
                self.logger.warning("Database functionality disabled due to initialization failure")
                self.database_enabled = False
        else:
            self.logger.info("Database functionality is disabled in settings")
        
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
    
    def get_database_service(self) -> Optional[DatabaseService]:
        """Get a database service instance if database is enabled."""
        if not self.database_enabled:
            self.logger.warning("Database service requested but database is disabled")
            return None
        try:
            return DatabaseService()
        except Exception as e:
            self.logger.error(f"Failed to create database service: {e}", exc_info=True)
            return None


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