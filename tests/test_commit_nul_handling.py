#!/usr/bin/env python3
"""
Integration tests for ingest v2 commit with problematic data.
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.routers.ingest_v2 import _commit_single_file
from app.database.service import DatabaseService


@pytest.fixture
def temp_test_dir():
    """Create a temporary directory for test files."""
    temp_dir = Path(tempfile.mkdtemp())
    yield temp_dir
    shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.fixture
def mock_db_service():
    """Create a mock database service."""
    db = MagicMock(spec=DatabaseService)
    db.session = MagicMock()
    return db


def test_commit_single_file_with_nul_in_metadata(mock_db_service, temp_test_dir):
    """Test that files with NUL characters in metadata are handled gracefully."""
    # Create a test file
    test_file = temp_test_dir / "test.jpg"
    test_file.write_text("fake image data")
    
    # Mock the get_or_create_media_file to return a mock media file
    mock_media_file = MagicMock()
    mock_db_service.get_or_create_media_file.return_value = mock_media_file
    
    # File data with NUL characters in metadata
    file_data = {
        "filename": "test.jpg",
        "file_path": str(test_file),
        "metadata": {
            "prompt": "A beautiful\x00landscape",
            "negative_prompt": "bad\x00quality",
            "model": "stable\x00diffusion"
        }
    }
    
    parameters = {
        "nsfw_threshold": 0.5
    }
    
    # This should not raise an exception
    error = _commit_single_file(mock_db_service, file_data, parameters)
    
    # Should succeed (no error returned)
    assert error is None
    
    # Verify that metadata was stored (sanitized)
    mock_db_service.store_media_metadata.assert_called_once()
    call_args = mock_db_service.store_media_metadata.call_args
    stored_metadata = call_args[0][1]
    
    # Check that NUL characters were removed
    assert "\x00" not in stored_metadata["prompt"]
    assert "\x00" not in stored_metadata["negative_prompt"]
    assert "\x00" not in stored_metadata["model"]
    
    # Check that content is otherwise preserved
    assert "beautiful" in stored_metadata["prompt"]
    assert "landscape" in stored_metadata["prompt"]


def test_commit_single_file_with_nul_in_keywords(mock_db_service, temp_test_dir):
    """Test that files with NUL characters in keywords are handled gracefully."""
    # Create a test file
    test_file = temp_test_dir / "test.jpg"
    test_file.write_text("fake image data")
    
    # Mock the get_or_create_media_file to return a mock media file
    mock_media_file = MagicMock()
    mock_db_service.get_or_create_media_file.return_value = mock_media_file
    
    # File data with NUL characters in keywords
    file_data = {
        "filename": "test.jpg",
        "file_path": str(test_file),
        "keywords": ["landscape\x00", "nature\x00", "beautiful"]
    }
    
    parameters = {
        "nsfw_threshold": 0.5
    }
    
    # This should not raise an exception
    error = _commit_single_file(mock_db_service, file_data, parameters)
    
    # Should succeed (no error returned)
    assert error is None
    
    # Verify that keywords were added (sanitized)
    mock_db_service.add_keywords.assert_called_once()
    call_args = mock_db_service.add_keywords.call_args
    stored_keywords = call_args[0][1]
    
    # Check that NUL characters were removed
    for keyword in stored_keywords:
        assert "\x00" not in keyword
    
    # Check that content is otherwise preserved
    assert "landscape" in stored_keywords
    assert "nature" in stored_keywords
    assert "beautiful" in stored_keywords


def test_commit_single_file_handles_database_errors(mock_db_service, temp_test_dir):
    """Test that database errors are caught and reported."""
    # Create a test file
    test_file = temp_test_dir / "test.jpg"
    test_file.write_text("fake image data")
    
    # Mock get_or_create_media_file to raise an exception
    mock_db_service.get_or_create_media_file.side_effect = Exception("Database connection failed")
    
    # File data
    file_data = {
        "filename": "test.jpg",
        "file_path": str(test_file)
    }
    
    parameters = {
        "nsfw_threshold": 0.5
    }
    
    # This should catch the exception and return an error message
    error = _commit_single_file(mock_db_service, file_data, parameters)
    
    # Should return an error message
    assert error is not None
    assert "Database connection failed" in error
    assert "test.jpg" in error
    
    # Session should be rolled back
    mock_db_service.session.rollback.assert_called_once()


def test_commit_single_file_with_complex_nested_nul(mock_db_service, temp_test_dir):
    """Test that nested NUL characters in complex metadata are handled."""
    # Create a test file
    test_file = temp_test_dir / "test.jpg"
    test_file.write_text("fake image data")
    
    # Mock the get_or_create_media_file to return a mock media file
    mock_media_file = MagicMock()
    mock_db_service.get_or_create_media_file.return_value = mock_media_file
    
    # File data with deeply nested NUL characters
    file_data = {
        "filename": "test.jpg",
        "file_path": str(test_file),
        "metadata": {
            "prompt": "Test\x00prompt",
            "workflow_data": {
                "nodes": [
                    {
                        "type": "KSampler\x00",
                        "params": {
                            "sampler": "euler\x00a"
                        }
                    }
                ]
            }
        }
    }
    
    parameters = {
        "nsfw_threshold": 0.5
    }
    
    # This should not raise an exception
    error = _commit_single_file(mock_db_service, file_data, parameters)
    
    # Should succeed (no error returned)
    assert error is None
    
    # Verify that metadata was stored (sanitized)
    mock_db_service.store_media_metadata.assert_called_once()
    call_args = mock_db_service.store_media_metadata.call_args
    stored_metadata = call_args[0][1]
    
    # Check that all NUL characters were removed, even in nested structures
    assert "\x00" not in stored_metadata["prompt"]
    assert "\x00" not in stored_metadata["workflow_data"]["nodes"][0]["type"]
    assert "\x00" not in stored_metadata["workflow_data"]["nodes"][0]["params"]["sampler"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
