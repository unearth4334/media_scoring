"""Media file database model and generation parameters."""

import sqlite3
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class GenerationParameters:
    """Parameters extracted from AI-generated image metadata."""
    
    # Core generation parameters
    steps: Optional[int] = None
    sampler: Optional[str] = None
    schedule_type: Optional[str] = None
    cfg_scale: Optional[float] = None
    seed: Optional[int] = None
    size: Optional[str] = None  # e.g., "512x768" - might differ from actual image dimensions
    
    # Model information
    model_name: Optional[str] = None
    model_hash: Optional[str] = None
    
    # Hires/upscaling parameters
    denoising_strength: Optional[float] = None
    hires_module_1: Optional[str] = None
    hires_cfg_scale: Optional[float] = None
    hires_upscale: Optional[float] = None
    hires_upscaler: Optional[str] = None
    
    # Dynamic thresholding parameters
    dynthres_enabled: Optional[bool] = None
    dynthres_mimic_scale: Optional[float] = None
    dynthres_threshold_percentile: Optional[float] = None
    dynthres_mimic_mode: Optional[str] = None
    dynthres_mimic_scale_min: Optional[float] = None
    dynthres_cfg_mode: Optional[str] = None
    dynthres_cfg_scale_min: Optional[float] = None
    dynthres_sched_val: Optional[float] = None
    dynthres_separate_feature_channels: Optional[bool] = None
    dynthres_scaling_startpoint: Optional[float] = None
    dynthres_variability_measure: Optional[float] = None
    dynthres_interpolate_phi: Optional[float] = None
    
    # Version info
    version: Optional[str] = None
    
    # Store raw parameters text for reference
    raw_parameters: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON storage."""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GenerationParameters':
        """Create from dictionary loaded from JSON."""
        return cls(**data)


@dataclass
class MediaFile:
    """Media file with metadata and generation parameters."""
    
    # Primary identifiers
    id: Optional[int] = None
    filename: str = ""
    filepath: str = ""  # Relative to media directory
    
    # File metadata
    file_size: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    created_date: Optional[datetime] = None
    modified_date: Optional[datetime] = None
    
    # Score and user data
    score: Optional[int] = None
    
    # Generation parameters
    generation_params: Optional[GenerationParameters] = None
    
    # Timestamps
    scanned_date: Optional[datetime] = None
    updated_date: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API responses."""
        result = asdict(self)
        if self.generation_params:
            result['generation_params'] = self.generation_params.to_dict()
        return result


class MediaFileDatabase:
    """Database manager for media files."""
    
    def __init__(self, db_path: Path):
        """Initialize database connection."""
        self.db_path = db_path
        self._init_database()
    
    def _init_database(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS media_files (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    filename TEXT NOT NULL,
                    filepath TEXT NOT NULL,
                    file_size INTEGER,
                    width INTEGER,
                    height INTEGER,
                    created_date TEXT,
                    modified_date TEXT,
                    score INTEGER,
                    generation_params TEXT,  -- JSON blob for generation parameters
                    scanned_date TEXT,
                    updated_date TEXT,
                    UNIQUE(filepath)  -- Ensure unique file paths
                )
            ''')
            
            # Create indexes for common queries
            conn.execute('CREATE INDEX IF NOT EXISTS idx_filename ON media_files(filename)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_filepath ON media_files(filepath)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_score ON media_files(score)')
            conn.execute('CREATE INDEX IF NOT EXISTS idx_scanned_date ON media_files(scanned_date)')
    
    def upsert_media_file(self, media_file: MediaFile) -> int:
        """Insert or update a media file. Returns the file ID."""
        now = datetime.now().isoformat()
        
        generation_params_json = None
        if media_file.generation_params:
            generation_params_json = json.dumps(media_file.generation_params.to_dict())
        
        with sqlite3.connect(self.db_path) as conn:
            # Try to update existing record first
            cursor = conn.execute('''
                UPDATE media_files SET
                    filename = ?, file_size = ?, width = ?, height = ?,
                    created_date = ?, modified_date = ?, score = ?,
                    generation_params = ?, updated_date = ?
                WHERE filepath = ?
            ''', (
                media_file.filename, media_file.file_size, media_file.width, media_file.height,
                media_file.created_date.isoformat() if media_file.created_date else None,
                media_file.modified_date.isoformat() if media_file.modified_date else None,
                media_file.score, generation_params_json, now, media_file.filepath
            ))
            
            if cursor.rowcount == 0:
                # No existing record, insert new one
                cursor = conn.execute('''
                    INSERT INTO media_files (
                        filename, filepath, file_size, width, height,
                        created_date, modified_date, score, generation_params,
                        scanned_date, updated_date
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    media_file.filename, media_file.filepath, media_file.file_size,
                    media_file.width, media_file.height,
                    media_file.created_date.isoformat() if media_file.created_date else None,
                    media_file.modified_date.isoformat() if media_file.modified_date else None,
                    media_file.score, generation_params_json, now, now
                ))
                return cursor.lastrowid
            else:
                # Get the existing ID
                cursor = conn.execute('SELECT id FROM media_files WHERE filepath = ?', (media_file.filepath,))
                row = cursor.fetchone()
                return row[0] if row else None
    
    def get_media_file(self, filepath: str) -> Optional[MediaFile]:
        """Get a media file by filepath."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, filename, filepath, file_size, width, height,
                       created_date, modified_date, score, generation_params,
                       scanned_date, updated_date
                FROM media_files WHERE filepath = ?
            ''', (filepath,))
            
            row = cursor.fetchone()
            if not row:
                return None
            
            generation_params = None
            if row[9]:  # generation_params column
                try:
                    params_dict = json.loads(row[9])
                    generation_params = GenerationParameters.from_dict(params_dict)
                except (json.JSONDecodeError, TypeError):
                    pass
            
            return MediaFile(
                id=row[0],
                filename=row[1],
                filepath=row[2],
                file_size=row[3],
                width=row[4],
                height=row[5],
                created_date=datetime.fromisoformat(row[6]) if row[6] else None,
                modified_date=datetime.fromisoformat(row[7]) if row[7] else None,
                score=row[8],
                generation_params=generation_params,
                scanned_date=datetime.fromisoformat(row[10]) if row[10] else None,
                updated_date=datetime.fromisoformat(row[11]) if row[11] else None
            )
    
    def get_all_media_files(self) -> List[MediaFile]:
        """Get all media files."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT id, filename, filepath, file_size, width, height,
                       created_date, modified_date, score, generation_params,
                       scanned_date, updated_date
                FROM media_files ORDER BY filepath
            ''')
            
            files = []
            for row in cursor.fetchall():
                generation_params = None
                if row[9]:  # generation_params column
                    try:
                        params_dict = json.loads(row[9])
                        generation_params = GenerationParameters.from_dict(params_dict)
                    except (json.JSONDecodeError, TypeError):
                        pass
                
                files.append(MediaFile(
                    id=row[0],
                    filename=row[1],
                    filepath=row[2],
                    file_size=row[3],
                    width=row[4],
                    height=row[5],
                    created_date=datetime.fromisoformat(row[6]) if row[6] else None,
                    modified_date=datetime.fromisoformat(row[7]) if row[7] else None,
                    score=row[8],
                    generation_params=generation_params,
                    scanned_date=datetime.fromisoformat(row[10]) if row[10] else None,
                    updated_date=datetime.fromisoformat(row[11]) if row[11] else None
                ))
            
            return files
    
    def update_score(self, filepath: str, score: int) -> bool:
        """Update the score for a media file."""
        now = datetime.now().isoformat()
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                UPDATE media_files SET score = ?, updated_date = ?
                WHERE filepath = ?
            ''', (score, now, filepath))
            
            return cursor.rowcount > 0
    
    def delete_media_file(self, filepath: str) -> bool:
        """Delete a media file record."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('DELETE FROM media_files WHERE filepath = ?', (filepath,))
            return cursor.rowcount > 0
    
    def cleanup_missing_files(self, existing_filepaths: List[str]) -> int:
        """Remove records for files that no longer exist."""
        if not existing_filepaths:
            return 0
        
        placeholders = ','.join(['?'] * len(existing_filepaths))
        
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(f'''
                DELETE FROM media_files WHERE filepath NOT IN ({placeholders})
            ''', existing_filepaths)
            
            return cursor.rowcount