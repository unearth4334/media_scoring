# Video & Image Scorer (FastAPI)

A Python FastAPI web application for scoring and managing video and image files with an intuitive web interface.

**Always reference these instructions first and fallback to search or bash commands only when you encounter unexpected information that does not match the info here.**

## Working Effectively

### System Dependencies
- Install ffmpeg (required for video metadata extraction):
  ```bash
  # Ubuntu/Debian
  sudo apt update && sudo apt install -y ffmpeg
  
  # macOS
  brew install ffmpeg
  
  # Windows
  # Download from https://ffmpeg.org/ and add to PATH
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

### Run the Application
**ALWAYS run the bootstrapping steps first before starting the application.**

#### Option 1: Using Entry Scripts (Recommended)
- **Linux/macOS**: `./run_video_scorer.sh [media_dir] [port] [pattern]`
- **Windows PowerShell**: `.\run_video_scorer.ps1 -Dir "path" -Port 7862`
- **Windows CMD**: `run_video_scorer.bat "path" 7862 "127.0.0.1" "*.mp4|*.jpg"`

#### Option 2: Direct Python Execution
```bash
# NEVER CANCEL: Application startup takes ~5 seconds
python run.py --dir ./media --port 7862 --host 127.0.0.1 --pattern "*.mp4|*.png|*.jpg"
```

#### Option 3: Docker (Build: 45 seconds, NEVER CANCEL)
```bash
# NEVER CANCEL: Docker build takes ~45 seconds - set timeout to 60+ minutes
docker build -t media-scorer .
docker run --rm -p 7862:7862 -v /path/to/media:/media media-scorer
```

### Application Access
- **Web Interface**: http://127.0.0.1:7862
- **API Endpoint**: http://127.0.0.1:7862/api/videos

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

### Expected Behavior
- Application starts in ~5 seconds and displays media from configured directory
- Web UI should show a dark theme with media thumbnails/list on the left
- Main viewer shows selected media file with scoring controls
- API returns JSON with media files and their scores

## Common Tasks

### Changing Media Directory
1. Edit `config.yml` or use command line arguments
2. Restart application to scan new directory

### Adding New Media Formats
1. Update pattern in `config.yml` or command line
2. Ensure ffmpeg/ffprobe support the format for video files

### Development Workflow
1. Make code changes
2. Restart application (automatic reload not enabled)
3. Test in browser and via API
4. Verify logs in console output

## Repository Structure

### Key Files
```
├── app/                       # Modular application code
│   ├── main.py               # Main application factory and CLI interface
│   ├── settings.py           # Configuration handling
│   ├── state.py              # Global state management
│   ├── routers/              # FastAPI route handlers
│   ├── services/             # Business logic and utilities
│   ├── static/               # Static files (themes, JS)
│   └── templates/            # HTML templates
├── run.py                    # Application entry point
├── config.yml                # Default configuration
├── requirements.txt          # Python dependencies
├── read_config.py            # Configuration utility
│
├── run_video_scorer.sh        # Linux/macOS launcher
├── run_video_scorer.ps1       # PowerShell launcher  
├── run_video_scorer.bat       # Windows CMD launcher
│
├── Dockerfile                 # Docker configuration
├── docker-compose.yml         # Docker Compose setup
├── docker-entrypoint.sh       # Docker entry script
│
├── themes/                    # CSS themes
│   ├── style_default.css      # Default dark theme
│   ├── style_pastelcore.css   # Pastel theme
│   └── style_darkcandy.css    # Dark candy theme
│
└── media/                     # Sample media files (development)
```

### Auto-Generated Directories
- `.scores/` - Score files and logs (created at runtime)
- `workflows/` - Workflow extraction outputs (created at runtime)
- `.thumbnails/` - Generated thumbnails (if enabled)

## Configuration

### config.yml Settings
```yaml
dir: ./media                    # Media directory path
host: 127.0.0.1                # Server host
port: 7862                      # Server port  
pattern: "*.mp4|*.png|*.jpg"    # File patterns (pipe-separated)
style: style_default.css        # CSS theme file
generate_thumbnails: true       # Enable thumbnail generation
thumbnail_height: 64            # Thumbnail height in pixels
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
**Issue**: "PyYAML not installed" error when using read_config.py
**Workaround**: Install manually: `pip install pyyaml`

### Windows Path Issues
**Issue**: Path separators in Windows environments
**Workaround**: Use forward slashes or escape backslashes in paths

## Development Notes

### No Automatic Restart
The application does not auto-reload on code changes. Always restart after modifications.

### Themes
Available CSS themes in `themes/` directory:
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

### File Extensions Supported
- **Videos**: .mp4
- **Images**: .png, .jpg, .jpeg
- **Patterns**: Use pipe separator (|) for multiple: "*.mp4|*.png|*.jpg"

Always verify changes work by running the complete application and testing in both the web interface and via API calls.