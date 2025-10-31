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
from ..utils.hashing import compute_media_file_id, compute_perceptual_hash
from .db_logger import log_db_operation, _db_logger

logger = logging.getLogger(__name__)


class DatabaseService:
    """Service class for database operations."""
    
    def __init__(self):
        self.session: Optional[Session] = None
    
    def __enter__(self):
        self.session = get_session()
        _db_logger.log_transaction("SESSION_START", "Database session opened")
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            if exc_type:
                _db_logger.log_transaction("ROLLBACK", f"Session rolled back due to error: {exc_val}")
                self.session.rollback()
            else:
                _db_logger.log_transaction("COMMIT", "Session committed successfully")
                self.session.commit()
            _db_logger.log_transaction("SESSION_END", "Database session closed")
            self.session.close()
    
    # Media File Operations
    
    @log_db_operation("get_or_create_media_file")
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
            # Update hashes if they're missing
            if not media_file.media_file_id or not media_file.phash:
                self._update_media_file_hashes(media_file, file_path)
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
        
        # Compute and store hashes
        self._update_media_file_hashes(media_file, file_path)
        
        self.session.add(media_file)
        self.session.flush()  # Get the ID
        
        logger.info(f"Created new media file record: {file_path.name}")
        return media_file
    
    @log_db_operation("update_media_file_score")
    def update_media_file_score(self, file_path: Path, score: int) -> bool:
        """Update the score for a media file."""
        media_file = self.get_or_create_media_file(file_path)
        media_file.score = score
        media_file.updated_at = datetime.utcnow()
        return True
    
    @log_db_operation("get_media_file_score")
    def get_media_file_score(self, file_path: Path) -> Optional[int]:
        """Get the score for a media file."""
        file_path_str = str(file_path.resolve())
        media_file = self.session.query(MediaFile).filter(
            MediaFile.file_path == file_path_str
        ).first()
        return media_file.score if media_file else None
    
    @log_db_operation("get_media_files_by_directory")
    def get_media_files_by_directory(self, directory: Path) -> List[MediaFile]:
        """Get all media files in a directory."""
        return self.session.query(MediaFile).filter(
            MediaFile.directory == str(directory)
        ).order_by(MediaFile.filename).all()
    
    @log_db_operation("get_media_files_by_score")
    def get_media_files_by_score(self, min_score: Optional[int] = None, 
                                 max_score: Optional[int] = None) -> List[MediaFile]:
        """Get media files filtered by score range."""
        query = self.session.query(MediaFile)
        
        if min_score is not None:
            query = query.filter(MediaFile.score >= min_score)
        if max_score is not None:
            query = query.filter(MediaFile.score <= max_score)
            
        return query.order_by(desc(MediaFile.score), MediaFile.filename).all()
    
    @log_db_operation("get_all_media_files")
    def get_all_media_files(self, 
                           min_score: Optional[int] = None,
                           max_score: Optional[int] = None,
                           file_types: Optional[List[str]] = None,
                           start_date: Optional[datetime] = None,
                           end_date: Optional[datetime] = None,
                           nsfw_filter: Optional[str] = None,
                           sort_field: str = "name",
                           sort_direction: str = "asc",
                           offset: Optional[int] = None,
                           limit: Optional[int] = None) -> List[MediaFile]:
        """Get all media files with optional filters and sorting."""
        query = self.session.query(MediaFile)
        
        # Apply score filters
        if min_score is not None:
            query = query.filter(MediaFile.score >= min_score)
        if max_score is not None:
            query = query.filter(MediaFile.score <= max_score)
        
        # Apply file type filters
        if file_types:
            # Convert extensions to include dot prefix if needed
            extensions = []
            for ext in file_types:
                if not ext.startswith('.'):
                    extensions.append(f'.{ext}')
                else:
                    extensions.append(ext)
            query = query.filter(MediaFile.extension.in_(extensions))
        
        # Apply date filters using original_created_at with fallback to created_at
        if start_date is not None:
            # Use original creation date if available, otherwise fall back to database creation date
            query = query.filter(
                func.coalesce(MediaFile.original_created_at, MediaFile.created_at) >= start_date
            )
        if end_date is not None:
            # Use original creation date if available, otherwise fall back to database creation date
            query = query.filter(
                func.coalesce(MediaFile.original_created_at, MediaFile.created_at) <= end_date
            )
        
        # Apply NSFW filter
        if nsfw_filter and nsfw_filter != 'all':
            if nsfw_filter == 'sfw':
                # Show only SFW content (nsfw=False or nsfw_label=False)
                query = query.filter(
                    (MediaFile.nsfw == False) | (MediaFile.nsfw_label == False)
                )
            elif nsfw_filter == 'nsfw':
                # Show only NSFW content (nsfw=True or nsfw_label=True)
                query = query.filter(
                    (MediaFile.nsfw == True) | (MediaFile.nsfw_label == True)
                )
        
        # Apply dynamic sorting
        sort_func = desc if sort_direction == "desc" else asc
        
        if sort_field == "name":
            query = query.order_by(sort_func(MediaFile.filename))
        elif sort_field == "date":
            # Use original_created_at if available, fallback to created_at
            query = query.order_by(
                sort_func(MediaFile.original_created_at.is_(None)), 
                sort_func(MediaFile.original_created_at), 
                sort_func(MediaFile.created_at), 
                MediaFile.filename
            )
        elif sort_field == "size": 
            query = query.order_by(sort_func(MediaFile.file_size), MediaFile.filename)
        elif sort_field == "rating":
            query = query.order_by(sort_func(MediaFile.score), MediaFile.filename)
        else:
            # Default fallback to name sorting
            query = query.order_by(sort_func(MediaFile.filename))
        
        # Apply pagination if specified
        if offset is not None:
            query = query.offset(offset)
        if limit is not None:
            query = query.limit(limit)
            
        return query.all()
    
    # Metadata Operations
    
    @log_db_operation("store_media_metadata")
    def store_media_metadata(self, file_path: Path, metadata: Dict) -> MediaMetadata:
        """Store or update metadata for a media file."""
        media_file = self.get_or_create_media_file(file_path)
        
        # Update MediaFile's original_created_at if provided and not already set
        if 'original_created_at' in metadata and metadata['original_created_at'] is not None:
            if media_file.original_created_at is None:
                from datetime import datetime
                media_file.original_created_at = datetime.fromtimestamp(metadata['original_created_at'])
        
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
            if hasattr(metadata_obj, key) and key not in ['png_text', 'workflow_data', 'parsed_prompt_data', 'hires_config', 'dynthres_config']:
                setattr(metadata_obj, key, value)
        
        # Store PNG text as JSON if present
        if 'png_text' in metadata and metadata['png_text']:
            metadata_obj.png_text = json.dumps(metadata['png_text'])
        
        # Store workflow data as JSON if present  
        if 'workflow_data' in metadata and metadata['workflow_data']:
            metadata_obj.workflow_data = json.dumps(metadata['workflow_data'])
        
        # Store hires config as JSON if present
        if 'hires_config' in metadata and metadata['hires_config']:
            metadata_obj.hires_config = metadata['hires_config']
        
        # Store dynthres config as JSON if present
        if 'dynthres_config' in metadata and metadata['dynthres_config']:
            metadata_obj.dynthres_config = metadata['dynthres_config']
        
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
    
    @log_db_operation("get_media_metadata")
    def get_media_metadata(self, file_path: Path) -> Optional[MediaMetadata]:
        """Get metadata for a media file."""
        file_path_str = str(file_path.resolve())
        
        return self.session.query(MediaMetadata).join(MediaFile).filter(
            MediaFile.file_path == file_path_str
        ).first()
    
    # Keyword Operations
    
    @log_db_operation("add_keywords")
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
    
    @log_db_operation("search_by_keywords")
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
    
    @log_db_operation("get_keywords_for_file")
    def get_keywords_for_file(self, file_path: Path) -> List[MediaKeyword]:
        """Get all keywords for a media file."""
        file_path_str = str(file_path.resolve())
        
        return self.session.query(MediaKeyword).join(MediaFile).filter(
            MediaFile.file_path == file_path_str
        ).order_by(MediaKeyword.keyword_type, MediaKeyword.keyword).all()
    
    @log_db_operation("get_all_keywords")
    def get_all_keywords(self, keyword_type: Optional[str] = None) -> List[str]:
        """Get all unique keywords, optionally filtered by type."""
        query = self.session.query(MediaKeyword.keyword).distinct()
        
        if keyword_type:
            query = query.filter(MediaKeyword.keyword_type == keyword_type)
        
        return [row[0] for row in query.order_by(MediaKeyword.keyword).all()]
    
    # Thumbnail Operations
    
    @log_db_operation("store_thumbnail")
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
    
    @log_db_operation("get_thumbnail")
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
    
    def _update_media_file_hashes(self, media_file: MediaFile, file_path: Path) -> None:
        """Compute and update hashes for a media file."""
        try:
            # Compute content hash (SHA256 of pixel data)
            if not media_file.media_file_id:
                content_hash = compute_media_file_id(file_path)
                if content_hash:
                    media_file.media_file_id = content_hash
                    logger.debug(f"Computed content hash for {file_path.name}: {content_hash[:16]}...")
            
            # Compute perceptual hash
            if not media_file.phash:
                perceptual_hash = compute_perceptual_hash(file_path)
                if perceptual_hash:
                    media_file.phash = perceptual_hash
                    logger.debug(f"Computed perceptual hash for {file_path.name}: {perceptual_hash}")
                    
        except Exception as e:
            logger.error(f"Failed to update hashes for {file_path}: {e}")
    
    @log_db_operation("update_media_file_hashes")
    def update_media_file_hashes(self, file_path: Path) -> bool:
        """Public method to update hashes for an existing media file."""
        try:
            media_file = self.get_or_create_media_file(file_path)
            # Force recomputation by clearing existing hashes
            media_file.media_file_id = None
            media_file.phash = None
            self._update_media_file_hashes(media_file, file_path)
            media_file.updated_at = datetime.utcnow()
            return True
        except Exception as e:
            logger.error(f"Failed to update hashes for {file_path}: {e}")
            return False
    
    @log_db_operation("find_similar_files_by_hash")
    def find_similar_files_by_hash(self, target_hash: str, threshold: int = 5,
                                   file_types: Optional[List[str]] = None,
                                   min_score: Optional[int] = None,
                                   max_score: Optional[int] = None,
                                   start_date: Optional[datetime] = None,
                                   end_date: Optional[datetime] = None,
                                   nsfw_filter: Optional[str] = None) -> List[Tuple[MediaFile, int]]:
        """Find files with similar perceptual hashes.
        
        Returns a list of tuples (MediaFile, distance) for similar files.
        """
        try:
            import imagehash
            from PIL import Image as PILImage
            
            # Build query with filters
            query = self.session.query(MediaFile).filter(
                MediaFile.phash.isnot(None)
            )
            
            # Apply file type filters
            if file_types:
                extensions = []
                for ext in file_types:
                    if not ext.startswith('.'):
                        extensions.append(f'.{ext}')
                    else:
                        extensions.append(ext)
                query = query.filter(MediaFile.extension.in_(extensions))
            
            # Apply score filters
            if min_score is not None:
                query = query.filter(MediaFile.score >= min_score)
            if max_score is not None:
                query = query.filter(MediaFile.score <= max_score)
            
            # Apply date filters
            if start_date is not None:
                query = query.filter(
                    func.coalesce(MediaFile.original_created_at, MediaFile.created_at) >= start_date
                )
            if end_date is not None:
                query = query.filter(
                    func.coalesce(MediaFile.original_created_at, MediaFile.created_at) <= end_date
                )
            
            # Apply NSFW filter
            if nsfw_filter and nsfw_filter != 'all':
                if nsfw_filter == 'sfw':
                    # Show only SFW content - both nsfw AND nsfw_label should be False/None
                    query = query.filter(
                        and_(
                            or_(MediaFile.nsfw == False, MediaFile.nsfw.is_(None)),
                            or_(MediaFile.nsfw_label == False, MediaFile.nsfw_label.is_(None))
                        )
                    )
                elif nsfw_filter == 'nsfw':
                    # Show only NSFW content - at least one should be True
                    query = query.filter(
                        or_(MediaFile.nsfw == True, MediaFile.nsfw_label == True)
                    )
            
            files_with_hashes = query.all()
            
            similar_files = []
            target_hash_obj = imagehash.hex_to_hash(target_hash)
            
            for media_file in files_with_hashes:
                try:
                    file_hash_obj = imagehash.hex_to_hash(media_file.phash)
                    # Calculate Hamming distance
                    distance = target_hash_obj - file_hash_obj
                    if distance <= threshold:
                        similar_files.append((media_file, int(distance)))
                except Exception as e:
                    logger.debug(f"Error comparing hash for {media_file.filename}: {e}")
                    continue
            
            return similar_files
        except Exception as e:
            logger.error(f"Error finding similar files: {e}")
            return []
    
    @log_db_operation("get_stats")
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
    
    @log_db_operation("cleanup_orphaned_records")
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