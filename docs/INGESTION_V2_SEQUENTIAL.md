# Data Ingestion Tool v2 - Sequential Processing Implementation

## Overview

The Data Ingestion Tool v2 has been redesigned to process files **sequentially (one at a time)** with **immediate database commits** and **persistent server-side state**. This allows for real-time progress tracking and recovery from interruptions or browser refreshes.

## Key Features

### 1. Sequential File Processing
- **One-by-one processing**: Each file is processed individually and committed to the database immediately after completion
- **No batch commits**: Data is saved as soon as each file is processed, eliminating the need for a separate commit step
- **Immediate feedback**: Progress updates in real-time after each file completes

### 2. Persistent Server State
- **Local file storage**: Session state is stored in `.ingestion_state/` directory on the server
- **Recovery support**: If the browser is refreshed or crashes, the session can be resumed from where it left off
- **State includes**:
  - Total files in the batch
  - Count of completed files
  - Paths of ingested files
  - Current file being processed
  - Statistics (metadata, keywords, scores, NSFW detections)
  - Error logs

### 3. Real-Time Progress Tracking
- **Live statistics**: UI displays updated counts after every completed file
- **Progress bar**: Visual indication of overall progress (percentage complete)
- **Current file indicator**: Shows which file is currently being processed
- **Committed files counter**: Displays how many files have been saved to database

### 4. Directory-Tree Ingest Tracking
- **Visual indicators**: Each folder shows ingestion statistics in format `(ingested/total)`
- **Color coding**:
  - Green `(5/5)`: Fully ingested
  - Yellow `(3/5)`: Partially ingested
  - No badge: No files or not yet ingested
- **Recursive stats**: Statistics include files in immediate directory only

### 5. Page Refresh Recovery
- **Session persistence**: Active sessions survive browser refreshes
- **Automatic resume**: On page load, checks for active sessions and resumes display
- **Seamless experience**: Users can refresh the page without losing progress

## Architecture Changes

### Backend Changes

#### New Components

1. **`app/services/ingestion_state.py`**
   - `IngestionState`: Manages persistent state storage/retrieval
   - `SessionState`: Represents session data with methods for state management
   - Thread-safe file-based persistence

2. **Modified `app/routers/ingest_v2.py`**
   - `process_files_sequential()`: New background task for sequential processing
   - `commit_single_file_to_database()`: Commits each file immediately
   - `get_directory_ingest_stats()`: Calculates ingestion statistics per directory
   - Updated `/api/ingest/process`: Creates persistent session state
   - New `/api/ingest/resume`: Resumes interrupted sessions
   - Updated `/api/ingest/status`: Supports state recovery from disk
   - Updated `/api/ingest/directories`: Returns ingestion stats with directory listing

### Frontend Changes

#### Modified `app/templates/ingest_v2.html`

1. **Workflow Simplification**
   - Removed 4-step workflow (Configure → Process → Preview → Commit)
   - New 3-step workflow (Configure → Process & Commit → Complete)

2. **UI Updates**
   - Added "Committed" stat card to show files saved to database
   - Removed preview/report functionality (no longer needed)
   - Removed separate commit section

3. **JavaScript Enhancements**
   - `saveSessionToStorage()`: Saves session ID to sessionStorage
   - `clearSessionFromStorage()`: Clears session from storage
   - Page load recovery: Checks for active sessions and restores UI state
   - Updated progress display to show committed files count

4. **Directory Tree**
   - Displays ingestion statistics next to each folder
   - Color-coded badges for quick visual feedback

## API Changes

### New/Modified Endpoints

#### `POST /api/ingest/process`
- **Change**: Now creates persistent session state
- **Behavior**: Starts sequential processing with immediate commits
- **Requires**: Database must be enabled (enforced)

#### `POST /api/ingest/resume`
- **New endpoint**: Resume an interrupted session
- **Parameters**: `{ "session_id": "uuid" }`
- **Returns**: Session status and progress

#### `GET /api/ingest/status/{session_id}`
- **Change**: Now checks disk for session state if not in memory
- **Behavior**: Supports state recovery
- **Returns**: Full session status including committed files count

#### `GET /api/ingest/directories`
- **Change**: Now includes ingestion statistics
- **New fields**: 
  - `ingest_stats` (on directory objects): `{"total_files": N, "ingested_files": M}`
  - `ingest_stats` (on response root): Stats for current directory

#### Removed Endpoints
- `POST /api/ingest/commit` - No longer needed (commits are immediate)
- `GET /api/ingest/commit-status/{session_id}` - No longer needed
- `GET /api/ingest/report/{session_id}` - Preview reports removed

## Usage

### Starting a New Ingestion Session

1. Navigate to `http://localhost:7862/ingest-v2`
2. Configure parameters:
   - Select directory (use Browse button for directory tree)
   - Set file pattern (e.g., `*.png|*.jpg|*.mp4`)
   - Enable/disable NSFW detection
   - Configure metadata extraction options
3. Click "🚀 Start Processing"
4. Watch real-time progress as files are processed and committed

### Resuming After Browser Refresh

1. Simply refresh the page
2. The UI automatically detects the active session
3. Progress display is restored
4. If processing is still ongoing, updates continue

### Directory Tree Browser

1. Click "Browse" button next to directory input
2. Navigate through directories
3. Look for colored badges showing ingestion status:
   - `(5/5)` in green = fully ingested
   - `(3/5)` in yellow = partially ingested
4. Select desired directory and click "Select This Directory"

## File Structure

```
.ingestion_state/           # Persistent session state (auto-created)
├── {session-id-1}.json     # Session 1 state
├── {session-id-2}.json     # Session 2 state
└── ...

app/
├── routers/
│   └── ingest_v2.py        # Sequential processing implementation
├── services/
│   └── ingestion_state.py  # State persistence management
└── templates/
    └── ingest_v2.html      # Updated UI

tests/
└── test_sequential_ingestion.py  # Unit tests
```

## Database Requirements

**Important**: Sequential processing with immediate commits **requires database to be enabled**. 

The application will return an error if you try to start processing without database support:
```json
{
  "detail": "Database functionality is disabled. Sequential processing requires database."
}
```

### Enabling Database

See main README.md for database configuration instructions. Common setup:

```bash
# Using PostgreSQL
export DATABASE_URL="postgresql://user:password@localhost:5432/media_scorer"

# Or SQLite (for testing)
export DATABASE_URL="sqlite:///./media_scorer.db"
```

## Testing

### Unit Tests

```bash
# Run unit tests for state management
python -m pytest tests/test_sequential_ingestion.py -v
```

### Integration Tests

```bash
# Run full workflow test
python tests/test_ingestion_v2.py --directory ./media
```

### Manual Testing

1. Start the application with database enabled
2. Navigate to `/ingest-v2`
3. Process a small batch of files (use `max_files` parameter to limit)
4. Verify real-time updates
5. Refresh the page mid-processing
6. Verify that progress is restored
7. Check database for committed records

## Performance Considerations

### Sequential vs. Batch Processing

- **Sequential**: Each file is committed individually
  - **Pro**: Immediate feedback, can recover from failures
  - **Pro**: Database always in consistent state
  - **Con**: Slightly slower due to per-file commits
  
- **Old Batch**: All files processed, then single commit
  - **Pro**: Faster for large batches
  - **Con**: No progress updates until completion
  - **Con**: Lose all progress if fails before commit

### Optimization Tips

1. **Use filters**: Set max_files to limit batch size for testing
2. **Network location**: For best performance, run on local network
3. **Database**: PostgreSQL is faster than SQLite for large batches
4. **NSFW detection**: Disable if not needed (CPU-intensive)

## Troubleshooting

### Session not found after refresh
- Check that `.ingestion_state/` directory exists and is writable
- Check browser console for JavaScript errors
- Try starting a new session

### Files not appearing in database
- Verify database is enabled and accessible
- Check application logs for commit errors
- Verify file permissions on media directory

### Progress stuck/not updating
- Check browser network tab for failed API calls
- Check server logs for processing errors
- Try refreshing the page to resume

### Directory stats not showing
- Verify database is enabled
- Check that files were previously ingested
- Directory stats only count files in that specific directory (non-recursive)

## Migration from v1

If upgrading from the old batch processing workflow:

1. **No migration needed**: Old and new workflows are separate
2. **Old sessions**: Cannot be resumed with new workflow
3. **Database**: Existing data is compatible
4. **UI**: Access via `/ingest-v2` (old UI still at `/ingest`)

## Future Enhancements

Potential improvements for future versions:

- [ ] Pause/resume functionality
- [ ] Progress export (CSV/JSON report)
- [ ] Parallel processing (multiple files at once)
- [ ] Retry failed files
- [ ] Email/webhook notifications on completion
- [ ] Recursive directory stats
- [ ] Session history/audit log
