#!/usr/bin/env python3
"""
Tests for the data mining tool.

This script tests the mine_data.py tool to ensure it works correctly.
"""

import subprocess
import tempfile
import json
import sqlite3
from pathlib import Path
import sys

# Add the parent directory to Python path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.database.engine import init_database
from app.database.service import DatabaseService


def run_command(cmd, check=True):
    """Run a command and return the result."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Command failed: {cmd}")
        print(f"Return code: {result.returncode}")
        print(f"STDOUT: {result.stdout}")
        print(f"STDERR: {result.stderr}")
        raise subprocess.CalledProcessError(result.returncode, cmd)
    return result


def test_basic_functionality():
    """Test basic functionality with sample media directory."""
    print("Testing basic functionality...")
    
    # Test dry run
    result = run_command("python mine_data.py ./media --dry-run")
    assert result.returncode == 0
    assert "Processing completed successfully!" in result.stdout
    assert "Files processed: 6" in result.stdout
    
    print("✓ Basic dry run test passed")
    
    # Test with database
    result = run_command("python mine_data.py ./media --enable-database")
    assert result.returncode == 0
    assert "Processing completed successfully!" in result.stdout
    
    print("✓ Database mode test passed")


def test_pattern_filtering():
    """Test file pattern filtering."""
    print("Testing pattern filtering...")
    
    # Create test directory
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test files
        (temp_path / "test1.jpg").touch()
        (temp_path / "test2.png").touch()
        (temp_path / "test3.mp4").touch()
        (temp_path / "test4.txt").touch()
        
        # Test images only
        result = run_command(f"python mine_data.py {temp_dir} --pattern '*.jpg|*.png' --dry-run")
        assert result.returncode == 0
        assert "Total files found: 2" in result.stdout
        
        # Test videos only
        result = run_command(f"python mine_data.py {temp_dir} --pattern '*.mp4' --dry-run")
        assert result.returncode == 0
        assert "Total files found: 1" in result.stdout
        
    print("✓ Pattern filtering test passed")


def test_error_handling():
    """Test error handling for invalid inputs."""
    print("Testing error handling...")
    
    # Test non-existent directory
    result = run_command("python mine_data.py /nonexistent/directory", check=False)
    assert result.returncode != 0
    assert "Directory does not exist" in result.stdout
    
    # Test file instead of directory
    result = run_command("python mine_data.py ./mine_data.py", check=False)
    assert result.returncode != 0
    assert "Path is not a directory" in result.stdout
    
    print("✓ Error handling test passed")


def test_database_integration():
    """Test database integration."""
    print("Testing database integration...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create a test image file (copy from existing)
        test_image = temp_path / "test.jpg"
        import shutil
        shutil.copy("./media/image1.jpg", test_image)
        
        # Run mining with database
        result = run_command(f"python mine_data.py {temp_dir} --enable-database")
        assert result.returncode == 0
        
        # Check database was created
        db_path = temp_path / ".scores" / "media.db"
        assert db_path.exists()
        
        # Check database contents
        init_database(f"sqlite:///{db_path}")
        with DatabaseService() as db:
            stats = db.get_stats()
            assert stats['total_files'] >= 1
            assert stats['files_with_metadata'] >= 1
        
    print("✓ Database integration test passed")


def test_wrapper_script():
    """Test the wrapper script."""
    print("Testing wrapper script...")
    
    # Test help command
    result = run_command("./mine_archive.sh help")
    assert result.returncode == 0
    assert "Media Archive Data Mining Tool" in result.stdout
    
    # Test the test command
    result = run_command("./mine_archive.sh test ./media")
    assert result.returncode == 0
    # Check for either the colored or plain version of the success message
    output = result.stdout
    assert ("Mining completed successfully!" in output or 
           "[SUCCESS]" in output), f"Expected success message not found in: {output}"
    
    print("✓ Wrapper script test passed")


def test_sidecar_import():
    """Test importing scores from sidecar files."""
    print("Testing sidecar score import...")
    
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)
        
        # Create test file and sidecar
        test_file = temp_path / "test.jpg"
        test_file.touch()
        
        # Create scores directory and sidecar file
        scores_dir = temp_path / ".scores"
        scores_dir.mkdir()
        sidecar = scores_dir / "test.jpg.json"
        
        sidecar_data = {
            "file": "test.jpg",
            "score": 4,
            "updated": "2025-01-01T12:00:00"
        }
        sidecar.write_text(json.dumps(sidecar_data))
        
        # Run mining
        result = run_command(f"python mine_data.py {temp_dir} --enable-database")
        assert result.returncode == 0
        assert "Scores imported: 1" in result.stdout
        
        # Verify score was imported
        db_path = temp_path / ".scores" / "media.db"
        init_database(f"sqlite:///{db_path}")
        with DatabaseService() as db:
            score = db.get_media_file_score(test_file)
            assert score == 4
        
    print("✓ Sidecar import test passed")


def main():
    """Run all tests."""
    print("Running Data Mining Tool Tests")
    print("=" * 40)
    
    # Change to script directory
    script_dir = Path(__file__).parent
    import os
    os.chdir(script_dir)
    
    try:
        test_basic_functionality()
        test_pattern_filtering()
        test_error_handling()
        test_database_integration()
        test_wrapper_script()
        test_sidecar_import()
        
        print("\n" + "=" * 40)
        print("✓ All tests passed!")
        print("The data mining tool is working correctly.")
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()