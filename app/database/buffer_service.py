"""Buffer service for materialized search results."""

import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass

from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from .models import MediaFile
from .service import DatabaseService

logger = logging.getLogger(__name__)


@dataclass
class FilterCriteria:
    """Filter criteria for search results."""
    keywords: Optional[List[str]] = None
    match_all: bool = False
    file_types: Optional[List[str]] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    nsfw_filter: Optional[str] = None
    sort_field: str = "date"
    sort_direction: str = "desc"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for hashing."""
        return {
            "keywords": sorted(self.keywords) if self.keywords else None,
            "match_all": self.match_all,
            "file_types": sorted(self.file_types) if self.file_types else None,
            "min_score": self.min_score,
            "max_score": self.max_score,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "nsfw_filter": self.nsfw_filter,
            "sort_field": self.sort_field,
            "sort_direction": self.sort_direction,
        }
    
    def compute_hash(self) -> str:
        """Compute SHA256 hash of filter criteria."""
        filter_json = json.dumps(self.to_dict(), sort_keys=True)
        return hashlib.sha256(filter_json.encode()).hexdigest()


class BufferService:
    """Service for managing buffered search results."""
    
    def __init__(self, buffer_db_path: Optional[Path] = None):
        """Initialize buffer service with SQLite database.
        
        Args:
            buffer_db_path: Path to SQLite database for buffers. 
                          If None, uses in-memory database.
        """
        if buffer_db_path is None:
            # Use in-memory database for testing
            db_url = "sqlite:///:memory:"
            connect_args = {"check_same_thread": False}
            poolclass = StaticPool
        else:
            # Use file-based database
            buffer_db_path.parent.mkdir(parents=True, exist_ok=True)
            db_url = f"sqlite:///{buffer_db_path}"
            connect_args = {}
            poolclass = None
        
        # Create engine with optimized settings for SQLite
        self.engine = create_engine(
            db_url,
            connect_args=connect_args,
            poolclass=poolclass,
            echo=False
        )
        
        self.session_factory = sessionmaker(bind=self.engine)
        self._setup_database()
        
        # Configuration
        self.max_buffer_size_mb = 500  # Maximum total buffer size in MB
        self.max_buffers = 10  # Maximum number of buffers to keep
    
    def _setup_database(self):
        """Create necessary tables and set SQLite pragmas."""
        with self.engine.connect() as conn:
            # Set SQLite performance pragmas
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA temp_store=MEMORY"))
            conn.execute(text("PRAGMA cache_size=-64000"))  # 64MB cache
            conn.commit()
            
            # Create buffer_registry table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS buffer_registry (
                    filter_hash TEXT PRIMARY KEY,
                    buffer_table_name TEXT NOT NULL,
                    item_count INTEGER NOT NULL DEFAULT 0,
                    size_bytes INTEGER NOT NULL DEFAULT 0,
                    created_at TEXT NOT NULL,
                    last_accessed_at TEXT NOT NULL,
                    filter_criteria TEXT NOT NULL
                )
            """))
            
            # Create ui_state table
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS ui_state (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """))
            
            # Create indexes
            conn.execute(text("""
                CREATE INDEX IF NOT EXISTS idx_buffer_registry_accessed 
                ON buffer_registry(last_accessed_at)
            """))
            
            conn.commit()
    
    def _get_buffer_table_name(self, filter_hash: str) -> str:
        """Generate buffer table name from filter hash."""
        return f"buffer_items_{filter_hash[:16]}"
    
    def get_or_create_buffer(self, filters: FilterCriteria, 
                            db_service: DatabaseService,
                            force_rebuild: bool = False) -> Tuple[str, int]:
        """Get existing buffer or create new one for given filters.
        
        Args:
            filters: Filter criteria for the buffer
            db_service: Database service to query media files
            force_rebuild: If True, delete existing buffer and rebuild from scratch
            
        Returns:
            Tuple of (filter_hash, item_count)
        """
        filter_hash = filters.compute_hash()
        
        # If force_rebuild, delete existing buffer first
        if force_rebuild:
            logger.info(f"Force rebuild requested for filter hash {filter_hash[:8]}")
            with self.session_factory() as session:
                result = session.execute(
                    text("SELECT buffer_table_name FROM buffer_registry WHERE filter_hash = :hash"),
                    {"hash": filter_hash}
                ).fetchone()
                
                if result:
                    buffer_table_name = result[0]
                    logger.info(f"Deleting existing buffer table {buffer_table_name}")
                    session.execute(text(f"DROP TABLE IF EXISTS {buffer_table_name}"))
                    session.execute(
                        text("DELETE FROM buffer_registry WHERE filter_hash = :hash"),
                        {"hash": filter_hash}
                    )
                    session.commit()
        
        # Check if buffer already exists (will be False if force_rebuild was True)
        with self.session_factory() as session:
            result = session.execute(
                text("SELECT buffer_table_name, item_count FROM buffer_registry WHERE filter_hash = :hash"),
                {"hash": filter_hash}
            ).fetchone()
            
            if result:
                # Buffer exists, update last accessed time
                buffer_table_name, item_count = result
                session.execute(
                    text("UPDATE buffer_registry SET last_accessed_at = :now WHERE filter_hash = :hash"),
                    {"now": datetime.utcnow().isoformat(), "hash": filter_hash}
                )
                session.commit()
                
                logger.info(f"Reusing existing buffer {filter_hash[:8]} with {item_count} items")
                return filter_hash, item_count
        
        # Create new buffer
        logger.info(f"Creating new buffer for filter hash {filter_hash[:8]}")
        return self._create_buffer(filter_hash, filters, db_service)
    
    def _create_buffer(self, filter_hash: str, filters: FilterCriteria,
                      db_service: DatabaseService) -> Tuple[str, int]:
        """Create a new buffer table with filtered results.
        
        Uses atomic swap pattern:
        1. Create temp table
        2. Populate with filtered data
        3. Create indexes
        4. Rename tables atomically
        5. Drop old table
        """
        buffer_table_name = self._get_buffer_table_name(filter_hash)
        temp_table_name = f"{buffer_table_name}_new"
        
        # Query media files using existing database service
        media_files = self._query_media_files(db_service, filters)
        item_count = len(media_files)
        
        logger.info(f"Building buffer with {item_count} items")
        
        with self.engine.begin() as conn:
            # Drop temp table if it exists
            conn.execute(text(f"DROP TABLE IF EXISTS {temp_table_name}"))
            
            # Create temp buffer table with only UI-needed fields
            conn.execute(text(f"""
                CREATE TABLE {temp_table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    media_file_id INTEGER NOT NULL,
                    filename TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    file_size INTEGER,
                    file_type TEXT,
                    extension TEXT,
                    score INTEGER DEFAULT 0,
                    width INTEGER,
                    height INTEGER,
                    created_at TEXT NOT NULL,
                    original_created_at TEXT,
                    nsfw BOOLEAN DEFAULT 0,
                    nsfw_score REAL
                )
            """))
            
            # Insert filtered data
            for media_file in media_files:
                # Get metadata if available
                metadata = db_service.get_media_metadata(Path(media_file.file_path))
                
                conn.execute(text(f"""
                    INSERT INTO {temp_table_name} 
                    (media_file_id, filename, file_path, file_size, file_type, extension, 
                     score, width, height, created_at, original_created_at, nsfw, nsfw_score)
                    VALUES 
                    (:media_file_id, :filename, :file_path, :file_size, :file_type, :extension,
                     :score, :width, :height, :created_at, :original_created_at, :nsfw, :nsfw_score)
                """), {
                    "media_file_id": media_file.id,
                    "filename": media_file.filename,
                    "file_path": media_file.file_path,
                    "file_size": media_file.file_size,
                    "file_type": media_file.file_type,
                    "extension": media_file.extension,
                    "score": media_file.score,
                    "width": metadata.width if metadata else None,
                    "height": metadata.height if metadata else None,
                    "created_at": media_file.created_at.isoformat(),
                    "original_created_at": media_file.original_created_at.isoformat() if media_file.original_created_at else None,
                    "nsfw": media_file.nsfw,
                    "nsfw_score": media_file.nsfw_score,
                })
            
            # Create indexes for keyset pagination
            conn.execute(text(f"""
                CREATE INDEX idx_{temp_table_name}_pagination 
                ON {temp_table_name}(created_at DESC, id DESC)
            """))
            
            conn.execute(text(f"""
                CREATE INDEX idx_{temp_table_name}_original_pagination 
                ON {temp_table_name}(original_created_at DESC, id DESC)
            """))
            
            conn.execute(text(f"""
                CREATE INDEX idx_{temp_table_name}_score 
                ON {temp_table_name}(score DESC, filename)
            """))
            
            # Drop old buffer table if it exists
            conn.execute(text(f"DROP TABLE IF EXISTS {buffer_table_name}"))
            
            # Rename temp table to final name (atomic swap)
            conn.execute(text(f"ALTER TABLE {temp_table_name} RENAME TO {buffer_table_name}"))
            
            # Calculate approximate buffer size
            # For simplicity, estimate based on row count and average row size
            buffer_size = item_count * 500  # Rough estimate: 500 bytes per row
            
            # Register buffer in registry
            conn.execute(text("""
                INSERT OR REPLACE INTO buffer_registry 
                (filter_hash, buffer_table_name, item_count, size_bytes, created_at, last_accessed_at, filter_criteria)
                VALUES (:hash, :table_name, :count, :size, :now, :now, :criteria)
            """), {
                "hash": filter_hash,
                "table_name": buffer_table_name,
                "count": item_count,
                "size": buffer_size,
                "now": datetime.utcnow().isoformat(),
                "criteria": json.dumps(filters.to_dict())
            })
        
        # Check if we need to evict old buffers
        self._evict_old_buffers()
        
        logger.info(f"Created buffer {filter_hash[:8]} with {item_count} items ({buffer_size / 1024 / 1024:.2f} MB)")
        return filter_hash, item_count
    
    def _query_media_files(self, db_service: DatabaseService, 
                          filters: FilterCriteria) -> List[MediaFile]:
        """Query media files using filter criteria."""
        from datetime import datetime as dt
        
        # Convert date strings to datetime objects if provided
        start_date = dt.fromisoformat(filters.start_date) if filters.start_date else None
        end_date = dt.fromisoformat(filters.end_date) if filters.end_date else None
        
        # Use existing database service query method
        if filters.keywords:
            # Keyword search
            media_files = db_service.search_by_keywords(
                filters.keywords,
                match_all=filters.match_all
            )
            
            # Apply additional filters
            if filters.file_types:
                media_files = [f for f in media_files if f.extension.lstrip('.') in filters.file_types]
            if filters.min_score is not None:
                media_files = [f for f in media_files if f.score >= filters.min_score]
            if filters.max_score is not None:
                media_files = [f for f in media_files if f.score <= filters.max_score]
        else:
            # Regular query with all filters
            media_files = db_service.get_all_media_files(
                min_score=filters.min_score,
                max_score=filters.max_score,
                file_types=filters.file_types,
                start_date=start_date,
                end_date=end_date,
                nsfw_filter=filters.nsfw_filter,
                sort_field=filters.sort_field,
                sort_direction=filters.sort_direction
            )
        
        return media_files
    
    def get_page(self, filter_hash: str, cursor: Optional[Dict[str, Any]] = None,
                limit: int = 50) -> Tuple[List[Dict], Optional[Dict[str, Any]]]:
        """Get a page of results using keyset pagination.
        
        Args:
            filter_hash: Hash of the filter criteria
            cursor: Cursor from previous page (dict with created_at and id)
            limit: Number of items per page
            
        Returns:
            Tuple of (items, next_cursor)
        """
        with self.session_factory() as session:
            # Get buffer table name
            result = session.execute(
                text("SELECT buffer_table_name FROM buffer_registry WHERE filter_hash = :hash"),
                {"hash": filter_hash}
            ).fetchone()
            
            if not result:
                raise ValueError(f"Buffer not found for hash {filter_hash}")
            
            buffer_table_name = result[0]
            
            # Update last accessed time
            session.execute(
                text("UPDATE buffer_registry SET last_accessed_at = :now WHERE filter_hash = :hash"),
                {"now": datetime.utcnow().isoformat(), "hash": filter_hash}
            )
            session.commit()
            
            # Build keyset pagination query
            if cursor:
                # Continue from cursor
                cursor_created_at = cursor.get("created_at")
                cursor_id = cursor.get("id")
                
                # Use COALESCE to handle NULL original_created_at
                query = f"""
                    SELECT * FROM {buffer_table_name}
                    WHERE 
                        (COALESCE(original_created_at, created_at) < :created_at)
                        OR (COALESCE(original_created_at, created_at) = :created_at AND id < :id)
                    ORDER BY COALESCE(original_created_at, created_at) DESC, id DESC
                    LIMIT :limit
                """
                params = {
                    "created_at": cursor_created_at,
                    "id": cursor_id,
                    "limit": limit
                }
            else:
                # First page
                query = f"""
                    SELECT * FROM {buffer_table_name}
                    ORDER BY COALESCE(original_created_at, created_at) DESC, id DESC
                    LIMIT :limit
                """
                params = {"limit": limit}
            
            results = session.execute(text(query), params).fetchall()
            
            # Convert to list of dicts
            items = []
            for row in results:
                items.append({
                    "id": row.id,
                    "media_file_id": row.media_file_id,
                    "filename": row.filename,
                    "file_path": row.file_path,
                    "file_size": row.file_size,
                    "file_type": row.file_type,
                    "extension": row.extension,
                    "score": row.score,
                    "width": row.width,
                    "height": row.height,
                    "created_at": row.created_at,
                    "original_created_at": row.original_created_at,
                    "nsfw": row.nsfw,
                    "nsfw_score": row.nsfw_score,
                })
            
            # Create next cursor
            next_cursor = None
            if items and len(items) == limit:
                last_item = items[-1]
                next_cursor = {
                    "created_at": last_item["original_created_at"] or last_item["created_at"],
                    "id": last_item["id"]
                }
            
            return items, next_cursor
    
    def _evict_old_buffers(self):
        """Evict least recently used buffers if limits exceeded."""
        with self.session_factory() as session:
            # Get total size and count
            result = session.execute(
                text("SELECT COUNT(*), SUM(size_bytes) FROM buffer_registry")
            ).fetchone()
            
            if not result:
                return
            
            buffer_count, total_size = result
            total_size_mb = (total_size or 0) / 1024 / 1024
            
            # Check if we need to evict
            if buffer_count <= self.max_buffers and total_size_mb <= self.max_buffer_size_mb:
                return
            
            logger.info(f"Evicting old buffers (count: {buffer_count}/{self.max_buffers}, size: {total_size_mb:.2f}/{self.max_buffer_size_mb} MB)")
            
            # Get LRU buffers to evict
            buffers_to_evict = session.execute(
                text("""
                    SELECT filter_hash, buffer_table_name 
                    FROM buffer_registry 
                    ORDER BY last_accessed_at ASC 
                    LIMIT :limit
                """),
                {"limit": max(1, buffer_count - self.max_buffers + 1)}
            ).fetchall()
            
            # Evict buffers
            with self.engine.begin() as conn:
                for filter_hash, table_name in buffers_to_evict:
                    # Drop buffer table
                    conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                    
                    # Remove from registry
                    conn.execute(
                        text("DELETE FROM buffer_registry WHERE filter_hash = :hash"),
                        {"hash": filter_hash}
                    )
                    
                    logger.info(f"Evicted buffer {filter_hash[:8]}")
    
    def save_ui_state(self, key: str, value: Dict[str, Any]):
        """Save UI state to persistence layer."""
        with self.session_factory() as session:
            session.execute(
                text("""
                    INSERT OR REPLACE INTO ui_state (key, value, updated_at)
                    VALUES (:key, :value, :now)
                """),
                {
                    "key": key,
                    "value": json.dumps(value),
                    "now": datetime.utcnow().isoformat()
                }
            )
            session.commit()
    
    def get_ui_state(self, key: str) -> Optional[Dict[str, Any]]:
        """Get UI state from persistence layer."""
        with self.session_factory() as session:
            result = session.execute(
                text("SELECT value FROM ui_state WHERE key = :key"),
                {"key": key}
            ).fetchone()
            
            if result:
                return json.loads(result[0])
            return None
    
    def get_buffer_stats(self) -> Dict[str, Any]:
        """Get statistics about buffers."""
        with self.session_factory() as session:
            result = session.execute(
                text("""
                    SELECT 
                        COUNT(*) as buffer_count,
                        SUM(item_count) as total_items,
                        SUM(size_bytes) as total_size
                    FROM buffer_registry
                """)
            ).fetchone()
            
            if result:
                return {
                    "buffer_count": result[0],
                    "total_items": result[1] or 0,
                    "total_size_mb": (result[2] or 0) / 1024 / 1024
                }
            
            return {
                "buffer_count": 0,
                "total_items": 0,
                "total_size_mb": 0
            }
    
    def delete_buffer(self, filter_hash: str):
        """Delete a specific buffer."""
        with self.session_factory() as session:
            result = session.execute(
                text("SELECT buffer_table_name FROM buffer_registry WHERE filter_hash = :hash"),
                {"hash": filter_hash}
            ).fetchone()
            
            if not result:
                return
            
            buffer_table_name = result[0]
            
            with self.engine.begin() as conn:
                # Drop buffer table
                conn.execute(text(f"DROP TABLE IF EXISTS {buffer_table_name}"))
                
                # Remove from registry
                conn.execute(
                    text("DELETE FROM buffer_registry WHERE filter_hash = :hash"),
                    {"hash": filter_hash}
                )
            
            logger.info(f"Deleted buffer {filter_hash[:8]}")
    
    def clear_all_buffers(self):
        """Clear all buffers."""
        with self.session_factory() as session:
            buffers = session.execute(
                text("SELECT filter_hash, buffer_table_name FROM buffer_registry")
            ).fetchall()
            
            with self.engine.begin() as conn:
                for filter_hash, table_name in buffers:
                    conn.execute(text(f"DROP TABLE IF EXISTS {table_name}"))
                
                conn.execute(text("DELETE FROM buffer_registry"))
            
            logger.info(f"Cleared {len(buffers)} buffers")
