#!/usr/bin/env python3
"""
Tests for string sanitization utilities.
"""

import pytest
from app.utils.sanitization import (
    sanitize_string,
    sanitize_dict,
    sanitize_list,
    sanitize_file_data
)


def test_sanitize_string_removes_nul():
    """Test that NUL characters are removed from strings."""
    # Test string with NUL character
    input_str = "Hello\x00World"
    expected = "HelloWorld"
    assert sanitize_string(input_str) == expected
    
    # Test string with multiple NUL characters
    input_str = "Test\x00\x00String\x00"
    expected = "TestString"
    assert sanitize_string(input_str) == expected


def test_sanitize_string_preserves_clean_strings():
    """Test that clean strings are not modified."""
    input_str = "Clean string without NUL characters"
    assert sanitize_string(input_str) == input_str


def test_sanitize_string_handles_empty():
    """Test that empty strings are handled correctly."""
    assert sanitize_string("") == ""


def test_sanitize_string_non_string():
    """Test that non-string values are returned unchanged."""
    assert sanitize_string(123) == 123
    assert sanitize_string(None) is None


def test_sanitize_dict_simple():
    """Test dictionary sanitization with simple values."""
    input_dict = {
        "key1": "value\x00with\x00nul",
        "key2": "clean value",
        "key3": 123
    }
    expected = {
        "key1": "valuewithnul",
        "key2": "clean value",
        "key3": 123
    }
    assert sanitize_dict(input_dict) == expected


def test_sanitize_dict_nested():
    """Test dictionary sanitization with nested structures."""
    input_dict = {
        "level1": {
            "level2": {
                "text": "nested\x00value"
            }
        },
        "list": ["item1\x00", "item2"]
    }
    expected = {
        "level1": {
            "level2": {
                "text": "nestedvalue"
            }
        },
        "list": ["item1", "item2"]
    }
    assert sanitize_dict(input_dict) == expected


def test_sanitize_dict_with_nul_in_keys():
    """Test that NUL characters in keys are also removed."""
    input_dict = {
        "key\x00with\x00nul": "value"
    }
    expected = {
        "keywithnul": "value"
    }
    assert sanitize_dict(input_dict) == expected


def test_sanitize_list_simple():
    """Test list sanitization with simple values."""
    input_list = ["value1\x00", "clean", 123, "value2\x00"]
    expected = ["value1", "clean", 123, "value2"]
    assert sanitize_list(input_list) == expected


def test_sanitize_list_nested():
    """Test list sanitization with nested structures."""
    input_list = [
        {"key": "value\x00"},
        ["nested\x00", "list"],
        "string\x00"
    ]
    expected = [
        {"key": "value"},
        ["nested", "list"],
        "string"
    ]
    assert sanitize_list(input_list) == expected


def test_sanitize_file_data_metadata():
    """Test sanitization of file data with metadata."""
    file_data = {
        "filename": "test\x00.jpg",
        "file_path": "/path/to/file\x00.jpg",
        "metadata": {
            "prompt": "A test\x00prompt",
            "negative_prompt": "bad\x00quality",
            "model": "stable\x00diffusion"
        }
    }
    
    result = sanitize_file_data(file_data)
    
    assert result["filename"] == "test.jpg"
    assert result["file_path"] == "/path/to/file.jpg"
    assert result["metadata"]["prompt"] == "A testprompt"
    assert result["metadata"]["negative_prompt"] == "badquality"
    assert result["metadata"]["model"] == "stablediffusion"


def test_sanitize_file_data_keywords():
    """Test sanitization of file data with keywords."""
    file_data = {
        "filename": "test.jpg",
        "keywords": ["keyword1\x00", "clean keyword", "keyword2\x00"]
    }
    
    result = sanitize_file_data(file_data)
    
    assert result["keywords"] == ["keyword1", "clean keyword", "keyword2"]


def test_sanitize_file_data_complex():
    """Test sanitization of complex file data structure."""
    file_data = {
        "filename": "test\x00.jpg",
        "file_path": "/path\x00/to/file.jpg",
        "file_size": 12345,
        "score": 5,
        "metadata": {
            "prompt": "Test\x00prompt",
            "width": 512,
            "height": 512,
            "workflow_data": {
                "nodes": [
                    {"type": "KSampler\x00", "seed": 123}
                ]
            }
        },
        "keywords": ["tag1\x00", "tag2", "tag3\x00"],
        "nsfw_score": 0.1,
        "nsfw_label": "sfw"
    }
    
    result = sanitize_file_data(file_data)
    
    # Check all string values are sanitized
    assert result["filename"] == "test.jpg"
    assert result["file_path"] == "/path/to/file.jpg"
    assert result["metadata"]["prompt"] == "Testprompt"
    assert result["metadata"]["workflow_data"]["nodes"][0]["type"] == "KSampler"
    assert result["keywords"] == ["tag1", "tag2", "tag3"]
    
    # Check non-string values are preserved
    assert result["file_size"] == 12345
    assert result["score"] == 5
    assert result["nsfw_score"] == 0.1
    assert result["nsfw_label"] == "sfw"


def test_sanitize_file_data_empty():
    """Test sanitization of empty file data."""
    file_data = {}
    result = sanitize_file_data(file_data)
    assert result == {}


def test_sanitize_file_data_no_modifications_needed():
    """Test that clean file data is not modified unnecessarily."""
    file_data = {
        "filename": "clean.jpg",
        "metadata": {
            "prompt": "Clean prompt"
        },
        "keywords": ["clean", "tags"]
    }
    
    result = sanitize_file_data(file_data)
    
    # Should produce equivalent data (though not necessarily the same object)
    assert result["filename"] == file_data["filename"]
    assert result["metadata"]["prompt"] == file_data["metadata"]["prompt"]
    assert result["keywords"] == file_data["keywords"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
