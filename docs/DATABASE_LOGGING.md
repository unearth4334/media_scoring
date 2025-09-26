# Database Interaction Logging

This document describes the detailed database interaction logging system implemented in the media scoring application.

## Overview

The database logging system provides comprehensive tracking of all database operations with the following features:

- **Daily Log Rotation**: New log file created each day with format `database_interactions_YYYY-MM-DD.log`
- **Detailed Operation Tracking**: All database operations, queries, transactions, and errors are logged
- **Configurable Logging**: Enable/disable logging and set log levels via configuration
- **Automatic Fallback**: Falls back to user home directory if `/app/.logs` is not writable

## Configuration

Database logging is configured in `config/config.yml`:

```yaml
# Database logging settings
enable_database_logging: true   # Enable detailed logging of all database interactions
database_log_dir: /app/.logs     # Directory for database interaction logs (daily rotation)
database_log_level: INFO        # Log level for database operations (DEBUG, INFO, WARNING, ERROR)
```

### Configuration Options

- `enable_database_logging`: Boolean to enable/disable database logging (default: true)
- `database_log_dir`: Directory path for log files (default: `/app/.logs`)
- `database_log_level`: Logging level - DEBUG, INFO, WARNING, ERROR (default: INFO)

## Log Format

Each log entry follows this format:

```
YYYY-MM-DD HH:MM:SS | LEVEL | FUNCTION_NAME | MESSAGE
```

### Example Log Entries

```
2025-09-26 07:00:07 | INFO  | _setup_daily_logger       | Database logger initialized for date: 2025-09-26
2025-09-26 07:00:07 | INFO  | log_operation             | DB_OP: START_get_or_create_media_file | args=(/path/to/file.jpg,)
2025-09-26 07:00:07 | INFO  | log_query                 | DB_QUERY: SELECT | table=media_files | params=file_path='/path/to/file.jpg' | results=1
2025-09-26 07:00:07 | INFO  | log_operation             | DB_OP: SUCCESS_get_or_create_media_file | id=123
2025-09-26 07:00:07 | INFO  | log_transaction           | DB_TRANSACTION: COMMIT | Session committed successfully
2025-09-26 07:00:07 | ERROR | log_error                 | DB_ERROR: update_media_file_score | error=Database connection lost
```

## Log Categories

### 1. Database Operations (DB_OP)
Tracks the start and completion of database service methods:
- `START_<method_name>`: Operation started with parameters
- `SUCCESS_<method_name>`: Operation completed successfully with results

### 2. Database Queries (DB_QUERY)
Logs SQL query operations:
- Query type (SELECT, INSERT, UPDATE, DELETE)  
- Target table
- Query parameters
- Result count

### 3. Database Transactions (DB_TRANSACTION)
Tracks transaction lifecycle:
- `SESSION_START`: Database session opened
- `BEGIN`: Transaction started
- `COMMIT`: Transaction committed
- `ROLLBACK`: Transaction rolled back
- `SESSION_END`: Database session closed

### 4. Database Errors (DB_ERROR)
Logs all database-related errors:
- Operation that failed
- Error message details

## Logged Operations

All public methods in `DatabaseService` are automatically logged:

### Media File Operations
- `get_or_create_media_file`
- `update_media_file_score`
- `get_media_file_score`
- `get_media_files_by_directory`
- `get_media_files_by_score`
- `get_all_media_files`
- `update_media_file_hashes`
- `find_similar_files_by_hash`

### Metadata Operations
- `store_media_metadata`
- `get_media_metadata`

### Keyword Operations
- `add_keywords`
- `search_by_keywords`
- `get_keywords_for_file`
- `get_all_keywords`

### Thumbnail Operations
- `store_thumbnail`
- `get_thumbnail`

### Utility Operations
- `get_stats`
- `cleanup_orphaned_records`

## File Location

Database logs are stored in the following locations:

1. **Primary Location**: `/app/.logs/`
2. **Fallback Location**: `~/.media_scoring/database_logs/` (if primary is not writable)

### Log File Naming

Files are named with the pattern: `database_interactions_YYYY-MM-DD.log`

Examples:
- `database_interactions_2025-09-26.log`
- `database_interactions_2025-09-27.log`

## Daily Rotation

The logging system automatically creates a new log file each day:

- New files are created at midnight (first log entry of new day)
- Previous day's log files are preserved
- No automatic cleanup - files accumulate over time

## Performance Impact

The database logging system is designed to be lightweight:

- Minimal overhead when logging is disabled
- Asynchronous file writing
- Efficient string formatting
- No impact on database transaction performance

## Troubleshooting

### Log Files Not Created

1. Check if database logging is enabled in configuration
2. Verify write permissions to `/app/.logs` directory
3. Check fallback location: `~/.media_scoring/database_logs/`
4. Review application startup logs for permission errors

### Missing Log Entries

1. Verify `database_log_level` configuration
2. Check if database operations are actually being performed
3. Ensure database service methods are being called (not bypassed)

### Log File Permissions

If running in Docker or with different users:

```bash
# Ensure proper permissions
mkdir -p /app/.logs
chmod 755 /app/.logs
chown -R app_user:app_group /app/.logs
```

## Integration

The logging system integrates automatically with the existing database service:

1. **Decorators**: All public database methods use `@log_db_operation` decorator
2. **Context Manager**: Session lifecycle is logged via `__enter__` and `__exit__` methods
3. **Error Handling**: Exceptions are logged before being re-raised

## Development

To add logging to new database operations:

```python
from .db_logger import log_db_operation

@log_db_operation("my_operation_name")
def my_database_method(self, param1, param2):
    # Method implementation
    pass
```

The decorator automatically handles:
- Operation start/success logging
- Parameter logging (configurable)
- Result logging (configurable)
- Error logging with stack traces