# Data Mining Tool for Media Archives

This tool allows you to extract metadata, scores, and keywords from existing archives of media files and store them in the database for the Media Scoring application.

## Features

- **Standalone CLI tool** - Runs independently of the web server
- **Flexible file patterns** - Support for multiple file types using glob patterns
- **Database integration** - Stores extracted data in SQLite or PostgreSQL database
- **Metadata extraction** - Extracts technical metadata from images and videos
- **Keyword extraction** - Automatically generates searchable keywords from metadata
- **Score import** - Imports existing scores from sidecar files
- **Progress reporting** - Shows detailed progress and statistics
- **Dry run mode** - Test without writing to database
- **Error handling** - Robust error handling with detailed logging

## Usage

### Basic Usage

```bash
# Dry run mode (no database writes) - good for testing
python mine_data.py /path/to/archive

# Dry run with HTML export showing what would be stored in database
python mine_data.py /path/to/archive --test-output-dir ./test_results

# With database storage enabled
python mine_data.py /path/to/archive --enable-database

# Specific file pattern
python mine_data.py /path/to/archive --pattern "*.mp4|*.png"

# Verbose output
python mine_data.py /path/to/archive --verbose --enable-database
```

### Advanced Usage

```bash
# Custom database path
python mine_data.py /path/to/archive --enable-database --database-path /custom/path/media.db

# External database (PostgreSQL)
python mine_data.py /path/to/archive --enable-database --database-url "postgresql://user:pass@host:5432/db"

# Process only images
python mine_data.py /path/to/archive --pattern "*.jpg|*.png|*.jpeg" --enable-database
```

## Command Line Options

- `directory` - **Required**. Directory containing media files to mine
- `--pattern` - File pattern to match (default: `*.mp4|*.png|*.jpg`)
- `--enable-database` - Enable database storage (default: false for dry run)
- `--database-path` - Custom database file path (default: `<directory>/.scores/media.db`)
- `--database-url` - Database URL for external database (overrides `--database-path`)
- `--verbose, -v` - Enable verbose logging
- `--dry-run` - Dry run mode - don't store data in database
- `--test-output-dir` - Export collected data as HTML file to this directory (for dry run mode)

## What the Tool Does

1. **Scans Directory** - Finds all files matching the specified pattern
2. **Extracts Metadata** - For each file:
   - Technical metadata (dimensions, duration, etc.)
   - AI generation parameters (from PNG text chunks, video metadata)
   - File information (size, modification time)
3. **Generates Keywords** - Automatically creates searchable keywords from:
   - Prompts and generation parameters
   - Model names
   - Aspect ratios and common resolutions
4. **Imports Scores** - Reads existing scores from `.scores/*.json` sidecar files
5. **Stores in Database** - All data is stored in the database for search and management

## Output Examples

### Dry Run Mode
```
2025-09-11 04:53:20 | INFO  | Data Mining Tool for Media Archives
2025-09-11 04:53:20 | INFO  | ========================================
2025-09-11 04:53:20 | INFO  | Source directory: /media/archive
2025-09-11 04:53:20 | INFO  | File pattern: *.mp4|*.png|*.jpg
2025-09-11 04:53:20 | INFO  | Database enabled: False
2025-09-11 04:53:20 | INFO  | Running in dry-run mode (no database storage)
2025-09-11 04:53:20 | INFO  | Starting to mine directory: /media/archive
2025-09-11 04:53:20 | INFO  | Found 156 files matching pattern
2025-09-11 04:53:20 | INFO  | Processing files without database (dry run mode)
2025-09-11 04:53:22 | INFO  | ==================================================
2025-09-11 04:53:22 | INFO  | DATA MINING COMPLETED
2025-09-11 04:53:22 | INFO  | ==================================================
2025-09-11 04:53:22 | INFO  | Total files found: 156
2025-09-11 04:53:22 | INFO  | Files processed: 156
2025-09-11 04:53:22 | INFO  | Metadata extracted: 156
2025-09-11 04:53:22 | INFO  | Keywords added: 0
2025-09-11 04:53:22 | INFO  | Scores imported: 23
2025-09-11 04:53:22 | INFO  | Errors encountered: 0
2025-09-11 04:53:22 | INFO  | Processing completed successfully!
```

### Database Mode
```
2025-09-11 04:54:06 | INFO  | Database initialized with URL: sqlite:///archive/.scores/media.db
2025-09-11 04:54:06 | INFO  | Found 156 files matching pattern
2025-09-11 04:54:06 | INFO  | Processing files with database storage enabled
2025-09-11 04:54:07 | INFO  | Processing file 50/156: image_050.png
2025-09-11 04:54:08 | INFO  | Processing file 100/156: image_100.jpg
2025-09-11 04:54:09 | INFO  | Processing file 156/156: video_001.mp4
2025-09-11 04:54:09 | INFO  | Total files found: 156
2025-09-11 04:54:09 | INFO  | Files processed: 156
2025-09-11 04:54:09 | INFO  | Metadata extracted: 156
2025-09-11 04:54:09 | INFO  | Keywords added: 312
2025-09-11 04:54:09 | INFO  | Scores imported: 23
2025-09-11 04:54:09 | INFO  | Errors encountered: 0
```

## Integration with Media Scoring Application

Once you've mined data from your archives:

1. **Start the web application** pointing to the same directory:
   ```bash
   python run.py --dir /path/to/archive --enable-database
   ```

2. **Use the search functionality** via the web interface or API:
   ```bash
   curl -X POST http://localhost:7862/api/search/files \
     -H "Content-Type: application/json" \
     -d '{"keywords": ["portrait", "anime"], "min_score": 3}'
   ```

3. **View database statistics**:
   ```bash
   curl http://localhost:7862/api/search/stats
   ```

## Database Storage

- **SQLite** (default): Database stored in `<directory>/.scores/media.db`
- **PostgreSQL**: Use `--database-url` for external databases
- **Backward compatible**: Works alongside existing sidecar score files

## Performance

- **Fast processing**: Typically processes 100-500 files per second for metadata extraction
- **Memory efficient**: Processes files one at a time, suitable for large archives
- **Progress reporting**: Shows progress every 10 files
- **Error resilient**: Continues processing even if individual files fail

## Troubleshooting

### Common Issues

1. **Permission errors**: Ensure you have read access to the source directory
2. **Missing ffmpeg**: Install ffmpeg for video metadata extraction
3. **Database errors**: Check disk space and permissions for database directory
4. **No files found**: Verify your file pattern matches your files

### Getting Help

```bash
python mine_data.py --help
```

### Debug Mode

```bash
python mine_data.py /path/to/archive --verbose --dry-run
```

## Examples for Different Use Cases

### Archive of AI-generated Images
```bash
# Mine PNG images with AI metadata
python mine_data.py /archive/ai_images --pattern "*.png" --enable-database --verbose
```

### Video Archive
```bash
# Mine MP4 videos
python mine_data.py /archive/videos --pattern "*.mp4" --enable-database
```

### Mixed Media Archive
```bash
# Mine all supported media types
python mine_data.py /archive/mixed --enable-database
```

### Test Before Full Processing
```bash
# Always test first with dry run
python mine_data.py /large/archive --verbose --dry-run
# Export results to see what would be collected
python mine_data.py /large/archive --dry-run --test-output-dir ./test_results
# Then run for real
python mine_data.py /large/archive --enable-database
```

## HTML Export Feature

The `--test-output-dir` option allows you to export a detailed HTML report showing:

- **Summary statistics** - Total files, types, scores, keywords found
- **File details** - Complete metadata for each file with extracted keywords 
- **Database preview** - Visual representation of how data would be stored
- **Next steps** - Instructions for running with database enabled

This is particularly useful for:
- **Testing patterns** - Verify your file pattern captures the right files
- **Reviewing metadata** - See what information can be extracted from your files
- **Planning database setup** - Understand the structure before committing to storage
- **Troubleshooting** - Debug extraction issues on a subset of files

Example output structure:
```
test_results/
└── mining_test_results.html  # Complete interactive report
```