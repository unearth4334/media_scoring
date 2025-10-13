#!/usr/bin/env python3
"""Test the exact CLI that the container runs."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.main import cli_main

# Simulate the exact command line arguments the container uses
test_args = [
    'run.py',
    '--dir', '/media',
    '--port', '7862',
    '--host', '0.0.0.0',
    '--pattern', '*.mp4|*.png|*.jpg',
    '--style', 'style_default.css',
    '--generate-thumbnails',
    '--thumbnail-height', '64',
    '--database-url', 'postgresql://media_user:media_password@postgres:5432/media_scoring'
]

print("=== Testing CLI with exact container arguments ===")
print(f"Arguments: {test_args[1:]}")
print()

# Replace sys.argv to simulate command line
sys.argv = test_args

# Set up logging to see database initialization
import logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

try:
    print("Calling cli_main()...")
    # This should initialize everything but won't start the server (we'll interrupt)
    cli_main()
except KeyboardInterrupt:
    print("CLI test interrupted (expected)")
except Exception as e:
    print(f"CLI test failed: {e}")
    import traceback
    traceback.print_exc()
