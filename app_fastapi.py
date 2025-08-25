#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

# ---------------------------
# Config / Globals
# ---------------------------
APP = FastAPI()
VIDEO_DIR: Path = Path.cwd()
LOGGER: logging.Logger = logging.getLogger("video_scorer_fastapi")
FILE_LIST: List[Path] = []

def scores_dir_for(directory: Path) -> Path:
    sdir = directory / ".scores"
    sdir.mkdir(exist_ok=True, parents=True)
    (sdir / ".log").mkdir(exist_ok=True, parents=True)
    return sdir

def sidecar_path_for(video_path: Path) -> Path:
    return scores_dir_for(video_path.parent) / f"{video_path.name}.json"

def read_score(video_path: Path) -> Optional[int]:
    scp = sidecar_path_for(video_path)
    if not scp.exists():
        return None
    try:
        data = json.loads(scp.read_text(encoding="utf-8"))
        val = int(data.get("score", 0))
        if val < -1 or val > 5:
            return 0
        return val
    except Exception:
        return None

def write_score(video_path: Path, score: int) -> None:
    scp = sidecar_path_for(video_path)
    payload = {
        "file": video_path.name,
        "score": int(score),
        "updated": dt.datetime.now().isoformat(timespec="seconds"),
    }
    scp.write_text(json.dumps(payload, indent=2), encoding="utf-8")

def discover_videos(directory: Path) -> List[Path]:
    return sorted([p for p in directory.glob("*.mp4")])

def setup_logging(directory: Path):
    global LOGGER
    LOGGER.setLevel(logging.DEBUG)
    for h in list(LOGGER.handlers):
        LOGGER.removeHandler(h)
    log_dir = scores_dir_for(directory) / ".log"
    log_file = log_dir / "video_scorer.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fmt = logging.Formatter("%(asctime)s | %(levelname)-5s | %(message)s")
    fh.setFormatter(fmt)
    LOGGER.addHandler(fh)
    LOGGER.info(f"Logger initialized. dir={directory}")

# ---------------------------
# API Routes
# ---------------------------

@APP.get("/", response_class=HTMLResponse)
def index():
    # Serve a minimal single-page app
    return HTMLResponse(CLIENT_HTML)

@APP.get("/api/videos")
def api_videos():
    # Return list of video entries with current score
    items = []
    for p in FILE_LIST:
        items.append({
            "name": p.name,
            "url": f"/media/{p.name}",
            "score": read_score(p) if read_score(p) is not None else 0
        })
    return {"videos": items}

@APP.post("/api/score")
async def api_score(req: Request):
    data = await req.json()
    name = data.get("name")
    score = int(data.get("score", 0))
    target = VIDEO_DIR / name
    if not target.exists() or target not in FILE_LIST:
        raise HTTPException(404, "Video not found")
    write_score(target, score)
    LOGGER.info(f"SCORE file={name} score={score}")
    return {"ok": True}

@APP.post("/api/key")
async def api_key(req: Request):
    data = await req.json()
    key = str(data.get("key"))
    fname = str(data.get("name"))
    LOGGER.info(f"KEY key={key} file={fname}")
    return {"ok": True}

# ---------------------------
# Client HTML/JS
# ---------------------------

CLIENT_HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Video Scorer (FastAPI)</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body { background:#181818; color:#eee; font-family:system-ui, Segoe UI, Roboto, sans-serif; margin:0; }
    header { padding:12px 16px; background:#242424; border-bottom:1px solid #333; }
    h1 { font-size:18px; margin:0; }
    main { padding:16px; max-width:1100px; margin:0 auto; }
    .row { display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
    .filename { font-family:monospace; opacity:0.9; }
    .controls button { background:#2f2f2f; color:#eee; border:1px solid #666; padding:8px 12px; border-radius:8px; cursor:pointer; }
    .controls button:hover { background:#3a3a3a; }
    .video-wrap { background:#000; padding:8px; border-radius:12px; }
    .scorebar { margin-top:8px; }
    .pill { background:#2d2d2d; padding:4px 8px; border-radius:999px; border:1px solid #555; }
  </style>
</head>
<body>
  <header>
    <h1>🎬 Video Scorer (FastAPI)</h1>
    <div class="pill">Keys: ←/→ navigate • 1–5 rate • R reject</div>
  </header>
  <main>
    <div class="row">
      <div class="filename" id="filename">(loading…)</div>
    </div>
    <div class="row">
      <div class="video-wrap">
        <video id="player" width="960" height="540" controls preload="metadata"></video>
        <div class="scorebar" id="scorebar"></div>
      </div>
    </div>
    <div class="row controls">
      <button id="prev">← Prev</button>
      <button id="next">Next →</button>
      <button id="reject">Reject (R)</button>
      <button data-star="1">★1</button>
      <button data-star="2">★2</button>
      <button data-star="3">★3</button>
      <button data-star="4">★4</button>
      <button data-star="5">★5</button>
    </div>
  </main>
<script>
let videos = [];
let idx = 0;

function svgReject(selected){
  const circleFill = selected ? "white" : "black";
  const xColor = selected ? "black" : "white";
  const r = 16, cx=20, cy=20;
  return `
<svg width="40" height="40" viewBox="0 0 40 40">
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="${circleFill}" stroke="white" stroke-width="2" />
  <line x1="${cx-10}" y1="${cy-10}" x2="${cx+10}" y2="${cy+10}" stroke="${xColor}" stroke-width="4" stroke-linecap="round" />
  <line x1="${cx-10}" y1="${cy+10}" x2="${cx+10}" y2="${cy-10}" stroke="${xColor}" stroke-width="4" stroke-linecap="round" />
</svg>`;
}

function svgStar(filled){
  const fill = filled ? "white" : "black";
  return `
<svg width="40" height="40" viewBox="0 0 40 40">
  <polygon points="20,4 24,16 36,16 26,24 30,36 20,28 10,36 14,24 4,16 16,16"
    fill="${fill}" stroke="white" stroke-width="2"/>
</svg>`;
}

function renderScoreBar(score){
  const bar = document.getElementById("scorebar");
  let html = `<div style="display:flex; gap:8px; align-items:center;">`;
  html += svgReject(score === -1);
  const stars = (score === -1) ? 0 : Math.max(0, score||0);
  for (let i=0;i<5;i++) html += svgStar(i<stars);
  html += `</div>`;
  bar.innerHTML = html;
}

function show(i){
  if (videos.length === 0) return;
  idx = Math.max(0, Math.min(i, videos.length-1));
  const v = videos[idx];
  const player = document.getElementById("player");
  player.src = v.url + `#t=0.001`; // small offset to force thumb load in some browsers
  document.getElementById("filename").textContent = `${idx+1}/${videos.length}  •  ${v.name}`;
  renderScoreBar(v.score || 0);
}

async function loadVideos(){
  const res = await fetch("/api/videos");
  const data = await res.json();
  videos = data.videos || [];
  show(0);
}

async function postScore(score){
  const v = videos[idx];
  if (!v) return;
  await fetch("/api/score", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ name: v.name, score: score })
  });
  v.score = score;
  renderScoreBar(score);
}

async function postKey(key){
  const v = videos[idx];
  await fetch("/api/key", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ key: key, name: v ? v.name : "" })
  });
}

document.getElementById("prev").addEventListener("click", () => { show(idx-1); });
document.getElementById("next").addEventListener("click", () => { show(idx+1); });
document.getElementById("reject").addEventListener("click", () => { postScore(-1); });

document.querySelectorAll("[data-star]").forEach(btn => {
  btn.addEventListener("click", () => {
    const n = parseInt(btn.getAttribute("data-star"));
    postScore(n);
  });
});

document.addEventListener("keydown", (e) => {
  if (["INPUT","TEXTAREA"].includes((e.target.tagName||"").toUpperCase())) return;
  const player = document.getElementById("player");
  function togglePlay(){
    if (!player) return;
    if (player.paused) { player.play(); } else { player.pause(); }
  }
  if (e.key === "ArrowLeft"){ e.preventDefault(); postKey("ArrowLeft"); show(idx-1); return; }
  if (e.key === "ArrowRight"){ e.preventDefault(); postKey("ArrowRight"); show(idx+1); return; }
  if (e.key === " "){ e.preventDefault(); postKey("Space"); togglePlay(); return; }
  if (e.key === "1"){ e.preventDefault(); postKey("1"); postScore(1); return; }
  if (e.key === "2"){ e.preventDefault(); postKey("2"); postScore(2); return; }
  if (e.key === "3"){ e.preventDefault(); postKey("3"); postScore(3); return; }
  if (e.key === "4"){ e.preventDefault(); postKey("4"); postScore(4); return; }
  if (e.key === "5"){ e.preventDefault(); postKey("5"); postScore(5); return; }
  if (e.key === "r" || e.key === "R"){ e.preventDefault(); postKey("R"); postScore(-1); return; }
});

window.addEventListener("load", loadVideos);
</script>
</body>
</html>
"""

# ---------------------------
# CLI & Startup
# ---------------------------
def main():
    global VIDEO_DIR, FILE_LIST

    ap = argparse.ArgumentParser(description="Video Scorer (FastAPI)")
    ap.add_argument("--dir", required=False, default=str(Path.cwd()), help="Directory with .mp4 files")
    ap.add_argument("--port", type=int, default=7862, help="Port to serve")
    ap.add_argument("--host", default="127.0.0.1", help="Host to bind")
    args = ap.parse_args()

    VIDEO_DIR = Path(args.dir).expanduser().resolve()
    if not VIDEO_DIR.exists() or not VIDEO_DIR.is_dir():
        raise SystemExit(f"Directory not found: {VIDEO_DIR}")

    setup_logging(VIDEO_DIR)
    FILE_LIST = discover_videos(VIDEO_DIR)
    LOGGER.info(f"Discovered {len(FILE_LIST)} videos in {VIDEO_DIR}")

    # Mount static serving for the target directory at /media
    APP.mount("/media", StaticFiles(directory=str(VIDEO_DIR), html=False), name="media")

    uvicorn.run(APP, host=args.host, port=args.port, log_level="info")

if __name__ == "__main__":
    main()
