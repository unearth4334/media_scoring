"""Search router for database-powered search functionality."""

import json
import subprocess
from pathlib import Path
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Query
from pydantic import BaseModel

from ..state import get_state
from ..database.service import DatabaseService

router = APIRouter(prefix="/api/search")


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
        with state.get_database_service() as db:
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