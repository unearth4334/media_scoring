"""Database service layer for media scoring application."""

import json
import logging
from pathlib import Path
from typing import List, Dict, Optional, Union, Tuple
from datetime import datetime

from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, desc, asc

from .engine import get_session
from .models import MediaFile, MediaMetadata, MediaKeyword, MediaThumbnail

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service class for database operations."""
    
    def __init__(self):
        self.session: Optional[Session] = None
    
    def __enter__(self):
        self.session = get_session()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type:
                self.session.rollback()
            else:
                self.session.commit()
            self.session.close()
    
    # Media File Operations
    
    def get_or_create_media_file(self, file_path: Path) -> MediaFile:
        """Get existing media file or create new one."""
        file_path_str = str(file_path.resolve())
        
        # Try to find existing file
        media_file = self.session.query(MediaFile).filter(
            MediaFile.file_path == file_path_str
        ).first()
        
        if media_file:
            # Update last accessed
            media_file.last_accessed = datetime.utcnow()
            return media_file
        
        # Create new file record
        file_stat = file_path.stat()
        media_file = MediaFile(
            filename=file_path.name,
            directory=str(file_path.parent),
            file_path=file_path_str,
            file_size=file_stat.st_size,
            file_type=self._get_file_type(file_path),
            extension=file_path.suffix.lower(),
            last_accessed=datetime.utcnow()
        )
        
        self.session.add(media_file)
        self.session.flush()  # Get the ID
        
        logger.info(f"Created new media file record: {file_path.name}")
        return media_file
    
    def update_media_file_score(self, file_path: Path, score: int) -> bool:
        """Update the score for a media file."""
        media_file = self.get_or_create_media_file(file_path)
        media_file.score = score
        media_file.updated_at = datetime.utcnow()
        return True
    
    def get_media_file_score(self, file_path: Path) -> Optional[int]:
        """Get the score for a media file."""
        file_path_str = str(file_path.resolve())
        media_file = self.session.query(MediaFile).filter(
            MediaFile.file_path == file_path_str
        ).first()
        return media_file.score if media_file else None
    
    def get_media_files_by_directory(self, directory: Path) -> List[MediaFile]:
        """Get all media files in a directory."""
        return self.session.query(MediaFile).filter(
            MediaFile.directory == str(directory)
        ).order_by(MediaFile.filename).all()
    
    def get_media_files_by_score(self, min_score: Optional[int] = None, 
                                 max_score: Optional[int] = None) -> List[MediaFile]:
        """Get media files filtered by score range."""
        query = self.session.query(MediaFile)
        
        if min_score is not None:
            query = query.filter(MediaFile.score >= min_score)
        if max_score is not None:
            query = query.filter(MediaFile.score <= max_score)
            
        return query.order_by(desc(MediaFile.score), MediaFile.filename).all()
    
    # Metadata Operations
    
    def store_media_metadata(self, file_path: Path, metadata: Dict) -> MediaMetadata:
        """Store or update metadata for a media file."""
        media_file = self.get_or_create_media_file(file_path)
        
        # Check if metadata already exists
        existing_metadata = self.session.query(MediaMetadata).filter(
            MediaMetadata.media_file_id == media_file.id
        ).first()
        
        if existing_metadata:
            # Update existing metadata
            metadata_obj = existing_metadata
        else:
            # Create new metadata
            metadata_obj = MediaMetadata(media_file_id=media_file.id)
            self.session.add(metadata_obj)
        
        # Update fields from metadata dict
        for key, value in metadata.items():
            if hasattr(metadata_obj, key) and key not in ['png_text', 'workflow_data', 'parsed_prompt_data']:
                setattr(metadata_obj, key, value)
        
        # Store PNG text as JSON if present
        if 'png_text' in metadata and metadata['png_text']:
            metadata_obj.png_text = json.dumps(metadata['png_text'])
        
        # Store workflow data as JSON if present  
        if 'workflow_data' in metadata and metadata['workflow_data']:
            metadata_obj.workflow_data = json.dumps(metadata['workflow_data'])
        
        # Store parsed prompt data if present
        if 'parsed_prompt_data' in metadata:
            prompt_data = metadata['parsed_prompt_data']
            
            # Convert keyword objects to JSON-serializable format
            if 'positive_keywords' in prompt_data:
                metadata_obj.positive_prompt_keywords = [
                    {'text': kw.text, 'weight': kw.weight} 
                    for kw in prompt_data['positive_keywords']
                ]
            
            if 'negative_keywords' in prompt_data:
                metadata_obj.negative_prompt_keywords = [
                    {'text': kw.text, 'weight': kw.weight} 
                    for kw in prompt_data['negative_keywords']
                ]
            
            if 'loras' in prompt_data:
                metadata_obj.loras = [
                    {'name': lora.name, 'weight': lora.weight} 
                    for lora in prompt_data['loras']
                ]
            
        metadata_obj.metadata_extracted_at = datetime.utcnow()
        
        # Update file modification time
        try:
            file_stat = file_path.stat()
            metadata_obj.file_modified_at = datetime.fromtimestamp(file_stat.st_mtime)
        except OSError:
            pass
            
        return metadata_obj
    
    def get_media_metadata(self, file_path: Path) -> Optional[MediaMetadata]:
        """Get metadata for a media file."""
        file_path_str = str(file_path.resolve())
        
        return self.session.query(MediaMetadata).join(MediaFile).filter(
            MediaFile.file_path == file_path_str
        ).first()
    
    # Keyword Operations
    
    def add_keywords(self, file_path: Path, keywords: List[str], 
                     keyword_type: str = 'user', source: str = 'manual') -> List[MediaKeyword]:
        """Add keywords to a media file."""
        media_file = self.get_or_create_media_file(file_path)
        
        keyword_objects = []
        for keyword in keywords:
            keyword = keyword.strip().lower()
            if not keyword:
                continue
                
            # Check if keyword already exists
            existing = self.session.query(MediaKeyword).filter(
                MediaKeyword.media_file_id == media_file.id,
                MediaKeyword.keyword == keyword,
                MediaKeyword.keyword_type == keyword_type
            ).first()
            
            if not existing:
                keyword_obj = MediaKeyword(
                    media_file_id=media_file.id,
                    keyword=keyword,
                    keyword_type=keyword_type,
                    source=source
                )
                self.session.add(keyword_obj)
                keyword_objects.append(keyword_obj)
        
        return keyword_objects
    
    def search_by_keywords(self, keywords: List[str], 
                          match_all: bool = False) -> List[MediaFile]:
        """Search media files by keywords."""
        if not keywords:
            return []
        
        # Normalize keywords
        keywords = [k.strip().lower() for k in keywords if k.strip()]
        
        query = self.session.query(MediaFile).join(MediaKeyword)
        
        if match_all:
            # All keywords must match (AND)
            for keyword in keywords:
                query = query.filter(
                    MediaFile.keywords.any(MediaKeyword.keyword.contains(keyword))
                )
        else:
            # Any keyword can match (OR)
            keyword_filters = [
                MediaKeyword.keyword.contains(keyword) for keyword in keywords
            ]
            query = query.filter(or_(*keyword_filters))
        
        return query.distinct().order_by(desc(MediaFile.score), MediaFile.filename).all()
    
    def get_keywords_for_file(self, file_path: Path) -> List[MediaKeyword]:
        """Get all keywords for a media file."""
        file_path_str = str(file_path.resolve())
        
        return self.session.query(MediaKeyword).join(MediaFile).filter(
            MediaFile.file_path == file_path_str
        ).order_by(MediaKeyword.keyword_type, MediaKeyword.keyword).all()
    
    def get_all_keywords(self, keyword_type: Optional[str] = None) -> List[str]:
        """Get all unique keywords, optionally filtered by type."""
        query = self.session.query(MediaKeyword.keyword).distinct()
        
        if keyword_type:
            query = query.filter(MediaKeyword.keyword_type == keyword_type)
        
        return [row[0] for row in query.order_by(MediaKeyword.keyword).all()]
    
    # Thumbnail Operations
    
    def store_thumbnail(self, file_path: Path, size: str, 
                       thumbnail_data: Optional[str] = None,
                       thumbnail_file_path: Optional[Path] = None,
                       mime_type: str = 'image/jpeg') -> MediaThumbnail:
        """Store thumbnail data for a media file."""
        media_file = self.get_or_create_media_file(file_path)
        
        # Check if thumbnail already exists
        existing = self.session.query(MediaThumbnail).filter(
            MediaThumbnail.media_file_id == media_file.id,
            MediaThumbnail.thumbnail_size == size
        ).first()
        
        if existing:
            thumbnail = existing
        else:
            thumbnail = MediaThumbnail(
                media_file_id=media_file.id,
                thumbnail_size=size
            )
            self.session.add(thumbnail)
        
        # Update thumbnail data
        thumbnail.thumbnail_data = thumbnail_data
        thumbnail.file_path = str(thumbnail_file_path) if thumbnail_file_path else None
        thumbnail.mime_type = mime_type
        thumbnail.created_at = datetime.utcnow()
        
        return thumbnail
    
    def get_thumbnail(self, file_path: Path, size: str) -> Optional[MediaThumbnail]:
        """Get thumbnail for a media file."""
        file_path_str = str(file_path.resolve())
        
        return self.session.query(MediaThumbnail).join(MediaFile).filter(
            MediaFile.file_path == file_path_str,
            MediaThumbnail.thumbnail_size == size
        ).first()
    
    # Utility Methods
    
    def _get_file_type(self, file_path: Path) -> str:
        """Determine file type based on extension."""
        ext = file_path.suffix.lower()
        if ext in {'.mp4', '.avi', '.mov', '.mkv'}:
            return 'video'
        elif ext in {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}:
            return 'image'
        else:
            return 'unknown'
    
    def get_stats(self) -> Dict:
        """Get database statistics."""
        return {
            'total_files': self.session.query(MediaFile).count(),
            'total_videos': self.session.query(MediaFile).filter(MediaFile.file_type == 'video').count(),
            'total_images': self.session.query(MediaFile).filter(MediaFile.file_type == 'image').count(),
            'files_with_metadata': self.session.query(MediaFile).join(MediaMetadata).count(),
            'total_keywords': self.session.query(MediaKeyword).count(),
            'unique_keywords': self.session.query(MediaKeyword.keyword).distinct().count(),
            'files_with_thumbnails': self.session.query(MediaFile).join(MediaThumbnail).count(),
        }
    
    def cleanup_orphaned_records(self) -> Dict[str, int]:
        """Clean up orphaned records and return count of cleaned items."""
        counts = {}
        
        # Clean up metadata for non-existent files
        orphaned_metadata = self.session.query(MediaMetadata).join(MediaFile).filter(
            ~MediaFile.file_path.in_(
                self.session.query(MediaFile.file_path).filter(
                    func.length(MediaFile.file_path) > 0
                )
            )
        ).all()
        
        for metadata in orphaned_metadata:
            self.session.delete(metadata)
        counts['orphaned_metadata'] = len(orphaned_metadata)
        
        # Similar cleanup for keywords and thumbnails can be added here
        
        return counts