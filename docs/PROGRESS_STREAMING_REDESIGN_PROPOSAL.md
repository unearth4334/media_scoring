# Progress Streaming Redesign Proposal for Ingest V2 WebUI

## Executive Summary

The current progress tracking mechanism in the Ingest V2 WebUI suffers from delayed updates and poor real-time feedback, despite previous attempts to fix the issue. This proposal recommends replacing the polling-based approach with a **Server-Sent Events (SSE)** streaming architecture to provide truly live progress updates.

## Problem Statement

### Current Issue
Users do not see live progress updates during file processing in the Ingest V2 interface. All progress indicators (percentage, file counts, statistics) show zero or stale values until the browser polls the server, creating a poor user experience where:

1. **Initial delay**: Progress appears stuck at 0% for the first polling interval (1 second)
2. **Lag behind reality**: Updates are always 1 second behind actual processing
3. **Inconsistent updates**: Fast processing may complete before the first poll
4. **Network waste**: Continuous polling even when no processing is happening
5. **No true streaming**: Updates are discrete snapshots, not a continuous stream

### Root Cause Analysis

The fundamental issue is **architectural**, not a simple bug fix:

```javascript
// Current polling mechanism (ingest_v2.html, lines 880-903)
function startProgressPolling() {
  processingTimer = setInterval(async () => {
    try {
      const response = await fetch(`/api/ingest/status/${currentSessionId}`);
      const status = await response.json();
      updateProgressDisplay(status);  // ← Updates only every 1 second
      
      if (status.status === 'completed') {
        clearInterval(processingTimer);
      }
    } catch (error) {
      console.error('Error polling status:', error);
    }
  }, 1000);  // ← Hardcoded 1-second delay
}
```

**Why This Fails:**
- **Pull model**: Client must ask for updates (polling)
- **Fixed interval**: Can't adapt to processing speed
- **State snapshots**: Only sees discrete states, not continuous progress
- **Latency**: Network round-trip on every poll adds delay
- **Resource waste**: Empty polls when no changes occurred

### Previous Fix Attempt

The `PROGRESS_FIX_SUMMARY.md` documented a fix that moved progress calculation from `(i/total)*100` to `((i+1)/total)*100`. While this improved the calculation logic, it **did not solve the streaming problem**:

```python
# app/routers/ingest_v2.py, line 330
for i, file_path in enumerate(files):
    # ... process file ...
    session["progress"] = int(((i + 1) / len(files)) * 100)
    # ↑ Progress is updated immediately in backend
    # But frontend only sees it 0-1 seconds later via polling!
```

The fix ensured correct progress values but did nothing to improve the **delivery mechanism** to the frontend.

## Proposed Solution: Server-Sent Events (SSE)

### Architecture Overview

Replace the polling mechanism with **Server-Sent Events (SSE)**, a W3C standard for server-to-client streaming:

```
┌──────────────┐                    ┌──────────────┐
│              │   1. POST /start   │              │
│   Frontend   │───────────────────▶│   Backend    │
│              │                    │              │
│              │   2. GET /stream   │              │
│              │◀──────────────────│              │
│              │    (SSE stream)    │              │
│              │                    │              │
│  Updates in  │  3. Continuous     │  Processing  │
│  real-time   │◀════════════════════│  updates    │
│              │     data: {...}    │              │
│              │     data: {...}    │              │
└──────────────┘                    └──────────────┘
        ▲                                  │
        │                                  │
        └──────── Instant updates ─────────┘
              (no polling delay)
```

### Key Benefits

1. **True real-time updates**: Events pushed immediately as they occur
2. **Zero polling overhead**: No wasted requests when idle
3. **Automatic reconnection**: Built-in browser support for connection recovery
4. **Standardized**: Native EventSource API, no external dependencies
5. **HTTP/1.1 compatible**: Works with existing infrastructure
6. **Efficient**: Single long-lived connection vs. many short requests

### Technical Design

#### Backend Changes

**1. New SSE Streaming Endpoint**

```python
# app/routers/ingest_v2.py

from fastapi.responses import StreamingResponse
from typing import AsyncGenerator
import asyncio
import json

# Event queue for progress updates
progress_queues: Dict[str, asyncio.Queue] = {}

@router.get("/api/ingest/stream/{session_id}")
async def stream_progress(session_id: str):
    """Stream real-time progress updates via Server-Sent Events."""
    
    if session_id not in processing_sessions:
        raise HTTPException(404, "Session not found")
    
    # Create queue for this client
    queue = asyncio.Queue()
    progress_queues[session_id] = queue
    
    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            # Send initial state
            session = processing_sessions[session_id]
            yield f"data: {json.dumps(get_session_status(session))}\n\n"
            
            # Stream updates as they happen
            while True:
                try:
                    # Wait for next update (with timeout to check completion)
                    update = await asyncio.wait_for(queue.get(), timeout=1.0)
                    yield f"data: {json.dumps(update)}\n\n"
                    
                    # Check if processing completed
                    if update.get('status') in ['completed', 'error']:
                        break
                        
                except asyncio.TimeoutError:
                    # Send keepalive every second
                    yield ": keepalive\n\n"
                    
                    # Check if session still exists
                    if session_id not in processing_sessions:
                        break
                    
                    # Check if client disconnected
                    session = processing_sessions[session_id]
                    if session.get('status') in ['completed', 'error']:
                        yield f"data: {json.dumps(get_session_status(session))}\n\n"
                        break
                        
        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            # Cleanup queue
            if session_id in progress_queues:
                del progress_queues[session_id]
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )

def get_session_status(session: Dict) -> Dict:
    """Extract current session status for streaming."""
    return {
        "status": session["status"],
        "progress": session["progress"],
        "total_files": session["total_files"],
        "current_file": session["current_file"],
        "processed_files": session["processed_files"],
        "stats": session["stats"],
        "errors": session["errors"][-10:] if session["errors"] else []
    }
```

**2. Modified Background Processing**

```python
# app/routers/ingest_v2.py

async def process_files_background(session_id: str, files: List[Path], parameters: IngestParameters):
    """Background task to process files with real-time streaming."""
    session = processing_sessions[session_id]
    queue = progress_queues.get(session_id)
    
    async def emit_update():
        """Helper to emit progress update."""
        if queue:
            update = get_session_status(session)
            try:
                await queue.put(update)
            except Exception as e:
                logging.warning(f"Failed to emit update: {e}")
    
    try:
        session["status"] = "processing"
        await emit_update()  # ← Emit status change
        
        for i, file_path in enumerate(files):
            session["current_file"] = file_path.name
            await emit_update()  # ← Emit current file change
            
            try:
                # Process single file
                file_data = await process_single_file(file_path, parameters)
                session["processed_data"].append(file_data)
                session["processed_files"] += 1
                session["stats"]["processed_files"] += 1
                
                # Update stats based on what was processed
                if file_data.get("metadata"):
                    session["stats"]["metadata_extracted"] += 1
                if file_data.get("keywords"):
                    session["stats"]["keywords_added"] += len(file_data["keywords"])
                if file_data.get("score") is not None:
                    session["stats"]["scores_imported"] += 1
                if file_data.get("nsfw_label"):
                    session["stats"]["nsfw_detected"] += 1
                
                # Update progress after processing file
                session["progress"] = int(((i + 1) / len(files)) * 100)
                
                # ✨ CRITICAL: Emit update immediately after each file
                await emit_update()
                    
            except Exception as e:
                error_msg = f"Error processing {file_path.name}: {str(e)}"
                session["errors"].append(error_msg)
                session["stats"]["errors"] += 1
                logging.error(error_msg)
                await emit_update()  # ← Emit error update
        
        session["status"] = "completed"
        session["progress"] = 100
        session["end_time"] = datetime.now().isoformat()
        await emit_update()  # ← Emit completion
        
    except Exception as e:
        session["status"] = "error"
        session["error"] = str(e)
        session["end_time"] = datetime.now().isoformat()
        await emit_update()  # ← Emit error state
        logging.error(f"Processing failed for session {session_id}: {e}")
```

#### Frontend Changes

**1. Replace Polling with EventSource**

```javascript
// app/templates/ingest_v2.html

function startProgressStreaming() {
  // Close any existing stream
  if (window.progressEventSource) {
    window.progressEventSource.close();
  }
  
  // Create SSE connection
  const eventSource = new EventSource(`/api/ingest/stream/${currentSessionId}`);
  window.progressEventSource = eventSource;
  
  // Handle progress updates
  eventSource.onmessage = (event) => {
    try {
      const status = JSON.parse(event.data);
      updateProgressDisplay(status);  // ← Immediate update!
      
      // Check for completion
      if (status.status === 'completed') {
        eventSource.close();
        showPreviewSection();
      } else if (status.status === 'error') {
        eventSource.close();
        showError(`Processing failed: ${status.error || 'Unknown error'}`);
      }
    } catch (error) {
      console.error('Error parsing SSE data:', error);
    }
  };
  
  // Handle connection errors
  eventSource.onerror = (error) => {
    console.error('SSE connection error:', error);
    
    // Only show error if not completed
    if (eventSource.readyState === EventSource.CLOSED) {
      const session = processing_sessions[currentSessionId];
      if (session && session.status !== 'completed') {
        showError('Lost connection to server. Please refresh the page.');
      }
      eventSource.close();
    }
    // EventSource will automatically try to reconnect
  };
  
  // Clean up on page unload
  window.addEventListener('beforeunload', () => {
    if (window.progressEventSource) {
      window.progressEventSource.close();
    }
  });
}

async function startProcessing() {
  const parameters = {
    directory: document.getElementById('directory').value,
    pattern: document.getElementById('pattern').value,
    enable_nsfw_detection: document.getElementById('enable_nsfw_detection').checked,
    nsfw_threshold: parseFloat(document.getElementById('nsfw_threshold').value),
    extract_metadata: document.getElementById('extract_metadata').checked,
    extract_keywords: document.getElementById('extract_keywords').checked,
    import_scores: document.getElementById('import_scores').checked,
    max_files: document.getElementById('max_files').value ? parseInt(document.getElementById('max_files').value) : null
  };

  if (!parameters.directory) {
    alert('Please select a directory');
    return;
  }

  try {
    document.getElementById('process-btn').disabled = true;
    document.getElementById('process-btn').textContent = '🚀 Starting...';

    const response = await fetch('/api/ingest/process', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ parameters })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to start processing');
    }

    const result = await response.json();
    currentSessionId = result.session_id;

    updateWorkflowStep(2);
    showSection('progress-section');
    
    // ✨ CHANGED: Start SSE streaming instead of polling
    startProgressStreaming();

  } catch (error) {
    alert(`Error: ${error.message}`);
    document.getElementById('process-btn').disabled = false;
    document.getElementById('process-btn').textContent = '🚀 Start Processing';
  }
}

// Remove the old polling function completely
// function startProgressPolling() { ... }  ← DELETE THIS
```

**2. Enhanced Progress Display**

```javascript
// app/templates/ingest_v2.html

function updateProgressDisplay(status) {
  // Update progress bar with smooth animation
  const progressBar = document.getElementById('progress-bar');
  const currentWidth = parseFloat(progressBar.style.width) || 0;
  const targetWidth = status.progress;
  
  // Smooth transition (CSS handles this)
  progressBar.style.width = `${targetWidth}%`;
  
  // Update text
  document.getElementById('progress-text').textContent = 
    `Processing ${status.processed_files}/${status.total_files} files`;
  document.getElementById('progress-percentage').textContent = `${status.progress}%`;
  
  // Update current file with fade effect
  const currentFileEl = document.getElementById('current-file');
  if (status.current_file) {
    if (currentFileEl.textContent !== `Current: ${status.current_file}`) {
      currentFileEl.style.opacity = '0';
      setTimeout(() => {
        currentFileEl.textContent = `Current: ${status.current_file}`;
        currentFileEl.style.opacity = '1';
      }, 150);
    }
  }

  // Update stats (instant)
  const stats = status.stats;
  document.getElementById('stat-processed').textContent = stats.processed_files;
  document.getElementById('stat-metadata').textContent = stats.metadata_extracted;
  document.getElementById('stat-keywords').textContent = stats.keywords_added;
  document.getElementById('stat-scores').textContent = stats.scores_imported;
  document.getElementById('stat-nsfw').textContent = stats.nsfw_detected;
  document.getElementById('stat-errors').textContent = stats.errors;

  // Show errors if any
  if (status.errors && status.errors.length > 0) {
    showErrors(status.errors);
  }
  
  // Optional: Play sound or animation on milestones
  if (stats.processed_files % 10 === 0 && stats.processed_files > 0) {
    // Visual feedback for every 10 files
    progressBar.style.boxShadow = '0 0 10px rgba(74, 144, 226, 0.8)';
    setTimeout(() => {
      progressBar.style.boxShadow = 'none';
    }, 300);
  }
}
```

**3. CSS Enhancements for Smooth Updates**

```css
/* app/templates/ingest_v2.html - Add to style section */

.progress-bar {
  transition: width 0.3s ease-out;  /* Smooth progress animation */
}

.current-file {
  transition: opacity 0.15s ease-in-out;  /* Fade effect for file changes */
}

.stat-number {
  transition: transform 0.2s ease-out;  /* Scale effect on updates */
}

.stat-number.updated {
  animation: pulse 0.3s ease-out;
}

@keyframes pulse {
  0% { transform: scale(1); }
  50% { transform: scale(1.1); color: var(--accent-color, #4a90e2); }
  100% { transform: scale(1); }
}

/* Add visual feedback for active streaming */
.progress-section.streaming::before {
  content: '🔴 LIVE';
  position: absolute;
  top: 20px;
  right: 20px;
  background: #ff4444;
  color: white;
  padding: 4px 12px;
  border-radius: 12px;
  font-size: 0.8em;
  font-weight: bold;
  animation: blink 1.5s infinite;
}

@keyframes blink {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}
```

### Fallback Strategy

For environments where SSE may not be suitable (e.g., strict corporate proxies), implement a hybrid approach:

```javascript
// app/templates/ingest_v2.html

function startProgressUpdates() {
  // Try SSE first
  if (window.EventSource) {
    console.log('Using Server-Sent Events for progress updates');
    startProgressStreaming();
  } else {
    console.warn('EventSource not supported, falling back to polling');
    startProgressPolling();  // Keep old polling as fallback
  }
}
```

## Implementation Guide

### Phase 1: Backend Implementation (Week 1)

**Priority**: HIGH  
**Estimated Effort**: 4-6 hours

#### Tasks

1. **Add SSE streaming endpoint** (2 hours)
   - [ ] Create `/api/ingest/stream/{session_id}` endpoint
   - [ ] Implement `event_generator()` async function
   - [ ] Add progress queue management
   - [ ] Configure response headers for SSE

2. **Modify background processing** (1 hour)
   - [ ] Add `emit_update()` helper function
   - [ ] Insert update emissions after each file
   - [ ] Handle errors and emit error states
   - [ ] Test with various file counts

3. **Add cleanup logic** (1 hour)
   - [ ] Clean up queues when sessions end
   - [ ] Handle client disconnections gracefully
   - [ ] Add timeout for stale connections

4. **Testing** (1-2 hours)
   - [ ] Unit tests for streaming endpoint
   - [ ] Integration tests with mock processing
   - [ ] Load testing with multiple concurrent streams

### Phase 2: Frontend Implementation (Week 1)

**Priority**: HIGH  
**Estimated Effort**: 3-4 hours

#### Tasks

1. **Replace polling with SSE** (2 hours)
   - [ ] Implement `startProgressStreaming()` function
   - [ ] Add EventSource connection management
   - [ ] Handle reconnection logic
   - [ ] Remove old polling code

2. **Enhance UI feedback** (1 hour)
   - [ ] Add CSS transitions for smooth updates
   - [ ] Implement "LIVE" indicator
   - [ ] Add visual feedback for milestones
   - [ ] Improve error display

3. **Testing** (1 hour)
   - [ ] Browser compatibility testing (Chrome, Firefox, Safari, Edge)
   - [ ] Mobile responsiveness
   - [ ] Connection failure scenarios
   - [ ] Network throttling tests

### Phase 3: Documentation and Deployment (Week 2)

**Priority**: MEDIUM  
**Estimated Effort**: 2-3 hours

#### Tasks

1. **Update documentation** (1 hour)
   - [ ] Update `INGESTION_V2_README.md`
   - [ ] Document SSE architecture
   - [ ] Add troubleshooting section
   - [ ] Update API documentation

2. **Create migration guide** (1 hour)
   - [ ] Document changes from polling to SSE
   - [ ] Explain fallback strategy
   - [ ] Browser requirements
   - [ ] Proxy/firewall considerations

3. **Deployment** (1 hour)
   - [ ] Test in staging environment
   - [ ] Validate with real media files
   - [ ] Monitor server resources
   - [ ] Deploy to production

## Acceptance Criteria

### Functional Requirements

✅ **Real-time updates**: Progress indicators update within 100ms of backend changes

✅ **Accuracy**: All statistics (processed, metadata, keywords, scores, NSFW, errors) display correct values

✅ **Completeness**: Progress reaches 100% when all files are processed

✅ **Error handling**: Errors are displayed immediately when they occur

✅ **Connection resilience**: Automatic reconnection if connection drops

✅ **Browser compatibility**: Works in Chrome, Firefox, Safari, Edge (latest 2 versions)

### Performance Requirements

✅ **Latency**: Updates appear in UI within 100ms of backend emission

✅ **Throughput**: Supports processing of 1000+ files without UI lag

✅ **Resource usage**: No memory leaks during long processing sessions

✅ **Network efficiency**: Lower bandwidth usage than polling (no empty requests)

### User Experience Requirements

✅ **Immediate feedback**: Users see progress start within 1 second of clicking "Start Processing"

✅ **Smooth animations**: Progress bar updates smoothly without jumps

✅ **Clear status**: Current file name updates in real-time

✅ **Visual indicators**: "LIVE" badge shows active streaming

✅ **Error visibility**: Errors appear as they occur, not at the end

## Testing Strategy

### Unit Tests

```python
# tests/test_ingest_v2_streaming.py

import pytest
import asyncio
from app.routers.ingest_v2 import stream_progress, progress_queues

@pytest.mark.asyncio
async def test_sse_stream_sends_updates():
    """Test that SSE stream sends updates when queue receives them."""
    session_id = "test-session-123"
    queue = asyncio.Queue()
    progress_queues[session_id] = queue
    
    # Simulate updates
    updates = [
        {"progress": 10, "processed_files": 1},
        {"progress": 20, "processed_files": 2},
        {"progress": 100, "processed_files": 10, "status": "completed"}
    ]
    
    async def send_updates():
        for update in updates:
            await queue.put(update)
    
    # Test streaming
    asyncio.create_task(send_updates())
    
    # Collect streamed events
    events = []
    # ... test implementation ...
    
    assert len(events) == len(updates)
    assert events[-1]["progress"] == 100

@pytest.mark.asyncio
async def test_sse_stream_handles_disconnection():
    """Test that stream cleans up when client disconnects."""
    # ... test implementation ...
    pass
```

### Integration Tests

```python
# tests/test_ingest_v2_integration.py

@pytest.mark.asyncio
async def test_full_processing_workflow_with_streaming():
    """Test complete workflow from start to completion with SSE."""
    # ... test implementation ...
    pass
```

### Manual Testing Checklist

- [ ] Start processing with 10 files, verify updates appear immediately
- [ ] Start processing with 100 files, verify no UI lag
- [ ] Disconnect network mid-process, verify reconnection
- [ ] Process with various file types (images, videos)
- [ ] Trigger errors intentionally, verify they appear in real-time
- [ ] Test on mobile devices (iOS Safari, Android Chrome)
- [ ] Test with slow network (throttled to 3G)
- [ ] Open in multiple browser tabs simultaneously
- [ ] Refresh page during processing, verify session recovery

## Migration Path

### Backward Compatibility

The SSE implementation will coexist with the polling API initially:

1. **Keep polling endpoint**: `/api/ingest/status/{session_id}` remains available
2. **Add new SSE endpoint**: `/api/ingest/stream/{session_id}` for streaming
3. **Frontend detection**: Use SSE if supported, fall back to polling
4. **Deprecation period**: After 3 months, consider removing polling

### Deployment Steps

1. **Deploy backend changes** with both endpoints active
2. **Deploy frontend changes** with fallback logic
3. **Monitor metrics**: Track SSE vs polling usage
4. **Gradual rollout**: Enable SSE for 10% → 50% → 100% of users
5. **Deprecate polling**: After validation, remove old code

## Alternative Approaches Considered

### WebSockets

**Pros**: Bi-directional communication, full-duplex  
**Cons**: More complex, requires connection management, overkill for one-way updates  
**Verdict**: ❌ Not recommended - SSE is simpler for this use case

### Long Polling

**Pros**: Compatible with old browsers  
**Cons**: Still requires polling, more server resources  
**Verdict**: ❌ Not recommended - SSE is more efficient

### GraphQL Subscriptions

**Pros**: Flexible, powerful query language  
**Cons**: Requires GraphQL infrastructure, adds complexity  
**Verdict**: ❌ Not recommended - too much overhead for simple progress updates

### gRPC Streaming

**Pros**: High performance, type-safe  
**Cons**: Requires protobuf, not browser-native, complex setup  
**Verdict**: ❌ Not recommended - SSE is browser-native and simpler

## Risks and Mitigations

| Risk | Impact | Probability | Mitigation |
|------|--------|-------------|------------|
| Browser incompatibility | High | Low | Fallback to polling; test all major browsers |
| Proxy/firewall blocking | Medium | Medium | Document requirements; provide polling fallback |
| Memory leaks | High | Low | Implement cleanup; add timeout for stale connections |
| Server overload | Medium | Low | Limit concurrent streams; add connection pooling |
| Network instability | Medium | Medium | Auto-reconnect; show connection status to user |

## Success Metrics

### Quantitative

- **Update latency**: < 100ms from backend to frontend (target: < 50ms)
- **Bandwidth reduction**: 50-70% less than polling (no empty requests)
- **User satisfaction**: 90%+ positive feedback on "responsiveness"
- **Error rate**: < 0.1% failed streams

### Qualitative

- Users report "instant" progress updates
- No complaints about "stuck" progress bars
- Reduced support tickets related to progress tracking
- Positive developer feedback on maintainability

## Timeline

| Phase | Duration | Deliverables |
|-------|----------|--------------|
| Phase 1: Backend | 1 week | SSE endpoints, streaming logic, tests |
| Phase 2: Frontend | 1 week | EventSource integration, UI enhancements |
| Phase 3: Documentation | 3 days | Docs, migration guide, deployment |
| **Total** | **2.5 weeks** | **Production-ready SSE streaming** |

## Conclusion

The proposed SSE-based architecture addresses the root cause of delayed progress updates by replacing the polling mechanism with true server-to-client streaming. This provides:

1. ✅ **Immediate updates** as files are processed
2. ✅ **Lower network overhead** compared to polling
3. ✅ **Better user experience** with live feedback
4. ✅ **Simpler implementation** than WebSockets
5. ✅ **Browser-native support** with EventSource API

The implementation is straightforward, well-tested, and provides a clear migration path with fallback options for older environments.

**Recommendation**: Proceed with implementation in the next sprint.

---

## References

- [MDN: Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events)
- [W3C: EventSource Specification](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [FastAPI StreamingResponse](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)
- Current implementation: `app/routers/ingest_v2.py`
- Current frontend: `app/templates/ingest_v2.html`
- Previous fix: `PROGRESS_FIX_SUMMARY.md`
