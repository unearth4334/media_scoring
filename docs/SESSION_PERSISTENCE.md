# Session Persistence for Ingest V2

## Overview

The ingest_v2 system now maintains session state in temporary files on the host, allowing in-progress ingestion jobs to survive page refreshes. This ensures users don't lose their work if they accidentally close or refresh the browser tab.

## Features

### 1. Automatic Session Saving
- Sessions are automatically saved to disk when created
- Progress updates are saved every 10 files during processing
- Final state is saved when processing completes or encounters an error
- Commit progress is also tracked and saved

### 2. Session Restoration on Page Load
When you visit `/ingest-v2`, the page automatically checks for active sessions and:
- Restores in-progress processing jobs (shows progress view with live updates)
- Restores completed jobs (shows preview/commit view)
- Restores commit-in-progress jobs (shows commit progress)
- Shows the parameter form only if no active session exists

### 3. Session Priority
The system prioritizes sessions based on:
1. **Active sessions first**: `processing`, `starting`, or `committing` states
2. **Most recent active session**: If multiple active sessions exist
3. **Recent completed sessions**: Within last 5 minutes
4. **Most recent overall**: Based on start time

## Technical Implementation

### Session Storage Location
```bash
# Inside the container
/tmp/media_scoring_sessions/{session_id}.json
```

### Session File Structure
```json
{
  "session_id": "815da50f-545e-4f1a-b0b5-17affee5d815",
  "status": "completed",
  "progress": 100,
  "total_files": 50,
  "current_file": "00047-248257778.png",
  "processed_files": 50,
  "stats": {
    "total_files": 50,
    "processed_files": 50,
    "metadata_extracted": 50,
    "keywords_added": 879,
    "scores_imported": 0,
    "nsfw_detected": 0,
    "errors": 0
  },
  "errors": [],
  "start_time": "2025-11-04T00:15:28.141664",
  "end_time": "2025-11-04T00:15:35.552189",
  "parameters": {
    "directory": "/media/txt2img-images/2025-10-21",
    "pattern": "*.png|*.jpg|*.jpeg",
    "enable_nsfw_detection": false,
    "nsfw_threshold": 0.5,
    "extract_metadata": true,
    "extract_keywords": true,
    "import_scores": true,
    "max_files": 50
  },
  "commit_progress": null,
  "commit_errors": []
}
```

### API Endpoints

#### Get Active Session
```bash
GET /api/ingest/active-session
```

**Response:**
```json
{
  "session_id": "815da50f-545e-4f1a-b0b5-17affee5d815",
  "status": "processing"
}
```

Returns `{"session_id": null, "status": null}` if no active session exists.

#### Get Session Status
```bash
GET /api/ingest/status/{session_id}
```

This endpoint now automatically loads sessions from disk if not in memory.

#### Delete Session
```bash
DELETE /api/ingest/session/{session_id}
```

Removes session from both memory and disk.

## Session Lifecycle

### 1. Session Creation
```python
# When user starts processing
session_id = str(uuid.uuid4())
processing_sessions[session_id] = {...}
save_session_to_disk(session_id, session_data)
```

### 2. During Processing
```python
# Every 10 files processed
if (i + 1) % 10 == 0:
    save_session_to_disk(session_id, session)
```

### 3. On Completion
```python
session["status"] = "completed"
session["end_time"] = datetime.now().isoformat()
save_session_to_disk(session_id, session)
```

### 4. On Page Load
```javascript
// Frontend checks for active session
async function checkForActiveSession() {
  const response = await fetch('/api/ingest/active-session');
  const data = await response.json();
  
  if (data.session_id) {
    // Restore appropriate view based on status
    currentSessionId = data.session_id;
    
    if (data.status === 'processing') {
      showSection('progress-section');
      startProgressPolling();
    } else if (data.status === 'completed') {
      showSection('preview-section');
    }
    // ... etc
  }
}
```

## Automatic Cleanup

### Session File Cleanup
Old session files are automatically cleaned up:
- **Trigger**: When a new ingestion starts
- **Age Threshold**: Sessions older than 24 hours
- **Method**: `cleanup_old_sessions(max_age_hours=24)`

### Manual Cleanup
Delete specific session:
```bash
curl -X DELETE http://10.0.78.66:7862/api/ingest/session/{session_id}
```

Or via container:
```bash
docker exec media-scorer rm /tmp/media_scoring_sessions/{session_id}.json
```

## User Experience

### Before (Without Persistence)
1. User starts ingesting 500 files
2. User accidentally refreshes the page
3. ❌ Progress is lost, back to parameter form
4. User must start over

### After (With Persistence)
1. User starts ingesting 500 files  
2. User accidentally refreshes the page
3. ✅ Progress view automatically restored
4. Live progress updates continue
5. User can see current status

## Testing Session Persistence

### Test 1: Refresh During Processing
```bash
# Start a large job
curl -X POST http://10.0.78.66:7862/api/ingest/process \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "directory": "/media/txt2img-images/2025-10-21",
      "max_files": 200,
      "enable_nsfw_detection": true
    }
  }'

# Immediately refresh the browser at http://10.0.78.66:7862/ingest-v2
# Expected: Progress view loads automatically with current stats
```

### Test 2: Check Active Session
```bash
# Get current active session
curl http://10.0.78.66:7862/api/ingest/active-session

# Should return session_id if one exists
```

### Test 3: Verify Session File
```bash
# List session files
docker exec media-scorer ls -lah /tmp/media_scoring_sessions/

# View session content
docker exec media-scorer cat /tmp/media_scoring_sessions/{session_id}.json | python -m json.tool
```

## Performance Considerations

### Disk I/O
- Session saves occur every 10 files (not every file)
- Minimal performance impact (~1-2ms per save)
- Uses `/tmp` directory (typically RAM-based tmpfs)

### Memory Usage
- Only active/recent sessions kept in memory
- Processed file data excluded from disk saves
- Old sessions automatically cleaned up

### File Size
- Typical session file: ~700 bytes to 1KB
- Excludes `processed_data` array (can be large)
- Excludes `files` array (paths only needed in memory)

## Troubleshooting

### Issue: Page doesn't restore session

**Check if session file exists:**
```bash
docker exec media-scorer ls /tmp/media_scoring_sessions/
```

**Check browser console:**
```javascript
// Should see log message
"Found active session: {session_id} Status: {status}"
```

**Verify API response:**
```bash
curl http://10.0.78.66:7862/api/ingest/active-session
```

### Issue: Old sessions not cleaning up

**Manually trigger cleanup:**
Start any new ingestion job - this triggers automatic cleanup.

**Check session ages:**
```bash
docker exec media-scorer find /tmp/media_scoring_sessions -name "*.json" -mtime +1
```

### Issue: Session shows wrong status

**Check session file directly:**
```bash
docker exec media-scorer cat /tmp/media_scoring_sessions/{session_id}.json | grep status
```

**Check server logs:**
```bash
docker logs media-scorer | grep session
```

## Future Enhancements

### Potential Improvements
1. **Database persistence**: Store sessions in PostgreSQL instead of temp files
2. **Session history**: Keep completed sessions for user review
3. **Multi-user support**: Track sessions per user
4. **Resume processing**: Allow resuming failed jobs from last checkpoint
5. **Session export**: Download session data as JSON report

### Known Limitations
1. Sessions don't survive container restarts (temp files are lost)
2. No cross-device session sharing
3. Single active session per browser (could support multiple)

## Security Considerations

### Session Isolation
- Session IDs are UUIDs (non-guessable)
- No authentication required (local network only)
- Files stored in container's `/tmp` (not host filesystem)

### Data Privacy
- Processed file data not saved to disk (memory only)
- Only metadata and statistics persisted
- Sessions auto-cleanup after 24 hours

---

**Date**: 2025-11-03  
**Author**: GitHub Copilot  
**Related Commits**:
- 539aee7: Add session persistence for ingest_v2 to survive page refreshes
- b63eec1: Fix active session detection to prioritize most recent session
