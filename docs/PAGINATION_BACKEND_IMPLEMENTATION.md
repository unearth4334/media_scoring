# Backend Pagination Implementation - Phase 1

## Overview

Implemented server-side pagination for the Media Scoring application to address mobile performance issues with large datasets. This is Phase 1 of the comprehensive performance optimization plan.

**Status**: ✅ COMPLETE (Backend)  
**Branch**: `feature/pagination-phase1`  
**Test Results**: 4/4 tests passed

## Problem Statement

The application was loading ALL media files at once, causing:
- 30-45 second initial load times with 10,000 files
- 500MB+ memory usage
- Mobile browser freezing/crashing
- Poor scroll performance (10-20 FPS)

## Solution

Implemented page-based API endpoint that returns small chunks of data (default: 100 items per page) instead of loading everything at once.

## Implementation Details

### 1. Database Service Count Method

**File**: `app/database/service.py` (Line 214)  
**Method**: `get_media_files_count()`

```python
@log_db_operation
async def get_media_files_count(
    self,
    min_score: Optional[int] = None,
    max_score: Optional[int] = None,
    file_types: Optional[List[str]] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    nsfw_filter: Optional[str] = None
) -> int:
    """
    Count media files matching filters without loading the data.
    Uses same filter logic as get_all_media_files() for consistency.
    
    Returns:
        int: Count of matching records
    """
```

**Features**:
- Efficient counting using `func.count(MediaFile.id)`
- Applies same filters as main query for consistency
- No LIMIT/OFFSET (counts all matching records)
- Decorated with `@log_db_operation` for monitoring

### 2. Pagination Request Model

**File**: `app/routers/media.py` (Lines 54-68)  
**Model**: `PaginationRequest`

```python
class PaginationRequest(BaseModel):
    # Pagination
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(100, ge=10, le=500, description="Items per page")
    
    # Filtering parameters
    min_score: Optional[int] = Field(None, ge=0, le=5)
    max_score: Optional[int] = Field(None, ge=0, le=5)
    file_types: Optional[List[str]] = None
    start_date: Optional[str] = None  # ISO format
    end_date: Optional[str] = None    # ISO format
    nsfw_filter: Optional[str] = None  # 'all', 'sfw', 'nsfw'
    
    # Sorting parameters
    sort_field: SortField = Field(SortField.NAME)
    sort_direction: SortDirection = Field(SortDirection.ASC)
```

**Validation**:
- Page: Must be ≥ 1 (1-indexed)
- Page size: 10-500 items (default: 100)
- Scores: 0-5 range
- Dates: ISO format strings (parsed in endpoint)

### 3. Paginated Endpoint

**File**: `app/routers/media.py` (Lines 200-325)  
**Endpoint**: `POST /api/videos/paginated`

```python
@router.post("/videos/paginated")
async def get_paginated_videos(request: PaginationRequest):
    """
    Get paginated list of videos with filtering and sorting.
    
    Returns:
        {
            "items": [...],           # Array of media file objects
            "pagination": {...},      # Pagination metadata
            "filters_applied": {...}, # Active filters
            "sorting": {...}          # Sort configuration
        }
    """
```

**Logic Flow**:
1. Validate request (Pydantic automatic)
2. Check database mode enabled (503 if not)
3. Parse date filters with error handling (400 on invalid format)
4. Get total count: `db.get_media_files_count()`
5. Calculate pagination:
   - `offset = (page - 1) * page_size`
   - `total_pages = ceil(total_count / page_size)`
6. Query paginated data: `db.get_all_media_files(offset=offset, limit=page_size)`
7. Format response with rich metadata

**Response Structure**:

```json
{
  "items": [
    {
      "name": "example.mp4",
      "url": "/media/example.mp4",
      "score": 3,
      "path": "/full/path/example.mp4",
      "created_at": "2025-01-13T05:41:35.347587",
      "original_created_at": null,
      "file_type": "video",
      "extension": ".mp4",
      "file_size": 1234567,
      "nsfw": false
    }
  ],
  "pagination": {
    "page": 1,
    "page_size": 100,
    "total_items": 523,
    "total_pages": 6,
    "has_next": true,
    "has_prev": false,
    "start_index": 1,
    "end_index": 100
  },
  "filters_applied": {
    "min_score": 3,
    "max_score": null,
    "file_types": ["mp4"],
    "start_date": "2025-01-01T00:00:00",
    "end_date": null,
    "nsfw_filter": "sfw"
  },
  "sorting": {
    "sort_field": "rating",
    "sort_direction": "desc"
  }
}
```

## Testing

### Test Suite

Created comprehensive test script: `test_pagination.py`

**Test Cases**:
1. ✅ Basic pagination (no filters)
2. ✅ Filtered pagination (min_score + sorting)
3. ✅ Multiple pages navigation
4. ✅ Edge cases (page beyond total)

**Results**: 4/4 tests passed

### Manual Testing

```bash
# Start the server with database enabled
export DATABASE_URL="postgresql://media_user:media_password@localhost:5432/media_scoring"
python run.py --dir ./media --enable-database

# Test basic pagination
curl -X POST http://127.0.0.1:7862/api/videos/paginated \
  -H "Content-Type: application/json" \
  -d '{"page": 1, "page_size": 10}'

# Test with filters and sorting
curl -X POST http://127.0.0.1:7862/api/videos/paginated \
  -H "Content-Type: application/json" \
  -d '{
    "page": 1,
    "page_size": 100,
    "min_score": 3,
    "file_types": ["mp4"],
    "sort_field": "rating",
    "sort_direction": "desc"
  }'
```

## Performance Impact

### Expected Improvements (Phase 1 Backend Only)

When frontend is integrated:

- **Initial Load Time**: 30-45s → 2-3s (90% reduction)
- **Memory Usage**: 500MB → 50MB (90% reduction)  
- **Network Payload**: 10MB → 100KB per page (99% reduction)
- **Database Query Time**: ~5s → ~50ms per page (99% reduction)

### Current Limitations

- Frontend still loads all files via `/api/videos`
- No UI changes yet
- Performance benefits realized only after frontend integration

## Next Steps - Frontend Integration

### Phase 1B: Frontend Pagination (Current Branch)

1. **Update loadVideos() function** (app.js line 1427)
   - Replace `/api/videos` with `/api/videos/paginated`
   - Add state: `currentPage`, `pageSize`, `totalPages`
   - Initial page load: `page=1, page_size=100`

2. **Implement Infinite Scroll**
   - Add scroll event listener to sidebar
   - Load next page when user scrolls to bottom
   - Append new items to existing list
   - Show loading indicator during fetch

3. **Update Filter/Sort Handlers**
   - Reset `currentPage = 1` when filters change
   - Clear existing items before loading filtered results
   - Maintain sort state across page loads

4. **Add Loading States**
   - Initial load spinner
   - Page transition indicators
   - "Loading more..." at scroll bottom
   - "No more items" at end

### Phase 2: Virtual Scrolling (Next Branch)

- Render only visible items in DOM
- Maintain scroll position with spacer elements
- Recycle DOM nodes for better performance
- Target: 60 FPS scroll on mobile

### Phase 3: Tile View Optimization (Future)

- Lazy render grid cells
- Intersection observer for visibility
- Progressive thumbnail loading
- Virtualized grid component

## Architecture Notes

### Design Decisions

1. **Page-based vs Cursor-based**: Chose page-based for simplicity and better UX (page numbers)
2. **Default page_size: 100**: Balance between request count and payload size
3. **Max page_size: 500**: Prevent abuse while allowing flexibility
4. **Database-only**: Filesystem mode not supported for pagination (complexity)
5. **Filter reuse**: Uses existing `get_all_media_files()` logic for consistency

### API Compatibility

- New endpoint does NOT break existing `/api/videos` endpoint
- Frontend can gradually migrate to paginated endpoint
- Both endpoints can coexist during transition

### Database Requirements

- **PostgreSQL required**: Application no longer supports SQLite
- Pagination requires database mode (`--enable-database`)
- Set `DATABASE_URL` environment variable
- Docker Compose automatically configures database

## Usage Examples

### Python (Requests)

```python
import requests

response = requests.post(
    "http://127.0.0.1:7862/api/videos/paginated",
    json={
        "page": 1,
        "page_size": 100,
        "min_score": 3,
        "sort_field": "rating",
        "sort_direction": "desc"
    }
)

data = response.json()
items = data["items"]
total_pages = data["pagination"]["total_pages"]
has_next = data["pagination"]["has_next"]
```

### JavaScript (Fetch)

```javascript
async function loadPage(page, pageSize = 100, filters = {}) {
    const response = await fetch('/api/videos/paginated', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            page,
            page_size: pageSize,
            ...filters
        })
    });
    
    const data = await response.json();
    return data;
}

// Usage
const result = await loadPage(1, 100, {
    min_score: 3,
    sort_field: 'rating',
    sort_direction: 'desc'
});
```

## Troubleshooting

### Common Issues

1. **503 Service Unavailable**
   - Cause: Database mode not enabled
   - Solution: Add `--enable-database` flag and set `DATABASE_URL`

2. **400 Bad Request (Invalid date format)**
   - Cause: Date string not in ISO format
   - Solution: Use format like "2025-01-13T00:00:00" or "2025-01-13"

3. **422 Validation Error**
   - Cause: Invalid parameter values (e.g., page_size < 10)
   - Solution: Check validation constraints in PaginationRequest model

4. **Empty Results on Page 2+**
   - Cause: Not enough data to fill multiple pages
   - Solution: Reduce page_size or add more test data

## Files Modified

1. **app/database/service.py** (538 → 592 lines)
   - Added: `get_media_files_count()` method (54 lines)

2. **app/routers/media.py** (863 → 1007 lines)  
   - Added: `PaginationRequest` model (15 lines)
   - Added: `/api/videos/paginated` endpoint (126 lines)

3. **test_pagination.py** (NEW)
   - Comprehensive test suite (200+ lines)

## Validation

### Code Quality
- ✅ No syntax errors
- ✅ Type hints consistent
- ✅ Pydantic validation working
- ✅ Error handling complete

### Functionality
- ✅ Basic pagination works
- ✅ Filtering applies correctly
- ✅ Sorting functions properly
- ✅ Edge cases handled
- ✅ Pagination metadata accurate

### Performance
- ✅ Count query efficient (no data loading)
- ✅ Paginated query uses offset/limit
- ✅ Response size appropriate (~10KB for 100 items)

## References

- **Original Issue**: Mobile performance with 5,000+ files
- **Planning Document**: `docs/PERFORMANCE_OPTIMIZATION_PLAN.md`
- **Feature Branch**: `feature/pagination-phase1`
- **Related Endpoints**: 
  - Existing: `GET /api/videos`
  - Existing: `POST /api/filter`
  - New: `POST /api/videos/paginated`

---

**Status**: ✅ Backend implementation complete  
**Next Task**: Frontend integration (Phase 1B)  
**Owner**: Development Team  
**Last Updated**: 2025-01-13
