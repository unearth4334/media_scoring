# Progress Streaming Architecture Diagrams

This document provides visual representations of the current and proposed progress streaming architectures for the Ingest V2 WebUI.

---

## Current Architecture (Polling-Based)

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CURRENT POLLING APPROACH                      │
└─────────────────────────────────────────────────────────────────────┘

Step 1: User Starts Processing
┌──────────┐                                              ┌──────────┐
│          │  POST /api/ingest/process                    │          │
│ Frontend │─────────────────────────────────────────────▶│ Backend  │
│          │                                              │          │
└──────────┘                                              └────┬─────┘
                                                               │
                                                               │ Start
                                                               │ Background
                                                               │ Task
                                                               ▼
                                                         ┌──────────┐
                                                         │ Process  │
                                                         │ Files    │
                                                         │ Loop     │
                                                         └──────────┘

Step 2: Frontend Polls for Status (Every 1 Second)
┌──────────┐                                              ┌──────────┐
│          │  GET /api/ingest/status/{session_id}         │          │
│ Frontend │◀────────────────────────────────────────────▶│ Backend  │
│          │                                              │          │
│  Timer:  │  Response: {"progress": 30, "stats": {...}}  │ Session  │
│  1000ms  │                                              │  Store   │
│          │  GET /api/ingest/status/{session_id}         │          │
│          │◀────────────────────────────────────────────▶│          │
│          │                                              │          │
│          │  Response: {"progress": 40, "stats": {...}}  │          │
│          │                                              │          │
└──────────┘                                              └──────────┘
    ▲                                                           │
    │                                                           │
    └───────────────── Repeat every 1s ────────────────────────┘
```

### Timing Diagram

```
Time (ms):  0      500    1000   1500   2000   2500   3000   3500   4000
            │       │       │       │       │       │       │       │
Backend:    [File1] │  [File2] [File3] │  [File4] │  [File5] │  [File6]
            │       │       │       │       │       │       │       │
Frontend    │       │       │       │       │       │       │       │
Polls:      Poll────│───────Poll────│───────Poll────│───────Poll────│
            │       │       │       │       │       │       │       │
UI Shows:   0%      0%      20%     20%     40%     40%     60%     60%
            │       │       │       │       │       │       │       │
Reality:    10%     20%     30%     40%     50%     60%     70%     80%
            │       │       │       │       │       │       │       │
Lag:        -10%    -20%    -10%    -20%    -10%    -20%    -10%    -20%
```

**Problem**: UI is always 0-1 second behind reality!

### Component Interaction (Current)

```
┌────────────────────────────────────────────────────────────────┐
│                         Browser (Frontend)                     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐         ┌─────────────────┐                │
│  │ UI Component │         │  Polling Timer  │                │
│  │              │         │  (setInterval)  │                │
│  │ - Progress   │◀────────│                 │                │
│  │ - Stats      │         │  Every 1000ms   │                │
│  │ - Errors     │         └────────┬────────┘                │
│  └──────────────┘                  │                          │
│                                    │                          │
│                                    ▼                          │
│                          ┌─────────────────┐                  │
│                          │ Fetch API Call  │                  │
│                          └────────┬────────┘                  │
│                                   │                           │
└───────────────────────────────────┼───────────────────────────┘
                                    │ HTTP Request
                                    │ GET /api/ingest/status/{id}
                                    ▼
┌────────────────────────────────────────────────────────────────┐
│                        Server (Backend)                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐         ┌─────────────────┐                │
│  │   Router     │         │   Session       │                │
│  │   Handler    │────────▶│   Dictionary    │                │
│  │ get_status() │         │                 │                │
│  └──────────────┘         │  {session_id:   │                │
│                           │   {progress: 30,│                │
│                           │    stats: {...}}│                │
│         ▲                 └─────────────────┘                │
│         │                          ▲                          │
│         │                          │                          │
│         │                 ┌────────┴────────┐                │
│         │                 │  Background     │                │
│         │                 │  Processing     │                │
│         │                 │  Task           │                │
│         │                 │                 │                │
│         └─────────────────│ Updates session │                │
│           Return snapshot │ after each file │                │
│                           └─────────────────┘                │
└────────────────────────────────────────────────────────────────┘
```

---

## Proposed Architecture (SSE Streaming)

### High-Level Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                  PROPOSED SSE STREAMING APPROACH                     │
└─────────────────────────────────────────────────────────────────────┘

Step 1: User Starts Processing
┌──────────┐                                              ┌──────────┐
│          │  POST /api/ingest/process                    │          │
│ Frontend │─────────────────────────────────────────────▶│ Backend  │
│          │                                              │          │
└────┬─────┘                                              └────┬─────┘
     │                                                         │
     │                                                         │ Start
     │                                                         │ Background
     │                                                         │ Task
     │                                                         ▼
     │                                                   ┌──────────┐
     │                                                   │ Process  │
     │                                                   │ Files    │
     │                                                   │ Loop     │
     │                                                   └─────┬────┘
     │                                                         │
     │                                                         │
Step 2: Open SSE Stream (Long-Lived Connection)              │
┌────┴─────┐                                              ┌───┴──────┐
│          │  GET /api/ingest/stream/{session_id}         │          │
│ Frontend │◀═════════════════════════════════════════════│ Backend  │
│          │         EventSource Connection               │          │
│          │                                              │  Queue   │
│          │  ◀─── data: {"progress": 10, ...}            │          │
│          │                                              │    ▲     │
│  Real-   │  ◀─── data: {"progress": 20, ...}            │    │     │
│  time    │                                              │    │     │
│  Updates │  ◀─── data: {"progress": 30, ...}            │    │     │
│          │                                              │    │     │
│          │  ◀─── data: {"progress": 100, ...}           │    │     │
│          │                                              │    │     │
└──────────┘                                              └────┼─────┘
                                                               │
                                                               │
                                                          emit_update()
                                                          after each file
```

### Timing Diagram

```
Time (ms):  0      500    1000   1500   2000   2500   3000   3500   4000
            │       │       │       │       │       │       │       │
Backend:    [File1] │  [File2] [File3] │  [File4] │  [File5] │  [File6]
            ├──▶    │  ├──▶   ├──▶    │  ├──▶    │  ├──▶    │  ├──▶
            │   emit│  │  emit│  emit  │  │  emit │  │  emit │  │  emit
            │       │  │      │        │  │       │  │       │  │
Frontend    │       │  │      │        │  │       │  │       │  │
Receives:   ├──────▶│  ├─────▶├───────▶  ├──────▶│  ├──────▶│  ├─────▶
            │  <50ms│  │ <50ms│  <50ms │  │ <50ms│  │ <50ms │  │ <50ms
            │       │  │      │        │  │       │  │       │  │
UI Shows:   10%     │  20%    30%     │  40%     │  50%     │  60%
            │       │  │      │        │  │       │  │       │  │
Reality:    10%     │  20%    30%     │  40%     │  50%     │  60%
            │       │  │      │        │  │       │  │       │  │
Lag:        0ms     │  0ms    0ms     │  0ms     │  0ms     │  0ms
```

**Solution**: UI updates within 50ms of reality!

### Component Interaction (Proposed)

```
┌────────────────────────────────────────────────────────────────┐
│                         Browser (Frontend)                     │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐         ┌─────────────────┐                │
│  │ UI Component │         │  EventSource    │                │
│  │              │         │  Connection     │                │
│  │ - Progress   │◀────────│                 │                │
│  │ - Stats      │         │  .onmessage     │                │
│  │ - Errors     │         │  .onerror       │                │
│  └──────────────┘         └────────┬────────┘                │
│                                    │                          │
│                                    │ Persistent               │
│                                    │ HTTP Connection          │
│                                    │ (EventStream)            │
└───────────────────────────────────┼───────────────────────────┘
                                    │
                                    ║ SSE Stream
                                    ║ (Server pushes data)
                                    ▼
┌────────────────────────────────────────────────────────────────┐
│                        Server (Backend)                        │
├────────────────────────────────────────────────────────────────┤
│                                                                │
│  ┌──────────────┐         ┌─────────────────┐                │
│  │ SSE Endpoint │         │  Event Queue    │                │
│  │              │────────▶│  (asyncio.Queue)│                │
│  │ /stream/{id} │         │                 │                │
│  │              │         │  per session_id │                │
│  │ async        │◀────────│                 │                │
│  │ generator    │  Yield  │  .put(update)   │                │
│  └──────────────┘  events └────────┬────────┘                │
│         │                           ▲                          │
│         │                           │                          │
│         │                  ┌────────┴────────┐                │
│         │                  │  Background     │                │
│         │                  │  Processing     │                │
│         │                  │  Task           │                │
│         │                  │                 │                │
│         │                  │ emit_update()   │                │
│         │                  │ after each file │                │
│         │                  └─────────────────┘                │
│         │                                                      │
│         ▼                                                      │
│  ┌──────────────┐                                             │
│  │   Session    │                                             │
│  │  Dictionary  │                                             │
│  │              │                                             │
│  │ {session_id: │                                             │
│  │  {progress,  │                                             │
│  │   stats}}    │                                             │
│  └──────────────┘                                             │
└────────────────────────────────────────────────────────────────┘
```

### Data Flow Sequence

```
┌─────────┐         ┌─────────┐         ┌─────────┐         ┌─────────┐
│Frontend │         │ Router  │         │  Queue  │         │  Task   │
└────┬────┘         └────┬────┘         └────┬────┘         └────┬────┘
     │                   │                   │                   │
     │ POST /process     │                   │                   │
     │──────────────────▶│                   │                   │
     │                   │                   │                   │
     │                   │ create queue      │                   │
     │                   │──────────────────▶│                   │
     │                   │                   │                   │
     │                   │ start task        │                   │
     │                   │───────────────────────────────────────▶│
     │◀──────────────────│                   │                   │
     │ session_id        │                   │                   │
     │                   │                   │                   │
     │ GET /stream/{id}  │                   │                   │
     │──────────────────▶│                   │                   │
     │                   │                   │                   │
     │                   │ wait for updates  │                   │
     │                   │◀──────────────────│                   │
     │                   │                   │                   │
     │                   │                   │   processing...   │
     │                   │                   │                   │
     │                   │                   │   file 1 done     │
     │                   │                   │◀──────────────────│
     │                   │   yield update    │   emit_update()   │
     │◀──────────────────│◀──────────────────│                   │
     │ data: {progress}  │                   │                   │
     │                   │                   │                   │
     │                   │ wait for updates  │                   │
     │                   │◀──────────────────│                   │
     │                   │                   │                   │
     │                   │                   │   file 2 done     │
     │                   │                   │◀──────────────────│
     │                   │   yield update    │   emit_update()   │
     │◀──────────────────│◀──────────────────│                   │
     │ data: {progress}  │                   │                   │
     │                   │                   │                   │
     │     (repeat for each file processed)  │                   │
     │                   │                   │                   │
     │                   │                   │   all files done  │
     │                   │                   │◀──────────────────│
     │                   │   yield complete  │   emit_update()   │
     │◀──────────────────│◀──────────────────│                   │
     │ data: {status}    │                   │                   │
     │                   │                   │                   │
     │ close connection  │                   │                   │
     ├───────────────────X                   │                   │
     │                   │                   │                   │
     │                   │ cleanup queue     │                   │
     │                   │──────────────────▶│                   │
     │                   │                   X                   │
```

---

## Comparison Matrix

| Aspect | Current (Polling) | Proposed (SSE) |
|--------|-------------------|----------------|
| **Update Mechanism** | Pull (client requests) | Push (server sends) |
| **Latency** | 0-1000ms | 0-100ms |
| **Network Efficiency** | Low (many empty polls) | High (events only) |
| **Complexity** | Medium (timer management) | Low (browser handles) |
| **Real-time** | No (discrete snapshots) | Yes (continuous stream) |
| **Browser Support** | All browsers | Modern browsers (95%+) |
| **Reconnection** | Manual | Automatic |
| **Resource Usage** | Higher (repeated requests) | Lower (single connection) |

---

## Benefits Visualization

```
Current Polling:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                                          TIME
  │      │      │      │      │      │      │      │      │
  ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼      ▼
Request  Req    Req    Req    Req    Req    Req    Req   Req
  │      │      │      │      │      │      │      │      │
  └─────┘      └─────┘        └──────┘      └──────┘
   Empty        Empty          Update        Update
   
  Problem: Wasted requests when no updates available


Proposed SSE:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
                                                          TIME
  Connection Established
  ║
  ║ (idle... no data sent)
  ║
  ╠═▶ Update 1
  ║
  ║ (idle... no data sent)
  ║
  ╠═▶ Update 2
  ║
  ╠═▶ Update 3
  ║
  ║ (idle... no data sent)
  ║
  ╠═▶ Update 4
  ║
  Connection Closed
  
  Benefit: Data only sent when updates available
```

---

## Migration Path

```
Phase 1: Dual Operation (Weeks 1-2)
┌──────────────────────────────────────────┐
│  Frontend supports both:                 │
│  - Polling (fallback)                    │
│  - SSE (preferred)                       │
│                                          │
│  Backend provides both:                  │
│  - /api/ingest/status (existing)         │
│  - /api/ingest/stream (new)              │
└──────────────────────────────────────────┘

Phase 2: SSE Primary (Weeks 3-4)
┌──────────────────────────────────────────┐
│  Frontend auto-detects:                  │
│  - Use SSE if EventSource available      │
│  - Fall back to polling if not           │
│                                          │
│  Backend maintains both endpoints        │
└──────────────────────────────────────────┘

Phase 3: SSE Only (Week 5+)
┌──────────────────────────────────────────┐
│  Frontend uses SSE exclusively           │
│                                          │
│  Backend deprecates polling:             │
│  - Mark /api/ingest/status deprecated    │
│  - Remove after 3 months                 │
└──────────────────────────────────────────┘
```

---

## References

- Full proposal: [docs/PROGRESS_STREAMING_REDESIGN_PROPOSAL.md](docs/PROGRESS_STREAMING_REDESIGN_PROPOSAL.md)
- Implementation checklist: [PROGRESS_STREAMING_IMPLEMENTATION_CHECKLIST.md](PROGRESS_STREAMING_IMPLEMENTATION_CHECKLIST.md)
- Quick summary: [PROGRESS_STREAMING_REDESIGN_SUMMARY.md](PROGRESS_STREAMING_REDESIGN_SUMMARY.md)
