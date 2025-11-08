# Buffered Search Results Guide

## Overview

The buffered search results feature provides high-performance search and pagination for large media datasets by materializing search results into a SQLite buffer database. This dramatically improves UI responsiveness, especially on mobile devices.

## Key Features

### Performance Benefits
- **Fast Pagination**: 2-3ms page fetch times (vs 100ms+ for direct database queries)
- **Smooth Scrolling**: Keyset pagination eliminates offset-based query slowdown
- **Buffer Reuse**: Identical searches reuse existing buffers instantly
- **Mobile Optimized**: Designed for responsive mobile UI interactions

### Core Capabilities
- **Filter Persistence**: Active filters persist across browser refreshes
- **Atomic Updates**: Buffer rebuilds use atomic table swaps (no downtime)
- **Automatic Eviction**: LRU eviction when storage limits exceeded
- **Multi-Device Support**: Same filter state shared across devices

## Architecture

### Buffer Database
Uses SQLite for buffer storage (separate from main PostgreSQL database):
- Location: `{media_dir}/.scores/buffer.db`
- Configuration: WAL mode, NORMAL synchronous, memory temp store
- Tables:
  - `buffer_items_{hash}`: Materialized search results
  - `buffer_registry`: Tracks all buffers with metadata
  - `ui_state`: Persists filter state

### Filter Hashing
Each unique filter configuration gets a SHA256 hash:
```python
{
  "keywords": ["cat", "dog"],
  "min_score": 3,
  "sort_field": "date",
  "sort_direction": "desc"
}
→ Hash: 8b6da183f45f3ab8...
```

Identical filters (even with different order) produce the same hash, enabling buffer reuse.

## API Endpoints

### POST /api/search/refresh
Refresh the buffer with current filter criteria.

**Request Body:**
```json
{
  "keywords": ["landscape"],
  "match_all": false,
  "file_types": ["jpg", "png"],
  "min_score": 3,
  "max_score": 5,
  "start_date": "2024-01-01T00:00:00",
  "end_date": "2024-12-31T23:59:59",
  "nsfw_filter": "sfw",
  "sort_field": "date",
  "sort_direction": "desc"
}
```

**Response:**
```json
{
  "ok": true,
  "filter_hash": "8b6da183f45f3ab8...",
  "item_count": 1234,
  "message": "Buffer created with 1234 items"
}
```

### GET /api/search/page
Get a page of results using keyset pagination.

**Query Parameters:**
- `filter_hash` (required): Hash from refresh operation
- `cursor_created_at` (optional): Created timestamp from previous page
- `cursor_id` (optional): ID from previous page
- `limit` (default: 50, max: 200): Items per page

**Response:**
```json
{
  "items": [
    {
      "id": 123,
      "media_file_id": 456,
      "filename": "image.jpg",
      "file_path": "/path/to/image.jpg",
      "score": 4,
      "width": 1920,
      "height": 1080,
      "created_at": "2024-01-01T12:00:00",
      "nsfw": false
    }
  ],
  "count": 50,
  "next_cursor": {
    "created_at": "2024-01-01T12:00:00",
    "id": 123
  },
  "has_more": true
}
```

### GET /api/search/filters/active
Get the currently active filter state.

**Response:**
```json
{
  "ok": true,
  "filter_hash": "8b6da183f45f3ab8...",
  "filters": {
    "keywords": ["landscape"],
    "min_score": 3,
    "sort_field": "date"
  }
}
```

### POST /api/search/filters/active
Set the active filter state (without rebuilding buffer).

**Request Body:** Same as `/refresh` endpoint

**Response:**
```json
{
  "ok": true,
  "filter_hash": "8b6da183f45f3ab8...",
  "message": "Filter state updated (press Refresh to apply)"
}
```

### GET /api/search/buffer/stats
Get buffer statistics.

**Response:**
```json
{
  "ok": true,
  "stats": {
    "buffer_count": 3,
    "total_items": 5000,
    "total_size_mb": 2.5
  }
}
```

### DELETE /api/search/buffer/{filter_hash}
Delete a specific buffer.

### DELETE /api/search/buffer
Clear all buffers.

## Usage Pattern

### 1. Initial Load
```javascript
// On page load, restore active filter state
const response = await fetch('/api/search/filters/active');
const { filter_hash, filters } = await response.json();

if (filter_hash) {
  // Load first page using existing buffer
  loadPage(filter_hash, null);
} else {
  // No active filters, show all items
  refreshWithDefaultFilters();
}
```

### 2. Apply Filters (UI Update Only)
```javascript
// User changes filter fields in UI
function updateFilterUI(filters) {
  // Just update local state, don't rebuild buffer yet
  await fetch('/api/search/filters/active', {
    method: 'POST',
    body: JSON.stringify(filters)
  });
  // Show "Press Refresh to apply" message
}
```

### 3. Refresh Buffer
```javascript
// User presses Refresh button
async function refreshBuffer(filters) {
  showLoading();
  
  const response = await fetch('/api/search/refresh', {
    method: 'POST',
    body: JSON.stringify(filters)
  });
  
  const { filter_hash, item_count } = await response.json();
  
  // Load first page with new buffer
  await loadPage(filter_hash, null);
  
  hideLoading();
}
```

### 4. Pagination
```javascript
// Load a page of results
async function loadPage(filterHash, cursor) {
  const params = new URLSearchParams({
    filter_hash: filterHash,
    limit: 50
  });
  
  if (cursor) {
    params.append('cursor_created_at', cursor.created_at);
    params.append('cursor_id', cursor.id);
  }
  
  const response = await fetch(`/api/search/page?${params}`);
  const { items, next_cursor, has_more } = await response.json();
  
  displayItems(items);
  
  if (has_more) {
    // Store next_cursor for "Load More" button
    setNextCursor(next_cursor);
  }
}
```

### 5. Infinite Scroll
```javascript
let currentCursor = null;
let loading = false;

function setupInfiniteScroll() {
  window.addEventListener('scroll', async () => {
    if (loading) return;
    
    const { scrollTop, scrollHeight, clientHeight } = document.documentElement;
    
    // Trigger when 80% scrolled
    if (scrollTop + clientHeight >= scrollHeight * 0.8) {
      loading = true;
      await loadPage(currentFilterHash, currentCursor);
      loading = false;
    }
  });
}
```

## Configuration

### Buffer Service Settings
Configure in `buffer_service.py`:

```python
buffer_service = BufferService(buffer_db_path)
buffer_service.max_buffer_size_mb = 500  # Max total storage
buffer_service.max_buffers = 10          # Max number of buffers
```

### SQLite PRAGMA Settings
Automatically configured for performance:
```sql
PRAGMA journal_mode=WAL;       -- Write-Ahead Logging
PRAGMA synchronous=NORMAL;     -- Balance safety and speed
PRAGMA temp_store=MEMORY;      -- Use memory for temp tables
PRAGMA cache_size=-64000;      -- 64MB cache
```

## Performance Characteristics

### Measured with 10,000 Items
- Buffer creation: 1850 items/sec (5.4s total)
- Buffer reuse: < 1ms (instant)
- Page fetch: 2.4ms average
- Pagination throughput: 41,585 items/sec

### Memory Usage
- ~500 bytes per buffered item
- 10,000 items ≈ 5 MB
- 100,000 items ≈ 50 MB

### Storage
- Buffer database stored in `.scores/buffer.db`
- Automatically evicts LRU buffers when limit exceeded
- Old buffers deleted on eviction (no manual cleanup needed)

## Troubleshooting

### Buffer Not Found Error
```json
{
  "detail": "Buffer not found for hash abc123..."
}
```

**Solution:** Buffer was evicted or deleted. Call `/refresh` to rebuild.

### Slow Buffer Creation
**Symptoms:** Initial refresh takes > 10 seconds

**Possible Causes:**
1. Very large dataset (> 100,000 items)
2. Complex keyword searches with many keywords
3. Database not indexed properly

**Solutions:**
1. Ensure main database has proper indexes
2. Use more specific filters to reduce result set
3. Consider increasing `max_buffers` to cache more combinations

### Pagination Gaps or Duplicates
**Symptoms:** Items missing or duplicated between pages

**Cause:** Buffer was rebuilt while paginating

**Solution:** Store buffer hash with pagination state. If hash changes, restart pagination from page 1.

## Best Practices

1. **Always use Refresh button for buffer rebuild**
   - Don't rebuild on every filter change
   - Batch filter updates, then refresh once

2. **Persist filter state on the server**
   - Ensures consistent view across devices
   - Survives browser refresh

3. **Use keyset pagination, not offset**
   - Much faster for large datasets
   - No performance degradation on deep pages

4. **Monitor buffer statistics**
   - Check `/buffer/stats` periodically
   - Adjust limits if buffers evict too frequently

5. **Handle buffer eviction gracefully**
   - Catch 404 errors on `/page` endpoint
   - Automatically call `/refresh` to rebuild
   - Show user-friendly message during rebuild

## Migration from Direct Query

### Before (Direct Database Query)
```javascript
// Slow for large datasets, especially on mobile
const response = await fetch(`/api/search/files`, {
  method: 'POST',
  body: JSON.stringify({ keywords: ['cat'], min_score: 3 })
});
const { results } = await response.json(); // All results at once
```

### After (Buffered with Pagination)
```javascript
// Fast and scalable
// 1. Refresh buffer
const refreshResponse = await fetch(`/api/search/refresh`, {
  method: 'POST',
  body: JSON.stringify({ keywords: ['cat'], min_score: 3 })
});
const { filter_hash } = await refreshResponse.json();

// 2. Load pages as needed
const pageResponse = await fetch(
  `/api/search/page?filter_hash=${filter_hash}&limit=50`
);
const { items, next_cursor } = await pageResponse.json(); // One page at a time
```

## Future Enhancements

Potential improvements for future versions:

1. **Background refresh**: Rebuild buffers in background without blocking UI
2. **Incremental updates**: Update buffer when new files added (instead of full rebuild)
3. **Precomputed aggregations**: Store counts, score distributions in buffer
4. **Multi-sort support**: Allow sorting by different fields without rebuild
5. **Buffer compression**: Reduce storage using compression for older buffers
