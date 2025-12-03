# Media Loading and Display Strategy

This document describes the media loading and display architecture for the Video Scorer application, focusing on the server-side buffered approach triggered by the refresh-content button.

## Overview

The application uses a **server-side buffered approach** to provide fast user experience when interacting with the web UI. The key principle is:

1. **Refresh-content button**: Compiles a sorted, filtered list of media server-side and stores it in a temporary SQLite table
2. **Viewport-based lazy loading**: Only items visible in the sidebar viewport are loaded
3. **Progressive pagination**: Additional items are fetched as the user scrolls

## Architecture Components

### Backend Components

#### 1. Buffer Service (`app/database/buffer_service.py`)
- Creates and manages temporary SQLite tables for filtered results
- Uses atomic table swaps for safe concurrent access
- Implements LRU eviction for buffer cleanup
- Provides keyset pagination for efficient scrolling

#### 2. Search Router (`app/routers/search.py`)
- `/api/search/refresh`: Creates/updates buffer based on filter criteria
- `/api/search/page`: Returns a page of items from buffer using keyset pagination
- `/api/search/filters/active`: Stores/retrieves active filter state for session persistence

### Frontend Components

#### 1. Buffer Client (`app/static/js/buffer-client.js`)
- Manages buffer lifecycle on the client
- Handles pagination state (cursor, hasMore)
- Persists filter state across page reloads

#### 2. Viewport Loader (`app/static/js/viewport-loader.js`)
- Uses Intersection Observer for detecting visible items
- Triggers loading of next page when approaching bottom of list
- Lazy-loads thumbnails for visible items only

#### 3. Search Toolbar (`app/static/js/search-toolbar.js`)
- Provides filter controls (file type, rating, date, NSFW, sort)
- Indicates when filters have changed and refresh is needed
- Persists filter state to server

## Data Flow

### 1. Refresh Content Button Flow

```
User clicks "Refresh Content" button
           │
           ▼
┌─────────────────────────────────────────┐
│ Frontend: buildFilterCriteria()          │
│ - Collects current filter values         │
│ - Builds FilterRequest object            │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ POST /api/search/refresh                 │
│ - Receives: filters, sort, force_rebuild │
│ - Creates FilterCriteria from request    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ BufferService.get_or_create_buffer()     │
│ 1. Compute filter hash                   │
│ 2. If force_rebuild: delete existing     │
│ 3. Query media from main database        │
│ 4. Create temp SQLite table              │
│ 5. Populate with filtered+sorted data    │
│ 6. Create pagination indexes             │
│ 7. Register in buffer_registry           │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Response: { filter_hash, item_count }    │
└────────────────┬────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────┐
│ Frontend: loadBufferFirstPage()          │
│ - Calls GET /api/search/page             │
│ - Receives first 50 items                │
│ - Renders visible items in sidebar       │
└─────────────────────────────────────────┘
```

### 2. Viewport-Based Loading Flow

```
User scrolls sidebar
        │
        ▼
┌──────────────────────────────────────────┐
│ Intersection Observer detects items       │
│ approaching viewport bottom               │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ ViewportLoader.loadNextBufferPage()       │
│ - Check hasMoreItems flag                 │
│ - Call BufferClient.getPage() with cursor │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ GET /api/search/page                      │
│ ?filter_hash=xxx                          │
│ &cursor_created_at=yyyy-mm-ddThh:mm:ss    │
│ &cursor_id=123                            │
│ &limit=50                                 │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ BufferService.get_page()                  │
│ - Keyset pagination query                 │
│ - Returns items + next_cursor             │
└────────────────┬─────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────┐
│ Frontend: appendSidebarItems()            │
│ - Creates DOM elements for new items      │
│ - Observes them for thumbnail loading     │
└──────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Server-Side Buffering

The buffer is stored server-side in SQLite for several reasons:
- **Consistency**: All clients see the same filtered results
- **Performance**: SQLite is fast for this use case
- **Memory efficiency**: Client doesn't need to hold all items
- **Persistence**: Buffer survives page refreshes

### 2. Keyset Pagination

Instead of OFFSET-based pagination, we use keyset pagination:
- **Fast at any page**: No need to scan previous pages
- **Stable results**: Inserts don't shift pages
- **Works with sorting**: Cursor based on sort key + ID

### 3. Lazy Loading Strategy

Items are loaded lazily at two levels:
1. **Sidebar items**: Only visible items + buffer zone are fetched
2. **Thumbnails**: Only visible thumbnails are loaded via Intersection Observer

### 4. Sort Handling

Sorting is done server-side during buffer creation:
- **Name**: Alphabetical by filename
- **Date**: By original_created_at, falling back to created_at
- **Size**: By file_size
- **Rating**: By score

## Filter Criteria

The following filters are applied server-side:

| Filter | Description |
|--------|-------------|
| file_types | Array of extensions (e.g., ["jpg", "png", "mp4"]) |
| min_score | Minimum score (inclusive) |
| max_score | Maximum score (inclusive) |
| start_date | Start of date range (ISO format) |
| end_date | End of date range (ISO format) |
| nsfw_filter | "all", "sfw", or "nsfw" |
| sort_field | "name", "date", "size", or "rating" |
| sort_direction | "asc" or "desc" |

## Session Persistence

The application maintains state across page refreshes:

1. **Active filters**: Stored in `ui_state` table with key "active_filter"
2. **View state**: Current file and scroll position stored with key "view_state"
3. **Buffer tables**: Persist until evicted or manually cleared

## Performance Characteristics

### Buffer Creation
- Time: O(n) where n = matching media files
- Space: ~500 bytes per item in buffer table

### Page Retrieval
- Time: O(log n) using index-based keyset pagination
- Network: ~50 items per request (configurable)

### Eviction Policy
- Max buffers: 10 (configurable)
- Max total size: 500MB (configurable)
- Strategy: Least Recently Used (LRU)

## API Reference

### POST /api/search/refresh

Creates or refreshes the server-side buffer.

**Request:**
```json
{
  "file_types": ["jpg", "png"],
  "min_score": 3,
  "sort_field": "date",
  "sort_direction": "desc",
  "force_rebuild": true
}
```

**Response:**
```json
{
  "ok": true,
  "filter_hash": "abc123...",
  "item_count": 1500
}
```

### GET /api/search/page

Retrieves a page of items from the buffer.

**Query Parameters:**
- `filter_hash`: Required. Hash from refresh response
- `cursor_created_at`: Optional. ISO timestamp for pagination
- `cursor_id`: Optional. Item ID for pagination
- `limit`: Optional. Items per page (default: 50, max: 200)

**Response:**
```json
{
  "items": [...],
  "count": 50,
  "next_cursor": {
    "created_at": "2024-01-15T10:30:00",
    "id": 123
  },
  "has_more": true
}
```

## Troubleshooting

### Buffer Not Updating After New Content Ingestion

Set `force_rebuild: true` in the refresh request to ensure the buffer is rebuilt from current database state.

### Slow Initial Load

The first refresh after server restart may be slower as indexes are built. Subsequent refreshes with the same filters use cached buffers.

### Memory Usage

If buffer size exceeds limits, oldest buffers are evicted. Monitor via `GET /api/search/buffer/stats`.
