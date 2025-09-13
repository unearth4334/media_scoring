#!/usr/bin/env python3
"""
Data Mining Tool for Media Archives

This tool scans directories of media files and extracts metadata, scores, and keywords
into the database for the Media Scoring application. It can be used to process existing
archives of media files without running the web server.

Usage:
    python mine_data.py /path/to/archive --pattern "*.mp4|*.png|*.jpg"
    python mine_data.py /path/to/archive --enable-database --pattern "*.jpg"
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Dict, Optional
import time

# Set up path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.settings import Settings
from app.database.engine import init_database, get_session
from app.database.service import DatabaseService
from app.services.files import discover_files, read_score, get_scores_dir_for
from app.services.metadata import extract_metadata, extract_keywords_from_metadata


class DataMiner:
    """Main class for mining data from media archives."""
    
    def __init__(self, settings: Settings, logger: logging.Logger):
        self.settings = settings
        self.logger = logger
        self.stats = {
            'total_files': 0,
            'processed_files': 0,
            'metadata_extracted': 0,
            'keywords_added': 0,
            'scores_imported': 0,
            'errors': 0
        }
    
    def mine_directory(self, directory: Path, pattern: str = "*.mp4|*.png|*.jpg") -> Dict:
        """Mine data from a single directory."""
        self.logger.info(f"Starting to mine directory: {directory}")
        self.logger.info(f"Using pattern: {pattern}")
        
        if not directory.exists():
            raise FileNotFoundError(f"Directory does not exist: {directory}")
        
        if not directory.is_dir():
            raise ValueError(f"Path is not a directory: {directory}")
        
        # Initialize database if enabled
        if self.settings.enable_database:
            try:
                database_url = self._get_database_url(directory)
                init_database(database_url)
                self.logger.info(f"Database initialized with URL: {database_url}")
            except Exception as e:
                self.logger.error(f"Failed to initialize database: {e}")
                if not self.settings.database_url:  # Only fail if using local SQLite
                    raise
        
        # Discover files
        files = discover_files(directory, pattern)
        self.stats['total_files'] = len(files)
        self.logger.info(f"Found {len(files)} files matching pattern")
        
        if not files:
            self.logger.warning("No files found matching the specified pattern")
            return self.stats
        
        # Process files
        if self.settings.enable_database:
            self._process_files_with_database(files)
        else:
            self._process_files_without_database(files)
        
        # Report final statistics
        self._report_final_stats()
        return self.stats
    
    def _get_database_url(self, directory: Path) -> str:
        """Get the database URL for the directory."""
        if self.settings.database_url:
            return self.settings.database_url
        
        if self.settings.database_path:
            return f"sqlite:///{self.settings.database_path}"
        
        # Default: create database in .scores directory
        scores_dir = get_scores_dir_for(directory)
        db_path = scores_dir / "media.db"
        return f"sqlite:///{db_path}"
    
    def _process_files_with_database(self, files: List[Path]) -> None:
        """Process files and store data in database."""
        self.logger.info("Processing files with database storage enabled")
        
        with DatabaseService() as db:
            for i, file_path in enumerate(files, 1):
                try:
                    self._process_single_file_with_db(db, file_path, i, len(files))
                except Exception as e:
                    self.logger.error(f"Error processing {file_path.name}: {e}")
                    self.stats['errors'] += 1
                    continue
    
    def _process_single_file_with_db(self, db: DatabaseService, file_path: Path, 
                                   current: int, total: int) -> None:
        """Process a single file with database storage."""
        if current % 10 == 0 or current == total:
            self.logger.info(f"Processing file {current}/{total}: {file_path.name}")
        
        # Create/update media file record
        media_file = db.get_or_create_media_file(file_path)
        self.stats['processed_files'] += 1
        
        # Import score from sidecar file if exists
        sidecar_score = read_score(file_path)
        if sidecar_score is not None and media_file.score != sidecar_score:
            media_file.score = sidecar_score
            self.stats['scores_imported'] += 1
            self.logger.debug(f"Imported score {sidecar_score} for {file_path.name}")
        
        # Extract and store metadata
        try:
            metadata = extract_metadata(file_path)
            if metadata:
                db.store_media_metadata(file_path, metadata)
                self.stats['metadata_extracted'] += 1
                self.logger.debug(f"Extracted metadata for {file_path.name}")
                
                # Extract and add keywords from metadata
                keywords = extract_keywords_from_metadata(metadata)
                if keywords:
                    keyword_objects = db.add_keywords(
                        file_path, keywords, 
                        keyword_type='auto', 
                        source='metadata_extraction'
                    )
                    self.stats['keywords_added'] += len(keyword_objects)
                    self.logger.debug(f"Added {len(keyword_objects)} keywords for {file_path.name}")
        
        except Exception as e:
            self.logger.warning(f"Failed to extract metadata for {file_path.name}: {e}")
    
    def _process_files_without_database(self, files: List[Path]) -> None:
        """Process files without database (metadata extraction only)."""
        self.logger.info("Processing files without database (dry run mode)")
        
        for i, file_path in enumerate(files, 1):
            try:
                if i % 10 == 0 or i == len(files):
                    self.logger.info(f"Processing file {i}/{len(files)}: {file_path.name}")
                
                # Just extract metadata to verify it works
                metadata = extract_metadata(file_path)
                if metadata:
                    self.stats['metadata_extracted'] += 1
                
                # Check for existing sidecar scores
                sidecar_score = read_score(file_path)
                if sidecar_score is not None:
                    self.stats['scores_imported'] += 1
                
                self.stats['processed_files'] += 1
                
            except Exception as e:
                self.logger.error(f"Error processing {file_path.name}: {e}")
                self.stats['errors'] += 1
    
    def _report_final_stats(self) -> None:
        """Report final processing statistics."""
        self.logger.info("=" * 50)
        self.logger.info("DATA MINING COMPLETED")
        self.logger.info("=" * 50)
        self.logger.info(f"Total files found: {self.stats['total_files']}")
        self.logger.info(f"Files processed: {self.stats['processed_files']}")
        self.logger.info(f"Metadata extracted: {self.stats['metadata_extracted']}")
        self.logger.info(f"Keywords added: {self.stats['keywords_added']}")
        self.logger.info(f"Scores imported: {self.stats['scores_imported']}")
        self.logger.info(f"Errors encountered: {self.stats['errors']}")
        
        if self.stats['errors'] > 0:
            self.logger.warning(f"Processing completed with {self.stats['errors']} errors")
        else:
            self.logger.info("Processing completed successfully!")


def setup_logging(verbose: bool = False) -> logging.Logger:
    """Setup logging for the data mining tool."""
    logger = logging.getLogger("data_miner")
    logger.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Remove existing handlers
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG if verbose else logging.INFO)
    
    # Formatter
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    return logger


def main():
    """Main entry point for the data mining tool."""
    parser = argparse.ArgumentParser(
        description="Mine data from media archives for the Media Scoring application",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python mine_data.py /media/archive1
  python mine_data.py /media/archive1 --pattern "*.mp4|*.png"
  python mine_data.py /media/archive1 --enable-database
  python mine_data.py /media/archive1 --database-path /custom/path/media.db
  python mine_data.py /media/archive1 --verbose --dry-run
        """
    )
    
    # Required arguments
    parser.add_argument(
        "directory",
        type=Path,
        help="Directory containing media files to mine"
    )
    
    # Optional arguments
    parser.add_argument(
        "--pattern",
        default="*.mp4|*.png|*.jpg",
        help="File pattern to match (e.g., '*.mp4|*.png|*.jpg')"
    )
    
    parser.add_argument(
        "--enable-database",
        action="store_true",
        help="Enable database storage (default: false for dry run)"
    )
    
    parser.add_argument(
        "--database-path",
        type=Path,
        help="Custom database file path (default: <directory>/.scores/media.db)"
    )
    
    parser.add_argument(
        "--database-url",
        help="Database URL for external database (overrides --database-path)"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging"
    )
    
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry run mode - don't store data in database (same as not using --enable-database)"
    )
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(args.verbose)
    
    # Validate arguments
    if not args.directory.exists():
        logger.error(f"Directory does not exist: {args.directory}")
        sys.exit(1)
    
    if not args.directory.is_dir():
        logger.error(f"Path is not a directory: {args.directory}")
        sys.exit(1)
    
    # Create settings
    try:
        # Start with default settings
        settings = Settings.load_from_yaml()
        
        # Override with command line arguments
        settings.dir = args.directory
        settings.pattern = args.pattern
        settings.enable_database = args.enable_database and not args.dry_run
        
        if args.database_path:
            settings.database_path = args.database_path
        if args.database_url:
            settings.database_url = args.database_url
            
    except Exception as e:
        logger.error(f"Failed to load settings: {e}")
        sys.exit(1)
    
    # Report configuration
    logger.info("Data Mining Tool for Media Archives")
    logger.info("=" * 40)
    logger.info(f"Source directory: {args.directory}")
    logger.info(f"File pattern: {args.pattern}")
    logger.info(f"Database enabled: {settings.enable_database}")
    if settings.enable_database:
        if settings.database_url:
            logger.info(f"Database URL: {settings.database_url}")
        else:
            db_path = args.database_path or (args.directory / ".scores" / "media.db")
            logger.info(f"Database path: {db_path}")
    else:
        logger.info("Running in dry-run mode (no database storage)")
    
    # Run the data mining
    try:
        start_time = time.time()
        miner = DataMiner(settings, logger)
        stats = miner.mine_directory(args.directory, args.pattern)
        elapsed_time = time.time() - start_time
        
        logger.info(f"Total processing time: {elapsed_time:.2f} seconds")
        
        # Exit with error code if there were errors
        if stats['errors'] > 0:
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Data mining failed: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()