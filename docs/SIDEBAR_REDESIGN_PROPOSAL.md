# Sidebar Content Retrieval Redesign Proposal

## Executive Summary

This document proposes a comprehensive redesign of the sidebar content retrieval system to resolve persistent issues with filtering and sorting in database mode. The current implementation suffers from a fundamental architectural disconnect between the frontend filtering logic and backend database queries, resulting in sort criteria failing to be applied correctly.

## Problem Statement

### Current Issues

1. **Sort Criteria Not Applied**: When database mode is enabled, sort settings (name, date, size, rating) selected in the UI are not transmitted to the backend, causing the sidebar to always display items in database default order.

2. **Dual Filtering Logic**: The application maintains two separate filtering implementations:
   - `applyClientSideFilters()` - Works on in-memory array of videos
   - `applyDatabaseFilters()` - Calls `/api/filter` endpoint but doesn't pass sort parameters

3. **Incomplete API Contract**: The `/api/filter` endpoint accepts filtering parameters (min_score, max_score, file_types, dates) but has no parameters for sorting or ordering.

4. **Frontend State Management**: The `searchToolbarFilters` object tracks sort field and direction, but this state is never serialized and sent to the backend.

5. **Database Query Limitations**: The `DatabaseService.get_all_media_files()` method has hardcoded sorting (`order_by(desc(MediaFile.score), MediaFile.filename)`) with no flexibility for dynamic sort criteria.

## Current Architecture Analysis

### Data Flow (Database Mode)

```
User Interaction
    ↓
searchToolbarFilters.sort = 'rating'
searchToolbarFilters.sortDirection = 'desc'
    ↓
applyCurrentFilters()
    ↓
applyDatabaseFilters()
    ↓
fetch('/api/filter', { file_types, min_score, max_score, dates })  ← Sort params NOT sent
    ↓
filter_videos() endpoint
    ↓
db.get_all_media_files(min_score, max_score, file_types, start_date, end_date)  ← No sort params
    ↓
Hardcoded: order_by(desc(MediaFile.score), MediaFile.filename)
    ↓
Return videos array to frontend
    ↓
Frontend receives unsorted data
    ↓
applySortFilter() attempts client-side sort  ← But 'date' and 'size' fields missing!
    ↓
Sidebar renders with incomplete/incorrect sorting
```

### Key Problems in Flow

1. **Missing Data**: Frontend sort by 'date' or 'size' requires metadata (file creation date, file size) that isn't included in the `/api/filter` response.

2. **Inefficient**: Loading all filtered records then sorting client-side defeats the purpose of database queries for large datasets.

3. **Inconsistent**: Client-side mode supports all sort options, but database mode only properly supports 'name' and 'rating'.

4. **Race Conditions**: The `videos` array is replaced by API response, then `filtered` array is created and sorted client-side, creating potential state inconsistencies.

## Proposed Solution

### Design Principles

1. **Single Source of Truth**: Database queries should be the authoritative source for filtered and sorted data.
2. **Complete Data**: API responses must include all fields needed for UI rendering and client-side operations.
3. **Explicit Contracts**: API parameters and responses should be clearly defined with validation.
4. **Performance**: Leverage database indexing and query optimization for sorting large datasets.
5. **Backward Compatibility**: Non-database mode should continue to work as-is.

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         Frontend Layer                           │
├─────────────────────────────────────────────────────────────────┤
│  Search Toolbar                                                  │
│  - Maintains UI state (searchToolbarFilters)                    │
│  - Triggers filtering on user interaction                       │
│  - Renders pill badges with current filter values              │
└─────────────────┬───────────────────────────────────────────────┘
                  │
                  ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Filter Orchestrator                          │
│  applyCurrentFilters()                                          │
│  - Detects database vs client mode                             │
│  - Routes to appropriate handler                               │
└─────────────────┬───────────────────────────────────────────────┘
                  │
         ┌────────┴────────┐
         ↓                 ↓
┌────────────────┐  ┌─────────────────────────────────────────────┐
│  Client Mode   │  │          Database Mode                      │
│  Filter/Sort   │  │                                             │
└────────────────┘  │  1. Build FilterRequest from UI state       │
                    │     - filters: { min_score, file_types }    │
                    │     - sort: { field, direction }            │
                    │     - pagination: { offset, limit }         │
                    │                                             │
                    │  2. POST /api/filter with complete params   │
                    │                                             │
                    │  3. Backend applies filters + sort in SQL   │
                    │                                             │
                    │  4. Response includes complete metadata     │
                    │     - name, score, url, path                │
                    │     - created_at, file_size (for sort)      │
                    │     - width, height (for display)           │
                    │                                             │
                    │  5. Frontend uses response as-is            │
                    │     - No client-side re-sorting needed      │
                    │     - Update videos and filtered arrays     │
                    └─────────────────────────────────────────────┘
```

### Component Changes

#### 1. Frontend: Search Toolbar (`app/static/js/search-toolbar.js`)

**Changes to `applyDatabaseFilters()`:**

```javascript
async function applyDatabaseFilters() {
  console.log('Applying database filters with sort...', searchToolbarFilters);
  
  try {
    // Build comprehensive filter request
    const filterRequest = {
      // Existing filters
      file_types: searchToolbarFilters.filetype,
      start_date: searchToolbarFilters.dateStart ? 
        `${searchToolbarFilters.dateStart}T00:00:00Z` : null,
      end_date: searchToolbarFilters.dateEnd ? 
        `${searchToolbarFilters.dateEnd}T23:59:59Z` : null,
      
      // NEW: Add sorting parameters
      sort_field: searchToolbarFilters.sort,      // 'name', 'date', 'size', 'rating'
      sort_direction: searchToolbarFilters.sortDirection,  // 'asc' or 'desc'
      
      // NEW: Add pagination (future-proofing)
      offset: 0,
      limit: 1000  // Or null for all results
    };
    
    // Add rating filters
    if (searchToolbarFilters.rating !== 'none') {
      if (searchToolbarFilters.rating === 'unrated') {
        filterRequest.max_score = 0;
      } else {
        filterRequest.min_score = parseInt(searchToolbarFilters.rating);
      }
    }
    
    console.log('Filter request:', filterRequest);
    
    const response = await fetch('/api/filter', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filterRequest)
    });
    
    if (response.ok) {
      const data = await response.json();
      console.log('Filter response received:', data);
      
      // Backend returns pre-sorted results
      videos = data.videos;
      
      // Apply search filter client-side (filename search)
      if (searchToolbarFilters.search) {
        filtered = videos.filter(video => 
          video.name.toLowerCase().includes(searchToolbarFilters.search.toLowerCase())
        );
      } else {
        filtered = [...videos];
      }
      
      console.log('Filtered results:', filtered.length);
      
      // NO client-side sorting needed - backend did it!
      // applySortFilter(); ← REMOVE THIS
      
      // Update display
      if (typeof renderSidebar === 'function') {
        renderSidebar();
      }
      
      if (filtered.length > 0) {
        show(0);
      }
    } else {
      console.error('Filter request failed:', response.status, response.statusText);
      const errorText = await response.text();
      console.error('Error response:', errorText);
    }
  } catch (error) {
    console.error('Database filter failed:', error);
    // Fallback to client-side filtering
    applyClientSideFilters();
  }
}
```

**Key Changes:**
- Add `sort_field` and `sort_direction` to filter request
- Remove client-side `applySortFilter()` call - backend handles sorting
- Add optional pagination parameters for future scalability

#### 2. Backend: Filter Endpoint (`app/routers/media.py`)

**Enhanced FilterRequest Model:**

```python
from pydantic import BaseModel, Field
from typing import Optional, List
from enum import Enum

class SortField(str, Enum):
    """Valid sort fields for media files."""
    NAME = "name"
    DATE = "date"
    SIZE = "size"
    RATING = "rating"

class SortDirection(str, Enum):
    """Valid sort directions."""
    ASC = "asc"
    DESC = "desc"

class FilterRequest(BaseModel):
    """Request model for filtering media files."""
    # Filtering parameters
    min_score: Optional[int] = Field(None, ge=0, le=5)
    max_score: Optional[int] = Field(None, ge=0, le=5)
    file_types: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    
    # Sorting parameters
    sort_field: SortField = Field(SortField.NAME, description="Field to sort by")
    sort_direction: SortDirection = Field(SortDirection.ASC, description="Sort direction")
    
    # Pagination parameters (optional)
    offset: Optional[int] = Field(None, ge=0)
    limit: Optional[int] = Field(None, ge=1, le=10000)
```

**Updated `/api/filter` Endpoint:**

```python
@router.post("/filter")
async def filter_videos(request: FilterRequest):
    """Filter media files based on criteria with sorting."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    # Convert date strings to datetime objects
    from datetime import datetime
    start_date_obj = None
    end_date_obj = None
    
    if request.start_date:
        try:
            start_date_obj = datetime.fromisoformat(request.start_date.replace('Z', '+00:00'))
        except ValueError:
            pass
    
    if request.end_date:
        try:
            end_date_obj = datetime.fromisoformat(request.end_date.replace('Z', '+00:00'))
        except ValueError:
            pass
    
    try:
        db_service = state.get_database_service()
        if db_service is None:
            raise HTTPException(503, "Database service is not available")
            
        with db_service as db:
            # Call enhanced database method with sort parameters
            media_files = db.get_all_media_files(
                min_score=request.min_score,
                max_score=request.max_score,
                file_types=request.file_types,
                start_date=start_date_obj,
                end_date=end_date_obj,
                sort_field=request.sort_field,
                sort_direction=request.sort_direction,
                offset=request.offset,
                limit=request.limit
            )
            
            items = []
            for media_file in media_files:
                file_path = Path(media_file.file_path)
                relative_path = file_path.name
                
                items.append({
                    "name": media_file.filename,
                    "url": f"/media/{relative_path}",
                    "score": media_file.score or 0,
                    "path": media_file.file_path,
                    
                    # NEW: Include all metadata needed for sorting
                    "created_at": media_file.created_at.isoformat() if media_file.created_at else None,
                    "file_size": media_file.file_size,  # For size sorting
                    "file_type": media_file.file_type,
                    "extension": media_file.extension,
                    
                    # NEW: Include dimension metadata (useful for display)
                    "width": None,  # Will be populated from metadata if available
                    "height": None
                })
                
                # Optionally include dimensions from metadata
                metadata = db.get_media_metadata(file_path)
                if metadata:
                    items[-1]["width"] = metadata.width
                    items[-1]["height"] = metadata.height
            
            return {
                "videos": items,
                "count": len(items),
                "filters_applied": {
                    "min_score": request.min_score,
                    "max_score": request.max_score,
                    "file_types": request.file_types,
                    "start_date": request.start_date,
                    "end_date": request.end_date,
                    "sort_field": request.sort_field,
                    "sort_direction": request.sort_direction
                }
            }
    
    except Exception as e:
        state.logger.error(f"Filter failed: {e}")
        raise HTTPException(500, f"Filter failed: {str(e)}")
```

**Key Changes:**
- Use Pydantic model for request validation
- Accept `sort_field` and `sort_direction` parameters
- Pass sorting to database service layer
- Include `file_size` and `created_at` in response for sorting
- Optionally include dimension metadata

#### 3. Backend: Database Service (`app/database/service.py`)

**Enhanced `get_all_media_files()` Method:**

```python
from sqlalchemy import desc, asc

@log_db_operation("get_all_media_files")
def get_all_media_files(self, 
                       min_score: Optional[int] = None,
                       max_score: Optional[int] = None,
                       file_types: Optional[List[str]] = None,
                       start_date: Optional[datetime] = None,
                       end_date: Optional[datetime] = None,
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
        extensions = []
        for ext in file_types:
            if not ext.startswith('.'):
                extensions.append(f'.{ext}')
            else:
                extensions.append(ext)
        query = query.filter(MediaFile.extension.in_(extensions))
    
    # Apply date filters using created_at
    if start_date is not None:
        query = query.filter(MediaFile.created_at >= start_date)
    if end_date is not None:
        query = query.filter(MediaFile.created_at <= end_date)
    
    # Apply sorting
    sort_direction_func = desc if sort_direction == "desc" else asc
    
    if sort_field == "name":
        query = query.order_by(sort_direction_func(MediaFile.filename))
    elif sort_field == "date":
        # Sort by created_at, fallback to filename for ties
        query = query.order_by(
            sort_direction_func(MediaFile.created_at),
            asc(MediaFile.filename)
        )
    elif sort_field == "size":
        # Sort by file_size, fallback to filename for ties
        query = query.order_by(
            sort_direction_func(MediaFile.file_size),
            asc(MediaFile.filename)
        )
    elif sort_field == "rating":
        # Sort by score, fallback to filename for ties
        query = query.order_by(
            sort_direction_func(MediaFile.score),
            asc(MediaFile.filename)
        )
    else:
        # Default to filename sort
        query = query.order_by(asc(MediaFile.filename))
    
    # Apply pagination if specified
    if offset is not None:
        query = query.offset(offset)
    if limit is not None:
        query = query.limit(limit)
    
    return query.all()
```

**Key Changes:**
- Accept `sort_field` and `sort_direction` parameters
- Implement dynamic sorting based on field
- Use SQLAlchemy `asc()` and `desc()` for proper database sorting
- Add secondary sort by filename for consistent ordering
- Support pagination for large datasets

### Database Schema Considerations

The existing `MediaFile` model already has the necessary fields:

```python
class MediaFile(Base):
    __tablename__ = 'media_files'
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(512), nullable=False, index=True)  # ← For name sorting
    file_path = Column(String(1024), nullable=False, unique=True, index=True)
    file_size = Column(BigInteger)  # ← For size sorting
    created_at = Column(DateTime, default=datetime.utcnow, index=True)  # ← For date sorting
    score = Column(Integer, default=0, index=True)  # ← For rating sorting
    # ... other fields
```

**Recommendations:**
1. Ensure `created_at`, `score`, and `file_size` have database indexes for efficient sorting
2. Consider adding composite indexes for common filter+sort combinations:
   ```sql
   CREATE INDEX idx_score_filename ON media_files(score DESC, filename ASC);
   CREATE INDEX idx_created_filename ON media_files(created_at DESC, filename ASC);
   CREATE INDEX idx_size_filename ON media_files(file_size DESC, filename ASC);
   ```

### Migration Strategy

**Phase 1: Backend Enhancement (Week 1)**
1. Add Pydantic models for `FilterRequest` and `FilterResponse`
2. Update `/api/filter` endpoint to accept sort parameters
3. Enhance `DatabaseService.get_all_media_files()` with sorting logic
4. Add database indexes for performance
5. Write unit tests for sorting combinations

**Phase 2: Frontend Integration (Week 1-2)**
1. Update `applyDatabaseFilters()` to send sort parameters
2. Remove client-side sorting for database mode
3. Update response handling to use backend-sorted data
4. Test all sort combinations (name, date, size, rating × asc/desc)
5. Verify backward compatibility with client-side mode

**Phase 3: Testing & Validation (Week 2)**
1. Test with small datasets (< 100 files)
2. Test with medium datasets (100-1000 files)
3. Test with large datasets (> 1000 files)
4. Performance testing and query optimization
5. Cross-browser testing
6. Edge case testing (empty results, single result, etc.)

**Phase 4: Documentation & Deployment (Week 2-3)**
1. Update API documentation
2. Update user guide for database features
3. Create migration guide for existing deployments
4. Deploy to staging environment
5. Production deployment with rollback plan

## Benefits of Proposed Solution

### Performance
- **Database-Level Sorting**: Leverage PostgreSQL/SQLite query optimizer instead of JavaScript array sorting
- **Reduced Data Transfer**: Only send necessary fields, not entire metadata objects
- **Pagination Ready**: Infrastructure for handling large datasets efficiently

### Maintainability
- **Single Sorting Implementation**: Database handles all sorting, eliminating code duplication
- **Type Safety**: Pydantic models ensure request validation
- **Clear Contracts**: Explicit API parameters and responses
- **Easier Testing**: Sorting logic in one place (database layer)

### User Experience
- **Consistent Behavior**: Sorting works the same way in all modes
- **Faster Response**: Database indexing provides faster sorting for large datasets
- **Reliable Results**: No race conditions or state inconsistencies

### Future Extensions
- **Advanced Sorting**: Multi-field sorting (e.g., "sort by rating, then by date")
- **Saved Filters**: Store filter+sort combinations as presets
- **Smart Pagination**: Load results incrementally for very large collections
- **Search Integration**: Combine full-text search with sorting

## Risks and Mitigations

### Risk 1: Breaking Changes to API
**Mitigation**: Make sort parameters optional with sensible defaults. Existing clients continue to work without changes.

### Risk 2: Database Performance
**Mitigation**: Add appropriate indexes before deployment. Monitor query performance and add composite indexes as needed.

### Risk 3: Client-Side Mode Compatibility
**Mitigation**: Keep `applyClientSideFilters()` unchanged. Only modify database mode path.

### Risk 4: Migration Complexity
**Mitigation**: Use feature flags to enable new sorting incrementally. Provide rollback script.

## Testing Strategy

### Unit Tests
```python
# app/tests/test_database_service.py
def test_sort_by_name_ascending():
    files = db.get_all_media_files(sort_field="name", sort_direction="asc")
    names = [f.filename for f in files]
    assert names == sorted(names)

def test_sort_by_rating_descending():
    files = db.get_all_media_files(sort_field="rating", sort_direction="desc")
    scores = [f.score for f in files]
    assert scores == sorted(scores, reverse=True)

def test_sort_by_date_with_filter():
    files = db.get_all_media_files(
        min_score=3,
        sort_field="date",
        sort_direction="desc"
    )
    assert all(f.score >= 3 for f in files)
    # Verify descending date order
```

### Integration Tests
```javascript
// app/static/js/tests/test_search_toolbar.js
describe('Database Filtering with Sorting', () => {
  it('should send sort parameters to backend', async () => {
    searchToolbarFilters.sort = 'rating';
    searchToolbarFilters.sortDirection = 'desc';
    
    const fetchSpy = jest.spyOn(global, 'fetch');
    await applyDatabaseFilters();
    
    const callArgs = fetchSpy.mock.calls[0];
    const requestBody = JSON.parse(callArgs[1].body);
    
    expect(requestBody.sort_field).toBe('rating');
    expect(requestBody.sort_direction).toBe('desc');
  });
  
  it('should not re-sort results from backend', async () => {
    const mockResponse = {
      videos: [
        { name: 'z.png', score: 5 },
        { name: 'a.png', score: 3 }
      ]
    };
    
    global.fetch = jest.fn(() => Promise.resolve({
      ok: true,
      json: () => Promise.resolve(mockResponse)
    }));
    
    await applyDatabaseFilters();
    
    // Results should maintain backend order
    expect(filtered[0].name).toBe('z.png');
    expect(filtered[1].name).toBe('a.png');
  });
});
```

### Manual Test Cases

| Test Case | Steps | Expected Result |
|-----------|-------|----------------|
| Sort by Name (Asc) | Select "Name ↑" in toolbar | Sidebar shows A-Z order |
| Sort by Name (Desc) | Select "Name ↓" in toolbar | Sidebar shows Z-A order |
| Sort by Rating (Desc) | Select "Rating ↓" in toolbar | Sidebar shows 5★ → 1★ order |
| Sort by Date (Desc) | Select "Date ↓" in toolbar | Sidebar shows newest → oldest |
| Sort by Size (Asc) | Select "Size ↑" in toolbar | Sidebar shows smallest → largest |
| Filter + Sort | Filter "Rating ≥3", Sort "Date ↓" | Shows only 3★+ items, newest first |
| Empty Results | Filter with no matches | Shows empty state correctly |
| Change Sort While Filtered | Apply filter, then change sort | Maintains filter, updates order |

## Success Criteria

1. **Functional**: All 4 sort fields (name, date, size, rating) work correctly in both ascending and descending order
2. **Performance**: Sorting 1000 files completes in < 500ms
3. **Reliability**: No console errors, no incorrect ordering
4. **Compatibility**: Client-side mode continues to work as before
5. **Maintainability**: Sorting logic centralized in database layer

## Conclusion

The current sidebar content retrieval implementation suffers from a fundamental architectural flaw: the frontend tracking sort state that never reaches the backend. This proposal addresses the root cause by:

1. Extending the API contract to accept sort parameters
2. Implementing database-level sorting for efficiency
3. Removing redundant client-side sorting logic
4. Providing complete metadata in API responses

The solution is backward compatible, performant, and positions the application for future enhancements like pagination and advanced search.

## Appendix A: Current Code Issues

### Issue 1: Frontend Tracks Sort State But Never Uses It (Database Mode)

**File**: `app/static/js/search-toolbar.js` (Lines 216-240)

```javascript
// Sort field select - apply instantly
const sortSelect = document.getElementById('sort-select');
if (sortSelect) {
  sortSelect.addEventListener('change', () => {
    searchToolbarFilters.sort = sortSelect.value;  // ← Updates state
    updatePillValues();
    applyCurrentFilters();  // ← Calls applyDatabaseFilters()
  });
}

// Sort direction toggle buttons - apply instantly
const ascBtn = document.getElementById('sort-asc-btn');
const descBtn = document.getElementById('sort-desc-btn');
if (ascBtn && descBtn) {
  ascBtn.addEventListener('click', () => {
    searchToolbarFilters.sortDirection = 'asc';  // ← Updates state
    ascBtn.classList.add('active');
    descBtn.classList.remove('active');
    updatePillValues();
    applyCurrentFilters();  // ← Calls applyDatabaseFilters()
  });
  // ...
}
```

**Problem**: State is updated but never sent to backend in `applyDatabaseFilters()` (Lines 590-655).

### Issue 2: Client-Side Sort Missing Required Data

**File**: `app/static/js/search-toolbar.js` (Lines 464-496)

```javascript
function applySortFilter() {
  const sortBy = searchToolbarFilters.sort;
  const sortDirection = searchToolbarFilters.sortDirection;
  
  filtered.sort((a, b) => {
    let result;
    
    switch (sortBy) {
      case 'name':
        result = a.name.localeCompare(b.name);
        break;
      case 'date':
        // Note: This would require metadata from the backend
        result = a.name.localeCompare(b.name); // Fallback to name
        break;
      case 'size':
        // Note: This would require metadata from the backend  
        result = a.name.localeCompare(b.name); // Fallback to name
        break;
      case 'rating':
        const scoreA = a.score || 0;
        const scoreB = b.score || 0;
        result = scoreA - scoreB;
        break;
      default:
        result = a.name.localeCompare(b.name);
        break;
    }
    
    return sortDirection === 'desc' ? -result : result;
  });
}
```

**Problem**: Date and size sorting fall back to name because metadata isn't available in the video objects.

### Issue 3: Database Service Has Hardcoded Sorting

**File**: `app/database/service.py` (Line 118)

```python
return query.order_by(desc(MediaFile.score), MediaFile.filename).all()
```

**Problem**: Always sorts by score descending, ignoring user preferences.

## Appendix B: API Contract Definition

### Request Schema

```json
{
  "type": "object",
  "properties": {
    "min_score": {
      "type": "integer",
      "minimum": 0,
      "maximum": 5,
      "nullable": true
    },
    "max_score": {
      "type": "integer",
      "minimum": 0,
      "maximum": 5,
      "nullable": true
    },
    "file_types": {
      "type": "array",
      "items": {
        "type": "string",
        "enum": ["mp4", "png", "jpg", "jpeg"]
      },
      "nullable": true
    },
    "start_date": {
      "type": "string",
      "format": "date-time",
      "nullable": true
    },
    "end_date": {
      "type": "string",
      "format": "date-time",
      "nullable": true
    },
    "sort_field": {
      "type": "string",
      "enum": ["name", "date", "size", "rating"],
      "default": "name"
    },
    "sort_direction": {
      "type": "string",
      "enum": ["asc", "desc"],
      "default": "asc"
    },
    "offset": {
      "type": "integer",
      "minimum": 0,
      "nullable": true
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000,
      "nullable": true
    }
  }
}
```

### Response Schema

```json
{
  "type": "object",
  "required": ["videos", "count"],
  "properties": {
    "videos": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["name", "url", "score"],
        "properties": {
          "name": { "type": "string" },
          "url": { "type": "string" },
          "score": { "type": "integer", "minimum": -1, "maximum": 5 },
          "path": { "type": "string" },
          "created_at": { "type": "string", "format": "date-time", "nullable": true },
          "file_size": { "type": "integer", "nullable": true },
          "file_type": { "type": "string", "enum": ["image", "video"] },
          "extension": { "type": "string" },
          "width": { "type": "integer", "nullable": true },
          "height": { "type": "integer", "nullable": true }
        }
      }
    },
    "count": { "type": "integer" },
    "filters_applied": {
      "type": "object",
      "properties": {
        "min_score": { "type": "integer", "nullable": true },
        "max_score": { "type": "integer", "nullable": true },
        "file_types": { "type": "array", "nullable": true },
        "start_date": { "type": "string", "nullable": true },
        "end_date": { "type": "string", "nullable": true },
        "sort_field": { "type": "string" },
        "sort_direction": { "type": "string" }
      }
    }
  }
}
```

## Appendix C: Database Index Recommendations

```sql
-- Index for name sorting (already exists via PRIMARY KEY/UNIQUE on filename)
CREATE INDEX IF NOT EXISTS idx_media_filename ON media_files(filename);

-- Index for date sorting
CREATE INDEX IF NOT EXISTS idx_media_created_at ON media_files(created_at DESC);

-- Index for rating sorting  
CREATE INDEX IF NOT EXISTS idx_media_score ON media_files(score DESC);

-- Index for size sorting
CREATE INDEX IF NOT EXISTS idx_media_file_size ON media_files(file_size DESC);

-- Composite indexes for common filter+sort combinations
CREATE INDEX IF NOT EXISTS idx_score_created ON media_files(score DESC, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_score_size ON media_files(score DESC, file_size DESC);
CREATE INDEX IF NOT EXISTS idx_extension_score ON media_files(extension, score DESC);
CREATE INDEX IF NOT EXISTS idx_extension_created ON media_files(extension, created_at DESC);
```

## Appendix D: Implementation Checklist

- [ ] Backend: Create `FilterRequest` Pydantic model with sort parameters
- [ ] Backend: Update `/api/filter` endpoint signature
- [ ] Backend: Enhance `DatabaseService.get_all_media_files()` with sorting
- [ ] Backend: Add database indexes for sort fields
- [ ] Backend: Write unit tests for all sort combinations
- [ ] Frontend: Update `applyDatabaseFilters()` to send sort parameters
- [ ] Frontend: Remove `applySortFilter()` call in database mode
- [ ] Frontend: Update response handling to preserve backend order
- [ ] Frontend: Add integration tests for sort functionality
- [ ] Testing: Manual testing of all sort field × direction combinations
- [ ] Testing: Performance testing with 1000+ files
- [ ] Documentation: Update API documentation
- [ ] Documentation: Update user guide
- [ ] Deployment: Create migration script for database indexes
- [ ] Deployment: Deploy to staging and validate
- [ ] Deployment: Production deployment with monitoring

---

**Document Version**: 1.0  
**Author**: GitHub Copilot  
**Date**: 2025-01-XX  
**Status**: Proposal for Review
