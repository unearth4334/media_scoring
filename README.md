# 🎬 Video & Image Scorer

An interactive **FastAPI + HTML/JS** web application for **reviewing, scoring, and managing video and image datasets**.  
Supports `.mp4` videos, `.png`, `.jpg`, and `.jpeg` images, with workflow extraction and metadata parsing.  
Designed for datasets from **ComfyUI / Stable Diffusion pipelines** but useful in any scoring/annotation workflow.

---

## ✨ Features

### Media Handling
- **Supported formats**: `.mp4`, `.png`, `.jpg`, `.jpeg`
- **Navigation**: left/right arrows to flip through files
- **Playback**: spacebar toggles play/pause for videos
- **Resolution display**: `[WxH]` appended to filename
  - Uses `ffprobe` for videos, Pillow for images
- **Glob patterns**:
  - Control which files are shown (`*.mp4`, `*.png|*.jpg`, etc.)
  - Help button `?` shows quick syntax guide

### Data Mining
- **Archive Processing**: Extract metadata from existing media archives
- **Standalone CLI Tool**: `mine_data.py` for batch processing without web server
- **Database Integration**: Store extracted metadata, keywords, and scores
- **Flexible Patterns**: Process specific file types with glob patterns
- **Progress Reporting**: Detailed statistics and progress tracking
- **Score Import**: Import existing scores from sidecar files

### Scoring
- **1–5 stars**: press number keys or buttons
- **Reject (R)**: reject a file
- Graphical score bar:
  - ❌ reject symbol
  - ⭐ filled/empty stars
- Scores saved to `.scores/<filename>.json` sidecar files

### Filtering
- Dropdown for **minimum rating filter** (None / 1–5)
- Sidebar greys out files that don’t pass the filter

### Sidebar
- Lists all files in current directory
- Current item highlighted
- Displays each file’s score badge (—, ★, R)
- **Optional thumbnail previews**:
  - Enabled via `generate_thumbnails: true` in config.yml
  - Shows scaled preview images (64px height by default)
  - Supports images (.png, .jpg, .jpeg) and videos (.mp4)
  - Video thumbnails extracted from first frame
  - "Toggle Thumbnails" button to show/hide when enabled

### Metadata
- **PNG info parsing**:
  - Detects embedded **parameters** (tEXt/zTXt/iTXt chunks)
  - Shows an ⓘ button when metadata exists
  - Clicking toggles an overlay with full metadata text
  - Copy button to copy all text to clipboard

### Workflow Extraction
- Integration with `extract_comfyui_workflow.py`
- Buttons:
  - Extract workflow JSON for **current file**
  - Extract workflows for **all filtered files**
- Output saved in `workflows/<filename>_workflow.json`

### File Management
- **Download button**: saves current file to your computer

### Logging
- Detailed logs written to `.scores/.log/video_scorer.log`
- Includes:
  - Directory scans
  - Key presses
  - Score changes
  - Workflow extraction results

---

## 📂 Project Structure

```
.
├── run.py                     # Main entry point
├── mine_data.py               # ✨ NEW: Data mining CLI tool
├── mine_archive.sh            # ✨ NEW: Convenient wrapper script
├── extract_comfyui_workflow.py # Extracts workflow JSON from MP4 metadata
├── config.yml                  # Default config values (dir, host, port, pattern)
├── requirements.txt            # Python dependencies
├── LICENSE                     # Apache 2.0 license
├── README.md                   # This documentation
├── MINING_TOOL.md              # ✨ NEW: Mining tool documentation
├── DOCKER.md                   # Docker deployment guide
│
├── Dockerfile                  # Docker container configuration
├── docker-compose.yml          # Basic Docker Compose setup
├── docker-compose.override.yml # Advanced Docker Compose with env vars
├── .env.example               # Example environment configuration
├── validate-docker-setup.sh   # Docker setup validation script
│
├── run_video_scorer.sh         # Linux/macOS entrypoint
├── run_video_scorer.ps1        # Windows PowerShell entrypoint
├── run_video_scorer.bat        # Windows CMD entrypoint
│
├── .scores/                    # Auto-created: stores sidecar score files + logs
│   ├── file1.mp4.json
│   ├── media.db               # ✨ NEW: SQLite database (when enabled)
│   └── .log/video_scorer.log
│
└── workflows/                  # Auto-created: workflow JSON outputs
    └── file1_workflow.json
```

---

## ⚙️ Configuration

Configuration is stored in `config.yml` (or `config.wml` in some setups):

```yaml
dir: /path/to/media        # Default directory to scan
host: 127.0.0.1            # Host to bind the server
port: 7862                 # Port to serve
pattern: "*.mp4"           # Glob pattern for media files (e.g., *.mp4|*.png|*.jpg)
generate_thumbnails: false # Generate thumbnail previews for media files
thumbnail_height: 64       # Height in pixels for thumbnail previews
```

You can override these values at runtime via:
- **CLI arguments** (`--dir`, `--port`, `--host`, `--pattern`)
- **Entrypoint script parameters** (see below)

---

## 🚀 Entrypoint Scripts

To simplify launching, three entrypoints are provided.  
All scripts read defaults from **config.yml**, but allow overrides.

### Linux/macOS (sh)
```bash
chmod +x run_video_scorer.sh
./run_video_scorer.sh                 # use config.yml defaults
./run_video_scorer.sh /media/dir 9000 "*.mp4|*.jpg"  # override dir, port & pattern
```

### Windows PowerShell
```powershell
.\run_video_scorer.ps1                 # use config.yml defaults
.\run_video_scorer.ps1 -Dir "D:\media" -Port 9000 -Pattern "*.mp4|*.jpg" -Host 0.0.0.0
```

### Windows CMD
```bat
run_video_scorer.bat                   REM use config.yml defaults
run_video_scorer.bat "D:\media" 9000 0.0.0.0 "*.mp4|*.jpg" style_default.css
```

---

## 🗂️ Data Mining Tool *(NEW)*

Extract metadata from existing media archives and populate the database without running the web server.

### Quick Start
```bash
# Test archive scanning (dry run)
python mine_data.py /path/to/archive

# Mine data and store in database
python mine_data.py /path/to/archive --enable-database

# Use convenient wrapper script
./mine_archive.sh quick /path/to/archive
./mine_archive.sh images /path/to/photos
./mine_archive.sh videos /path/to/videos
```

### Key Features
- **Standalone CLI tool** - runs independently of web server
- **Batch processing** - handle large archives efficiently  
- **Database integration** - stores metadata, keywords, scores
- **Score import** - imports existing `.scores/*.json` files
- **Flexible patterns** - `*.mp4|*.png|*.jpg` or custom patterns
- **Progress tracking** - detailed statistics and logging
- **Dry run mode** - test without database writes

### Example Output
```
$ ./mine_archive.sh images /media/photos
[INFO] Mining images from: /media/photos
[INFO] Database initialized with URL: sqlite:///media/photos/.scores/media.db
[INFO] Found 156 files matching pattern
[INFO] Processing files with database storage enabled
[INFO] Processing file 50/156: portrait_050.png
[INFO] Processing file 100/156: landscape_100.jpg
[INFO] Processing file 156/156: anime_156.jpeg
[INFO] ==================================================
[INFO] DATA MINING COMPLETED
[INFO] ==================================================
[INFO] Total files found: 156
[INFO] Files processed: 156
[INFO] Metadata extracted: 156
[INFO] Keywords added: 312
[INFO] Scores imported: 23
[INFO] Errors encountered: 0
[INFO] Processing completed successfully!
[SUCCESS] Mining completed successfully!
```

See **[MINING_TOOL.md](MINING_TOOL.md)** for complete documentation.

---

## 🛠 Installation

### Option 1: Local Installation

1. **Clone / extract** this project.

2. **Create a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate   # Linux/macOS
   .venv\Scripts\activate      # Windows
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

   Requirements:
   - `fastapi`
   - `uvicorn`
   - `pillow` (for image resolution)
   - `pyyaml` (for config.yml reading)

   System dependencies:
   - `ffmpeg` / `ffprobe` must be installed and in PATH

4. **Run**:
   ```bash
   python run.py --dir /path/to/media --port 7862 --pattern "*.mp4|*.png|*.jpg"
   ```

5. Open in browser: [http://127.0.0.1:7862](http://127.0.0.1:7862)

### Option 2: Docker Installation

For containerized deployment (recommended for NAS/server hosting):

1. **Clone the repository**:
   ```bash
   git clone https://github.com/unearth4334/media_scoring.git
   cd media_scoring
   ```

2. **Configure for your setup**:
   ```bash
   cp .env.example .env
   # Edit .env file to set your media path and preferences
   ```

3. **Deploy with Docker Compose**:
   ```bash
   docker-compose up -d
   ```

4. **Access**: Open browser to `http://your-server-ip:7862`

📖 **See [DOCKER.md](DOCKER.md) for complete Docker deployment guide including QNAP NAS setup.**

---

## 🎮 Controls

- **← / →**: Previous / Next file
- **Space**: Play/Pause (videos only)
- **1–5**: Assign star rating
- **R**: Reject file
- **ⓘ**: Toggle PNG metadata overlay (if available)
- **Copy**: Copy PNG metadata text
- **Download current**: Save active file locally
- **Extract one**: Extract workflow JSON for current file
- **Extract filtered**: Extract workflow JSONs for all filtered files
- **Export Filtered**: Download all filtered files as a ZIP archive

---

## 📝 Logging

Logs stored in `.scores/.log/video_scorer.log`  
Sample:
```
2025-08-24 20:36:33 | INFO  | Logger initialized. dir=/mnt/media
2025-08-24 20:37:01 | INFO  | SCORE file=clip1.mp4 score=5
2025-08-24 20:37:15 | INFO  | KEY key=ArrowRight file=clip1.mp4
2025-08-24 20:37:20 | INFO  | EXTRACT success file=clip1.mp4 out=workflows/clip1_workflow.json
```

---

## ⚖ License

This project is licensed under the [Apache License 2.0](LICENSE).

---

## 🤝 Contributing

- File issues for bugs or feature requests
- Submit PRs for improvements
- Suggestions for workflow integrations welcome

---

## 🔮 Roadmap

- Recursive glob patterns (`**/*.png`)
- ✅ Image/video thumbnails in sidebar
- Multi-directory support
- ✅ Bulk download of filtered items
- Sorting by score/filename/date
