# 🎬 Video & Image Scorer (FastAPI)

A comprehensive Python FastAPI web application for **reviewing, scoring, and managing video and image datasets** with database integration, workflow extraction, and batch processing capabilities. Supports `.mp4` videos, `.png`, `.jpg`, and `.jpeg` images, designed for ComfyUI/Stable Diffusion workflows but useful for any media scoring pipeline.

**Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## 🔑 Key Features
- **Media Management**: Browse, score (1-5 ⭐), and navigate video/image files
- **Database Integration**: PostgreSQL/SQLite for persistent metadata and scores
- **Batch Processing**: Ingest archives and extract metadata with CLI tools
- **Workflow Extraction**: Parse ComfyUI workflows and generation metadata
- **Search & Filter**: Query by scores, keywords, dimensions, and metadata
- **Thumbnail Generation**: Fast preview generation for large collections

## Working Effectively

### System Dependencies
- **FFmpeg** (required for video metadata extraction):
  ```bash
  # Ubuntu/Debian
  sudo apt update && sudo apt install -y ffmpeg
  
  # macOS
  brew install ffmpeg
  
  # Windows - Download from https://ffmpeg.org/ and add to PATH
  ```

- **PostgreSQL** (optional, for advanced features):
  ```bash
  # Ubuntu/Debian
  sudo apt install -y postgresql postgresql-contrib
  
  # macOS
  brew install postgresql
  
  # Docker (recommended for development)
  docker run --name media-scorer-db -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres:15
  ```

### Bootstrap, Build, and Test
**NEVER CANCEL: These commands may take time but will complete. Use appropriate timeouts.**

1. **Create and activate virtual environment** (2 seconds):
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate    # Linux/macOS
   .venv\Scripts\activate       # Windows
   ```

2. **Install Python dependencies** (5-20 seconds, NEVER CANCEL):
   ```bash
   # TIMEOUT WARNING: pip install may take up to 20 seconds and may timeout on slow networks
   pip install --upgrade pip
   pip install -r requirements.txt
   ```
   **Known Issue**: If pip install times out due to network issues, retry with longer timeout:
   ```bash
   pip install --timeout 300 -r requirements.txt
   ```

3. **Verify installation**:
   ```bash
   python run.py --help
   ```

4. **Setup Database** (optional, for advanced features):
   ```bash
   # Using PostgreSQL
   export DATABASE_URL="postgresql://user:password@localhost:5432/media_scorer"
   
   # Or SQLite (default)
   export DATABASE_URL="sqlite:///./media_scorer.db"
   
   # Run database migrations
   python -m app.database.migration upgrade
   ```

### Run the Application
**ALWAYS run the bootstrapping steps first before starting the application.**

#### Option 1: Using Entry Scripts (Recommended)
- **Linux/macOS**: `./scripts/run_video_scorer.sh [media_dir] [port] [pattern]`
- **Windows PowerShell**: `.\scripts\run_video_scorer.ps1 -Dir "path" -Port 7862`
- **Windows CMD**: `scripts\run_video_scorer.bat "path" 7862 "127.0.0.1" "*.mp4|*.jpg"`

#### Option 2: Direct Python Execution
```bash
# NEVER CANCEL: Application startup takes ~5 seconds
python run.py --dir ./media --port 7862 --host 127.0.0.1 --pattern "*.mp4|*.png|*.jpg"
```

#### Option 3: Using Configuration File
```bash
# Edit config/config.yml first, then:
python run.py --config config/config.yml
```

#### Option 4: With Database Integration
```bash
# Set database URL and run with database features
export DATABASE_URL="postgresql://user:pass@localhost:5432/media_scorer"
python run.py --dir ./media --use-db
```

#### Option 5: Docker (Build: 45 seconds, NEVER CANCEL)
```bash
# NEVER CANCEL: Docker build takes ~45 seconds - set timeout to 60+ minutes
docker build -t media-scorer .
docker run --rm -p 7862:7862 -v /path/to/media:/media media-scorer
```

#### Option 6: Docker Compose (with PostgreSQL)
```bash
# NEVER CANCEL: Initial setup with database
docker-compose up -d
# Access at http://localhost:7862
```

### Application Access
- **Web Interface**: http://127.0.0.1:7862
- **API Documentation**: http://127.0.0.1:7862/docs (Swagger UI)
- **Core API Endpoints**: 
  - `/api/videos` - List media files
  - `/api/search` - Database search
  - `/api/ingest` - Batch processing

### Container Access (Docker Testing)
- **SSH Access**: `ssh root@10.0.78.66 -p 2222`
- **Web Interface**: http://10.0.78.66:7862
- **Container logs**: `docker logs media-scorer`
- **Database logs**: Available in `/app/.logs/` inside container

## Validation

### Manual Testing Requirements
**ALWAYS manually validate any new code by running through these scenarios:**

1. **Basic Functionality Test**:
   - Start the application using any method above
   - Open http://127.0.0.1:7862 in browser
   - Verify the web interface loads with media files listed
   - Test navigation buttons (Prev/Next)
   - Test scoring buttons (★1-★5)
   - Verify media files display correctly

2. **API Validation**:
   ```bash
   # Test the main API endpoint
   curl http://127.0.0.1:7862/api/videos
   # Should return JSON with media files array
   ```

3. **Configuration Testing**:
   - Modify config.yml with different settings
   - Restart application and verify changes take effect
   - Test different media patterns (*.mp4, *.jpg, *.png)

4. **Container Testing** (Docker environment):
   ```bash
   # Access container via SSH
   ssh root@10.0.78.66 -p 2222
   
   # Check application status inside container
   ps aux | grep python
   
   # View container logs
   docker logs media-scorer
   
   # Test web interface
   curl http://10.0.78.66:7862/api/videos
   
   # Check database logs (if database enabled)
   ls -la /app/.logs/
   ```

### Expected Behavior
- Application starts in ~5 seconds and displays media from configured directory
- Web UI should show a dark theme with media thumbnails/list on the left
- Main viewer shows selected media file with scoring controls
- API returns JSON with media files and their scores

## Common Tasks

### Changing Media Directory
1. Edit `config/config.yml` or use command line arguments
2. Restart application to scan new directory

### Adding New Media Formats
1. Update pattern in `config/config.yml` or command line
2. Ensure ffmpeg/ffprobe support the format for video files

### Database Operations
1. **Ingesting Existing Archives**:
   ```bash
   python tools/ingest_data.py --source /path/to/media --use-db
   ```

2. **Running Database Migrations**:
   ```bash
   python -m app.database.migration upgrade
   ```

3. **Search and Filter Media**:
   ```bash
   curl "http://127.0.0.1:7862/api/search?query=landscape&min_score=3"
   ```

### Development Workflow
1. Make code changes
2. Restart application (automatic reload not enabled)
3. Test in browser and via API
4. Verify logs in console output
5. Run database tests: `python -m pytest tests/test_database.py`

## Repository Structure

### Key Files
```
├── run.py                     # Main entry point
├── config/                    # Configuration directory
│   ├── config.yml             # Default configuration
│   └── schema.yml             # Configuration schema validation
├── requirements.txt           # Python dependencies
│
├── scripts/                   # Entry scripts directory
│   ├── run_video_scorer.sh    # Linux/macOS launcher
│   ├── run_video_scorer.ps1   # PowerShell launcher  
│   └── run_video_scorer.bat   # Windows CMD launcher
│
├── tools/                     # CLI utilities
│   ├── ingest_data.py         # Batch ingesting tool
│   ├── read_config.py         # Configuration utility
│   └── schema_cli.py          # Schema validation CLI
│
├── Dockerfile                 # Docker configuration
├── docker-compose.yml         # Docker Compose setup
├── docker-entrypoint.sh       # Docker entry script
│
├── app/                       # Main application directory  
│   ├── database/              # Database models and services
│   ├── routers/               # FastAPI route handlers
│   ├── services/              # Business logic services
│   ├── static/
│   │   ├── themes/            # CSS themes
│   │   │   ├── style_default.css      # Default dark theme
│   │   │   ├── style_pastelcore.css   # Pastel theme
│   │   │   └── style_darkcandy.css    # Dark candy theme
│   │   └── js/                # JavaScript files
│   ├── templates/             # HTML templates
│   └── utils/                 # Utility modules
│
├── docs/                      # Documentation
├── tests/                     # Test suite
└── media/                     # Sample media files (development)
```

### Auto-Generated Directories
- `.scores/` - Score files and logs (created at runtime)
- `.workflows/` - Workflow extraction outputs (created at runtime)
- `.thumbnails/` - Generated thumbnails (if enabled)

## Configuration

### config/config.yml Settings
```yaml
dir: ./media                    # Media directory path
host: 127.0.0.1                # Server host
port: 7862                      # Server port  
pattern: "*.mp4|*.png|*.jpg"    # File patterns (pipe-separated)
style: style_default.css        # CSS theme file
generate_thumbnails: true       # Enable thumbnail generation
thumbnail_height: 64            # Thumbnail height in pixels
use_db: false                   # Enable database features
database_url: null              # Database connection string
```

### Command Line Overrides
All config.yml settings can be overridden via command line arguments:
```bash
python run.py --dir /path/to/media --port 8000 --pattern "*.mp4"
```

## Known Issues and Workarounds

### Network Timeouts
**Issue**: pip install may timeout on slow networks
**Workaround**: Use longer timeout: `pip install --timeout 300 -r requirements.txt`

### Missing Dependencies
**Issue**: "PyYAML not installed" error when using tools/read_config.py
**Workaround**: Install manually: `pip install pyyaml`

### Windows Path Issues
**Issue**: Path separators in Windows environments
**Workaround**: Use forward slashes or escape backslashes in paths

## Development Notes

### No Automatic Restart
The application does not auto-reload on code changes. Always restart after modifications.

### Themes
Available CSS themes in `app/static/themes/` directory:
- `style_default.css` - Dark theme (default)
- `style_pastelcore.css` - Light pastel theme
- `style_darkcandy.css` - Dark colorful theme

### API Endpoints
- `GET /` - Web interface (HTML)
- `GET /api/videos` - List media files (JSON)
- `GET /media/{filename}` - Serve media files
- `GET /api/meta/{filename}` - Get media metadata
- `POST /api/score` - Update file scores
- `POST /api/switch` - Change directory/pattern
- `GET /api/search` - Database search functionality
- `POST /api/ingest` - Batch processing and ingestion

### File Extensions Supported
- **Videos**: .mp4
- **Images**: .png, .jpg, .jpeg
- **Patterns**: Use pipe separator (|) for multiple: "*.mp4|*.png|*.jpg"

Always verify changes work by running the complete application and testing in both the web interface and via API calls.