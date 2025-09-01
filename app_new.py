#!/usr/bin/env python3
"""
Media Scorer - Modular FastAPI Application
Reorganized for better maintainability and separation of concerns.
"""
import argparse
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
import uvicorn

# Import our modules
from src.core.config import config
from src.core.state import state
from src.api.main import router as main_router
from src.api.scoring import router as scoring_router
from src.api.scanning import router as scanning_router
from src.api.thumbnails import router as thumbnails_router
from src.api.metadata import router as metadata_router
from src.api.workflow import router as workflow_router


def create_app() -> FastAPI:
    """Create and configure the FastAPI application"""
    app = FastAPI(title="Media Scorer", description="Video & Image Scoring Application")
    
    # Mount static files
    app.mount("/static", StaticFiles(directory=Path(__file__).parent), name="static")
    app.mount("/themes", StaticFiles(directory=Path(__file__).parent / "themes"), name="themes")
    
    # Include routers
    app.include_router(main_router)
    app.include_router(scoring_router)
    app.include_router(scanning_router)
    app.include_router(thumbnails_router)
    app.include_router(metadata_router)
    app.include_router(workflow_router)
    
    return app


def main():
    """Main entry point"""
    # Load configuration from file first
    config.load_from_file()
    
    # Parse command line arguments
    ap = argparse.ArgumentParser(description="Video/Image Scorer (FastAPI)")
    ap.add_argument("--dir", required=False, default=config.dir, help="Directory with media files")
    ap.add_argument("--port", type=int, default=7862, help="Port to serve")
    ap.add_argument("--host", default="127.0.0.1", help="Host to bind")
    ap.add_argument("--pattern", default=config.pattern, help="Glob pattern, union with | (e.g., *.mp4|*.png|*.jpg)")
    ap.add_argument("--style", default=config.style, help="CSS style file from themes folder")
    ap.add_argument("--generate-thumbnails", action="store_true", default=config.generate_thumbnails, help="Generate thumbnail previews for media files")
    ap.add_argument("--thumbnail-height", type=int, default=config.thumbnail_height, help="Height in pixels for thumbnail previews")
    ap.add_argument("--toggle-extensions", nargs='*', default=config.toggle_extensions, help="File extensions for toggle buttons")
    ap.add_argument("--directory-sort-desc", action="store_true", help="Sort directory dropdown in descending order")
    ap.add_argument("--directory-sort-asc", action="store_true", help="Sort directory dropdown in ascending order")
    args = ap.parse_args()

    # Validate directory
    start_dir = Path(args.dir).expanduser().resolve()
    if not start_dir.exists() or not start_dir.is_dir():
        raise SystemExit(f"Directory not found: {start_dir}")

    # Update configuration with CLI arguments
    config.pattern = args.pattern or config.pattern
    config.style = args.style or config.style
    config.generate_thumbnails = args.generate_thumbnails
    config.thumbnail_height = args.thumbnail_height
    config.toggle_extensions = args.toggle_extensions or config.toggle_extensions
    
    # Handle directory sort direction
    if args.directory_sort_asc:
        config.directory_sort_desc = False
    elif args.directory_sort_desc:
        config.directory_sort_desc = True
    
    # Initialize application state
    state.switch_directory(start_dir, config.pattern)
    
    # Create and run the app
    app = create_app()
    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


if __name__ == "__main__":
    main()