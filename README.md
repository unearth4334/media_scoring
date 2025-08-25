# 🎬 Video Scorer (FastAPI) — with Directory Picker

A minimal, robust video scorer that **captures keyboard shortcuts** and now includes a **directory picker** so you can switch folders on the fly.

## Features
- **Minimum rating filter** dropdown (No filter, 1–5). Navigation and queue respect the filter; scoring re-applies it on the fly.
- Plain HTML + JS → reliable keys (←/→, Space, 1–5, R)
- Change directory from the UI (textbox + Load button or press Enter)
- Serves media from the **current** directory via `/media/<file>`
- Score sidecars in `.scores/<filename>.json` (auto-load existing)
- Verbose logging to `.scores/.log/video_scorer.log` — includes **keystrokes** and directory scans
- SVG score bar: reject circle + five stars

## Install
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run
```bash
python app_fastapi.py --dir /path/to/initial/videos --port 7862
# open http://127.0.0.1:7862/
```

## Change directory (in the UI)
- Paste a path (e.g., `/mnt/qnap-sd/SecretFolder/WAN/2025-08-24/test`) into the **Directory** box
- Click **Load** or press **Enter**
- The app scans that folder for `*.mp4`, loads scores, and starts serving `/media/<file>` from it

## Logs
```
<video_dir>/.scores/.log/video_scorer.log
```
Examples:
```
INFO | Logger initialized. dir=/mnt/qnap-sd/SecretFolder/WAN/2025-08-24/test
INFO | SCAN dir=/mnt/qnap-sd/SecretFolder/WAN/2025-08-24/test videos=24
INFO | KEY key=Space file=134405_IN_00002.mp4
INFO | SCORE file=134405_IN_00003.mp4 score=3
```

## Notes
- Refresh the page if you change files on disk while the app is running.
- The `/media/{name}` endpoint is secured to the currently selected directory; it won’t serve paths outside of it.
