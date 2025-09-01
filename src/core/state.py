"""Main state and operations for Media Scorer"""
import threading
from pathlib import Path
from typing import List, Optional
import logging

from .config import config
from .files import discover_files
from .logging import setup_logging
from .thumbnails import generate_thumbnails_for_directory


class MediaScorerState:
    """Global state manager for the application"""
    
    def __init__(self):
        self.video_dir: Path = Path.cwd()
        self.file_list: List[Path] = []
        self.file_pattern: str = "*.mp4"
        self.logger: Optional[logging.Logger] = None
    
    def switch_directory(self, new_dir: Path, pattern: Optional[str] = None):
        """Switch to a new directory and pattern"""
        self.video_dir = new_dir
        if pattern is not None and pattern.strip():
            self.file_pattern = pattern.strip()
        
        # Setup logging
        self.logger = setup_logging(self.video_dir)
        
        # Discover files
        self.file_list = discover_files(self.video_dir, self.file_pattern)
        self.logger.info(f"SCAN dir={self.video_dir} pattern={self.file_pattern} files={len(self.file_list)}")
        
        # Generate thumbnails if enabled (in background thread)
        if config.generate_thumbnails:
            thumbnail_thread = threading.Thread(
                target=generate_thumbnails_for_directory,
                args=(self.video_dir, self.file_list, config.thumbnail_height),
                daemon=True
            )
            thumbnail_thread.start()


# Global state instance
state = MediaScorerState()