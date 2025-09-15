# Database Architecture Guide

## Overview

This document describes the database implementation for the Media Scoring application. The database system provides persistent storage for media file metadata, scoring data, searchable keywords, and thumbnail information.

## Technology Stack

- **Database**: SQLite (file-based, no server required)
- **ORM**: SQLAlchemy 2.0+ with declarative models
- **Migration**: Alembic (for future schema changes)
- **Location**: Stored in `.scores/media.db` within each media directory

## Database Schema

### MediaFile Table

Primary entity representing media files in the system.

```sql
CREATE TABLE media_files (
    id INTEGER PRIMARY KEY,
    filename VARCHAR(512) NOT NULL,
    directory VARCHAR(1024) NOT NULL,
    file_path VARCHAR(1536) NOT NULL UNIQUE,
    file_size INTEGER,
    file_type VARCHAR(50),  -- 'video', 'image'
    extension VARCHAR(10),
    score INTEGER DEFAULT 0,  -- -1 to 5 (-1=rejected, 0=unrated, 1-5=stars)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    last_accessed DATETIME
);
```

**Indexes:**
- `idx_media_file_path` on `file_path` (unique lookups)
- `idx_media_directory` on `directory` (directory scans)
- `idx_media_score` on `score` (filtering by rating)
- `idx_media_type` on `file_type` (filtering by media type)
- `idx_media_updated` on `updated_at` (sorting by recency)

### MediaMetadata Table

Detailed technical and AI-related metadata for media files.

```sql
CREATE TABLE media_metadata (
    id INTEGER PRIMARY KEY,
    media_file_id INTEGER REFERENCES media_files(id),
    
    -- Dimensions and technical metadata
    width INTEGER,
    height INTEGER,
    duration FLOAT,  -- Video duration in seconds
    frame_rate FLOAT,
    color_mode VARCHAR(50),  -- RGB, RGBA, etc.
    has_alpha BOOLEAN DEFAULT FALSE,
    
    -- AI/Generation metadata
    png_text TEXT,  -- JSON string of PNG text chunks
    workflow_data TEXT,  -- JSON string of ComfyUI workflow
    prompt TEXT,
    negative_prompt TEXT,
    model_name VARCHAR(256),
    sampler VARCHAR(100),
    steps INTEGER,
    cfg_scale FLOAT,
    seed VARCHAR(50),
    
    -- File tracking
    file_modified_at DATETIME,
    metadata_extracted_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Indexes:**
- `idx_metadata_media_file` on `media_file_id`
- `idx_metadata_dimensions` on `width, height`
- `idx_metadata_model` on `model_name`

### MediaKeyword Table

Searchable keywords and tags associated with media files.

```sql
CREATE TABLE media_keywords (
    id INTEGER PRIMARY KEY,
    media_file_id INTEGER REFERENCES media_files(id),
    keyword VARCHAR(256) NOT NULL,
    keyword_type VARCHAR(50) DEFAULT 'user',  -- 'user', 'prompt', 'auto', 'workflow'
    confidence FLOAT DEFAULT 1.0,  -- For auto-generated keywords
    source VARCHAR(100),  -- Where keyword came from
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Constraints:**
- Unique constraint on `(media_file_id, keyword, keyword_type)`

**Indexes:**
- `idx_keyword_media_file` on `media_file_id`
- `idx_keyword_search` on `keyword` (text searches)
- `idx_keyword_type` on `keyword_type`

### MediaThumbnail Table

Thumbnail storage (either as base64 data or file paths).

```sql
CREATE TABLE media_thumbnails (
    id INTEGER PRIMARY KEY,
    media_file_id INTEGER REFERENCES media_files(id),
    thumbnail_size VARCHAR(20) NOT NULL,  -- e.g., '64x64', '128x128'
    thumbnail_data TEXT,  -- Base64 encoded image data
    mime_type VARCHAR(50) DEFAULT 'image/jpeg',
    file_path VARCHAR(1024),  -- Alternative: path to thumbnail file
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Constraints:**
- Unique constraint on `(media_file_id, thumbnail_size)`

## Database Service Layer

### DatabaseService Class

The `DatabaseService` class provides a high-level interface for database operations:

```python
from app.database import DatabaseService

# Usage with context manager (recommended)
with DatabaseService() as db:
    media_file = db.get_or_create_media_file(file_path)
    db.update_media_file_score(file_path, 5)
    keywords = db.search_by_keywords(["portrait", "anime"])
```

### Key Methods

**File Operations:**
- `get_or_create_media_file(file_path)` - Get existing or create new file record
- `update_media_file_score(file_path, score)` - Update file score
- `get_media_files_by_directory(directory)` - Get all files in directory
- `get_media_files_by_score(min_score, max_score)` - Filter by score range

**Metadata Operations:**
- `store_media_metadata(file_path, metadata)` - Store/update metadata
- `get_media_metadata(file_path)` - Retrieve metadata

**Search Operations:**
- `search_by_keywords(keywords, match_all=False)` - Search files by keywords
- `add_keywords(file_path, keywords, keyword_type)` - Add keywords to file
- `get_keywords_for_file(file_path)` - Get all keywords for file
- `get_all_keywords(keyword_type=None)` - Get all unique keywords

**Thumbnail Operations:**
- `store_thumbnail(file_path, size, data)` - Store thumbnail data
- `get_thumbnail(file_path, size)` - Retrieve thumbnail

## API Integration

### New Search Endpoints

The database enables powerful new API endpoints:

**Search Files:**
```http
POST /api/search/files
Content-Type: application/json

{
  "keywords": ["portrait", "anime"],
  "match_all": false,
  "file_types": ["png", "jpg"],
  "min_score": 3
}
```

**Add Keywords:**
```http
POST /api/search/keywords
Content-Type: application/json

{
  "filename": "image001.png",
  "keywords": ["portrait", "detailed", "high_quality"],
  "keyword_type": "user"
}
```

**Get Keywords:**
```http
GET /api/search/keywords?keyword_type=user
GET /api/search/keywords/image001.png
```

**Database Stats:**
```http
GET /api/search/stats
```

**Sync Directory:**
```http
POST /api/search/sync
```

## Configuration

### Settings

Database functionality is controlled by these settings:

```yaml
# config.yml
enable_database: true  # Enable/disable database functionality
database_path: null    # Custom database path (default: .scores/media.db)
```

**Command Line:**
```bash
python run.py --enable-database --database-path /custom/path/media.db
python run.py --disable-database
```

### Default Database Location

When `database_path` is not specified, the database is created at:
```
{media_directory}/.scores/media.db
```

This keeps the database alongside the media files and sidecar score files.

## Automatic Metadata Extraction

### When Metadata is Extracted

1. **Directory Scanning**: When switching directories or starting the app
2. **On-Demand**: When metadata is requested via `/api/meta/{filename}`
3. **Manual Sync**: Via `/api/search/sync` endpoint

### Extracted Information

**From Video Files (via ffprobe):**
- Dimensions (width, height)
- Duration and frame rate
- ComfyUI workflow data from metadata tags

**From Image Files (via Pillow + PNG chunks):**
- Dimensions and color information
- PNG text parameters (common in AI-generated images)
- Auto1111/ComfyUI generation parameters

**Automatic Keyword Extraction:**
- Keywords from prompts (split and cleaned)
- Model type detection (SD1.5, SDXL, etc.)
- Aspect ratio categories (square, landscape, portrait)
- Common resolution tags (512x512, 1080p, etc.)

## Backward Compatibility

### Sidecar File Integration

The database system maintains full backward compatibility:

1. **Score Storage**: Scores are written to both sidecar files AND database
2. **Score Reading**: Scores are read from sidecar files when available
3. **Migration**: Existing sidecar scores are imported during directory sync

### Graceful Degradation

If database is disabled or fails:
- Application continues working with sidecar files only
- Search functionality returns "503 Service Unavailable"
- Metadata extraction falls back to on-demand mode

## Performance Considerations

### Indexing Strategy

Critical indexes are automatically created:
- File path lookups (primary key for operations)
- Directory scans (for listing files)
- Score filtering (for rating-based searches)
- Keyword searches (for text-based searches)

### Batch Operations

For large directories:
- Use `sync_directory_to_database()` for bulk import
- Metadata extraction is performed lazily
- Database operations use transactions for consistency

### Memory Usage

- SQLite is file-based with minimal memory footprint
- Connection pooling handles concurrent access
- Large metadata (like workflow JSON) is stored as TEXT

## Migration and Upgrades

### Schema Versioning

Future schema changes will use Alembic migrations:

```bash
# Generate migration (for developers)
alembic revision --autogenerate -m "Add new_field to media_metadata"

# Apply migrations (automatic in future versions)
alembic upgrade head
```

### Data Migration

When upgrading from file-only to database:

1. Start application with `--enable-database`
2. Use `/api/search/sync` to import existing sidecar data
3. Metadata will be extracted automatically on access

## Troubleshooting

### Common Issues

**Database Lock Errors:**
- Ensure no multiple instances are accessing the same database
- Use context managers for proper connection handling

**Missing Metadata:**
- Run `/api/search/sync` to trigger extraction
- Check logs for ffprobe/Pillow errors
- Verify file permissions

**Search Not Working:**
- Confirm `enable_database: true` in config
- Check database file permissions
- Verify keywords were added to files

### Debugging

**Enable SQL Logging:**
```python
# In development, set echo=True in engine.py
_engine = create_engine(database_url, echo=True)
```

**Check Database Contents:**
```bash
sqlite3 .scores/media.db
.tables
SELECT COUNT(*) FROM media_files;
SELECT * FROM media_keywords LIMIT 10;
```

**API Diagnostics:**
- `GET /api/search/stats` - Database statistics
- Check application logs for database errors

## External Database Access

When using Docker Compose, the application uses PostgreSQL as an external database service that can be accessed from outside the container for debugging and data inspection.

### Connection Information

**Default Database Connection:**
- **Host**: `localhost` (when accessing from host machine)
- **Port**: `5432` (configurable via `POSTGRES_PORT` in .env)
- **Database**: `media_scoring` (configurable via `POSTGRES_DB` in .env)
- **Username**: `media_user` (configurable via `POSTGRES_USER` in .env)  
- **Password**: `media_password` (configurable via `POSTGRES_PASSWORD` in .env)

### Connecting with Database Tools

**Using psql (Command Line):**
```bash
# Connect from host machine
psql -h localhost -p 5432 -U media_user -d media_scoring

# Connect from within Docker network
docker exec -it media-scorer-db psql -U media_user -d media_scoring
```

**Using pgAdmin:**
1. Install pgAdmin or use web version
2. Create new server connection with:
   - Host: `localhost`
   - Port: `5432`
   - Database: `media_scoring`
   - Username: `media_user`
   - Password: `media_password`

**Using DBeaver:**
1. Create new PostgreSQL connection
2. Configure with the connection details above
3. Test connection and browse database schema

**Using DataGrip (JetBrains):**
1. Add new Data Source → PostgreSQL
2. Enter connection details
3. Download drivers if prompted
4. Test connection

### Useful SQL Queries for Debugging

**Check media files:**
```sql
SELECT filename, score, created_at FROM media_files ORDER BY created_at DESC LIMIT 10;
```

**Check metadata extraction:**
```sql
SELECT mf.filename, mm.width, mm.height, mm.prompt 
FROM media_files mf 
LEFT JOIN media_metadata mm ON mf.id = mm.media_file_id 
WHERE mm.id IS NOT NULL;
```

**Check keywords:**
```sql
SELECT mf.filename, mk.keyword, mk.keyword_type 
FROM media_files mf 
JOIN media_keywords mk ON mf.id = mk.media_file_id 
ORDER BY mf.filename, mk.keyword;
```

**Database statistics:**
```sql
SELECT 'media_files' as table_name, COUNT(*) as count FROM media_files
UNION ALL
SELECT 'media_metadata' as table_name, COUNT(*) as count FROM media_metadata
UNION ALL  
SELECT 'media_keywords' as table_name, COUNT(*) as count FROM media_keywords
UNION ALL
SELECT 'media_thumbnails' as table_name, COUNT(*) as count FROM media_thumbnails;
```

### Volume Persistence

The PostgreSQL data is stored in a Docker volume named `postgres_data`, ensuring data persistence across container restarts:

```bash
# View Docker volumes
docker volume ls

# Inspect the postgres data volume
docker volume inspect media_scoring_postgres_data

# Backup database
docker exec media-scorer-db pg_dump -U media_user media_scoring > backup.sql

# Restore database
docker exec -i media-scorer-db psql -U media_user media_scoring < backup.sql
```

### Development vs Production

**Development (Local SQLite):**
- Uses file-based SQLite database in `.scores/media.db`
- No external dependencies
- Data stored alongside media files

**Production (Docker with PostgreSQL):**
- Uses PostgreSQL service in Docker
- Accessible via external tools
- Data persisted in Docker volume
- Better performance for concurrent access

To switch between modes, set or unset the `DATABASE_URL` environment variable.

## Future Extensions

### Planned Features

1. **Advanced Search:**
   - Semantic similarity search
   - Image analysis (colors, composition)
   - Duplicate detection

2. **Metadata Enhancement:**
   - EXIF data extraction
   - Audio metadata for videos
   - Custom metadata fields

3. **Performance:**
   - Full-text search with FTS5
   - Materialized views for complex queries
   - Background metadata extraction

4. **Integration:**
   - Import from external databases
   - Export to CSV/JSON formats
   - REST API for external tools

### Extension Points

The database architecture is designed for extensibility:

- **Custom Keyword Types**: Add new `keyword_type` values
- **Additional Metadata**: Extend `MediaMetadata` table with new fields
- **Custom Services**: Create specialized service classes
- **Plugin System**: Register custom metadata extractors

## Example Workflows

### Basic Usage

```python
# Initialize database
from app.database.engine import init_database
init_database(Path("media.db"))

# Add files and metadata
with DatabaseService() as db:
    # Add a media file
    media_file = db.get_or_create_media_file(Path("image.png"))
    
    # Store metadata
    metadata = {"width": 512, "height": 512, "prompt": "beautiful portrait"}
    db.store_media_metadata(Path("image.png"), metadata)
    
    # Add searchable keywords
    db.add_keywords(Path("image.png"), ["portrait", "art"], "user")
    
    # Search for files
    results = db.search_by_keywords(["portrait"])
```

### Advanced Search

```python
with DatabaseService() as db:
    # Complex search with multiple criteria
    files = db.search_by_keywords(["anime", "portrait"], match_all=True)
    high_rated = [f for f in files if f.score >= 4]
    
    # Get detailed info
    for file in high_rated:
        metadata = db.get_media_metadata(Path(file.file_path))
        keywords = db.get_keywords_for_file(Path(file.file_path))
        print(f"{file.filename}: {file.score}★, {len(keywords)} keywords")
```

This database system provides a solid foundation for advanced media management, search, and organization features while maintaining the simplicity and reliability of the existing application.