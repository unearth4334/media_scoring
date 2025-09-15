# Enhanced Metadata Features

This document describes the new comprehensive metadata extraction and HTML export features added to the Media Scoring application.

## Overview

The application now includes:

1. **Comprehensive PNG Metadata Parsing** - Extracts AI generation parameters from PNG files
2. **SQLite Database Schema** - Stores detailed metadata for all media files  
3. **HTML Export** - Generates detailed reports with all metadata fields
4. **Dual Implementation** - Available in both monolithic (`app.py`) and modular (`run.py`) versions

## Features Added

### PNG Metadata Extraction

The application now extracts the following parameters from AI-generated PNG files:

**Core Generation Parameters:**
- Steps, Sampler, Schedule type, CFG scale, Seed, Size
- Model name and hash
- Version information

**Hires/Upscaling Parameters:**
- Denoising strength, Hires Module 1, Hires CFG Scale
- Hires upscale factor, Hires upscaler

**Dynamic Thresholding Parameters:**
- dynthres_enabled, dynthres_mimic_scale, dynthres_threshold_percentile
- dynthres_mimic_mode, dynthres_mimic_scale_min, dynthres_cfg_mode
- dynthres_cfg_scale_min, dynthres_sched_val, dynthres_separate_feature_channels
- dynthres_scaling_startpoint, dynthres_variability_measure, dynthres_interpolate_phi

### Database Schema

**Media Files Table (`media_files`):**
```sql
CREATE TABLE media_files (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    filename TEXT NOT NULL,
    filepath TEXT NOT NULL,  -- Relative to media directory
    file_size INTEGER,
    width INTEGER,
    height INTEGER,
    created_date TEXT,
    modified_date TEXT,
    score INTEGER,
    generation_params TEXT,  -- JSON blob with all generation parameters
    scanned_date TEXT,
    updated_date TEXT,
    UNIQUE(filepath)
);
```

### HTML Export

The new HTML export feature generates comprehensive reports including:

- **Summary Statistics** - Total files, scored files, average score, files with metadata
- **Detailed Table** - All metadata fields for each file in a sortable, styled table
- **Professional Styling** - Modern, responsive design with gradient headers and hover effects
- **Complete Metadata** - All 30+ metadata fields including generation parameters

## API Endpoints

### New Endpoints

1. **`POST /api/export-html`**
   - Export HTML report with full metadata
   - Body: `{"names": ["file1.png", "file2.png"]}` (optional - exports all files if omitted)
   - Returns: HTML file download

2. **`GET /api/database-info`** (modular version only)
   - Get database statistics
   - Returns: JSON with file counts and database path

### Enhanced Endpoints

1. **`GET /api/meta/{filename}`**
   - Now includes parsed generation parameters for PNG files
   - Returns: JSON with dimensions, raw PNG text, and parsed parameters

## Usage Examples

### Starting the Application

**Modular Version (Recommended):**
```bash
python run.py --dir ./media --pattern "*.png|*.jpg|*.mp4" --port 7862
```

**Monolithic Version:**
```bash
python app.py --dir ./media --pattern "*.png|*.jpg|*.mp4" --port 7862
```

### Using the HTML Export

**Via Web Interface:**
1. Open the application in your browser
2. Filter files as desired using the rating filters
3. Click "Export HTML Report" button in the sidebar

**Via API:**
```bash
# Export all files
curl -X POST http://localhost:7862/api/export-html \
  -H "Content-Type: application/json" \
  -d '{}' \
  --output mining_test_results.html

# Export specific files
curl -X POST http://localhost:7862/api/export-html \
  -H "Content-Type: application/json" \
  -d '{"names": ["image1.png", "image2.png"]}' \
  --output filtered_results.html
```

### Checking Database Status (Modular Version)

```bash
curl http://localhost:7862/api/database-info
```

Example response:
```json
{
  "database_initialized": true,
  "total_files": 150,
  "scored_files": 45,
  "files_with_metadata": 89,
  "database_path": "/path/to/media/.scores/media_files.db"
}
```

## File Structure

The application creates the following structure in your media directory:

```
media_directory/
├── image1.png
├── image2.png
├── video1.mp4
└── .scores/
    ├── media_files.db          # SQLite database with metadata
    ├── image1.png.json         # Legacy sidecar files (for compatibility)
    ├── image2.png.json
    ├── video1.mp4.json
    └── .log/
        └── video_scorer.log    # Application logs
```

## Backward Compatibility

The new features maintain full backward compatibility:

- **Legacy sidecar files** continue to work and are still created/updated
- **Existing scores** are preserved and migrated to the database
- **All existing functionality** remains unchanged

## Implementation Notes

### Modular vs Monolithic

**Modular Version (`run.py`):**
- Clean separation of concerns
- Full database integration
- Comprehensive HTML export with all 30+ metadata fields
- Better maintainability and testing

**Monolithic Version (`app.py`):**
- Single file deployment
- Simplified HTML export (5 main columns)
- Maintains compatibility with existing deployments
- All core features available

### Performance

- **Database operations** are optimized with indexes on common query fields
- **PNG parsing** is cached during directory scanning
- **HTML export** uses streaming for large datasets
- **Memory usage** is minimized through efficient data structures

## Troubleshooting

### Common Issues

1. **"Database not initialized" error**
   - Ensure the media directory is writable
   - Check that the directory scan completed successfully

2. **Missing PNG metadata**
   - Verify PNG files contain tEXt/zTXt/iTXt chunks with 'parameters' data
   - Check that files were generated by compatible AI tools (Automatic1111, ComfyUI, etc.)

3. **HTML export fails**
   - Ensure sufficient disk space for temporary files
   - Check application logs for detailed error messages

### Debug Information

Enable debug logging by checking the log files in `.scores/.log/video_scorer.log` in your media directory.

## Examples

See the `test_media/` directory for example PNG files with embedded metadata that demonstrate the parsing capabilities.