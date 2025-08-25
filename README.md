# 🎬 Video Scorer (FastAPI)

A minimal, robust video scorer that **runs locally** and captures **keyboard shortcuts** reliably (←/→ navigation, 1–5 stars, R reject).  
This is a replacement for the Gradio-based UI when global key handling is finicky.

## Features
- Plain HTML + JS → **reliable** keyboard handling
- Serve videos directly from your target folder (`/media/<file>`)
- Score sidecars in `.scores/<filename>.json` (auto-load existing)
- Verbose logging to `.scores/.log/video_scorer.log` including **keystrokes**
- SVG score bar exactly as specified

## Install
```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Run
```bash
python app_fastapi.py --dir /path/to/videos --port 7862
# open http://127.0.0.1:7862/
```

## Scores
Example sidecar:
```json
{
  "file": "clip001.mp4",
  "score": 4,
  "updated": "2025-08-24T17:25:00"
}
```

## Logs
Log file at:
```
<video_dir>/.scores/.log/video_scorer.log
```
Contains entries like:
```
INFO | SCORE file=134405_IN_00003.mp4 score=3
INFO | KEY key=ArrowRight file=134405_IN_00004.mp4
```

## Notes
- Single-user design; state lives client-side (the current index) and server-side scans the folder at startup.
- If you add/remove files while running, refresh the page to reload the list.
