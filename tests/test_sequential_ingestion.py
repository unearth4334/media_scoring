#!/usr/bin/env python3
"""
Unit tests for the sequential ingestion workflow with persistent state.
"""

import pytest
import tempfile
import json
from pathlib import Path
from datetime import datetime

# Import the state management classes
from app.services.ingestion_state import IngestionState, SessionState


class TestIngestionState:
    """Test the IngestionState persistence manager."""
    
    def test_save_and_load_state(self, tmp_path):
        """Test saving and loading state from disk."""
        # Create state manager with temp directory
        state_manager = IngestionState(state_dir=tmp_path)
        
        # Create test state
        test_state = {
            "session_id": "test-123",
            "status": "processing",
            "total_files": 10,
            "processed_files": ["file1.png", "file2.png"]
        }
        
        # Save state
        state_manager.save_state("test-123", test_state)
        
        # Verify file was created
        state_file = tmp_path / "test-123.json"
        assert state_file.exists()
        
        # Load state
        loaded_state = state_manager.load_state("test-123")
        assert loaded_state is not None
        assert loaded_state["session_id"] == "test-123"
        assert loaded_state["status"] == "processing"
        assert loaded_state["total_files"] == 10
        assert len(loaded_state["processed_files"]) == 2
        assert "last_updated" in loaded_state
    
    def test_load_nonexistent_state(self, tmp_path):
        """Test loading a state that doesn't exist."""
        state_manager = IngestionState(state_dir=tmp_path)
        
        # Try to load non-existent state
        loaded_state = state_manager.load_state("nonexistent")
        assert loaded_state is None
    
    def test_delete_state(self, tmp_path):
        """Test deleting state from disk."""
        state_manager = IngestionState(state_dir=tmp_path)
        
        # Create and save state
        test_state = {"session_id": "test-delete", "status": "completed"}
        state_manager.save_state("test-delete", test_state)
        
        # Verify file exists
        state_file = tmp_path / "test-delete.json"
        assert state_file.exists()
        
        # Delete state
        state_manager.delete_state("test-delete")
        
        # Verify file is gone
        assert not state_file.exists()
    
    def test_list_sessions(self, tmp_path):
        """Test listing all active sessions."""
        state_manager = IngestionState(state_dir=tmp_path)
        
        # Create multiple sessions
        for i in range(3):
            session_id = f"session-{i}"
            state_manager.save_state(session_id, {"session_id": session_id})
        
        # List sessions
        sessions = state_manager.list_sessions()
        assert len(sessions) == 3
        assert "session-0" in sessions
        assert "session-1" in sessions
        assert "session-2" in sessions


class TestSessionState:
    """Test the SessionState class."""
    
    def test_initialization(self):
        """Test creating a new session state."""
        files = ["/media/file1.png", "/media/file2.png", "/media/file3.png"]
        parameters = {
            "directory": "/media",
            "pattern": "*.png",
            "enable_nsfw_detection": True
        }
        
        session = SessionState("test-session", parameters, files)
        
        assert session.session_id == "test-session"
        assert session.total_files == 3
        assert len(session.files) == 3
        assert len(session.processed_files) == 0
        assert session.current_file_index == 0
        assert session.status == "initialized"
        assert session.stats["total_files"] == 3
        assert session.stats["processed_files"] == 0
    
    def test_get_next_file(self):
        """Test getting the next file to process."""
        files = ["/media/file1.png", "/media/file2.png", "/media/file3.png"]
        parameters = {"directory": "/media"}
        
        session = SessionState("test", parameters, files)
        
        # Get first file
        next_file = session.get_next_file()
        assert next_file == "/media/file1.png"
        
        # Mark as processed and move to next
        session.mark_file_processed(next_file)
        session.current_file_index += 1
        
        # Get second file
        next_file = session.get_next_file()
        assert next_file == "/media/file2.png"
    
    def test_mark_file_processed(self):
        """Test marking files as processed."""
        files = ["/media/file1.png", "/media/file2.png"]
        parameters = {"directory": "/media"}
        
        session = SessionState("test", parameters, files)
        
        # Mark first file as processed
        session.mark_file_processed("/media/file1.png", success=True)
        
        assert "/media/file1.png" in session.processed_files
        assert session.stats["processed_files"] == 1
        
        # Mark second file as failed
        session.mark_file_processed("/media/file2.png", success=False, 
                                   error="Test error")
        
        assert "/media/file2.png" in session.processed_files
        assert session.stats["processed_files"] == 2
        assert session.stats["errors"] == 1
        assert len(session.errors) == 1
    
    def test_skip_already_processed_files(self):
        """Test that get_next_file skips already processed files."""
        files = ["/media/file1.png", "/media/file2.png", "/media/file3.png"]
        parameters = {"directory": "/media"}
        
        session = SessionState("test", parameters, files)
        
        # Mark file1 as processed
        session.mark_file_processed("/media/file1.png")
        
        # Get next file - should skip file1 and return file2
        next_file = session.get_next_file()
        assert next_file == "/media/file2.png"
        
        # Mark file2 as processed and increment index
        session.mark_file_processed("/media/file2.png")
        session.current_file_index = 2
        
        # Now should return file3
        next_file = session.get_next_file()
        assert next_file == "/media/file3.png"
    
    def test_progress_percentage(self):
        """Test progress percentage calculation."""
        files = [f"/media/file{i}.png" for i in range(10)]
        parameters = {"directory": "/media"}
        
        session = SessionState("test", parameters, files)
        
        # No files processed
        assert session.get_progress_percentage() == 0
        
        # Process 5 files
        for i in range(5):
            session.mark_file_processed(f"/media/file{i}.png")
        
        assert session.get_progress_percentage() == 50
        
        # Process all files
        for i in range(5, 10):
            session.mark_file_processed(f"/media/file{i}.png")
        
        assert session.get_progress_percentage() == 100
    
    def test_to_dict_and_from_dict(self):
        """Test serialization and deserialization."""
        files = ["/media/file1.png", "/media/file2.png"]
        parameters = {
            "directory": "/media",
            "pattern": "*.png"
        }
        
        # Create session
        session1 = SessionState("test-serialization", parameters, files)
        session1.mark_file_processed("/media/file1.png")
        session1.current_file_index = 1
        session1.status = "processing"
        
        # Serialize
        state_dict = session1.to_dict()
        
        # Verify dict structure
        assert state_dict["session_id"] == "test-serialization"
        assert state_dict["total_files"] == 2
        assert len(state_dict["processed_files"]) == 1
        assert state_dict["current_file_index"] == 1
        assert state_dict["status"] == "processing"
        
        # Deserialize
        session2 = SessionState.from_dict(state_dict)
        
        # Verify restored state
        assert session2.session_id == session1.session_id
        assert session2.total_files == session1.total_files
        assert session2.current_file_index == session1.current_file_index
        assert session2.status == session1.status
        assert len(session2.processed_files) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
