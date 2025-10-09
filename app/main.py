"""Main application factory and CLI interface."""

import argparse
import sys
from pathlib import Path

import uvicorn
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .settings import Settings
from .state import init_state
from .routers import core, media, extract, thumbnails_api, root, search, ingest, ingest_v2
from .services.files import switch_directory
from .services.thumbnails import start_thumbnail_generation


def create_app(settings: Settings) -> FastAPI:
    """Create and configure the FastAPI application."""
    
    # Initialize global state
    state = init_state(settings)
    
    # Create FastAPI app
    app = FastAPI(title="Media Scoring Application")
    
    # Mount static files
    app.mount("/static", StaticFiles(directory="app/static"), name="static")
    app.mount("/themes", StaticFiles(directory="app/static/themes"), name="themes")
    
    # Include routers
    app.include_router(core.router)
    app.include_router(root.router)  # Root-level routes (media, download, thumbnail)
    app.include_router(media.router)
    app.include_router(extract.router)
    app.include_router(thumbnails_api.router)
    app.include_router(search.router)  # Database search functionality
    app.include_router(ingest.router)  # Data ingestion tool
    app.include_router(ingest_v2.router)  # Enhanced data ingestion tool v2
    
    # Initialize application
    _initialize_app(state)
    
    return app


def _initialize_app(state):
    """Initialize the application with directory scanning."""
    # Ensure directory is resolved to absolute path
    resolved_dir = state.video_dir.resolve()
    
    # Switch to initial directory and discover files
    file_list = switch_directory(resolved_dir, state.file_pattern)
    
    # Start thumbnail generation if enabled
    start_thumbnail_generation(resolved_dir, file_list)


def cli_main():
    """Command line interface entry point."""
    
    # Load settings from config file first
    try:
        settings = Settings.load_from_yaml()
    except Exception as e:
        print(f"Error loading settings: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Parse command line arguments to override settings
    parser = argparse.ArgumentParser(description="Video/Image Scorer (FastAPI)")
    parser.add_argument("--dir", type=Path, help="Directory with media files")
    parser.add_argument("--port", type=int, help="Port to serve")
    parser.add_argument("--host", help="Host to bind")
    parser.add_argument("--pattern", help="Glob pattern, union with | (e.g., *.mp4|*.png|*.jpg)")
    parser.add_argument("--style", help="CSS style file from themes folder (e.g., style_default.css, style_pastelcore.css, style_darkpastelcore.css, or style_darkcandy.css)")
    parser.add_argument("--generate-thumbnails", action="store_true", help="Generate thumbnail previews for media files")
    parser.add_argument("--no-generate-thumbnails", action="store_true", help="Disable thumbnail generation")
    parser.add_argument("--thumbnail-height", type=int, help="Height in pixels for thumbnail previews")
    parser.add_argument("--toggle-extensions", nargs='*', help="File extensions for toggle buttons")
    parser.add_argument("--directory-sort-desc", action="store_true", help="Sort directory dropdown in descending order")
    parser.add_argument("--directory-sort-asc", action="store_true", help="Sort directory dropdown in ascending order")
    parser.add_argument("--enable-database", action="store_true", help="Enable database storage for metadata and search")
    parser.add_argument("--disable-database", action="store_true", help="Disable database functionality")
    parser.add_argument("--database-url", help="PostgreSQL database URL (respects DATABASE_URL/MEDIA_DB_URL env vars)")
    
    args = parser.parse_args()
    
    # Override settings with command line arguments
    overrides = {}
    if args.dir is not None:
        overrides['dir'] = args.dir
    if args.port is not None:
        overrides['port'] = args.port
    if args.host is not None:
        overrides['host'] = args.host
    if args.pattern is not None:
        overrides['pattern'] = args.pattern
    if args.style is not None:
        overrides['style'] = args.style
    if args.generate_thumbnails:
        overrides['generate_thumbnails'] = True
    if args.no_generate_thumbnails:
        overrides['generate_thumbnails'] = False
    if args.thumbnail_height is not None:
        overrides['thumbnail_height'] = args.thumbnail_height
    if args.toggle_extensions is not None:
        overrides['toggle_extensions'] = args.toggle_extensions
    if args.directory_sort_desc:
        overrides['directory_sort_desc'] = True
    if args.directory_sort_asc:
        overrides['directory_sort_desc'] = False
    if args.enable_database:
        overrides['enable_database'] = True
    if args.disable_database:
        overrides['enable_database'] = False
    if args.database_url is not None:
        overrides['database_url'] = args.database_url
        # Auto-enable database when URL is provided
        overrides['enable_database'] = True
    
    # Create new settings with overrides
    try:
        # Merge config file settings with CLI overrides
        config_data = settings.dict()
        config_data.update(overrides)
        settings = Settings(**config_data)
    except Exception as e:
        print(f"Error with settings: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Create and run the app
    app = create_app(settings)
    uvicorn.run(app, host=settings.host, port=settings.port, log_level="info")