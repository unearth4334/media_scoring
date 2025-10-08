# Sidebar Redesign Quick Reference

This is a condensed reference guide for the [Sidebar Content Retrieval Redesign Proposal](SIDEBAR_REDESIGN_PROPOSAL.md).

## The Problem (One-Liner)

**Sort settings are tracked in the frontend but never sent to the backend, and the database returns hardcoded-sorted results.**

## The Solution (One-Liner)

**Add `sort_field` and `sort_direction` parameters to the `/api/filter` endpoint and implement database-level sorting.**

## Key Changes Summary

### 1. Frontend (JavaScript)
**File**: `app/static/js/search-toolbar.js`

```diff
async function applyDatabaseFilters() {
  const filterRequest = {
    file_types: searchToolbarFilters.filetype,
    start_date: searchToolbarFilters.dateStart ? `${searchToolbarFilters.dateStart}T00:00:00Z` : null,
    end_date: searchToolbarFilters.dateEnd ? `${searchToolbarFilters.dateEnd}T23:59:59Z` : null,
+   sort_field: searchToolbarFilters.sort,
+   sort_direction: searchToolbarFilters.sortDirection,
  };
  
  // ... send to backend ...
  
  if (response.ok) {
    const data = await response.json();
    videos = data.videos;
    filtered = [...videos];
-   applySortFilter(); // ← REMOVE: Backend already sorted
  }
}
```

### 2. Backend API (Python)
**File**: `app/routers/media.py`

```diff
+from pydantic import BaseModel, Field
+from enum import Enum

+class SortField(str, Enum):
+    NAME = "name"
+    DATE = "date"
+    SIZE = "size"
+    RATING = "rating"

+class FilterRequest(BaseModel):
+    min_score: Optional[int] = None
+    max_score: Optional[int] = None
+    file_types: Optional[List[str]] = None
+    start_date: Optional[str] = None
+    end_date: Optional[str] = None
+    sort_field: SortField = Field(SortField.NAME)
+    sort_direction: str = Field("asc")

@router.post("/filter")
-async def filter_videos(req: Request):
+async def filter_videos(request: FilterRequest):
    state = get_state()
-   data = await req.json()
    
    with db_service as db:
        media_files = db.get_all_media_files(
-           min_score=data.get("min_score"),
+           min_score=request.min_score,
+           sort_field=request.sort_field,
+           sort_direction=request.sort_direction
        )
```

### 3. Database Service (Python)
**File**: `app/database/service.py`

```diff
def get_all_media_files(self, 
                       min_score: Optional[int] = None,
                       max_score: Optional[int] = None,
+                      sort_field: str = "name",
+                      sort_direction: str = "asc") -> List[MediaFile]:
    query = self.session.query(MediaFile)
    
    # Apply filters...
    
-   return query.order_by(desc(MediaFile.score), MediaFile.filename).all()
+   # Dynamic sorting
+   sort_func = desc if sort_direction == "desc" else asc
+   
+   if sort_field == "name":
+       query = query.order_by(sort_func(MediaFile.filename))
+   elif sort_field == "date":
+       query = query.order_by(sort_func(MediaFile.created_at))
+   elif sort_field == "size":
+       query = query.order_by(sort_func(MediaFile.file_size))
+   elif sort_field == "rating":
+       query = query.order_by(sort_func(MediaFile.score))
+   
+   return query.all()
```

## Before vs After Comparison

### Before (Broken)
```
User clicks "Sort by Rating ↓"
    ↓
searchToolbarFilters.sort = 'rating'  ← Updated
searchToolbarFilters.sortDirection = 'desc'  ← Updated
    ↓
applyDatabaseFilters()
    ↓
fetch('/api/filter', { file_types, min_score })  ← Sort NOT sent!
    ↓
Backend: ORDER BY score DESC, filename  ← Hardcoded
    ↓
Frontend: applySortFilter()  ← Tries to re-sort client-side
    ↓
Result: Inconsistent/incorrect order 🔴
```

### After (Fixed)
```
User clicks "Sort by Rating ↓"
    ↓
searchToolbarFilters.sort = 'rating'  ← Updated
searchToolbarFilters.sortDirection = 'desc'  ← Updated
    ↓
applyDatabaseFilters()
    ↓
fetch('/api/filter', { 
  file_types, 
  min_score,
  sort_field: 'rating',     ← NEW: Sent!
  sort_direction: 'desc'    ← NEW: Sent!
})
    ↓
Backend: ORDER BY score DESC  ← Dynamic!
    ↓
Frontend: Use response as-is  ← No re-sorting!
    ↓
Result: Correct sort order ✅
```

## Implementation Steps

### Phase 1: Backend (1-2 days)
1. Create `FilterRequest` Pydantic model
2. Update `/api/filter` endpoint
3. Add sorting to `get_all_media_files()`
4. Write unit tests

### Phase 2: Frontend (1 day)
1. Update `applyDatabaseFilters()` to send sort params
2. Remove client-side `applySortFilter()` call
3. Test all sort combinations

### Phase 3: Database (1 day)
1. Add indexes for `created_at`, `file_size`, `score`
2. Test query performance

### Phase 4: Testing & Deploy (1-2 days)
1. Manual testing
2. Performance validation
3. Documentation updates
4. Deploy to production

**Total Estimated Time**: 4-6 days

## Testing Checklist

- [ ] Sort by Name (Ascending) - A to Z
- [ ] Sort by Name (Descending) - Z to A
- [ ] Sort by Rating (Descending) - 5★ to 1★
- [ ] Sort by Rating (Ascending) - 1★ to 5★
- [ ] Sort by Date (Descending) - Newest first
- [ ] Sort by Date (Ascending) - Oldest first
- [ ] Sort by Size (Descending) - Largest first
- [ ] Sort by Size (Ascending) - Smallest first
- [ ] Filter + Sort combination (e.g., Rating ≥3, sorted by Date)
- [ ] Performance with 1000+ files (< 500ms)

## Database Indexes to Add

```sql
CREATE INDEX IF NOT EXISTS idx_media_created_at ON media_files(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_media_score ON media_files(score DESC);
CREATE INDEX IF NOT EXISTS idx_media_file_size ON media_files(file_size DESC);
```

## API Request Example

### Before
```json
POST /api/filter
{
  "file_types": ["png", "jpg"],
  "min_score": 3
}
```

### After
```json
POST /api/filter
{
  "file_types": ["png", "jpg"],
  "min_score": 3,
  "sort_field": "rating",
  "sort_direction": "desc"
}
```

## API Response Enhancement

### Before
```json
{
  "videos": [
    {
      "name": "image.png",
      "url": "/media/image.png",
      "score": 4
    }
  ]
}
```

### After
```json
{
  "videos": [
    {
      "name": "image.png",
      "url": "/media/image.png",
      "score": 4,
      "created_at": "2025-01-01T12:00:00Z",
      "file_size": 1024000,
      "width": 1920,
      "height": 1080
    }
  ],
  "filters_applied": {
    "sort_field": "rating",
    "sort_direction": "desc"
  }
}
```

## Files to Modify

| File | Lines | Change Type |
|------|-------|-------------|
| `app/static/js/search-toolbar.js` | ~590-655 | Modify: Add sort params to request |
| `app/routers/media.py` | ~52-129 | Modify: Add Pydantic model & sort handling |
| `app/database/service.py` | ~121-152 | Modify: Add dynamic sorting logic |
| `app/database/models.py` | N/A | No change (fields already exist) |

**Total Impact**: ~3 files, ~100 lines of code changes

## Success Metrics

✅ **Functional**: All 4 sort fields × 2 directions = 8 combinations work correctly  
✅ **Performance**: Sorting 1000 files completes in < 500ms  
✅ **Reliability**: No console errors, consistent behavior  
✅ **Compatibility**: Client-side mode unchanged  

## Rollback Plan

If issues occur:
1. Revert frontend changes (make sort params optional)
2. Backend will use defaults, existing functionality preserved
3. No data loss - only sorting behavior affected

## Related Documents

- **Full Proposal**: [SIDEBAR_REDESIGN_PROPOSAL.md](SIDEBAR_REDESIGN_PROPOSAL.md)
- **Database Architecture**: [DATABASE.md](DATABASE.md)
- **Development Guide**: [DEVELOPMENT.md](DEVELOPMENT.md)

---

**Quick Reference Version**: 1.0  
**Last Updated**: 2025-01-XX
