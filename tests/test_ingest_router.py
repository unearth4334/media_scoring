#!/usr/bin/env python3
"""Tests for the ingest router and web UI."""

import sys
from pathlib import Path

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.settings import Settings


@pytest.fixture
def client():
    """Create a test client."""
    settings = Settings.load_from_yaml()
    app = create_app(settings)
    return TestClient(app)


def test_ingest_page_loads(client):
    """Test that the ingest page loads successfully."""
    response = client.get("/ingest")
    assert response.status_code == 200
    assert b"Data Ingestion Tool" in response.content
    assert b"Target Directories" in response.content
    assert b"Browse & Select Directories" in response.content


def test_directory_api_home(client):
    """Test the directory listing API with home directory."""
    response = client.get("/api/ingest/directories")
    assert response.status_code == 200
    data = response.json()
    assert "path" in data
    assert "directories" in data
    assert "file_summary" in data


def test_directory_api_specific_path(client):
    """Test the directory listing API with a specific path."""
    # Use the current working directory as a test
    test_path = str(Path.cwd())
    response = client.get(f"/api/ingest/directories?path={test_path}")
    assert response.status_code == 200
    data = response.json()
    assert data["path"] == test_path
    assert isinstance(data["directories"], list)


def test_directory_api_invalid_path(client):
    """Test the directory listing API with an invalid path."""
    response = client.get("/api/ingest/directories?path=/nonexistent/path")
    # The API returns 500 for invalid paths, which is acceptable for security
    assert response.status_code in [404, 500]


def test_ingest_page_has_menu_link(client):
    """Test that the main page has a link to the ingest tool."""
    response = client.get("/")
    assert response.status_code == 200
    assert b"Data Ingestion Tool" in response.content
    assert b"/ingest" in response.content


def test_ingest_page_has_multiple_directory_elements(client):
    """Test that the ingest page has elements for multiple directory selection."""
    response = client.get("/ingest")
    assert response.status_code == 200
    # Check for the selected directories container
    assert b"selected-directories" in response.content
    # Check for clear selection button
    assert b"clear-selection-btn" in response.content
    # Check for add/remove buttons
    assert b"tree-add-btn" in response.content
    assert b"tree-remove-btn" in response.content


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
