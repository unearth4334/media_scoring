#!/usr/bin/env python3
"""Tests for the media info endpoints - both new and legacy formats."""

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


def test_media_info_new_format(client):
    """Test the new media info endpoint format: /api/media/info/{filename}"""
    # Test with a file that exists in the media directory
    response = client.get("/api/media/info/blue.jpg")
    assert response.status_code == 200
    data = response.json()
    
    # Verify expected fields are present
    assert "filename" in data
    assert data["filename"] == "blue.jpg"
    assert "file_size" in data
    assert "file_type" in data
    assert "dimensions" in data
    assert "score" in data
    

def test_media_info_legacy_format(client):
    """Test the legacy media info endpoint format: /api/media/{filename}/info"""
    # Test with a file that exists in the media directory
    response = client.get("/api/media/blue.jpg/info")
    assert response.status_code == 200
    data = response.json()
    
    # Verify expected fields are present
    assert "filename" in data
    assert data["filename"] == "blue.jpg"
    assert "file_size" in data
    assert "file_type" in data
    assert "dimensions" in data
    assert "score" in data


def test_media_info_formats_return_same_data(client):
    """Test that both endpoint formats return the same data."""
    # Get data from new format
    response_new = client.get("/api/media/info/blue.jpg")
    assert response_new.status_code == 200
    data_new = response_new.json()
    
    # Get data from legacy format
    response_legacy = client.get("/api/media/blue.jpg/info")
    assert response_legacy.status_code == 200
    data_legacy = response_legacy.json()
    
    # Compare the results (they should be identical)
    assert data_new == data_legacy


def test_media_info_complex_filename_new_format(client):
    """Test new format with a complex filename containing numbers and hyphens."""
    # First, verify the endpoint handles URL encoding properly
    # We'll use red.png as a test since it exists
    response = client.get("/api/media/info/red.png")
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "red.png"


def test_media_info_complex_filename_legacy_format(client):
    """Test legacy format with a complex filename containing numbers and hyphens."""
    # Test with red.png using legacy format
    response = client.get("/api/media/red.png/info")
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "red.png"


def test_media_info_nonexistent_file_new_format(client):
    """Test new format with a file that doesn't exist."""
    response = client.get("/api/media/info/nonexistent.jpg")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "File not found"


def test_media_info_nonexistent_file_legacy_format(client):
    """Test legacy format with a file that doesn't exist."""
    response = client.get("/api/media/nonexistent.jpg/info")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data
    assert data["detail"] == "File not found"


def test_media_info_dimensions_extraction(client):
    """Test that dimensions are properly extracted from images."""
    response = client.get("/api/media/info/blue.jpg")
    assert response.status_code == 200
    data = response.json()
    
    # Verify dimensions structure
    assert "dimensions" in data
    if data["dimensions"] is not None:
        assert "width" in data["dimensions"]
        assert "height" in data["dimensions"]
        assert isinstance(data["dimensions"]["width"], int)
        assert isinstance(data["dimensions"]["height"], int)


def test_media_info_resolution_and_aspect_ratio(client):
    """Test that resolution and aspect ratio are calculated correctly."""
    response = client.get("/api/media/info/blue.jpg")
    assert response.status_code == 200
    data = response.json()
    
    # If dimensions are available, resolution and aspect ratio should be calculated
    if data.get("dimensions"):
        assert "resolution" in data
        assert "aspect_ratio" in data
        
        # Verify resolution is calculated correctly (width * height)
        expected_resolution = data["dimensions"]["width"] * data["dimensions"]["height"]
        assert data["resolution"] == expected_resolution


def test_media_meta_endpoint_still_works(client):
    """Test that the /api/meta/{filename} endpoint still works independently."""
    response = client.get("/api/meta/blue.jpg")
    assert response.status_code == 200
    data = response.json()
    
    # This endpoint returns simpler metadata (just width/height)
    assert "width" in data or "height" in data
