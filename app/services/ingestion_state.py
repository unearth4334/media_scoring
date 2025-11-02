"""Persistent state management for ingestion v2 workflow."""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set
from threading import Lock

logger = logging.getLogger(__name__)


class IngestionState:
    """Manages persistent state for ingestion sessions."""
    
    def __init__(self, state_dir: Path = None):
        """Initialize the ingestion state manager.
        
        Args:
            state_dir: Directory to store state files. Defaults to .ingestion_state/
        """
        if state_dir is None:
            state_dir = Path.cwd() / ".ingestion_state"
        
        self.state_dir = state_dir
        self.state_dir.mkdir(exist_ok=True)
        self._lock = Lock()
    
    def get_state_file(self, session_id: str) -> Path:
        """Get the state file path for a session."""
        return self.state_dir / f"{session_id}.json"
    
    def save_state(self, session_id: str, state: Dict) -> None:
        """Save session state to disk.
        
        Args:
            session_id: Unique session identifier
            state: State dictionary to save
        """
        with self._lock:
            state_file = self.get_state_file(session_id)
            
            # Add timestamp
            state["last_updated"] = datetime.now().isoformat()
            
            try:
                with open(state_file, 'w', encoding='utf-8') as f:
                    json.dump(state, f, indent=2)
                logger.debug(f"Saved state for session {session_id}")
            except Exception as e:
                logger.error(f"Failed to save state for session {session_id}: {e}")
    
    def load_state(self, session_id: str) -> Optional[Dict]:
        """Load session state from disk.
        
        Args:
            session_id: Unique session identifier
            
        Returns:
            State dictionary or None if not found
        """
        with self._lock:
            state_file = self.get_state_file(session_id)
            
            if not state_file.exists():
                return None
            
            try:
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                logger.debug(f"Loaded state for session {session_id}")
                return state
            except Exception as e:
                logger.error(f"Failed to load state for session {session_id}: {e}")
                return None
    
    def delete_state(self, session_id: str) -> None:
        """Delete session state file.
        
        Args:
            session_id: Unique session identifier
        """
        with self._lock:
            state_file = self.get_state_file(session_id)
            
            if state_file.exists():
                try:
                    state_file.unlink()
                    logger.debug(f"Deleted state for session {session_id}")
                except Exception as e:
                    logger.error(f"Failed to delete state for session {session_id}: {e}")
    
    def list_sessions(self) -> List[str]:
        """List all active session IDs.
        
        Returns:
            List of session IDs
        """
        with self._lock:
            session_ids = []
            for state_file in self.state_dir.glob("*.json"):
                session_ids.append(state_file.stem)
            return session_ids
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """Clean up old session state files.
        
        Args:
            max_age_hours: Maximum age in hours before cleanup
            
        Returns:
            Number of sessions cleaned up
        """
        from datetime import timedelta
        
        with self._lock:
            cleaned = 0
            cutoff = datetime.now() - timedelta(hours=max_age_hours)
            
            for state_file in self.state_dir.glob("*.json"):
                try:
                    # Check file modification time
                    mtime = datetime.fromtimestamp(state_file.stat().st_mtime)
                    if mtime < cutoff:
                        state_file.unlink()
                        cleaned += 1
                        logger.debug(f"Cleaned up old session: {state_file.stem}")
                except Exception as e:
                    logger.error(f"Failed to cleanup {state_file}: {e}")
            
            return cleaned


class SessionState:
    """Represents the state of an ingestion session."""
    
    def __init__(self, session_id: str, parameters: Dict, files: List[str]):
        """Initialize session state.
        
        Args:
            session_id: Unique session identifier
            parameters: Ingestion parameters
            files: List of file paths to process
        """
        self.session_id = session_id
        self.parameters = parameters
        self.files = files
        self.total_files = len(files)
        self.processed_files: Set[str] = set()
        self.current_file_index = 0
        self.status = "initialized"
        self.start_time = datetime.now().isoformat()
        self.end_time: Optional[str] = None
        self.stats = {
            "total_files": self.total_files,
            "processed_files": 0,
            "metadata_extracted": 0,
            "keywords_added": 0,
            "scores_imported": 0,
            "nsfw_detected": 0,
            "errors": 0,
            "committed_files": 0
        }
        self.errors: List[str] = []
    
    def to_dict(self) -> Dict:
        """Convert state to dictionary for serialization."""
        return {
            "session_id": self.session_id,
            "parameters": self.parameters,
            "files": self.files,
            "total_files": self.total_files,
            "processed_files": list(self.processed_files),
            "current_file_index": self.current_file_index,
            "status": self.status,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "stats": self.stats,
            "errors": self.errors
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'SessionState':
        """Create SessionState from dictionary."""
        state = cls(
            session_id=data["session_id"],
            parameters=data["parameters"],
            files=data["files"]
        )
        state.processed_files = set(data.get("processed_files", []))
        state.current_file_index = data.get("current_file_index", 0)
        state.status = data.get("status", "initialized")
        state.start_time = data.get("start_time", datetime.now().isoformat())
        state.end_time = data.get("end_time")
        state.stats = data.get("stats", state.stats)
        state.errors = data.get("errors", [])
        return state
    
    def mark_file_processed(self, file_path: str, success: bool = True,
                           error: Optional[str] = None) -> None:
        """Mark a file as processed.
        
        Args:
            file_path: Path to the processed file
            success: Whether processing was successful
            error: Error message if processing failed
        """
        self.processed_files.add(file_path)
        self.stats["processed_files"] = len(self.processed_files)
        
        if not success and error:
            self.errors.append(error)
            self.stats["errors"] += 1
    
    def get_next_file(self) -> Optional[str]:
        """Get the next file to process.
        
        Returns:
            File path or None if all files processed
        """
        # Skip already processed files
        while self.current_file_index < len(self.files):
            file_path = self.files[self.current_file_index]
            if file_path not in self.processed_files:
                return file_path
            self.current_file_index += 1
        
        return None
    
    def get_progress_percentage(self) -> int:
        """Calculate progress percentage.
        
        Returns:
            Progress as integer percentage (0-100)
        """
        if self.total_files == 0:
            return 100
        return int((len(self.processed_files) / self.total_files) * 100)
