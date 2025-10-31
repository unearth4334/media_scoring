# Similar Images Search Feature

## Overview
The Similar Images search feature allows users to find visually similar images based on perceptual hash (PHASH) comparison. This feature integrates seamlessly with existing filter criteria and supports both user path lookup and file upload methods.

## Features

### 1. Search Methods
- **User Path Input**: Paste the full user path (user_path_prefix + file_path) to search for similar images
- **File Upload**: Upload an image from local filesystem to find similar matches

### 2. Search Parameters
- **Max Results**: Control the number of similar images returned (1-50, default: 10)
- **Max Distance**: Set the maximum PHASH distance threshold (1-32, default: 10)
  - Lower values = more strict matching (more similar)
  - Higher values = looser matching (less similar)

### 3. Filter Integration
The Similar Images search respects all existing filter criteria:
- File Type (JPG, PNG, MP4)
- Rating (Rejected, Unrated, 1-5 stars)
- Creation Date range
- NSFW filter (All, SFW Only, NSFW Only)

## Usage

### Frontend (Web UI)

1. Click the "Similar Images" pill in the toolbar
2. Choose search method:
   - **Option A**: Paste user path and click the ▶ button
   - **Option B**: Click "Upload Search Image" to select a file
3. Once loaded, the search image thumbnail and PHASH will be displayed
4. Adjust sliders for max results and max distance (optional)
5. Click "Apply" to execute the search
6. Results will be displayed in the sidebar, sorted by similarity

### API Endpoints

#### 1. Search by User Path
```http
POST /api/search/similar/by-path
Content-Type: application/json

{
  "user_path": "/mnt/qnap-sd/SecretFolder/path/to/image.png",
  "max_results": 10,
  "max_distance": 10,
  "file_types": ["jpg", "png"],
  "min_score": 1,
  "max_score": 5,
  "date_start": "2024-01-01T00:00:00Z",
  "date_end": "2024-12-31T23:59:59Z",
  "nsfw_filter": "all"
}
```

Response:
```json
{
  "search_image": {
    "name": "image.png",
    "path": "/media/path/to/image.png",
    "phash": "a1b2c3d4e5f6g7h8"
  },
  "results": [
    {
      "name": "similar1.png",
      "path": "/media/path/to/similar1.png",
      "score": 4,
      "file_type": "image",
      "extension": ".png",
      "phash": "a1b2c3d4e5f6g7h9",
      "distance": 1,
      "updated_at": "2024-10-31T00:00:00"
    }
  ],
  "total": 1
}
```

#### 2. Search by Upload
```http
POST /api/search/similar/by-upload
Content-Type: multipart/form-data

file: <image file>
max_results: 10
max_distance: 10
file_types: jpg,png
min_score: 1
nsfw_filter: all
```

Response: Same as search by path

#### 3. Get File Info by Path
```http
GET /api/search/file-info-by-path?user_path=/mnt/qnap-sd/SecretFolder/path/to/image.png
```

Response:
```json
{
  "name": "image.png",
  "path": "/media/path/to/image.png",
  "phash": "a1b2c3d4e5f6g7h8",
  "file_type": "image",
  "extension": ".png"
}
```

## Technical Details

### PHASH Algorithm
- Uses average hash (aHash) from the `imagehash` library
- Fast computation and comparison
- Good balance between accuracy and performance
- Hamming distance used for similarity comparison

### Database Integration
- PHASH values stored in `media_files.phash` column
- Indexed for faster lookups
- Computed automatically during media file ingestion
- Re-computed if missing

### Performance Considerations
- PHASH distance calculation is O(n) where n is the number of media files
- Results are sorted by distance for best matches first
- Filters are applied at database query level to reduce comparison set

## Configuration

### Required Settings
```yaml
# config/config.yml
enable_database: true
user_path_prefix: "/mnt/qnap-sd/SecretFolder"  # For user path conversion
```

### Dependencies
- `imagehash` - PHASH computation
- `pillow` - Image processing
- `python-multipart` - File upload support

## Limitations

1. Database must be enabled for this feature to work
2. Only images with PHASH values in the database can be found
3. PHASH computation requires valid image files (PNG, JPG, JPEG)
4. Video similarity uses first frame only
5. Upload method creates temporary files (cleaned up after use)

## Future Enhancements

Potential improvements:
- Batch PHASH computation for new files
- Alternative hash algorithms (pHash, dHash, wHash)
- Similarity threshold auto-adjustment
- Cached results for repeated searches
- Multi-frame video analysis
- ML-based similarity scoring
