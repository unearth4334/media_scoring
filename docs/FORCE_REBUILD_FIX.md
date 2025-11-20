# Force Rebuild Fix for Buffer Caching Issue

## Problem Statement

After ingesting new media into the database, refreshing with "All" filters (the default state) would not show the newly ingested content in the sidebar/tileview. The content would only appear if filters were changed to create a different filter hash (e.g., filtering by a specific date).

## Root Cause

The buffer service uses hash-based caching to optimize performance:
1. FilterCriteria computes an MD5 hash from all filter parameters
2. Buffer registry maps filter_hash → buffer_table_name
3. When `get_or_create_buffer()` is called, it checks if a buffer exists for the given hash
4. If found, it returns the existing cached buffer WITHOUT checking if the underlying data changed

**The Issue**: When filters remain set to "All", the hash stays the same, so the cached buffer is reused even after new media is ingested into the database.

## Solution

Implemented a `force_rebuild` parameter throughout the buffer stack that allows manual cache invalidation:

### 1. Backend: Buffer Service (`app/database/buffer_service.py`)

```python
def get_or_create_buffer(
    self, 
    filters: FilterCriteria, 
    db_service: DatabaseService,
    force_rebuild: bool = False
) -> Tuple[str, int]:
    """
    Get existing buffer or create new one for given filters.
    
    Args:
        filters: The filter criteria
        db_service: Database service instance
        force_rebuild: If True, delete existing buffer and rebuild from scratch
                      (default False for backward compatibility)
    
    Returns:
        Tuple of (filter_hash, item_count)
    """
```

**Logic**:
- When `force_rebuild=True`, the method:
  1. Checks if a buffer exists for the filter hash
  2. If found, drops the existing buffer table
  3. Deletes the registry entry
  4. Proceeds to create a fresh buffer from current database state

### 2. API Layer: Search Router (`app/routers/search.py`)

```python
class FilterRequest(BaseModel):
    """Request model for filter operations."""
    # ... existing fields ...
    force_rebuild: bool = True  # Default to True for refresh operations

@router.post("/refresh")
async def refresh_buffer(request: FilterRequest):
    """
    Refresh the buffer with current filter criteria.
    
    The force_rebuild parameter (default True) ensures that cached buffers
    are invalidated and rebuilt from current database state, allowing
    newly ingested media to appear even when filter criteria unchanged.
    """
    # ... existing code ...
    
    with db_service as db:
        filter_hash, item_count = buffer_service.get_or_create_buffer(
            filters, db, force_rebuild=request.force_rebuild
        )
```

**Default Behavior**: `force_rebuild=True` ensures that clicking the refresh button always shows the latest database state.

### 3. Frontend: Buffer Client (`app/static/js/buffer-client.js`)

```javascript
async function refreshBuffer(filters, forceRebuild = true) {
  console.info('[Buffer] Refreshing buffer with filters:', filters, 'forceRebuild:', forceRebuild);
  
  // Add force_rebuild flag to ensure cached buffers are invalidated
  const requestBody = {
    ...filters,
    force_rebuild: forceRebuild
  };
  
  const response = await fetch('/api/search/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(requestBody)
  });
  // ... rest of logic ...
}
```

**Default Parameter**: `forceRebuild = true` makes rebuild behavior explicit in JavaScript calls.

## Testing Workflow

To validate the fix:

1. **Start with existing data**:
   - Open application with existing media in database
   - Set all filters to "All"
   - Click refresh - note the content shown

2. **Ingest new media**:
   ```bash
   curl -X POST "http://localhost:7862/api/ingest/process" \
     -H "Content-Type: application/json" \
     -d '{"parameters": {"directory": "/path/to/new/media", "pattern": "*.png|*.jpg"}}'
   ```

3. **Test refresh behavior**:
   - Keep all filters set to "All" (same hash as before)
   - Click the refresh button
   - **Expected**: Newly ingested media appears in sidebar/tileview
   - **Previous behavior**: Only old media shown (cached buffer reused)

4. **Verify force_rebuild is working**:
   - Check browser console logs: Should see `forceRebuild: true`
   - Check application logs: Should see buffer deletion messages before rebuild

## Performance Considerations

- **Cache Bypass**: Setting `force_rebuild=True` by default means refresh always rebuilds the buffer
- **Optimization**: For large datasets, buffer creation may take a few seconds
- **Alternative**: Could implement automatic cache invalidation based on database change detection, but that adds complexity
- **Trade-off**: Acceptable performance impact for correctness - users expect refresh to show latest data

## Backward Compatibility

- Default `force_rebuild=False` in backend method signature maintains backward compatibility
- API endpoint defaults to `True` for refresh operations (expected behavior)
- Frontend explicitly passes `true` to make intent clear
- Existing code that calls `get_or_create_buffer()` without the parameter still works (uses False)

## Related Issues Fixed

This change also resolves:
- Issue where contribution graph shows updated counts but sidebar doesn't update
- Confusion when users see new data in filtered views but not in "All" view
- Need to manually change filters back and forth to trigger cache invalidation

## Files Modified

1. `app/database/buffer_service.py` - Added force_rebuild parameter and cache invalidation logic
2. `app/routers/search.py` - Added force_rebuild to FilterRequest model and passed to buffer service
3. `app/static/js/buffer-client.js` - Added forceRebuild parameter to refreshBuffer() function

## Deployment Notes

- No database schema changes required
- No configuration changes required
- Backward compatible with existing buffer tables
- Existing buffers will be automatically invalidated on next refresh
