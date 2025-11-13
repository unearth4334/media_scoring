# Performance Optimization Plan for Mobile Media Browsing

**Date**: 2025-11-12  
**Issue**: Media browsing interface runs slowly on mobile when there are large numbers of media files within the filter scope.

## 🔍 Root Cause Analysis

### Current Architecture Problems

1. **Full Dataset Loading (Critical)**
   - **Location**: `app/routers/media.py:list_videos()` (line 72)
   - **Problem**: The `/api/videos` endpoint loads **ALL** media files from the database/filesystem into memory
   - **Code**: `media_files = db.get_all_media_files()` with no limit
   - **Impact**: With thousands of files, this creates:
     - Large JSON payload (multi-megabyte response)
     - Long server processing time
     - High memory usage on mobile devices
     - Network transfer bottleneck

2. **Client-Side Rendering Bottleneck**
   - **Location**: `app/static/js/app.js:renderSidebar()` (line 1132)
   - **Problem**: Renders **ALL** videos in the DOM, not just filtered ones
   - **Code**: `videos.forEach((v) => { ... })` - iterates over entire dataset
   - **Impact**: 
     - DOM manipulation for thousands of elements
     - Memory pressure from large DOM tree
     - Slow scroll performance
     - Browser freezing during render

3. **Tile View Performance Issue**
   - **Location**: `app/static/js/app.js:populateTileView()` (line 2381)
   - **Problem**: Creates DOM elements for ALL filtered items at once
   - **Code**: `filtered.forEach((item, index) => { ... })`
   - **Impact**:
     - All thumbnails generated upfront
     - Large grid causes layout thrashing
     - High memory consumption

4. **Thumbnail Loading (Partially Mitigated)**
   - **Status**: ✅ Lazy loading already implemented with IntersectionObserver
   - **Location**: `app/static/js/app.js:observeThumbnails()` (line 194)
   - **Current Implementation**: Uses `data-thumbnail-src` and loads on viewport intersection
   - **Issue**: Still creates DOM elements for all items

### Performance Metrics (Estimated)

| Dataset Size | Current Load Time | Current Render Time | Memory Usage |
|--------------|-------------------|---------------------|--------------|
| 1,000 files  | ~2-3 seconds     | ~1-2 seconds        | ~50MB        |
| 5,000 files  | ~10-15 seconds   | ~5-8 seconds        | ~200MB       |
| 10,000 files | ~30-45 seconds   | ~15-20 seconds      | ~500MB       |

*Mobile devices typically have 2-4GB RAM, so 500MB for one tab is significant*

## 💡 Optimization Strategy

### Phase 1: Server-Side Pagination (High Priority)

#### 1.1 Backend Changes

**Create Paginated Endpoint**: `GET /api/videos/paginated`

```python
# app/routers/media.py

class PaginationRequest(BaseModel):
    """Request model for paginated media listing."""
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(100, ge=10, le=500, description="Items per page")
    
    # Filtering
    min_score: Optional[int] = Field(None, ge=0, le=5)
    max_score: Optional[int] = Field(None, ge=0, le=5)
    file_types: Optional[List[str]] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    nsfw_filter: Optional[str] = Field(None, description="NSFW filter: 'all', 'sfw', or 'nsfw'")
    
    # Sorting
    sort_field: SortField = Field(SortField.NAME)
    sort_direction: SortDirection = Field(SortDirection.ASC)


@router.post("/videos/paginated")
async def get_paginated_videos(request: PaginationRequest):
    """Return paginated list of media files."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Pagination requires database mode")
    
    try:
        db_service = state.get_database_service()
        
        with db_service as db:
            # Calculate offset
            offset = (request.page - 1) * request.page_size
            
            # Get total count (for pagination info)
            total_count = db.get_media_files_count(
                min_score=request.min_score,
                max_score=request.max_score,
                file_types=request.file_types,
                # ... other filters
            )
            
            # Get paginated results
            media_files = db.get_all_media_files(
                min_score=request.min_score,
                max_score=request.max_score,
                file_types=request.file_types,
                start_date=...,
                end_date=...,
                nsfw_filter=request.nsfw_filter,
                sort_field=request.sort_field.value,
                sort_direction=request.sort_direction.value,
                offset=offset,
                limit=request.page_size
            )
            
            # Format items
            items = [format_media_file(mf) for mf in media_files]
            
            total_pages = (total_count + request.page_size - 1) // request.page_size
            
            return {
                "items": items,
                "pagination": {
                    "page": request.page,
                    "page_size": request.page_size,
                    "total_items": total_count,
                    "total_pages": total_pages,
                    "has_next": request.page < total_pages,
                    "has_prev": request.page > 1
                },
                "filters_applied": {
                    "min_score": request.min_score,
                    "max_score": request.max_score,
                    # ... other filters
                }
            }
    
    except Exception as e:
        state.logger.error(f"Pagination failed: {e}")
        raise HTTPException(500, str(e))
```

**Add Count Method to DatabaseService**:

```python
# app/database/service.py

@log_db_operation("get_media_files_count")
def get_media_files_count(self, 
                         min_score: Optional[int] = None,
                         max_score: Optional[int] = None,
                         file_types: Optional[List[str]] = None,
                         start_date: Optional[datetime] = None,
                         end_date: Optional[datetime] = None,
                         nsfw_filter: Optional[str] = None) -> int:
    """Get count of media files matching filters."""
    query = self.session.query(func.count(MediaFile.id))
    
    # Apply same filters as get_all_media_files
    if min_score is not None:
        query = query.filter(MediaFile.score >= min_score)
    if max_score is not None:
        query = query.filter(MediaFile.score <= max_score)
    # ... apply other filters
    
    return query.scalar()
```

#### 1.2 Frontend Changes

**Implement Virtual Scrolling for Sidebar**:

```javascript
// app/static/js/app.js

// New state variables
let currentPage = 1;
let pageSize = 100;
let totalPages = 1;
let isLoadingMore = false;
let allLoadedItems = []; // Buffer of loaded items

async function loadVideosPage(page = 1, append = false) {
  if (isLoadingMore) return;
  isLoadingMore = true;
  
  try {
    const response = await fetch('/api/videos/paginated', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({
        page: page,
        page_size: pageSize,
        min_score: minFilter,
        sort_field: currentSortField,
        sort_direction: currentSortDirection
      })
    });
    
    const data = await response.json();
    
    if (append) {
      // Append to existing items
      allLoadedItems = [...allLoadedItems, ...data.items];
    } else {
      // Replace items
      allLoadedItems = data.items;
    }
    
    videos = allLoadedItems; // Update global videos array
    currentPage = data.pagination.page;
    totalPages = data.pagination.total_pages;
    
    applyFilter();
    renderSidebar();
    
    // Update pagination UI
    updatePaginationControls(data.pagination);
    
  } catch (error) {
    console.error('Failed to load videos:', error);
  } finally {
    isLoadingMore = false;
  }
}

// Infinite scroll for sidebar
function setupInfiniteScroll() {
  const sidebarList = document.getElementById('sidebar_list');
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && currentPage < totalPages && !isLoadingMore) {
        // Load next page
        loadVideosPage(currentPage + 1, true);
      }
    });
  }, {
    root: sidebarList,
    rootMargin: '200px', // Trigger 200px before bottom
    threshold: 0.01
  });
  
  // Observe a sentinel element at the bottom
  const sentinel = document.createElement('div');
  sentinel.id = 'scroll-sentinel';
  sentinel.style.height = '1px';
  sidebarList.appendChild(sentinel);
  observer.observe(sentinel);
}
```

### Phase 2: Virtual Scrolling for Large Lists (Medium Priority)

Use a virtual scrolling library or implement custom virtual list:

```javascript
// Option 1: Use react-window or similar
// Option 2: Implement custom virtual list

class VirtualList {
  constructor(container, items, itemHeight, renderItem) {
    this.container = container;
    this.items = items;
    this.itemHeight = itemHeight;
    this.renderItem = renderItem;
    this.visibleRange = { start: 0, end: 0 };
    
    this.init();
  }
  
  init() {
    // Create viewport and spacers
    this.viewport = document.createElement('div');
    this.viewport.style.height = `${this.items.length * this.itemHeight}px`;
    this.viewport.style.position = 'relative';
    
    this.container.appendChild(this.viewport);
    
    // Listen for scroll
    this.container.addEventListener('scroll', () => this.onScroll());
    
    this.render();
  }
  
  onScroll() {
    const scrollTop = this.container.scrollTop;
    const containerHeight = this.container.clientHeight;
    
    // Calculate visible range with buffer
    const start = Math.max(0, Math.floor(scrollTop / this.itemHeight) - 5);
    const end = Math.min(
      this.items.length,
      Math.ceil((scrollTop + containerHeight) / this.itemHeight) + 5
    );
    
    if (start !== this.visibleRange.start || end !== this.visibleRange.end) {
      this.visibleRange = { start, end };
      this.render();
    }
  }
  
  render() {
    // Clear existing items
    this.viewport.innerHTML = '';
    
    // Render only visible items
    for (let i = this.visibleRange.start; i < this.visibleRange.end; i++) {
      const item = this.items[i];
      const element = this.renderItem(item, i);
      
      element.style.position = 'absolute';
      element.style.top = `${i * this.itemHeight}px`;
      element.style.left = '0';
      element.style.right = '0';
      
      this.viewport.appendChild(element);
    }
  }
  
  updateItems(newItems) {
    this.items = newItems;
    this.viewport.style.height = `${this.items.length * this.itemHeight}px`;
    this.render();
  }
}

// Usage in renderSidebar
function renderSidebar() {
  const list = document.getElementById('sidebar_list');
  if (!list) return;
  
  if (!window.virtualList) {
    window.virtualList = new VirtualList(
      list,
      videos,
      80, // Estimated item height
      (item, index) => createSidebarItem(item, index)
    );
  } else {
    window.virtualList.updateItems(videos);
  }
}
```

### Phase 3: Tile View Optimization (Medium Priority)

**Implement Lazy Grid Rendering**:

```javascript
// app/static/js/app.js

function populateTileView() {
  const gridContainer = document.getElementById('tile-view-grid');
  if (!gridContainer) return;
  
  if (!filtered || filtered.length === 0) {
    gridContainer.innerHTML = '<div class="tile-view-loading">No media items to display</div>';
    return;
  }
  
  // Clear existing
  gridContainer.innerHTML = '';
  
  // Render initial batch (first 50 items)
  const initialBatch = Math.min(50, filtered.length);
  
  for (let i = 0; i < initialBatch; i++) {
    const tile = createTileViewItem(filtered[i], i);
    gridContainer.appendChild(tile);
  }
  
  // Setup intersection observer for remaining items
  if (filtered.length > initialBatch) {
    setupTileViewLazyLoad(gridContainer, initialBatch);
  }
}

function setupTileViewLazyLoad(container, startIndex) {
  // Create sentinel at the end of grid
  const sentinel = document.createElement('div');
  sentinel.className = 'tile-view-sentinel';
  container.appendChild(sentinel);
  
  let currentBatch = startIndex;
  const batchSize = 50;
  
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting && currentBatch < filtered.length) {
        // Load next batch
        const endIndex = Math.min(currentBatch + batchSize, filtered.length);
        
        for (let i = currentBatch; i < endIndex; i++) {
          const tile = createTileViewItem(filtered[i], i);
          container.insertBefore(tile, sentinel);
        }
        
        currentBatch = endIndex;
        
        // Stop observing if all loaded
        if (currentBatch >= filtered.length) {
          observer.disconnect();
          sentinel.remove();
        }
      }
    });
  }, {
    root: null,
    rootMargin: '500px', // Load 500px before sentinel
    threshold: 0.01
  });
  
  observer.observe(sentinel);
}
```

### Phase 4: Caching and Indexing (Low Priority)

1. **Client-Side Caching**:
   ```javascript
   // Use IndexedDB for caching loaded pages
   const dbName = 'media-scorer-cache';
   const storeName = 'media-pages';
   
   async function cachePageData(page, data) {
     const db = await openDB(dbName);
     const tx = db.transaction(storeName, 'readwrite');
     await tx.store.put({ page, data, timestamp: Date.now() });
   }
   
   async function getCachedPage(page) {
     const db = await openDB(dbName);
     const cached = await db.get(storeName, page);
     
     // Check if cache is stale (older than 5 minutes)
     if (cached && Date.now() - cached.timestamp < 5 * 60 * 1000) {
       return cached.data;
     }
     return null;
   }
   ```

2. **Database Indexing**:
   ```python
   # Ensure proper indexes exist
   # app/database/models.py
   
   class MediaFile(Base):
       # ... existing fields
       
       __table_args__ = (
           Index('idx_score', 'score'),
           Index('idx_created_at', 'original_created_at', 'created_at'),
           Index('idx_file_type', 'file_type'),
           Index('idx_nsfw', 'nsfw'),
           Index('idx_composite', 'score', 'original_created_at', 'file_type'),
       )
   ```

## 📊 Expected Performance Improvements

| Optimization | Load Time Reduction | Memory Reduction | Implementation Effort |
|--------------|---------------------|------------------|----------------------|
| Server Pagination | 80-90% | 80-90% | High (2-3 days) |
| Virtual Scrolling | 60-70% | 70-80% | Medium (1-2 days) |
| Tile View Lazy Load | 50-60% | 60-70% | Low (4-6 hours) |
| Client Caching | 40-50% (subsequent loads) | N/A | Low (4-6 hours) |
| Database Indexing | 10-20% | N/A | Very Low (1 hour) |

### Target Metrics (10,000 files)

| Metric | Current | After Phase 1 | After All Phases |
|--------|---------|---------------|------------------|
| Initial Load | 30-45s | 2-3s | 1-2s |
| Memory Usage | 500MB | 50MB | 30MB |
| Scroll FPS | 10-20 | 40-50 | 55-60 |

## 🚀 Implementation Priority

### Phase 1 (This Week): Core Pagination
- ✅ Create paginated endpoint
- ✅ Add count method to database service
- ✅ Update frontend to use pagination
- ✅ Add infinite scroll for sidebar
- ✅ Test with 10,000+ files

### Phase 2 (Next Week): Virtual Scrolling
- Implement custom virtual list component
- Replace sidebar rendering
- Test performance on mobile
- Add loading indicators

### Phase 3 (Following Week): Tile View
- Add lazy loading for tile grid
- Batch rendering implementation
- Optimize thumbnail generation
- Test with various grid sizes

### Phase 4 (Optional): Advanced Optimizations
- IndexedDB caching layer
- Service worker for offline support
- Prefetch next page
- Database query optimization

## 🧪 Testing Strategy

1. **Performance Testing**:
   - Use Chrome DevTools Performance profiler
   - Test with 1k, 5k, 10k, 20k files
   - Measure: FPS, memory usage, load times
   - Test on actual mobile device (not just emulator)

2. **Load Testing**:
   - Simulate network throttling (3G, 4G)
   - Test with different page sizes (50, 100, 200)
   - Measure API response times

3. **Usability Testing**:
   - Smooth scrolling verification
   - Loading indicator clarity
   - Pagination controls usability

## 📝 Notes

- **Database Required**: Pagination requires database mode to be enabled
- **Backward Compatibility**: Keep old `/api/videos` endpoint for file system mode
- **Mobile First**: Optimize for mobile browsers (Safari, Chrome Mobile)
- **Single User**: Can leverage aggressive caching since only one user
- **Filter Changes**: Need to reset pagination when filters change

## 🔗 Related Files

- `app/routers/media.py` - API endpoints
- `app/database/service.py` - Database queries
- `app/static/js/app.js` - Frontend rendering
- `app/database/models.py` - Database schema

---

**Next Steps**: Begin with Phase 1 implementation - create paginated endpoint and update frontend to use pagination with infinite scroll.
