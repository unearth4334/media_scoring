# 🎬 Gradio Video Scorer

A lightweight Gradio UI to **view** and **score** `.mp4` videos with fast **keyboard shortcuts**.

## Features
- Navigate videos in a folder (sorted by name)
- **Keyboard shortcuts**
  - `←` / `→` : Previous / Next video
  - `1`..`5` : Set star rating (1–5)
  - `R` : Mark as **Reject**
- Visual score bar rendered as SVG:
  - Leftmost: **Reject** badge (X in a circle) — inverts colors when selected
  - Five stars to the right — filled in white up to your rating
- Scores saved as **sidecar JSON** files in a `.scores` subfolder next to your videos
- Automatically loads existing scores when you open a folder

## Install

```bash
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run

```bash
python app.py --dir /path/to/your/videos --port 7860
# Then open the printed local URL in your browser.
```

You can change folders from inside the app too — enter a path and press **Load**.

## Score Files

Each video gets a JSON sidecar at:
```
<video_dir>/.scores/<filename>.json
```
Example:
```json
{
  "file": "clip001.mp4",
  "score": 4,          // -1 (reject) or 1..5, 0/absent => not set
  "updated": "2025-08-24T15:13:00"
}
```

## Notes
- The app only scans for `*.mp4` in the selected folder.
- Keyboard shortcuts are handled by a tiny bit of JS that "clicks" the corresponding buttons.
- The score bar is a fully inlined SVG (no external assets needed).
