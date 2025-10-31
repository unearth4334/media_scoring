"""Search router for database-powered search functionality."""

import json
import subprocess
import tempfile
from pathlib import Path
from typing import List, Dict, Optional

from fastapi import APIRouter, HTTPException, Request, Query, UploadFile, File
from pydantic import BaseModel

from ..state import get_state
from ..database.service import DatabaseService
from ..utils.hashing import compute_perceptual_hash

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


class PhashSearchRequest(BaseModel):
    """Request model for PHASH similarity search."""
    user_path: Optional[str] = None
    phash: Optional[str] = None
    max_results: int = 10
    max_distance: int = 10
    # Filter options
    file_types: Optional[List[str]] = None
    min_score: Optional[int] = None
    max_score: Optional[int] = None
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    nsfw_filter: Optional[str] = None


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


@router.post("/similar/by-path")
async def search_similar_by_path(request: PhashSearchRequest):
    """Search for similar images by user path."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    if not request.user_path:
        raise HTTPException(400, "user_path is required")
    
    try:
        # Get user_path_prefix from config
        user_path_prefix = state.settings.get('user_path_prefix', '')
        
        # Strip the user_path_prefix to get file_path
        if user_path_prefix and request.user_path.startswith(user_path_prefix):
            file_path_str = request.user_path[len(user_path_prefix):]
            # Remove leading slash if present
            file_path_str = file_path_str.lstrip('/')
        else:
            # If prefix doesn't match, treat user_path as relative to video_dir
            file_path_str = request.user_path
        
        # Try to find the file in the database
        with state.get_database_service() as db:
            # Query by file_path
            from ..database.models import MediaFile
            media_file = db.session.query(MediaFile).filter(
                MediaFile.file_path.like(f"%{file_path_str}")
            ).all()
            
            if not media_file:
                raise HTTPException(404, f"Image not found in database: {file_path_str}")
            
            if len(media_file) > 1:
                raise HTTPException(400, f"Multiple images found matching path: {file_path_str}")
            
            media_file = media_file[0]
            
            if not media_file.phash:
                raise HTTPException(400, f"Image has no PHASH value in database")
            
            # Parse date filters
            from datetime import datetime
            start_date = None
            end_date = None
            if request.date_start:
                start_date = datetime.fromisoformat(request.date_start)
            if request.date_end:
                end_date = datetime.fromisoformat(request.date_end)
            
            # Find similar files with filters
            similar_files_with_distance = db.find_similar_files_by_hash(
                media_file.phash, 
                threshold=request.max_distance,
                file_types=request.file_types,
                min_score=request.min_score,
                max_score=request.max_score,
                start_date=start_date,
                end_date=end_date,
                nsfw_filter=request.nsfw_filter
            )
            
            results = []
            for similar_file, distance in similar_files_with_distance:
                if similar_file.id == media_file.id:
                    continue  # Skip the search image itself
                
                results.append({
                    "name": similar_file.filename,
                    "path": similar_file.file_path,
                    "score": similar_file.score,
                    "file_type": similar_file.file_type,
                    "extension": similar_file.extension,
                    "phash": similar_file.phash,
                    "distance": distance,
                    "updated_at": similar_file.updated_at.isoformat() if similar_file.updated_at else None
                })
            
            # Sort by distance
            results.sort(key=lambda x: x['distance'])
            
            # Limit results
            results = results[:request.max_results]
            
            return {
                "search_image": {
                    "name": media_file.filename,
                    "path": media_file.file_path,
                    "phash": media_file.phash
                },
                "results": results,
                "total": len(results)
            }
    
    except HTTPException:
        raise
    except Exception as e:
        state.logger.error(f"PHASH search by path failed: {e}")
        raise HTTPException(500, f"PHASH search failed: {str(e)}")


@router.post("/similar/by-upload")
async def search_similar_by_upload(
    file: UploadFile = File(...),
    max_results: int = Query(10, ge=1, le=100),
    max_distance: int = Query(10, ge=1, le=64),
    file_types: Optional[str] = Query(None),
    min_score: Optional[int] = Query(None),
    max_score: Optional[int] = Query(None),
    date_start: Optional[str] = Query(None),
    date_end: Optional[str] = Query(None),
    nsfw_filter: Optional[str] = Query(None)
):
    """Search for similar images by uploading an image."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    # Validate file type
    if not file.content_type or not file.content_type.startswith('image/'):
        raise HTTPException(400, "File must be an image")
    
    try:
        # Save uploaded file to temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=Path(file.filename).suffix) as tmp_file:
            content = await file.read()
            tmp_file.write(content)
            tmp_file_path = Path(tmp_file.name)
        
        try:
            # Compute PHASH for uploaded image
            phash = compute_perceptual_hash(tmp_file_path)
            if not phash:
                raise HTTPException(500, "Failed to compute PHASH for uploaded image")
            
            # Parse file types
            file_types_list = None
            if file_types:
                file_types_list = [ft.strip() for ft in file_types.split(',')]
            
            # Parse date filters
            from datetime import datetime
            start_date = None
            end_date = None
            if date_start:
                start_date = datetime.fromisoformat(date_start)
            if date_end:
                end_date = datetime.fromisoformat(date_end)
            
            # Find similar files
            with state.get_database_service() as db:
                similar_files_with_distance = db.find_similar_files_by_hash(
                    phash, 
                    threshold=max_distance,
                    file_types=file_types_list,
                    min_score=min_score,
                    max_score=max_score,
                    start_date=start_date,
                    end_date=end_date,
                    nsfw_filter=nsfw_filter
                )
                
                results = []
                for similar_file, distance in similar_files_with_distance:
                    results.append({
                        "name": similar_file.filename,
                        "path": similar_file.file_path,
                        "score": similar_file.score,
                        "file_type": similar_file.file_type,
                        "extension": similar_file.extension,
                        "phash": similar_file.phash,
                        "distance": distance,
                        "updated_at": similar_file.updated_at.isoformat() if similar_file.updated_at else None
                    })
                
                # Sort by distance
                results.sort(key=lambda x: x['distance'])
                
                # Limit results
                results = results[:max_results]
                
                return {
                    "search_image": {
                        "filename": file.filename,
                        "temp_path": str(tmp_file_path),
                        "phash": phash
                    },
                    "results": results,
                    "total": len(results)
                }
        
        finally:
            # Clean up temporary file
            if tmp_file_path.exists():
                tmp_file_path.unlink()
    
    except HTTPException:
        raise
    except Exception as e:
        state.logger.error(f"PHASH search by upload failed: {e}")
        raise HTTPException(500, f"PHASH search by upload failed: {str(e)}")


@router.get("/file-info-by-path")
async def get_file_info_by_path(user_path: str = Query(...)):
    """Get file information by user path for PHASH search."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    try:
        # Get user_path_prefix from config
        user_path_prefix = state.settings.get('user_path_prefix', '')
        
        # Strip the user_path_prefix to get file_path
        if user_path_prefix and user_path.startswith(user_path_prefix):
            file_path_str = user_path[len(user_path_prefix):]
            # Remove leading slash if present
            file_path_str = file_path_str.lstrip('/')
        else:
            # If prefix doesn't match, treat user_path as relative to video_dir
            file_path_str = user_path
        
        # Try to find the file in the database
        with state.get_database_service() as db:
            # Query by file_path
            from ..database.models import MediaFile
            media_file = db.session.query(MediaFile).filter(
                MediaFile.file_path.like(f"%{file_path_str}")
            ).all()
            
            if not media_file:
                raise HTTPException(404, f"Image not found in database: {file_path_str}")
            
            if len(media_file) > 1:
                raise HTTPException(400, f"Multiple images found matching path: {file_path_str}")
            
            media_file = media_file[0]
            
            if not media_file.phash:
                raise HTTPException(400, f"Image has no PHASH value in database")
            
            return {
                "name": media_file.filename,
                "path": media_file.file_path,
                "phash": media_file.phash,
                "file_type": media_file.file_type,
                "extension": media_file.extension
            }
    
    except HTTPException:
        raise
    except Exception as e:
        state.logger.error(f"Failed to get file info by path: {e}")
        raise HTTPException(500, f"Failed to get file info: {str(e)}")