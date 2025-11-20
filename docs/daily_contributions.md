# Daily Contribution Tallies Feature

## Overview
This feature adds a pre-computed database table for daily contribution tallies to optimize the performance of the contribution graph rendering.

## Problem
Previously, the `/api/media/daily-counts` endpoint had to:
1. Query ALL media files from the database
2. Group them by creation date in memory
3. Count files for each date

This approach became slow as the number of media files grew, especially for large datasets with thousands of files.

## Solution
We introduced a new `daily_contributions` table that:
1. Stores pre-computed tallies of files per date
2. Gets incrementally updated during file ingestion
3. Can be rebuilt from existing media files if needed

## Performance Improvement
**4.9x faster** when querying contribution data:
- **Old approach**: 2.89ms (query all media files and group)
- **New approach**: 0.59ms (query pre-computed table)

## Database Schema

### New Table: `daily_contributions`
```sql
CREATE TABLE daily_contributions (
    id INTEGER PRIMARY KEY,
    date TIMESTAMP NOT NULL UNIQUE,  -- Date at midnight UTC
    count INTEGER NOT NULL DEFAULT 0,  -- Number of files created on this date
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE INDEX idx_daily_contribution_date ON daily_contributions (date);
```

## API Changes

### `/api/media/daily-counts` Endpoint
**Before**: Queried all MediaFile records and grouped by date
**After**: Queries the `daily_contributions` table directly

Response format unchanged:
```json
{
  "daily_counts": {
    "2025-11-20": 5,
    "2025-11-19": 6,
    "2025-11-18": 7
  },
  "total_files": 18,
  "total_days": 3
}
```

## Ingestion Workflow

### Modified: `_commit_single_file()` in `ingest_v2.py`
When committing a file to the database, the function now:
1. Creates/updates the MediaFile record
2. Extracts the file's creation date from `original_created_at` or `created_at`
3. Calls `db.increment_daily_contribution(date, count=1)` to update the tally

### Example
```python
# In _commit_single_file()
contribution_date = media_file.original_created_at or media_file.created_at
if contribution_date:
    db.increment_daily_contribution(contribution_date, count=1)
    db.session.flush()
```

## Database Service Methods

### New Methods in `DatabaseService`

#### `increment_daily_contribution(date, count=1)`
Increments the contribution count for a specific date.
- Creates a new record if the date doesn't exist
- Updates the existing record if it does
- Normalizes the date to midnight UTC

#### `get_all_daily_contributions()`
Returns all daily contribution records as a list of (date, count) tuples.

#### `rebuild_daily_contributions()`
Rebuilds the entire table from scratch by:
1. Clearing all existing records
2. Querying all MediaFile records
3. Grouping by creation date
4. Creating new DailyContribution records

Useful for:
- Initial setup on existing databases
- Fixing data inconsistencies
- Manual corrections

## Migration

The migration automatically creates the `daily_contributions` table on database initialization.

For existing databases:
```python
from app.database.engine import get_engine
from app.database.migrations import migrate_database

engine = get_engine()
migrate_database(engine)  # Creates the table if it doesn't exist
```

## Testing

### Unit Tests: `test_daily_contributions.py`
Tests:
- Creating and updating contribution records
- Incrementing counts
- Date normalization
- Rebuild functionality

### Integration Tests: `test_ingest_v2_contributions.py`
Tests:
- Full ingestion workflow
- Contribution tallies updated during commit
- Multiple files on same date
- Rebuild from existing media files

### Manual Verification: `manual_verify_contributions.py`
Demonstrates:
- Complete workflow with 100 files across 10 days
- Performance comparison between old and new approaches
- Rebuild functionality
- API endpoint behavior

## Maintenance

### Rebuilding Contributions
If the tallies get out of sync (e.g., due to manual database edits):

```python
from app.database.service import DatabaseService

with DatabaseService() as db:
    count = db.rebuild_daily_contributions()
    print(f"Rebuilt {count} contribution records")
```

### Monitoring
The contribution tallies should match the actual file counts:

```python
with DatabaseService() as db:
    # Get tally total
    contributions = db.get_all_daily_contributions()
    tally_total = sum(count for _, count in contributions)
    
    # Get actual file count
    from app.database.models import MediaFile
    actual_total = db.session.query(MediaFile).count()
    
    if tally_total != actual_total:
        print(f"Warning: Tallies ({tally_total}) don't match files ({actual_total})")
        print("Consider running rebuild_daily_contributions()")
```

## Backwards Compatibility
- The endpoint response format is unchanged
- Falls back to filesystem scanning if database is disabled
- Automatically rebuilds table if empty when first accessed
- No breaking changes to existing API consumers

## Future Improvements
- Add background job to periodically verify tallies
- Add endpoint to manually trigger rebuild
- Add caching layer for frequently accessed date ranges
- Consider hourly granularity for real-time dashboards
