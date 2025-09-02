#!/usr/bin/env python3
"""
Entry point for the Media Scoring Application.

This script provides a simple way to run the application:
    python run.py

All configuration and command-line argument handling is delegated to app.main.cli_main().
"""

from app.main import cli_main

if __name__ == "__main__":
    cli_main()