# Progress Streaming Redesign - Implementation Checklist

This checklist tracks the implementation of the Server-Sent Events (SSE) based progress streaming mechanism for the Ingest V2 WebUI.

**Reference**: [docs/PROGRESS_STREAMING_REDESIGN_PROPOSAL.md](docs/PROGRESS_STREAMING_REDESIGN_PROPOSAL.md)

---

## Phase 1: Backend Implementation (Week 1)

**Estimated Effort**: 4-6 hours

### Task 1: Add SSE Streaming Endpoint (2 hours)

- [ ] Create new route `@router.get("/api/ingest/stream/{session_id}")`
- [ ] Implement `event_generator()` async generator function
- [ ] Add global `progress_queues: Dict[str, asyncio.Queue]` dictionary
- [ ] Create `get_session_status()` helper function
- [ ] Configure StreamingResponse headers:
  - [ ] `Cache-Control: no-cache`
  - [ ] `Connection: keep-alive`
  - [ ] `X-Accel-Buffering: no` (for nginx)
- [ ] Implement keepalive messages (send every 1s when no updates)
- [ ] Add cleanup logic in `finally` block

**Files to modify**:
- `app/routers/ingest_v2.py`

### Task 2: Modify Background Processing (1 hour)

- [ ] Add `emit_update()` helper function in `process_files_background()`
- [ ] Emit update when status changes to "processing"
- [ ] Emit update when current file changes
- [ ] Emit update after each file is processed
- [ ] Emit update when errors occur
- [ ] Emit update when processing completes
- [ ] Emit update when processing fails

**Files to modify**:
- `app/routers/ingest_v2.py` (function `process_files_background()`)

### Task 3: Add Cleanup Logic (1 hour)

- [ ] Clean up queue when session ends
- [ ] Handle client disconnections (AsyncCancelledError)
- [ ] Add timeout for stale connections (configurable, default 5 minutes)
- [ ] Remove queue from global dict on cleanup
- [ ] Add logging for queue lifecycle events

**Files to modify**:
- `app/routers/ingest_v2.py`

### Task 4: Backend Testing (1-2 hours)

- [ ] Create `tests/test_ingest_v2_streaming.py`
- [ ] Unit test: SSE stream sends updates
- [ ] Unit test: SSE stream handles client disconnection
- [ ] Unit test: Multiple concurrent streams
- [ ] Integration test: Full processing workflow with SSE
- [ ] Load test: 10+ concurrent streams
- [ ] Verify no memory leaks with long-running sessions

**Files to create**:
- `tests/test_ingest_v2_streaming.py`

---

## Phase 2: Frontend Implementation (Week 1)

**Estimated Effort**: 3-4 hours

### Task 1: Replace Polling with SSE (2 hours)

- [ ] Create `startProgressStreaming()` function
- [ ] Initialize EventSource with `/api/ingest/stream/${currentSessionId}`
- [ ] Implement `onmessage` handler to parse JSON and call `updateProgressDisplay()`
- [ ] Implement `onerror` handler for connection issues
- [ ] Add connection state tracking (connected, disconnected, reconnecting)
- [ ] Close EventSource on completion or error
- [ ] Add cleanup on page unload (`beforeunload` event)
- [ ] Update `startProcessing()` to call `startProgressStreaming()` instead of polling
- [ ] **REMOVE** `startProgressPolling()` function
- [ ] **REMOVE** `processingTimer` variable and related cleanup

**Files to modify**:
- `app/templates/ingest_v2.html` (JavaScript section)

### Task 2: Enhance UI Feedback (1 hour)

- [ ] Add CSS transition for smooth progress bar animation
- [ ] Add fade effect for current file name changes
- [ ] Add "LIVE" indicator badge during active streaming
- [ ] Add pulse animation for stat numbers when they update
- [ ] Add visual feedback for milestone achievements (every 10 files)
- [ ] Add connection status indicator (connected/reconnecting/disconnected)
- [ ] Improve error display with timestamps

**Files to modify**:
- `app/templates/ingest_v2.html` (CSS section)
- `app/templates/ingest_v2.html` (JavaScript section, `updateProgressDisplay()` function)

### Task 3: Add Fallback Support (Optional) (30 minutes)

- [ ] Create `startProgressUpdates()` wrapper function
- [ ] Detect EventSource support: `if (window.EventSource)`
- [ ] Call `startProgressStreaming()` if supported
- [ ] Fall back to `startProgressPolling()` if not supported
- [ ] Log fallback decision to console
- [ ] Keep polling code for fallback only

**Files to modify**:
- `app/templates/ingest_v2.html` (JavaScript section)

### Task 4: Frontend Testing (1 hour)

- [ ] **Browser compatibility**: Chrome (latest 2 versions)
- [ ] **Browser compatibility**: Firefox (latest 2 versions)
- [ ] **Browser compatibility**: Safari (latest 2 versions)
- [ ] **Browser compatibility**: Edge (latest 2 versions)
- [ ] **Mobile**: iOS Safari
- [ ] **Mobile**: Android Chrome
- [ ] **Network**: Throttle to 3G, verify smooth updates
- [ ] **Network**: Disconnect mid-process, verify reconnection
- [ ] **Multiple tabs**: Open same page in 2+ tabs
- [ ] **Page refresh**: Refresh during processing, verify recovery
- [ ] **Long session**: Process 100+ files, check for memory leaks

**Tools**:
- Chrome DevTools (Network tab, Performance tab)
- Firefox Developer Tools
- Safari Web Inspector
- Network Link Conditioner (macOS) or Chrome Network Throttling

---

## Phase 3: Documentation and Deployment (Week 2)

**Estimated Effort**: 2-3 hours

### Task 1: Update Documentation (1 hour)

- [ ] Update `docs/INGESTION_V2_README.md`:
  - [ ] Add section on SSE streaming architecture
  - [ ] Update "Enhanced Progress Tracking" section
  - [ ] Add browser requirements
  - [ ] Update API endpoints section with `/stream` endpoint
- [ ] Update `README.md` (if applicable)
- [ ] Add troubleshooting section for SSE issues
- [ ] Document proxy/firewall considerations

**Files to modify**:
- `docs/INGESTION_V2_README.md`
- `README.md` (optional)

### Task 2: Create Migration Guide (1 hour)

- [ ] Document breaking changes (none expected, SSE is additive)
- [ ] Explain polling vs. SSE differences
- [ ] List browser requirements (EventSource support)
- [ ] Document fallback strategy
- [ ] Provide proxy/firewall configuration examples
- [ ] Add monitoring recommendations

**Files to create**:
- `docs/PROGRESS_STREAMING_MIGRATION_GUIDE.md`

### Task 3: Deployment (1 hour)

- [ ] **Staging deployment**:
  - [ ] Deploy backend changes to staging
  - [ ] Deploy frontend changes to staging
  - [ ] Run full test suite in staging
  - [ ] Process 10 test files, verify real-time updates
  - [ ] Process 100 test files, verify performance
  - [ ] Check server logs for errors
  - [ ] Monitor CPU/memory usage
- [ ] **Production deployment**:
  - [ ] Deploy backend to production
  - [ ] Deploy frontend to production
  - [ ] Enable for 10% of users (feature flag, if available)
  - [ ] Monitor error rates and performance
  - [ ] Gradually increase to 50%, then 100%
  - [ ] Monitor user feedback

**Monitoring**:
- Server logs: Check for SSE connection errors
- Network metrics: Bandwidth usage (should decrease)
- User metrics: Session duration, completion rates
- Error metrics: SSE connection failures, reconnection attempts

---

## Acceptance Testing

Before marking complete, verify all acceptance criteria:

### Functional Requirements

- [ ] Progress indicators update within 100ms of backend changes
- [ ] All statistics display correct values (processed, metadata, keywords, scores, NSFW, errors)
- [ ] Progress reaches exactly 100% when all files are processed
- [ ] Errors display immediately when they occur
- [ ] Connection automatically reconnects if dropped
- [ ] Works in Chrome, Firefox, Safari, Edge (latest 2 versions)

### Performance Requirements

- [ ] Updates appear in UI within 100ms of backend emission (measure with DevTools)
- [ ] Supports processing 1000+ files without UI lag
- [ ] No memory leaks during long processing sessions (check with DevTools Memory profiler)
- [ ] Network bandwidth usage lower than polling (measure with DevTools Network tab)

### User Experience Requirements

- [ ] Users see progress start within 1 second of clicking "Start Processing"
- [ ] Progress bar updates smoothly without jumps
- [ ] Current file name updates in real-time
- [ ] "LIVE" badge shows active streaming
- [ ] Errors appear as they occur, not at the end

---

## Rollback Plan

If issues are discovered after deployment:

1. **Immediate**: Revert frontend to polling (keep SSE endpoint for future)
   - [ ] Restore `startProgressPolling()` function
   - [ ] Change `startProcessing()` to call polling instead of streaming
2. **Investigate**: Check server logs and browser console for errors
3. **Fix**: Address issues identified
4. **Redeploy**: After fix is validated in staging

---

## Notes

- **Priority**: All Phase 1 and Phase 2 tasks are HIGH priority
- **Dependencies**: Phase 2 depends on Phase 1 completion
- **Testing**: Cannot be skipped - critical for production readiness
- **Documentation**: Required before production deployment

---

## Sign-off

- [ ] **Backend Lead**: Approved backend implementation
- [ ] **Frontend Lead**: Approved frontend implementation
- [ ] **QA Lead**: All tests passed
- [ ] **DevOps Lead**: Deployment successful
- [ ] **Product Owner**: Acceptance criteria met

---

## Completion Status

- [ ] Phase 1: Backend Implementation
- [ ] Phase 2: Frontend Implementation
- [ ] Phase 3: Documentation and Deployment
- [ ] Acceptance Testing
- [ ] Production Deployment

**Target Completion Date**: _____________

**Actual Completion Date**: _____________
