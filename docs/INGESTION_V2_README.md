# 🎬 Data Ingestion Tool v2 - Enhanced Workflow

The Data Ingestion Tool v2 introduces a comprehensive workflow-based approach to processing media files with preview and commit phases, including NSFW detection capabilities.

## ✨ New Features

### 🔄 Workflow-Based Processing
- **Step 1: Configure** - Set processing parameters
- **Step 2: Process** - Extract data with real-time progress
- **Step 3: Preview** - Review results before committing
- **Step 4: Commit** - Save verified data to database

### 🔞 NSFW Detection
- Uses the **Marqo/nsfw-image-detection-384** model
- Lightweight and accurate (98.56% accuracy)
- Configurable threshold (0.0-1.0)
- Supports images: PNG, JPG, JPEG

### 📊 Enhanced Progress Tracking
- Real-time progress bar
- Live statistics updates
- Current file indicator
- Error tracking and reporting

### 📄 Detailed Preview Reports
- HTML reports with comprehensive statistics
- Sample file previews
- NSFW analysis breakdown
- Error summaries

## 🚀 Getting Started

### Prerequisites

1. **Basic Requirements** (already included):
   ```bash
   pip install fastapi uvicorn pillow sqlalchemy psycopg2-binary
   ```

2. **NSFW Detection** (optional but recommended):
   ```bash
   pip install timm torch
   ```

3. **Database**: PostgreSQL instance running and accessible

### Quick Start

1. **Access the Tool**:
   ```
   http://your-app-url/ingest-v2
   ```

2. **Configure Parameters**:
   - Select source directory
   - Set file pattern (e.g., `*.mp4|*.png|*.jpg`)
   - Enable/disable NSFW detection
   - Configure processing options

3. **Start Processing**:
   - Click "🚀 Start Processing"
   - Monitor real-time progress
   - Watch statistics update

4. **Review Results**:
   - View detailed HTML report
   - Check NSFW classifications
   - Review any errors

5. **Commit to Database**:
   - Click "💾 Commit to Database"
   - Monitor commit progress
   - Confirm successful completion

## 📋 Processing Options

### 🔞 NSFW Detection
```yaml
enable_nsfw_detection: true    # Enable NSFW classification
nsfw_threshold: 0.5           # Classification threshold (0.0-1.0)
```

**Output**: 
- `nsfw_score`: Probability value (0.0-1.0)
- `nsfw_label`: Classification ('sfw' or 'nsfw')

### ⚙️ Metadata Extraction
```yaml
extract_metadata: true       # Extract file dimensions, duration, etc.
extract_keywords: true       # Extract keywords from metadata
import_scores: true          # Import existing .score files
```

### 🎯 Testing Options
```yaml
max_files: 100              # Limit files for testing (optional)
```

## 📊 Database Schema Changes

The v2 tool adds new fields to the `media_files` table:

```sql
-- NSFW Detection fields
ALTER TABLE media_files ADD COLUMN nsfw_score REAL;
ALTER TABLE media_files ADD COLUMN nsfw_label VARCHAR(10);

-- Index for efficient filtering
CREATE INDEX idx_media_nsfw_score ON media_files(nsfw_score);
```

### Migration

Run the migration to add NSFW fields:

```bash
python migrations/20251008_add_nsfw_fields.py upgrade --database-url "your-db-url"
```

## 🔧 API Endpoints

### Start Processing
```http
POST /api/ingest/process
Content-Type: application/json

{
  "parameters": {
    "directory": "/path/to/media",
    "pattern": "*.mp4|*.png|*.jpg",
    "enable_nsfw_detection": true,
    "nsfw_threshold": 0.5,
    "extract_metadata": true,
    "extract_keywords": true,
    "import_scores": true,
    "max_files": null
  }
}
```

### Get Processing Status
```http
GET /api/ingest/status/{session_id}
```

### Get Preview Report
```http
GET /api/ingest/report/{session_id}
```

### Commit to Database
```http
POST /api/ingest/commit
Content-Type: application/json

{
  "session_id": "session-uuid"
}
```

### Cleanup Session
```http
DELETE /api/ingest/session/{session_id}
```

## 🧪 Testing

Use the included test script to validate the workflow:

```bash
# Test with default settings
python test_ingestion_v2.py

# Test with custom directory and URL
python test_ingestion_v2.py --directory /path/to/test/media --url http://localhost:8000

# Expected output:
# 🎬 Data Ingestion Tool v2 - Workflow Test
# ============================================================
# 🔞 Testing NSFW Detection Availability...
#    NSFW Detection Available: ✅ Yes
# 📁 Testing Directory Listing API...
#    ✅ Directory listing works
# 🔄 Testing Processing Workflow...
#    ✅ Processing completed successfully!
# 📄 Testing Preview Report...
#    ✅ Preview report generated successfully
# 🧹 Testing Session Cleanup...
#    ✅ Session cleaned up successfully
# ============================================================
# 📊 TEST SUMMARY
# ============================================================
# 1. ✅ PASS NSFW Detection Availability
# 2. ✅ PASS Directory Listing API
# 3. ✅ PASS Processing Workflow
# 4. ✅ PASS Preview Report Generation
# 5. ✅ PASS Session Cleanup
# 
# Total: 5/5 tests passed (100.0%)
# 🎉 ALL TESTS PASSED! The ingestion workflow is working correctly!
```

## 📈 Performance

### NSFW Detection
- **Model**: Marqo/nsfw-image-detection-384 (lightweight)
- **Size**: ~18-20x smaller than alternatives
- **Accuracy**: 98.56% on test dataset
- **Speed**: Fast inference on CPU/GPU

### Processing Speed
- **Small datasets** (< 100 files): Near real-time
- **Medium datasets** (100-1000 files): 1-5 minutes
- **Large datasets** (1000+ files): 5-30 minutes

### Database Performance
- Bulk operations with transaction batching
- Efficient indexing for NSFW filtering
- Progress tracking with minimal overhead

## 🔍 NSFW Model Details

The tool uses **Marqo/nsfw-image-detection-384**:

- **Architecture**: Vision Transformer (ViT) Tiny
- **Input Size**: 384x384 pixels with 16x16 patches
- **Training Data**: 220K images (100K NSFW, 100K SFW, 20K test)
- **Content Types**: Real photos, drawings, Rule 34, memes, AI-generated
- **Output**: Binary classification with confidence scores

### Threshold Guidelines
- **0.3**: Conservative (more files marked as NSFW)
- **0.5**: Balanced (default, recommended)
- **0.7**: Permissive (fewer files marked as NSFW)

## 🛠️ Troubleshooting

### NSFW Detection Not Available
```bash
# Install required packages
pip install timm torch

# For CPU-only environments
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
```

### Database Connection Issues
- Ensure PostgreSQL is running and accessible
- Check `DATABASE_URL` environment variable
- Verify database permissions

### Processing Failures
- Check file permissions in source directory
- Verify file formats are supported
- Review error logs in processing status

### Memory Issues
- Reduce `max_files` for testing
- Process in smaller batches
- Ensure sufficient RAM for NSFW model

## 🔄 Migration from v1

The v2 tool runs alongside the original tool:
- **v2**: `/ingest-v2` - New workflow-based tool
- **v1**: `/ingest` - Original streaming tool (legacy)

Both tools are compatible and share the same database schema (with v2 extensions).

## 🎯 Use Cases

### 🏢 Content Moderation
- Bulk classify existing image collections
- Automatic NSFW filtering for web platforms
- Content audit and compliance checking

### 📊 Data Analysis
- Extract comprehensive metadata from media archives
- Build searchable keyword databases
- Generate detailed processing reports

### 🔄 Migration Projects
- Import existing media libraries
- Consolidate multiple archives
- Standardize metadata across collections

### 🧪 Development & Testing
- Process small batches for development
- Preview results before production commits
- Test classification accuracy with known datasets

## 🚀 Future Enhancements

- **Multi-model Support**: Additional NSFW detection models
- **Batch Processing**: Queue-based processing for very large datasets  
- **Advanced Filtering**: Custom classification thresholds per directory
- **Export Options**: CSV, JSON, and XML report formats
- **Scheduling**: Automated periodic processing
- **Cloud Storage**: Direct integration with S3, Google Cloud, etc.

---

## 📞 Support

For issues or questions:
1. Check the troubleshooting section above
2. Run the test script to validate your setup
3. Review application logs for detailed error information
4. Create an issue with your system details and error logs

**Happy Processing!** 🎬✨