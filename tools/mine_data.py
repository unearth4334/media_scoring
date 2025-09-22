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
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.settings import Settings
from app.database.engine import init_database, get_session
from app.database.service import DatabaseService
from app.services.files import discover_files, read_score, get_scores_dir_for
from app.services.metadata import extract_metadata, extract_keywords_from_metadata


class DataMiner:
    """Main class for mining data from media archives."""
    
    def __init__(self, settings: Settings, logger: logging.Logger, test_output_dir: Optional[Path] = None):
        self.settings = settings
        self.logger = logger
        self.test_output_dir = test_output_dir
        self.stats = {
            'total_files': 0,
            'processed_files': 0,
            'metadata_extracted': 0,
            'keywords_added': 0,
            'scores_imported': 0,
            'errors': 0
        }
        # Store detailed data for export when in test mode
        self.collected_data = [] if test_output_dir else None
    
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
                self.logger.debug(f"Attempting database initialization with URL: {database_url}")
                init_database(database_url)
                self.logger.info(f"Database initialized with URL: {database_url}")
            except PermissionError as e:
                self.logger.error(f"Permission denied accessing database directory: {e}")
                self.logger.error("Please check that you have write permissions to the target directory")
                self.logger.error("Consider using --database-path to specify an alternative location")
                raise
            except ValueError as e:
                self.logger.error(f"Invalid database configuration: {e}")
                raise
            except Exception as e:
                self.logger.error(f"Failed to initialize database: {e}")
                self.logger.error(f"Database URL was: {database_url if 'database_url' in locals() else 'not set'}")
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
        
        # Export test results if requested
        if self.test_output_dir and self.collected_data:
            self._export_test_results()
        
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
                
                # Extract metadata to verify it works
                metadata = extract_metadata(file_path)
                if metadata:
                    self.stats['metadata_extracted'] += 1
                
                # Check for existing sidecar scores
                sidecar_score = read_score(file_path)
                if sidecar_score is not None:
                    self.stats['scores_imported'] += 1
                
                # If test output is requested, collect detailed data
                if self.collected_data is not None:
                    file_data = self._collect_file_data(file_path, metadata, sidecar_score)
                    self.collected_data.append(file_data)
                
                self.stats['processed_files'] += 1
                
            except Exception as e:
                self.logger.error(f"Error processing {file_path.name}: {e}")
                self.stats['errors'] += 1
    
    def _collect_file_data(self, file_path: Path, metadata: Dict, sidecar_score: Optional[int]) -> Dict:
        """Collect detailed file data for export."""
        # Import hashing functions
        from app.utils.hashing import compute_media_file_id, compute_perceptual_hash
        
        # Extract keywords from metadata if available
        keywords = []
        if metadata:
            keywords = extract_keywords_from_metadata(metadata)
            if keywords:
                self.stats['keywords_added'] += len(keywords)
        
        # Compute media file ID and perceptual hash
        media_file_id = None
        phash = None
        try:
            media_file_id = compute_media_file_id(file_path)
            phash = compute_perceptual_hash(file_path)
        except Exception as e:
            self.logger.debug(f"Failed to compute hashes for {file_path.name}: {e}")
        
        # Handle thumbnail generation for HTML export
        thumbnail_data = self._get_thumbnail_data(file_path)
        
        return {
            'file_path': str(file_path),
            'filename': file_path.name,
            'file_size': metadata.get('file_size', 0) if metadata else 0,
            'file_type': 'video' if file_path.suffix.lower() == '.mp4' else 'image',
            'extension': file_path.suffix.lower(),
            'score': sidecar_score,
            'metadata': metadata or {},
            'keywords': keywords,
            'error': metadata.get('error') if metadata else None,
            'media_file_id': media_file_id,
            'phash': phash,
            'thumbnail': thumbnail_data
        }
    
    def _get_thumbnail_data(self, file_path: Path) -> Dict:
        """Generate thumbnail and return thumbnail data for HTML export."""
        import base64
        import subprocess
        import tempfile
        
        # For the mining script, we'll generate thumbnails directly without using the app state
        # since the thumbnail service requires the application state to be initialized
        
        # Define thumbnail path manually
        thumbnail_dir = file_path.parent / ".thumbnails"
        thumbnail_dir.mkdir(exist_ok=True, parents=True)
        thumbnail_path = thumbnail_dir / f"{file_path.stem}_thumbnail.jpg"
        
        thumbnail_exists = thumbnail_path.exists()
        
        # Try to generate thumbnail if it doesn't exist
        if not thumbnail_exists:
            name_lower = file_path.name.lower()
            success = False
            
            if name_lower.endswith(('.png', '.jpg', '.jpeg')):
                success = self._generate_image_thumbnail(file_path, thumbnail_path)
                self.logger.debug(f"Generated image thumbnail for {file_path.name}: {success}")
            elif name_lower.endswith('.mp4'):
                success = self._generate_video_thumbnail(file_path, thumbnail_path) 
                self.logger.debug(f"Generated video thumbnail for {file_path.name}: {success}")
            
            thumbnail_exists = success and thumbnail_path.exists()
        
        # Convert thumbnail to base64 for embedding in HTML
        thumbnail_base64 = None
        if thumbnail_exists:
            try:
                with open(thumbnail_path, 'rb') as f:
                    thumbnail_bytes = f.read()
                    thumbnail_base64 = base64.b64encode(thumbnail_bytes).decode('utf-8')
            except Exception as e:
                self.logger.warning(f"Failed to read thumbnail for {file_path.name}: {e}")
        
        return {
            'exists': thumbnail_exists,
            'path': str(thumbnail_path) if thumbnail_exists else None,
            'base64': thumbnail_base64
        }
    
    def _generate_image_thumbnail(self, image_path: Path, output_path: Path) -> bool:
        """Generate thumbnail for an image file using PIL."""
        try:
            from PIL import Image
            
            with Image.open(image_path) as img:
                # Calculate width to maintain aspect ratio (default height: 64px)
                thumbnail_height = 64
                aspect_ratio = img.width / img.height
                width = int(thumbnail_height * aspect_ratio)
                
                # Resize image
                img.thumbnail((width, thumbnail_height), Image.Resampling.LANCZOS)
                
                # Convert to RGB if needed (for RGBA images)
                if img.mode in ('RGBA', 'P'):
                    rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                    rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                    img = rgb_img
                
                # Save as JPEG
                img.save(output_path, 'JPEG', quality=85, optimize=True)
                return True
        except Exception as e:
            self.logger.error(f"Failed to generate image thumbnail for {image_path}: {e}")
            return False
    
    def _generate_video_thumbnail(self, video_path: Path, output_path: Path) -> bool:
        """Generate thumbnail for a video file by extracting first frame."""
        import subprocess
        try:
            # Use ffmpeg to extract first frame (default height: 64px)  
            thumbnail_height = 64
            cmd = [
                "ffmpeg", "-y", "-i", str(video_path), 
                "-vf", f"scale=-1:{thumbnail_height}",
                "-vframes", "1", "-q:v", "2",
                str(output_path)
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                return True
            else:
                self.logger.error(f"ffmpeg failed for {video_path}: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            self.logger.error(f"ffmpeg timeout for {video_path}")
            return False
        except Exception as e:
            self.logger.error(f"Failed to generate video thumbnail for {video_path}: {e}")
            return False
    
    def _make_json_serializable(self, obj):
        """Convert objects to JSON-serializable format."""
        from app.utils.prompt_parser import Keyword, LoRA
        
        if isinstance(obj, Keyword):
            return {"text": obj.text, "weight": obj.weight}
        elif isinstance(obj, LoRA):
            return {"name": obj.name, "weight": obj.weight}
        elif isinstance(obj, list):
            return [self._make_json_serializable(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self._make_json_serializable(value) for key, value in obj.items()}
        else:
            return obj

    def _format_json_config_with_button(self, config_name: str, config_data: dict) -> str:
        """Format JSON config data with readable display and {...} button for raw JSON."""
        import html
        import json
        
        # Create readable display of key-value pairs
        readable_html = ""
        for key, value in config_data.items():
            # Convert underscores to spaces and title case for display
            display_key = key.replace('_', ' ').title()
            readable_html += f'<span class="config-item"><strong>{display_key}:</strong> {value}</span> '
        
        # Create raw JSON for the button
        raw_json = json.dumps(config_data, indent=2)
        escaped_raw_json = html.escape(raw_json)
        
        # Generate HTML with both readable format and {...} button
        return f'''
        <tr>
            <td>{config_name}</td>
            <td>
                <div class="config-display">
                    {readable_html}
                    <button class="raw-data-button" onclick="showRawData(`{escaped_raw_json}`, '{config_name}')">{{...}}</button>
                </div>
            </td>
        </tr>'''

    def _format_parsed_prompt_data(self, parsed_prompt_data, file_index):
        """Format parsed prompt data with pill boxes and raw data button."""
        import html
        import json
        
        # Create the raw JSON for display
        raw_json = json.dumps(self._make_json_serializable(parsed_prompt_data), indent=2)
        escaped_raw_json = html.escape(raw_json)
        
        # Build pill boxes
        pill_boxes_html = f'<button class="raw-data-button" onclick="showRawData(`{escaped_raw_json}`)">{{...}}</button>'
        pill_boxes_html += '<div class="parsed-prompt-container">'
        
        # Process positive keywords (green pills)
        if 'positive_keywords' in parsed_prompt_data:
            for keyword in parsed_prompt_data['positive_keywords']:
                # Handle both Keyword objects and dict representations
                if hasattr(keyword, 'text') and hasattr(keyword, 'weight'):
                    weight = keyword.weight
                    text = keyword.text
                elif isinstance(keyword, dict) and 'text' in keyword and 'weight' in keyword:
                    weight = keyword['weight']
                    text = keyword['text']
                else:
                    continue
                    
                pill_boxes_html += f'''
                    <span class="pill-box pill-green">
                        <span class="pill-box-left">{weight:.2f}</span><span class="pill-box-right">{html.escape(text)}</span>
                    </span>'''
        
        # Process negative keywords (red pills)
        if 'negative_keywords' in parsed_prompt_data:
            for keyword in parsed_prompt_data['negative_keywords']:
                # Handle both Keyword objects and dict representations
                if hasattr(keyword, 'text') and hasattr(keyword, 'weight'):
                    weight = keyword.weight
                    text = keyword.text
                elif isinstance(keyword, dict) and 'text' in keyword and 'weight' in keyword:
                    weight = keyword['weight']
                    text = keyword['text']
                else:
                    continue
                    
                pill_boxes_html += f'''
                    <span class="pill-box pill-red">
                        <span class="pill-box-left">{weight:.2f}</span><span class="pill-box-right">{html.escape(text)}</span>
                    </span>'''
        
        # Process LoRAs (could add another color variant if needed)
        if 'loras' in parsed_prompt_data:
            for lora in parsed_prompt_data['loras']:
                # Handle both LoRA objects and dict representations
                if hasattr(lora, 'name') and hasattr(lora, 'weight'):
                    weight = lora.weight
                    name = lora.name
                elif isinstance(lora, dict) and 'name' in lora and 'weight' in lora:
                    weight = lora['weight']
                    name = lora['name']
                else:
                    continue
                    
                pill_boxes_html += f'''
                    <span class="pill-box">
                        <span class="pill-box-left">{weight:.2f}</span><span class="pill-box-right">LoRA: {html.escape(name)}</span>
                    </span>'''
        
        pill_boxes_html += '</div>'
        return pill_boxes_html

    def _export_test_results(self) -> None:
        """Export collected data as HTML file."""
        try:
            # Ensure output directory exists
            self.test_output_dir.mkdir(parents=True, exist_ok=True)
            
            # Generate HTML content
            html_content = self._generate_html_report()
            
            # Write to file
            output_file = self.test_output_dir / "mining_test_results.html"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            self.logger.info(f"Test results exported to: {output_file}")
            
        except Exception as e:
            self.logger.error(f"Failed to export test results: {e}")
    
    def _generate_html_report(self) -> str:
        """Generate HTML report showing collected data and database structure."""
        import datetime
        import json
        
        # Count totals by type
        total_files = len(self.collected_data)
        image_files = [f for f in self.collected_data if f['file_type'] == 'image']
        video_files = [f for f in self.collected_data if f['file_type'] == 'video']
        files_with_scores = [f for f in self.collected_data if f['score'] is not None]
        files_with_keywords = [f for f in self.collected_data if f['keywords']]
        
        total_keywords = sum(len(f['keywords']) for f in self.collected_data)
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Data Mining Test Results</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            line-height: 1.6;
            max-width: 1200px;
            margin: 0 auto;
            padding: 20px;
            background: #f8f9fa;
        }}
        .header {{
            background: #343a40;
            color: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
        }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: white;
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .stat-number {{
            font-size: 2em;
            font-weight: bold;
            color: #007bff;
        }}
        .section {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }}
        .section h2 {{
            margin-top: 0;
            color: #343a40;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }}
        .file-list {{
            display: grid;
            gap: 15px;
        }}
        .file-item {{
            border: 1px solid #dee2e6;
            border-radius: 8px;
            padding: 15px;
            background: #f8f9fa;
            display: flex;
            flex-direction: column;
        }}
        .file-content {{
            display: flex;
            gap: 15px;
            align-items: flex-start;
        }}
        .file-thumbnail {{
            flex-shrink: 0;
            width: 120px;
            height: 90px;
            border-radius: 4px;
            overflow: hidden;
            background: #fff;
            border: 1px solid #dee2e6;
            display: flex;
            align-items: center;
            justify-content: center;
        }}
        .file-thumbnail img {{
            max-width: 100%;
            max-height: 100%;
            object-fit: contain;
        }}
        .file-thumbnail.no-thumb {{
            background: #f1f3f4;
            color: #666;
            font-size: 0.8em;
            text-align: center;
        }}
        .file-details {{
            flex: 1;
            min-width: 0;
        }}
        .file-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }}
        .filename {{
            font-weight: bold;
            color: #495057;
        }}
        .file-type {{
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 0.8em;
            font-weight: bold;
        }}
        .file-type.image {{ background: #d1ecf1; color: #0c5460; }}
        .file-type.video {{ background: #d4edda; color: #155724; }}
        .score {{
            padding: 4px 8px;
            border-radius: 4px;
            font-weight: bold;
        }}
        .score.positive {{ background: #d1ecf1; color: #0c5460; }}
        .score.none {{ background: #f8d7da; color: #721c24; }}
        .metadata-table {{
            width: 100%;
            border-collapse: collapse;
            margin-top: 10px;
        }}
        .metadata-table th, .metadata-table td {{
            text-align: left;
            padding: 8px;
            border-bottom: 1px solid #dee2e6;
        }}
        .metadata-table th {{
            background: #e9ecef;
            font-weight: bold;
        }}
        .keywords {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-top: 10px;
        }}
        .keyword {{
            background: #e7f3ff;
            color: #004085;
            padding: 2px 6px;
            border-radius: 12px;
            font-size: 0.8em;
        }}
        .database-structure {{
            background: #f1f3f4;
            padding: 15px;
            border-radius: 8px;
            font-family: 'Courier New', monospace;
            font-size: 0.9em;
            overflow-x: auto;
        }}
        .highlight {{ background: #fff3cd; padding: 2px 4px; border-radius: 3px; }}
        /* pill box styles for parsed prompt data */
        .pill-box {{
            line-height: 25px;
        }}
        .pill-box-left,
        .pill-box-right {{
            border: 1px solid #e6e6e6;
            border-radius: 4px;
            color: #666;
            padding: 2px;
        }}
        .pill-box-left {{
            background-color: #e6e6e6;
            border-bottom-right-radius:0;
            border-top-right-radius:0;
            padding-left: 6px;
            text-align: center;
        }}
        .pill-box-right {{
            background-color: #fff;
            border-bottom-left-radius:0;
            border-top-left-radius:0;
            border-left: 0;
            padding-left: 4px;
            padding-right: 6px;
        }}
        /* red */
        .pill-red .pill-box-left,
        .pill-red .pill-box-right {{
            border-color: #ff704d;
        }}
        .pill-red .pill-box-left {{
            background-color: #ff704d;
            color: #991f00;
        }}
        /* green */
        .pill-green .pill-box-left,
        .pill-green .pill-box-right {{
            border-color: #70db70;
        }}
        .pill-green .pill-box-left {{
            background-color: #70db70;
            color: #ebfaeb;
        }}
        /* parsed prompt data display */
        .parsed-prompt-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            margin-top: 5px;
        }}
        .raw-data-button {{
            background: #6c757d;
            color: white;
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8em;
            margin-right: 10px;
        }}
        .raw-data-button:hover {{
            background: #5a6268;
        }}
        /* overlay styles */
        .overlay {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.7);
            z-index: 1000;
        }}
        .overlay-content {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            background: white;
            padding: 20px;
            border-radius: 8px;
            max-width: 80%;
            max-height: 80%;
            overflow: auto;
        }}
        .overlay-close {{
            float: right;
            font-size: 24px;
            cursor: pointer;
            background: none;
            border: none;
        }}
        .raw-json-display {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 15px;
            font-family: 'Courier New', monospace;
            white-space: pre-wrap;
            max-height: 400px;
            overflow: auto;
        }}
        .raw-data-modal {{
            display: none;
            position: fixed;
            z-index: 1000;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background-color: rgba(0,0,0,0.5);
        }}
        .raw-data-content {{
            background-color: white;
            margin: 5% auto;
            padding: 20px;
            border-radius: 8px;
            width: 80%;
            max-width: 800px;
            max-height: 80%;
            overflow: auto;
        }}
        .raw-data-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 15px;
            border-bottom: 2px solid #007bff;
            padding-bottom: 10px;
        }}
        .raw-data-close {{
            background: #dc3545;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
        }}
        .raw-data-close:hover {{
            background: #c82333;
        }}
        .raw-data-json {{
            background: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 4px;
            padding: 15px;
            font-family: 'Courier New', monospace;
            white-space: pre-wrap;
            max-height: 400px;
            overflow: auto;
        }}
        .config-display {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: 8px;
        }}
        .config-item {{
            background: #e7f3ff;
            color: #004085;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 0.9em;
            white-space: nowrap;
        }}
        .raw-data-button {{
            background: #6c757d;
            color: white;
            border: none;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8em;
            font-family: monospace;
        }}
        .raw-data-button:hover {{
            background: #5a6268;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🔍 Data Mining Test Results</h1>
        <p>Generated on {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <p>Source Directory: <code>{self.settings.dir}</code></p>
        <p>File Pattern: <code>{self.settings.pattern}</code></p>
    </div>

    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-number">{total_files}</div>
            <div>Total Files</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{len(image_files)}</div>
            <div>Image Files</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{len(video_files)}</div>
            <div>Video Files</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{len(files_with_scores)}</div>
            <div>Files with Scores</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{total_keywords}</div>
            <div>Keywords Generated</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{len(files_with_keywords)}</div>
            <div>Files with Keywords</div>
        </div>
    </div>

    <div class="section">
        <h2>📂 File Details</h2>
        <div class="file-list">
"""
        
        for file_data in self.collected_data:
            # Format file size
            size_mb = file_data['file_size'] / (1024 * 1024) if file_data['file_size'] else 0
            
            # Score display
            score_html = ""
            if file_data['score'] is not None:
                score_html = f'<span class="score positive">Score: {file_data["score"]}</span>'
            else:
                score_html = '<span class="score none">No Score</span>'
            
            # Metadata table
            metadata_html = ""
            if file_data['metadata'] or file_data.get('media_file_id') or file_data.get('phash'):
                metadata_html = "<table class='metadata-table'><thead><tr><th>Property</th><th>Value</th></tr></thead><tbody>"

                # 1) Hash information first (added in the id-hashes branch)
                if file_data.get('media_file_id'):
                    metadata_html += (
                        f"<tr><td>Media File ID</td><td><code>{file_data['media_file_id']}</code></td></tr>"
                    )
                if file_data.get('phash'):
                    metadata_html += (
                        f"<tr><td>Perceptual Hash</td><td><code>{file_data['phash']}</code></td></tr>"
                    )

                # 2) Enhanced metadata display with organized sections
                if file_data['metadata']:
                    # First show basic AI generation parameters prominently
                    ai_params = [
                        ('steps', 'Steps'),
                        ('sampler', 'Sampler'),
                        ('schedule_type', 'Schedule Type'),
                        ('cfg_scale', 'CFG Scale'),
                        ('seed', 'Seed'),
                        ('size', 'Size'),
                        ('model_name', 'Model Name'),
                        ('model_hash', 'Model Hash'),
                        ('denoising_strength', 'Denoising Strength'),
                    ]
                    
                    # Hires Fix parameters
                    hires_params = [
                        ('hires_module_1', 'Hires Module 1'),
                        ('hires_cfg_scale', 'Hires CFG Scale'),
                        ('hires_upscale', 'Hires Upscale'),
                        ('hires_upscaler', 'Hires Upscaler'),
                    ]
                    
                    # Dynamic Thresholding parameters
                    dynthres_params = [
                        ('dynthres_enabled', 'DynThres Enabled'),
                        ('dynthres_mimic_scale', 'DynThres Mimic Scale'),
                        ('dynthres_threshold_percentile', 'DynThres Threshold Percentile'),
                        ('dynthres_mimic_mode', 'DynThres Mimic Mode'),
                        ('dynthres_mimic_scale_min', 'DynThres Mimic Scale Min'),
                        ('dynthres_cfg_mode', 'DynThres CFG Mode'),
                        ('dynthres_cfg_scale_min', 'DynThres CFG Scale Min'),
                        ('dynthres_sched_val', 'DynThres Sched Val'),
                        ('dynthres_separate_feature_channels', 'DynThres Separate Feature Channels'),
                        ('dynthres_scaling_startpoint', 'DynThres Scaling Startpoint'),
                        ('dynthres_variability_measure', 'DynThres Variability Measure'),
                        ('dynthres_interpolate_phi', 'DynThres Interpolate Phi'),
                    ]
                    
                    # Version and hash info
                    version_params = [
                        ('version', 'Version'),
                        ('lora_hashes', 'LoRA Hashes'),
                    ]
                    
                    # Display AI generation parameters first
                    metadata_html += '<tr><td colspan="2" style="background-color: #e7f3ff; font-weight: bold;">🎨 AI Generation Parameters</td></tr>'
                    for key, display_name in ai_params:
                        value = file_data['metadata'].get(key)
                        if value is not None:
                            metadata_html += f"<tr><td>{display_name}</td><td><strong>{value}</strong></td></tr>"
                    
                    # Display Hires Fix parameters if any exist
                    hires_config = file_data['metadata'].get('hires_config')
                    if hires_config:
                        metadata_html += '<tr><td colspan="2" style="background-color: #f0f8e7; font-weight: bold;">🔍 Hires Fix Parameters</td></tr>'
                        metadata_html += self._format_json_config_with_button('Hires Fix', hires_config)
                    else:
                        # Fallback to individual parameters for backward compatibility
                        hires_values = [file_data['metadata'].get(key) for key, _ in hires_params]
                        if any(v is not None for v in hires_values):
                            metadata_html += '<tr><td colspan="2" style="background-color: #f0f8e7; font-weight: bold;">🔍 Hires Fix Parameters</td></tr>'
                            for key, display_name in hires_params:
                                value = file_data['metadata'].get(key)
                                if value is not None:
                                    metadata_html += f"<tr><td>{display_name}</td><td><strong>{value}</strong></td></tr>"
                    
                    # Display Dynamic Thresholding parameters if any exist
                    dynthres_config = file_data['metadata'].get('dynthres_config')
                    if dynthres_config:
                        metadata_html += '<tr><td colspan="2" style="background-color: #fff2e7; font-weight: bold;">⚡ Dynamic Thresholding Parameters</td></tr>'
                        metadata_html += self._format_json_config_with_button('Dynamic Thresholding', dynthres_config)
                    else:
                        # Fallback to individual parameters for backward compatibility
                        dynthres_values = [file_data['metadata'].get(key) for key, _ in dynthres_params]
                        if any(v is not None for v in dynthres_values):
                            metadata_html += '<tr><td colspan="2" style="background-color: #fff2e7; font-weight: bold;">⚡ Dynamic Thresholding Parameters</td></tr>'
                            for key, display_name in dynthres_params:
                                value = file_data['metadata'].get(key)
                                if value is not None:
                                    metadata_html += f"<tr><td>{display_name}</td><td><strong>{value}</strong></td></tr>"
                    
                    # Display version and hash info
                    version_values = [file_data['metadata'].get(key) for key, _ in version_params]
                    if any(v is not None for v in version_values):
                        metadata_html += '<tr><td colspan="2" style="background-color: #f8f0ff; font-weight: bold;">📋 Version & Hash Info</td></tr>'
                        for key, display_name in version_params:
                            value = file_data['metadata'].get(key)
                            if value is not None:
                                # Truncate long hashes for display
                                display_value = str(value)
                                if len(display_value) > 100:
                                    display_value = display_value[:100] + "..."
                                metadata_html += f"<tr><td>{display_name}</td><td><strong>{display_value}</strong></td></tr>"
                    
                    # Display other metadata (existing functionality preserved)
                    other_metadata = []
                    all_param_keys = set([key for key, _ in ai_params + hires_params + dynthres_params + version_params])
                    
                    for key, value in file_data['metadata'].items():
                        if (key in ['extracted_keywords', 'error'] or 
                            value is None or 
                            key in all_param_keys):
                            continue
                        other_metadata.append((key, value))
                    
                    if other_metadata:
                        metadata_html += '<tr><td colspan="2" style="background-color: #f0f0f0; font-weight: bold;">📊 Additional Metadata</td></tr>'
                        for key, value in other_metadata:
                            # Friendly formatting (existing logic preserved)
                            display_value = value
                            if key == 'file_size':
                                display_value = f"{size_mb:.2f} MB"
                            elif key == 'file_modified_at':
                                try:
                                    import datetime as _dt
                                    display_value = _dt.datetime.fromtimestamp(value).strftime('%Y-%m-%d %H:%M:%S')
                                except Exception:
                                    display_value = value
                            elif key == 'parsed_prompt_data' and isinstance(value, dict):
                                # Special: show pill boxes using helper, not JSON
                                file_index = self.collected_data.index(file_data)
                                display_value = self._format_parsed_prompt_data(value, file_index)
                            elif isinstance(value, dict):
                                # Make nested objects JSON-serializable and pretty
                                import json as _json
                                json_safe_value = self._make_json_serializable(value)
                                display_value = _json.dumps(json_safe_value, indent=2)

                            metadata_html += (
                                f"<tr><td>{key.replace('_', ' ').title()}</td><td>{str(display_value)}</td></tr>"
                            )

                metadata_html += "</tbody></table>"

            
            # Keywords
            keywords_html = ""
            if file_data['keywords']:
                keywords_html = '<div class="keywords">'
                for keyword in file_data['keywords']:
                    keywords_html += f'<span class="keyword">{keyword}</span>'
                keywords_html += '</div>'
            
            # Thumbnail
            thumbnail_html = ""
            if file_data.get('thumbnail', {}).get('base64'):
                thumbnail_html = f'<div class="file-thumbnail"><img src="data:image/jpeg;base64,{file_data["thumbnail"]["base64"]}" alt="Thumbnail for {file_data["filename"]}"></div>'
            else:
                thumbnail_html = '<div class="file-thumbnail no-thumb">No Preview</div>'
            
            html += f"""
            <div class="file-item">
                <div class="file-header">
                    <span class="filename">{file_data['filename']}</span>
                    <div>
                        <span class="file-type {file_data['file_type']}">{file_data['file_type'].upper()}</span>
                        {score_html}
                    </div>
                </div>
                <div class="file-content">
                    {thumbnail_html}
                    <div class="file-details">
                        {f'<div style="color: red; font-weight: bold;">Error: {file_data["error"]}</div>' if file_data['error'] else ''}
                        {metadata_html}
                        {keywords_html}
                    </div>
                </div>
            </div>
"""
        
        html += f"""
        </div>
    </div>

    <div class="section">
        <h2>🗃️ Database Structure Preview</h2>
        <p>This shows how the extracted data would be organized in the database tables:</p>
        
        <div class="database-structure">
<strong>media_files</strong> table would contain:
┌────────────────────────────────────────────────────────────────────────────────────────────────┐
│ id │ filename │ directory │ file_path │ score │ file_type │ media_file_id │ phash │
├────────────────────────────────────────────────────────────────────────────────────────────────┤"""
        
        for i, file_data in enumerate(self.collected_data[:5], 1):
            # Truncate hash values for display
            media_file_id_display = (file_data.get('media_file_id', 'NULL')[:16] + '...') if file_data.get('media_file_id') else 'NULL'
            phash_display = file_data.get('phash', 'NULL') or 'NULL'
            
            html += f"""
│ {i:2d} │ {file_data['filename'][:10]:<10} │ {str(self.settings.dir)[-9:]:<9} │ {file_data['file_path'][-15:]:<15} │ {str(file_data['score'] or 'NULL'):<5} │ {file_data['file_type']:<9} │ {media_file_id_display:<19} │ {phash_display:<16} │"""
        
        if len(self.collected_data) > 5:
            html += f"""
│ .. │ ... ({len(self.collected_data) - 5} more rows) ... │"""
        
        html += """
└────────────────────────────────────────────────────────────────────────────────────────────────┘

<strong>media_metadata</strong> table would contain technical metadata with enhanced PNG parameters:
┌────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ media_file_id │ width │ height │ model_name │ steps │ sampler │ cfg_scale │ seed │ size │ model_hash │ version │ dynthres_enabled │ ... │
├────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┤"""
        
        for i, file_data in enumerate(self.collected_data[:5], 1):
            metadata = file_data.get('metadata', {})
            width = metadata.get('width', 'NULL')
            height = metadata.get('height', 'NULL')
            model = str(metadata.get('model_name', 'NULL'))[:12] if metadata.get('model_name') else 'NULL'
            steps = metadata.get('steps', 'NULL')
            sampler = str(metadata.get('sampler', 'NULL'))[:10] if metadata.get('sampler') else 'NULL'
            cfg_scale = metadata.get('cfg_scale', 'NULL')
            seed = str(metadata.get('seed', 'NULL'))[:8] if metadata.get('seed') else 'NULL'
            size = str(metadata.get('size', 'NULL'))[:8] if metadata.get('size') else 'NULL'
            model_hash = str(metadata.get('model_hash', 'NULL'))[:8] if metadata.get('model_hash') else 'NULL'
            version = str(metadata.get('version', 'NULL'))[:8] if metadata.get('version') else 'NULL'
            dynthres = metadata.get('dynthres_enabled', 'NULL')
            
            html += f"""
│ {i:13d} │ {str(width):<5} │ {str(height):<6} │ {model:<12} │ {str(steps):<5} │ {sampler:<10} │ {str(cfg_scale):<9} │ {seed:<8} │ {size:<8} │ {model_hash:<10} │ {version:<8} │ {str(dynthres):<16} │ ... │"""
        
        if len(self.collected_data) > 5:
            html += f"""
│ ... ({len(self.collected_data) - 5} more rows with {24} new PNG parameter columns) ... │"""
        
        html += f"""
└────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────────┘

<strong>New PNG Parameter Columns Added (24 total):</strong>
• Basic AI Generation: model_hash, size, schedule_type, denoising_strength
• Hires Fix: hires_module_1, hires_cfg_scale, hires_upscale, hires_upscaler  
• Dynamic Thresholding: dynthres_enabled, dynthres_mimic_scale, dynthres_threshold_percentile,
  dynthres_mimic_mode, dynthres_mimic_scale_min, dynthres_cfg_mode, dynthres_cfg_scale_min,
  dynthres_sched_val, dynthres_separate_feature_channels, dynthres_scaling_startpoint,
  dynthres_variability_measure, dynthres_interpolate_phi
• Version Info: version, lora_hashes

<strong>media_keywords</strong> table would contain {total_keywords} keyword entries:
┌─────────────────────────────────────────────────────────────────┐
│ media_file_id │ keyword │ keyword_type │ confidence │ source │
├─────────────────────────────────────────────────────────────────┤"""
        
        keyword_count = 0
        for i, file_data in enumerate(self.collected_data, 1):
            for keyword in file_data.get('keywords', [])[:2]:  # Show first 2 keywords per file
                keyword_count += 1
                if keyword_count <= 5:
                    html += f"""
│ {i:13d} │ {keyword[:10]:<10} │ auto         │ 1.0        │ metadata │"""
        
        if total_keywords > 5:
            html += f"""
│ ... ({total_keywords - 5} more keyword entries) ... │"""
        
        html += """
└─────────────────────────────────────────────────────────────────┘
        </div>
        
        <p><span class="highlight">💡 Tip:</span> Run with <code>--enable-database</code> to actually store this data in the database for searching and management via the web interface.</p>
    </div>

    <div class="section">
        <h2>🚀 Next Steps</h2>
        <ol>
            <li><strong>Review the extracted data above</strong> to ensure it meets your expectations</li>
            <li><strong>Run with database enabled:</strong> <code>python mine_data.py {self.settings.dir} --enable-database</code></li>
            <li><strong>Start the web interface:</strong> <code>python run.py --dir {self.settings.dir} --enable-database</code></li>
            <li><strong>Search and manage your media</strong> via the web interface at <code>http://localhost:7862</code></li>
        </ol>
    </div>

    <!-- Overlay for raw data display -->
    <div id="rawDataOverlay" class="overlay">
        <div class="overlay-content">
            <button class="overlay-close" onclick="closeRawDataOverlay()">&times;</button>
            <h3>Raw Parsed Prompt Data</h3>
            <div id="rawJsonDisplay" class="raw-json-display"></div>
        </div>
    </div>

    <script>
        function showRawData(rawData) {
            document.getElementById('rawJsonDisplay').textContent = rawData;
            document.getElementById('rawDataOverlay').style.display = 'block';
        }
        
        function closeRawDataOverlay() {
            document.getElementById('rawDataOverlay').style.display = 'none';
        }
        
        // Close overlay when clicking outside of it
        document.getElementById('rawDataOverlay').addEventListener('click', function(e) {
            if (e.target === this) {
                closeRawDataOverlay();
            }
        });
        
        // Close overlay with escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeRawDataOverlay();
            }
        });
        
        // New function for JSON config modal
        function showRawData(jsonData, configName) {
            const modal = document.getElementById('rawDataModal');
            const title = document.getElementById('rawDataTitle');
            const content = document.getElementById('rawDataJson');
            
            title.textContent = configName + ' (Raw JSON for Database)';
            content.textContent = jsonData;
            modal.style.display = 'block';
        }
        
        function closeRawDataModal() {
            document.getElementById('rawDataModal').style.display = 'none';
        }
        
        // Close modal when clicking outside
        window.onclick = function(event) {
            const modal = document.getElementById('rawDataModal');
            if (event.target === modal) {
                closeRawDataModal();
            }
        }
        
        // Close modal with Escape key
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                closeRawDataModal();
            }
        });
    </script>
    
    <!-- Raw Data Modal -->
    <div id="rawDataModal" class="raw-data-modal">
        <div class="raw-data-content">
            <div class="raw-data-header">
                <h3 id="rawDataTitle">Raw JSON Data</h3>
                <button class="raw-data-close" onclick="closeRawDataModal()">Close</button>
            </div>
            <div id="rawDataJson" class="raw-data-json"></div>
        </div>
    </div>

</body>
</html>"""
        
        return html

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
  python mine_data.py /media/archive1 --dry-run --test-output-dir /tmp/results
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
    
    parser.add_argument(
        "--test-output-dir",
        type=Path,
        help="Export collected data as HTML file to this directory (for dry run mode)"
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
    
    # Validate test output directory if specified
    if args.test_output_dir and not args.dry_run and args.enable_database:
        logger.error("--test-output-dir can only be used in dry-run mode (without --enable-database)")
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
        if args.test_output_dir:
            logger.info(f"Test results will be exported to: {args.test_output_dir}")
    
    # Run the data mining
    try:
        start_time = time.time()
        miner = DataMiner(settings, logger, args.test_output_dir)
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