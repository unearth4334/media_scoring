"""Search router for database-powered search functionality."""

import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional, Any

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel

from ..state import get_state
from ..database.service import DatabaseService
from ..database.buffer_service import BufferService, FilterCriteria

router = APIRouter(prefix="/api/search")

# Global buffer service instance
_buffer_service: Optional[BufferService] = None


def get_buffer_service() -> BufferService:
    """Get or create the buffer service instance."""
    global _buffer_service
    if _buffer_service is None:
        state = get_state()
        # Store buffer database in the scores directory
        buffer_db_path = state.get_scores_dir() / "buffer.db"
        _buffer_service = BufferService(buffer_db_path)
    return _buffer_service


class SearchRequest(BaseModel):
    """Request model for search operations."""
    keywords: List[str]
    match_all: bool = False
    file_types: Optional[List[str]] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None


class AddKeywordsRequest(BaseModel):
    """Request model for adding keywords."""
    filename: str
    keywords: List[str]
    keyword_type: str = "user"
    source: str = "manual"


@router.post("/files")
async def search_files(request: SearchRequest):
    """Search media files using keywords and filters."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    try:
        db_service = state.get_database_service()
        if db_service is None:
            raise HTTPException(503, "Database service is not available")
            
        with db_service as db:
            # Start with keyword search if keywords provided
            if request.keywords:
                media_files = db.search_by_keywords(
                    request.keywords, 
                    match_all=request.match_all
                )
            else:
                # Get files by score if no keywords
                media_files = db.get_media_files_by_score(
                    min_score=request.min_score,
                    max_score=request.max_score
                )
            
            # Apply additional filters
            if request.file_types:
                media_files = [
                    f for f in media_files 
                    if f.extension.lstrip('.') in request.file_types
                ]
            
            if request.min_score is not None:
                media_files = [f for f in media_files if f.score >= request.min_score]
                
            if request.max_score is not None:
                media_files = [f for f in media_files if f.score <= request.max_score]
            
            # Convert to response format
            results = []
            for media_file in media_files:
                # Get keywords for this file
                keywords = db.get_keywords_for_file(Path(media_file.file_path))
                keyword_data = {
                    kw.keyword_type: [k.keyword for k in keywords if k.keyword_type == kw.keyword_type]
                    for kw in keywords
                }
                
                results.append({
                    "name": media_file.filename,
                    "path": media_file.file_path,
                    "score": media_file.score,
                    "file_type": media_file.file_type,
                    "extension": media_file.extension,
                    "keywords": keyword_data,
                    "updated_at": media_file.updated_at.isoformat() if media_file.updated_at else None
                })
            
            return {
                "results": results,
                "total": len(results),
                "query": {
                    "keywords": request.keywords,
                    "match_all": request.match_all,
                    "file_types": request.file_types,
                    "min_score": request.min_score,
                    "max_score": request.max_score
                }
            }
    
    except Exception as e:
        state.logger.error(f"Search failed: {e}")
        raise HTTPException(500, f"Search failed: {str(e)}")


@router.post("/keywords")
async def add_keywords(request: AddKeywordsRequest):
    """Add keywords to a media file."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    # Find the file in current directory
    file_path = state.video_dir / request.filename
    if not file_path.exists():
        raise HTTPException(404, f"File not found: {request.filename}")
    
    try:
        with state.get_database_service() as db:
            keyword_objects = db.add_keywords(
                file_path,
                request.keywords,
                keyword_type=request.keyword_type,
                source=request.source
            )
            
            state.logger.info(
                f"Added {len(keyword_objects)} keywords to {request.filename}"
            )
            
            return {
                "ok": True,
                "added_keywords": len(keyword_objects),
                "keywords": [kw.keyword for kw in keyword_objects]
            }
    
    except Exception as e:
        state.logger.error(f"Failed to add keywords: {e}")
        raise HTTPException(500, f"Failed to add keywords: {str(e)}")


@router.get("/keywords")
async def get_all_keywords(keyword_type: Optional[str] = Query(None)):
    """Get all available keywords, optionally filtered by type."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    try:
        with state.get_database_service() as db:
            keywords = db.get_all_keywords(keyword_type=keyword_type)
            
            return {
                "keywords": keywords,
                "total": len(keywords),
                "keyword_type": keyword_type
            }
    
    except Exception as e:
        state.logger.error(f"Failed to get keywords: {e}")
        raise HTTPException(500, f"Failed to get keywords: {str(e)}")


@router.get("/keywords/{filename}")
async def get_file_keywords(filename: str):
    """Get all keywords for a specific file."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    file_path = state.video_dir / filename
    if not file_path.exists():
        raise HTTPException(404, f"File not found: {filename}")
    
    try:
        with state.get_database_service() as db:
            keywords = db.get_keywords_for_file(file_path)
            
            # Group by type
            keyword_groups = {}
            for kw in keywords:
                if kw.keyword_type not in keyword_groups:
                    keyword_groups[kw.keyword_type] = []
                keyword_groups[kw.keyword_type].append({
                    "keyword": kw.keyword,
                    "source": kw.source,
                    "confidence": kw.confidence,
                    "created_at": kw.created_at.isoformat()
                })
            
            return {
                "filename": filename,
                "keywords": keyword_groups,
                "total_keywords": len(keywords)
            }
    
    except Exception as e:
        state.logger.error(f"Failed to get file keywords: {e}")
        raise HTTPException(500, f"Failed to get file keywords: {str(e)}")


@router.get("/stats")
async def get_database_stats():
    """Get database statistics."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    try:
        with state.get_database_service() as db:
            stats = db.get_stats()
            return stats
    
    except Exception as e:
        state.logger.error(f"Failed to get database stats: {e}")
        raise HTTPException(500, f"Failed to get database stats: {str(e)}")


@router.post("/sync")
async def sync_directory_to_database():
    """Sync current directory files to database."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    try:
        synced_count = 0
        with state.get_database_service() as db:
            for file_path in state.file_list:
                # Create/update media file record
                media_file = db.get_or_create_media_file(file_path)
                
                # Read score from sidecar file if exists
                from ..services.files import read_score
                sidecar_score = read_score(file_path)
                if sidecar_score is not None and media_file.score != sidecar_score:
                    media_file.score = sidecar_score
                
                synced_count += 1
        
        state.logger.info(f"Synced {synced_count} files to database")
        
        return {
            "ok": True,
            "synced_files": synced_count,
            "message": f"Synced {synced_count} files from current directory"
        }
    
    except Exception as e:
        state.logger.error(f"Failed to sync directory: {e}")
        raise HTTPException(500, f"Failed to sync directory: {str(e)}")


# New buffered search endpoints

class FilterRequest(BaseModel):
    """Request model for filter operations."""
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
    force_rebuild: bool = True  # Default to True for refresh operations


@router.post("/refresh")
async def refresh_buffer(request: FilterRequest):
    """Refresh the buffer with current filter criteria.
    
    This endpoint triggers a rebuild of the materialized buffer table
    based on the provided filters. Should be called when user presses
    the Refresh button.
    
    When refresh is triggered, all existing buffers are cleared to avoid
    leftover content from previous searches. This ensures a clean state
    and prevents stale data from being displayed.
    
    The force_rebuild parameter (default True) ensures that cached buffers
    are invalidated and rebuilt from current database state, allowing
    newly ingested media to appear even when filter criteria unchanged.
    """
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    try:
        db_service = state.get_database_service()
        if db_service is None:
            raise HTTPException(503, "Database service is not available")
        
        buffer_service = get_buffer_service()
        
        # Clear all existing buffers to avoid leftover content
        buffer_service.clear_all_buffers()
        state.logger.info("Cleared all buffers before refresh")
        
        # Convert request to FilterCriteria
        filters = FilterCriteria(
            keywords=request.keywords,
            match_all=request.match_all,
            file_types=request.file_types,
            min_score=request.min_score,
            max_score=request.max_score,
            start_date=request.start_date,
            end_date=request.end_date,
            nsfw_filter=request.nsfw_filter,
            sort_field=request.sort_field,
            sort_direction=request.sort_direction
        )
        
        # Create new buffer (force rebuild by default)
        with db_service as db:
            filter_hash, item_count = buffer_service.get_or_create_buffer(
                filters, db, force_rebuild=request.force_rebuild
            )
        
        # Save as active filter state
        buffer_service.save_ui_state("active_filter", {
            "filter_hash": filter_hash,
            "filters": filters.to_dict()
        })
        
        state.logger.info(f"Buffer refreshed: {filter_hash[:8]} with {item_count} items")
        
        return {
            "ok": True,
            "filter_hash": filter_hash,
            "item_count": item_count,
            "message": f"Buffer created with {item_count} items"
        }
    
    except Exception as e:
        state.logger.error(f"Failed to refresh buffer: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to refresh buffer: {str(e)}")


@router.get("/page")
async def get_page(
    filter_hash: str = Query(..., description="Filter hash from refresh operation"),
    cursor_created_at: Optional[str] = Query(None, description="Cursor created_at from previous page"),
    cursor_id: Optional[int] = Query(None, description="Cursor id from previous page"),
    limit: int = Query(50, ge=1, le=200, description="Number of items per page")
):
    """Get a page of results using keyset pagination.
    
    This endpoint provides fast pagination through buffered results.
    Pass cursor values from the previous page to get the next page.
    """
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    try:
        buffer_service = get_buffer_service()
        
        # Build cursor if provided
        cursor = None
        if cursor_created_at and cursor_id:
            cursor = {
                "created_at": cursor_created_at,
                "id": cursor_id
            }
        
        # Get page from buffer
        items, next_cursor = buffer_service.get_page(filter_hash, cursor, limit)
        
        return {
            "items": items,
            "count": len(items),
            "next_cursor": next_cursor,
            "has_more": next_cursor is not None
        }
    
    except ValueError as e:
        raise HTTPException(404, str(e))
    except Exception as e:
        state.logger.error(f"Failed to get page: {e}", exc_info=True)
        raise HTTPException(500, f"Failed to get page: {str(e)}")


@router.get("/filters/active")
async def get_active_filters():
    """Get the currently active filter state.
    
    This endpoint returns the last applied filter configuration,
    allowing UI to restore state after browser refresh.
    """
    state = get_state()
    
    try:
        buffer_service = get_buffer_service()
        active_state = buffer_service.get_ui_state("active_filter")
        
        if active_state:
            return {
                "ok": True,
                "filter_hash": active_state.get("filter_hash"),
                "filters": active_state.get("filters")
            }
        else:
            return {
                "ok": True,
                "filter_hash": None,
                "filters": None
            }
    
    except Exception as e:
        state.logger.error(f"Failed to get active filters: {e}")
        raise HTTPException(500, f"Failed to get active filters: {str(e)}")


@router.post("/filters/active")
async def set_active_filters(request: FilterRequest):
    """Set the active filter state without rebuilding buffer.
    
    This endpoint updates the local filter state that will be
    used when the user presses Refresh. Does not trigger buffer rebuild.
    """
    state = get_state()
    
    try:
        buffer_service = get_buffer_service()
        
        # Convert request to FilterCriteria to compute hash
        filters = FilterCriteria(
            keywords=request.keywords,
            match_all=request.match_all,
            file_types=request.file_types,
            min_score=request.min_score,
            max_score=request.max_score,
            start_date=request.start_date,
            end_date=request.end_date,
            nsfw_filter=request.nsfw_filter,
            sort_field=request.sort_field,
            sort_direction=request.sort_direction
        )
        
        filter_hash = filters.compute_hash()
        
        # Save as pending filter state (not active until refresh)
        buffer_service.save_ui_state("pending_filter", {
            "filter_hash": filter_hash,
            "filters": filters.to_dict()
        })
        
        return {
            "ok": True,
            "filter_hash": filter_hash,
            "message": "Filter state updated (press Refresh to apply)"
        }
    
    except Exception as e:
        state.logger.error(f"Failed to set active filters: {e}")
        raise HTTPException(500, f"Failed to set active filters: {str(e)}")


@router.post("/view-state")
async def save_view_state(request: Request):
    """Save current view state (selected file and scroll position).
    
    This endpoint stores the user's current viewing position to enable
    restoration after browser refresh.
    """
    state = get_state()
    
    try:
        view_state = await request.json()
        
        buffer_service = get_buffer_service()
        buffer_service.save_ui_state("view_state", view_state)
        
        state.logger.info(f"View state saved: {view_state.get('current_file', 'unknown')}")
        
        return {
            "ok": True,
            "message": "View state saved"
        }
    
    except Exception as e:
        state.logger.error(f"Failed to save view state: {e}")
        raise HTTPException(500, f"Failed to save view state: {str(e)}")


@router.get("/view-state")
async def get_view_state():
    """Get the saved view state.
    
    Returns the last saved viewing position (file and scroll).
    """
    state = get_state()
    
    try:
        buffer_service = get_buffer_service()
        view_state = buffer_service.get_ui_state("view_state")
        
        if view_state:
            return view_state
        else:
            raise HTTPException(404, "No saved view state")
    
    except HTTPException:
        raise
    except Exception as e:
        state.logger.error(f"Failed to get view state: {e}")
        raise HTTPException(500, f"Failed to get view state: {str(e)}")


@router.get("/buffer/stats")
async def get_buffer_stats():
    """Get statistics about buffered results."""
    state = get_state()
    
    try:
        buffer_service = get_buffer_service()
        stats = buffer_service.get_buffer_stats()
        
        return {
            "ok": True,
            "stats": stats
        }
    
    except Exception as e:
        state.logger.error(f"Failed to get buffer stats: {e}")
        raise HTTPException(500, f"Failed to get buffer stats: {str(e)}")


@router.delete("/buffer/{filter_hash}")
async def delete_buffer(filter_hash: str):
    """Delete a specific buffer by its hash."""
    state = get_state()
    
    try:
        buffer_service = get_buffer_service()
        buffer_service.delete_buffer(filter_hash)
        
        return {
            "ok": True,
            "message": f"Buffer {filter_hash[:8]} deleted"
        }
    
    except Exception as e:
        state.logger.error(f"Failed to delete buffer: {e}")
        raise HTTPException(500, f"Failed to delete buffer: {str(e)}")


@router.delete("/buffer")
async def clear_all_buffers():
    """Clear all buffers."""
    state = get_state()
    
    try:
        buffer_service = get_buffer_service()
        buffer_service.clear_all_buffers()
        
        return {
            "ok": True,
            "message": "All buffers cleared"
        }
    
    except Exception as e:
        state.logger.error(f"Failed to clear buffers: {e}")
        raise HTTPException(500, f"Failed to clear buffers: {str(e)}")