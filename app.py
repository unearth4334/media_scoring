#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import logging
from pathlib import Path
from typing import List, Dict, Optional
import subprocess
import sys

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
import uvicorn
import zlib

try:
    from PIL import Image
except Exception:
    Image = None  # Pillow optional; image metadata endpoint will degrade gracefully

# ---------------------------
# Config / Globals
# ---------------------------
APP = FastAPI()
VIDEO_DIR: Path = Path.cwd()
LOGGER: logging.Logger = logging.getLogger("video_scorer_fastapi")
FILE_LIST: List[Path] = []
FILE_PATTERN: str = "*.mp4"

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

# ---- file discovery (supports images + glob union) ----
def _match_union(directory: Path, pattern: str) -> List[Path]:
    pats = [p.strip() for p in (pattern or "").split("|") if p.strip()]
    if not pats:
        pats = ["*.mp4"]
    seen: Dict[Path, Path] = {}
    for pat in pats:
        for p in directory.glob(pat):
            if p.is_file():
                seen[p.resolve()] = p
    return sorted(seen.values())

def discover_files(directory: Path, pattern: str) -> List[Path]:
    return _match_union(directory, pattern)

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

def switch_directory(new_dir: Path, pattern: Optional[str] = None):
    global VIDEO_DIR, FILE_LIST, FILE_PATTERN
    VIDEO_DIR = new_dir
    if pattern is not None and pattern.strip():
        FILE_PATTERN = pattern.strip()
    setup_logging(VIDEO_DIR)
    FILE_LIST = discover_files(VIDEO_DIR, FILE_PATTERN)
    LOGGER.info(f"SCAN dir={VIDEO_DIR} pattern={FILE_PATTERN} files={len(FILE_LIST)}")


# ---------------------------
# Extractor helpers
# ---------------------------

def extractor_script_path() -> Path:
    # expect the script to live next to this app.py
    here = Path(__file__).resolve().parent
    return here / "extract_comfyui_workflow.py"

def ensure_workflows_dir(for_video: Path) -> Path:
    wf_dir = for_video.parent / "workflows"
    wf_dir.mkdir(parents=True, exist_ok=True)
    return wf_dir

def extract_workflow_for(video_path: Path) -> Dict[str, str]:
    """Run the external extractor for a single mp4 and write:
    ./workflows/<filename_without_ext>_workflow.json
    Returns a dict with status and paths.
    """
    if not video_path.exists():
        return {"name": video_path.name, "status": "error", "error": "file_not_found"}
    script = extractor_script_path()
    if not script.exists():
        return {"name": video_path.name, "status": "error", "error": "missing_extractor"}
    out_path = ensure_workflows_dir(video_path) / f"{video_path.stem}_workflow.json"
    cmd = [sys.executable, str(script), str(video_path), "-o", str(out_path)]
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, check=False)
        if cp.returncode == 0:
            LOGGER.info(f"EXTRACT success file={video_path.name} out={out_path}")
            return {"name": video_path.name, "status": "ok", "output": str(out_path)}
        else:
            LOGGER.warning(f"EXTRACT failed file={video_path.name} rc={cp.returncode} stderr={cp.stderr.strip()}")
            return {"name": video_path.name, "status": "error", "error": f"rc={cp.returncode}", "stderr": cp.stderr}
    except FileNotFoundError:
        return {"name": video_path.name, "status": "error", "error": "python_not_found"}

# ---------------------------
# API Routes
# ---------------------------


def _read_png_parameters_text(png_path: Path, max_bytes: int = 2_000_000) -> Optional[str]:
    """
    Best-effort parse of PNG tEXt/zTXt/iTXt chunks to extract a 'parameters' text blob
    (e.g., Automatic1111 / ComfyUI). Returns the text payload if found; otherwise None.
    """
    try:
        with open(png_path, "rb") as f:
            sig = f.read(8)
            if sig != b"\x89PNG\r\n\x1a\n":
                return None
            read_total = 8
            param_text = None
            while True:
                if read_total > max_bytes:
                    break
                len_bytes = f.read(4)
                if len(len_bytes) < 4:
                    break
                length = int.from_bytes(len_bytes, "big")
                ctype = f.read(4)
                if len(ctype) < 4:
                    break
                data = f.read(length)
                if len(data) < length:
                    break
                _crc = f.read(4)
                read_total += 12 + length
                if ctype in (b"tEXt", b"zTXt", b"iTXt"):
                    try:
                        if ctype == b"tEXt":
                            # keyword\0text
                            if b"\x00" in data:
                                keyword, text = data.split(b"\x00", 1)
                                key = keyword.decode("latin-1", "ignore").strip().lower()
                                if key in ("parameters", "comment", "description"):
                                    t = text.decode("utf-8", "ignore").strip()
                                    if t:
                                        param_text = t
                        elif ctype == b"zTXt":
                            # keyword\0compression_method\0 compressed_text
                            if b"\x00" in data:
                                parts = data.split(b"\x00", 2)
                                if len(parts) >= 3:
                                    keyword = parts[0].decode("latin-1", "ignore").strip().lower()
                                    comp_method = parts[1][:1] if parts[1] else b"\x00"
                                    comp_data = parts[2]
                                    if comp_method == b"\x00":  # zlib/deflate
                                        try:
                                            txt = zlib.decompress(comp_data).decode("utf-8", "ignore").strip()
                                            if keyword in ("parameters", "comment", "description") and txt:
                                                param_text = txt
                                        except Exception:
                                            pass
                        elif ctype == b"iTXt":
                            # keyword\0 compression_flag\0 compression_method\0 language_tag\0 translated_keyword\0 text
                            # We handle only uncompressed (compression_flag==0)
                            parts = data.split(b'\x00', 5)
                            if len(parts) >= 6:
                                keyword = parts[0].decode("utf-8", "ignore").strip().lower()
                                comp_flag = parts[1][:1] if parts[1] else b"\x00"
                                # parts[2]=comp_method, parts[3]=language_tag, parts[4]=translated_keyword
                                text = parts[5]
                                if comp_flag == b"\x00":
                                    t = text.decode("utf-8", "ignore").strip()
                                    if keyword in ("parameters", "comment", "description") and t:
                                        param_text = t
                    except Exception:
                        pass
                if ctype == b"IEND":
                    break
            return param_text
    except Exception:
        return None

@APP.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(CLIENT_HTML)

@APP.get("/api/videos")
def api_videos():
    # Return list of entries with current score
    items = []
    for p in FILE_LIST:
        items.append({
            "name": p.name,
            "url": f"/media/{p.name}",
            "score": read_score(p) if read_score(p) is not None else 0
        })
    return {"dir": str(VIDEO_DIR), "pattern": FILE_PATTERN, "videos": items}

@APP.post("/api/scan")
async def api_scan(req: Request):
    data = await req.json()
    new_dir = Path(str(data.get("dir",""))).expanduser().resolve()
    pattern = str(data.get("pattern","")).strip() or None
    if not new_dir.exists() or not new_dir.is_dir():
        raise HTTPException(400, f"Directory not found: {new_dir}")
    switch_directory(new_dir, pattern)
    return {"ok": True, "dir": str(VIDEO_DIR), "pattern": FILE_PATTERN, "count": len(FILE_LIST)}

@APP.get("/media/{name:path}")
def serve_media(name: str):
    target = (VIDEO_DIR / name).resolve()
    # Security: ensure the resolved path is within VIDEO_DIR
    try:
        target.relative_to(VIDEO_DIR)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
    ext = target.suffix.lower()
    if ext == ".mp4":
        mime = "video/mp4"
    elif ext == ".png":
        mime = "image/png"
    elif ext in {".jpg", ".jpeg"}:
        mime = "image/jpeg"
    else:
        mime = "application/octet-stream"
    return FileResponse(target, media_type=mime)

@APP.get("/api/meta/{name:path}")
def api_meta(name: str):
    target = (VIDEO_DIR / name).resolve()
    try:
        target.relative_to(VIDEO_DIR)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")

    ext = target.suffix.lower()
    if ext == ".mp4":
        # Use ffprobe to retrieve width/height
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-select_streams", "video:0",
                "-show_entries", "stream=width,height",
                "-of", "json", str(target)
            ]
            cp = subprocess.run(cmd, capture_output=True, text=True, check=True)
            info = json.loads(cp.stdout or "{}")
            if isinstance(info, dict) and info.get("streams"):
                st = info["streams"][0]
                w = st.get("width")
                h = st.get("height")
                if w and h:
                    return {"width": int(w), "height": int(h)}
        except Exception as e:
            return {"error": str(e)}
    elif ext in {".png", ".jpg", ".jpeg"}:
        try:
            if Image is None:
                meta = {"error": "Pillow not installed"}
            else:
                with Image.open(target) as im:
                    meta = {"width": int(im.width), "height": int(im.height)}
            if ext == ".png":
                txt = _read_png_parameters_text(target)
                if txt:
                    meta["png_text"] = txt
            return meta
        except Exception as e:
            return {"error": str(e)}
    return {}


@APP.get("/download/{name:path}")
def download_media(name: str):
    target = (VIDEO_DIR / name).resolve()
    try:
        target.relative_to(VIDEO_DIR)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
    # Force download via Content-Disposition
    return FileResponse(target, media_type="application/octet-stream", filename=name)


@APP.post("/api/score")
async def api_score(req: Request):
    data = await req.json()
    name = data.get("name")
    score = int(data.get("score", 0))
    target = VIDEO_DIR / name
    if not target.exists() or target not in FILE_LIST:
        raise HTTPException(404, "File not found")
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

@APP.post("/api/extract")
async def api_extract(req: Request):
    """Extract ComfyUI workflow JSON for one or more files.
    JSON body: { "names": ["file1.mp4", ...] }
    """
    data = await req.json()
    names = data.get("names") or []
    if not isinstance(names, list):
        raise HTTPException(400, "names must be a list of filenames")
    results = []
    for nm in names:
        vp = (VIDEO_DIR / nm).resolve()
        try:
            vp.relative_to(VIDEO_DIR)
        except Exception:
            results.append({"name": nm, "status": "error", "error": "forbidden_path"})
            continue
        results.append(extract_workflow_for(vp))
    return {"results": results}

# ---------------------------
# Client HTML/JS
# ---------------------------

CLIENT_HTML = r"""
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Video Scorer</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <!-- Favicon: small movie camera emoji as SVG data URI -->
  <link rel="icon" type="image/svg+xml" href="data:image/svg+xml,<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'><text y='50%' x='50%' text-anchor='middle' dominant-baseline='central' font-size='48'>🎬</text></svg>">
  <style>
    body { background:#181818; color:#eee; font-family:system-ui, Segoe UI, Roboto, sans-serif; margin:0; }
    header { padding:12px 16px; background:#242424; border-bottom:1px solid #333; }
    h1 { font-size:18px; margin:0 0 8px 0; }
    main { padding:16px; max-width:1300px; margin:0 auto; }
    .layout { display:grid; grid-template-columns: 320px 1fr; gap:16px; }
    .row { display:flex; gap:12px; align-items:center; flex-wrap:wrap; grid-column: 1 / -1; }
    .filename { font-family:monospace; opacity:0.9; }
    .controls button { background:#2f2f2f; color:#eee; border:1px solid #666; padding:8px 12px; border-radius:8px; cursor:pointer; }
    .controls button:hover { background:#3a3a3a; }
    .video-wrap { background:#000; padding:8px; border-radius:12px; position:relative; }
.overlay-top-left { position:absolute; top:12px; left:12px; display:flex; gap:8px; z-index:5; }
.overlay-btn { width:32px; height:32px; border-radius:50%; background:#1e1e1e; color:#fff; border:1px solid #777; display:flex; align-items:center; justify-content:center; cursor:pointer; opacity:0.9; }
.overlay-btn:hover { background:#2a2a2a; }
#pnginfo_panel { position:absolute; inset:8px; background:rgba(0,0,0,0.85); color:#fff; padding:12px; border-radius:10px; overflow:auto; z-index:4; display:none; }
#pnginfo_copy { position:absolute; top:16px; right:16px; border:1px solid #999; background:#222; color:#fff; padding:6px 10px; border-radius:8px; cursor:pointer; }
#pnginfo_text { white-space:pre-wrap; font-family:ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, 'Liberation Mono', 'Courier New', monospace; font-size:12px; line-height:1.4; }
    .scorebar { margin-top:8px; }
    .pill { background:#2d2d2d; padding:4px 8px; border-radius:999px; border:1px solid #555; }
    input[type=text] { background:#111; color:#eee; border:1px solid #444; padding:8px 10px; border-radius:8px; min-width:280px; }
    .grow { flex: 1 1 auto; min-width: 280px; }
    /* Sidebar */
    aside#sidebar { max-height: 66vh; overflow:auto; background:#202020; border:1px solid #333; border-radius:10px; padding:8px; }
    .item { display:grid; grid-template-columns: 1fr auto; align-items:center; gap:8px; padding:6px 8px; border-radius:8px; cursor:pointer; }
    .item:hover { background:#2a2a2a; }
    .item.current { background:#343434; border:1px solid #555; }
    .item .name { font-family:monospace; font-size:12px; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width: 230px; }
    .item .score { font-size:12px; opacity:0.9; }
    .item.disabled { opacity:0.4; cursor:default; }
    .helpbtn { background:#3a3a3a; border:1px solid #777; padding:6px 8px; border-radius:8px; cursor:pointer; }
    /* Download icon button */
    #download_btn svg { vertical-align: middle; }
  </style>
</head>
<body>
  <header>
    <h1>🎬 Video/Image Scorer (FastAPI)</h1>
    <div class="pill">Keys: ←/→ navigate • Space play/pause (video) • 1–5 rate • R reject</div>
  </header>
  <main class="layout">
    <div class="row">
      <input id="dir" type="text" class="grow" placeholder="/path/to/folder"/>
      <input id="pattern" type="text" style="min-width:240px" placeholder="glob pattern (e.g. *.mp4|*.png|*.jpg)" />
      <button id="pat_help" class="helpbtn">?</button>
      <button id="load">Load</button>
      <div id="dir_display" class="filename"></div>
    </div>
    <div class="row">
      <label for="min_filter">Minimum rating:</label>
      <select id="min_filter">
        <option value="none" selected>No filter</option>
        <option value="1">1</option>
        <option value="2">2</option>
        <option value="3">3</option>
        <option value="4">4</option>
        <option value="5">5</option>
      </select>
      <div id="filter_info" class="filename"></div>
    </div>
    <aside id="sidebar">
      <div id="sidebar_list"></div>
    </aside>
    <section id="right">
      <div class="row">
        <div class="filename" id="filename">(loading…)</div>
      </div>
      <div class="row">
        <div class="video-wrap">
          <div class="overlay-top-left" id="pnginfo_controls" style="display:none;">
            <div class="overlay-btn" id="pnginfo_btn" title="Show info">i</div>
            <div class="overlay-btn" id="pngplus_btn" title="More">+</div>
          </div>
          <div id="pnginfo_panel">
            <button id="pnginfo_copy" title="Copy all">Copy</button>
            <div id="pnginfo_text"></div>
          </div>
          <video id="player" width="960" height="540" controls preload="metadata" style="display:none"></video>
          <img id="imgview" style="max-width:960px; max-height:540px; display:none" />
          <div class="scorebar" id="scorebar"></div>
        </div>
      </div>
      <div class="row controls">
        <button id="prev">Prev</button>
        <button id="next">Next</button>
        <button id="reject">Reject</button>
        <button data-star="1">★1</button>
        <button data-star="2">★2</button>
        <button data-star="3">★3</button>
        <button data-star="4">★4</button>
        <button data-star="5">★5</button>
        <button id="extract_one">Extract workflow (current)</button>
        <button id="extract_filtered">Extract workflows (filtered)</button>
        <button id="download_btn" title="Download current">
          <!-- Download icon SVG -->
          <svg width="24" height="24" viewBox="0 0 24 24" fill="none">
            <path d="M12 3v12m0 0l-5-5m5 5l5-5M5 19h14" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </button>
      </div>
    </section>
  </main>
<script>
let videos = [];
let filtered = [];
let idx = 0;
let currentDir = "";
let currentPattern = "*.mp4";
let minFilter = null; // null means no filter; otherwise 1..5

let currentMeta = null;
function togglePngInfo(show){
  const panel = document.getElementById('pnginfo_panel');
  if (!panel) return;
  if (show === undefined){ panel.style.display = (panel.style.display==='none' || panel.style.display==='') ? 'block' : 'none'; }
  else { panel.style.display = show ? 'block' : 'none'; }
}
function setupPngInfo(meta, name){
  currentMeta = meta || null;
  const controls = document.getElementById('pnginfo_controls');
  const textDiv = document.getElementById('pnginfo_text');
  togglePngInfo(false);
  if (meta && meta.png_text && isImageName(name) && name.toLowerCase().endsWith('.png')){
    controls.style.display = 'flex';
    textDiv.textContent = meta.png_text;
  } else {
    controls.style.display = 'none';
    textDiv.textContent = '';
  }
}
document.addEventListener('click', (e)=>{
  if (e.target && e.target.id === 'pnginfo_btn'){ togglePngInfo(true); }
  if (e.target && e.target.id === 'pngplus_btn'){ togglePngInfo(true); } // plus also opens
  if (e.target && e.target.id === 'pnginfo_copy'){ 
    const text = (document.getElementById('pnginfo_text').textContent)||'';
    if (!navigator.clipboard){ 
      const ta = document.createElement('textarea'); ta.value = text; document.body.appendChild(ta); ta.select(); document.execCommand('copy'); document.body.removeChild(ta);
    } else {
      navigator.clipboard.writeText(text).catch(()=>{});
    }
  }
});


function updateDownloadButton(name){
  const db = document.getElementById('download_btn');
  if (!db) return;
  if (!name){ db.disabled = true; return; }
  db.disabled = false;
  db.onclick = () => {
    try { window.location.href = '/download/' + encodeURIComponent(name); }
    catch(e){ alert('Download failed to start: ' + e); }
  };
}


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
function scoreBadge(s){
  if (s === -1) return 'R';
  if (!s || s < 1) return '—';
  return s + '★';
}
function renderSidebar(){
  const list = document.getElementById('sidebar_list');
  if (!list) return;
  let html = '';
  const namesInFiltered = new Set(filtered.map(v => v.name));
  videos.forEach((v) => {
    const inFiltered = namesInFiltered.has(v.name);
    const s = scoreBadge(v.score || 0);
    const classes = ['item'];
    if (!inFiltered) classes.push('disabled');
    if (filtered.length && filtered[idx] && filtered[idx].name === v.name) classes.push('current');
    html += `<div class="${classes.join(' ')}" data-name="${v.name}" ${inFiltered ? '' : 'data-disabled="1"'}>` +
            `<div class="name" title="${v.name}">${v.name}</div>` +
            `<div class="score">${s}</div>` +
            `</div>`;
  });
  list.innerHTML = html;
  list.querySelectorAll('.item').forEach(el => {
    if (el.getAttribute('data-disabled') === '1') return;
    el.addEventListener('click', () => {
      const name = el.getAttribute('data-name');
      const j = filtered.findIndex(x => x.name === name);
      if (j >= 0) show(j);
    });
  });
}
function applyFilter(){
  filtered = (minFilter === null) ? videos.slice() : videos.filter(v => (v.score||0) >= minFilter);
  const info = document.getElementById('filter_info');
  const label = (minFilter===null? 'No filter' : ('rating ≥ ' + minFilter));
  info.textContent = `${label} — showing ${filtered.length}/${videos.length}`;
}
function isVideoName(n){ return n.toLowerCase().endsWith('.mp4'); }
function isImageName(n){ const s=n.toLowerCase(); return s.endsWith('.png')||s.endsWith('.jpg')||s.endsWith('.jpeg'); }
function showMedia(url, name){
  const vtag = document.getElementById('player');
  const itag = document.getElementById('imgview');
  if (isVideoName(name)){
    itag.style.display = 'none'; itag.removeAttribute('src');
    vtag.style.display = ''; vtag.src = url + '#t=0.001';
  } else if (isImageName(name)){
    vtag.pause && vtag.pause(); vtag.removeAttribute('src'); vtag.load && vtag.load(); vtag.style.display='none';
    itag.style.display = ''; itag.src = url;
  } else {
    vtag.style.display='none'; vtag.removeAttribute('src');
    itag.style.display=''; itag.src = url;
  }
  const b1 = document.getElementById('extract_one'); const b2 = document.getElementById('extract_filtered');
  if (b1 && b2){ const enable = isVideoName(name); b1.disabled = !enable; b2.disabled = !enable; }
}
function show(i){
  if (filtered.length === 0){
    document.getElementById('filename').textContent = '(no items match filter)';
    const player = document.getElementById('player');
    player.removeAttribute('src'); player.load();
    renderScoreBar(0);
    updateDownloadButton(null);
    const controls = document.getElementById('pnginfo_controls'); if (controls) controls.style.display='none';
    const panel = document.getElementById('pnginfo_panel'); if (panel) panel.style.display='none';
    renderSidebar();
    return;
  }
  idx = Math.max(0, Math.min(i, filtered.length-1));
  const v = filtered[idx];
  showMedia(v.url, v.name);
  document.getElementById('filename').textContent = `${idx+1}/${filtered.length}  •  ${v.name}`;
  fetch('/api/meta/' + encodeURIComponent(v.name))
    .then(r => r.ok ? r.json() : null)
    .then(meta => {
      if (meta && meta.width && meta.height) {
        document.getElementById('filename').textContent += ` [${meta.width}x${meta.height}]`;
      }
      setupPngInfo(meta, v.name);
    }).catch(()=>{ setupPngInfo(null, v.name); });

  updateDownloadButton(v.name);
  renderScoreBar(v.score || 0);
  renderSidebar();
}
async function loadVideos(){
  const res = await fetch("/api/videos");
  const data = await res.json();
  videos = data.videos || [];
  currentDir = data.dir || "";
  currentPattern = data.pattern || currentPattern;
  document.getElementById('dir_display').textContent = currentDir + '  •  ' + currentPattern;
  const dirInput = document.getElementById('dir');
  if (dirInput && !dirInput.value) dirInput.value = currentDir;
  const patInput = document.getElementById('pattern');
  if (patInput && !patInput.value) patInput.value = currentPattern;
  applyFilter();
  renderSidebar();
  show(0);
}
async function postScore(score){
  const v = filtered[idx];
  if (!v) return;
  await fetch('/api/score', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ name: v.name, score: score })
  });
  const source = videos.find(x => x.name === v.name);
  if (source) source.score = score;
  v.score = score;
  const curName = v.name;
  applyFilter();
  const newIndex = filtered.findIndex(x => x.name === curName);
  if (newIndex >= 0) {
    show(newIndex);
  } else {
    show(idx);
  }
  renderSidebar();
  renderScoreBar(score);
}
async function postKey(key){
  const v = filtered[idx];
  await fetch("/api/key", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ key: key, name: v ? v.name : "" })
  });
}
async function scanDir(path){
  const pattern = (document.getElementById('pattern')?.value || '').trim();
  const res = await fetch("/api/scan", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ dir: path, pattern: pattern })
  });
  if (!res.ok){
    const t = await res.text();
    alert("Scan failed: " + t);
    return;
  }
  await loadVideos();
}
document.getElementById("pat_help").addEventListener("click", () => {
  alert("Glob syntax:\\n- Use * and ? wildcards (e.g., *.mp4, image??.png)\\n- Union with | (e.g., *.mp4|*.png|*.jpg)\\n- Examples:\\n  *.mp4\\n  image*.png\\n  *.mp4|*.png|*.jpg");
});
document.getElementById("load").addEventListener("click", () => {
  const path = (document.getElementById("dir").value || "").trim();
  if (path) scanDir(path);
});
document.getElementById('min_filter').addEventListener('change', () => {
  const val = document.getElementById('min_filter').value;
  minFilter = (val === 'none') ? null : parseInt(val);
  fetch('/api/key', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ key: 'Filter=' + (minFilter===null?'none':('>='+minFilter)), name: '' })});
  applyFilter(); renderSidebar(); show(0);
});
document.getElementById('dir').addEventListener('keydown', (e) => {
  if (e.key === "Enter"){
    const path = (document.getElementById("dir").value || "").trim();
    if (path) scanDir(path);
  }
});
document.getElementById('pattern').addEventListener('keydown', (e) => {
  if (e.key === "Enter"){
    const path = (document.getElementById("dir").value || "").trim();
    if (path) scanDir(path);
  }
});
document.getElementById('prev').addEventListener('click', () => { show(idx-1); });
document.getElementById('next').addEventListener('click', () => { show(idx+1); });
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
  function togglePlay(){ if (!player || player.style.display==='none') return; if (player.paused) { player.play(); } else { player.pause(); } }
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
async function extractCurrent(){
  if (!filtered.length) { alert("No item selected."); return; }
  const v = filtered[idx];
  if (!v.name.toLowerCase().endsWith('.mp4')){ alert('Extractor only works for .mp4'); return; }
  try{
    const res = await fetch("/api/extract", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ names: [v.name] })
    });
    const data = await res.json();
    const ok = (data.results||[]).filter(r=>r.status==="ok").length;
    const err = (data.results||[]).length - ok;
    postKey("ExtractOne");
    alert(`Extracted: ${ok} OK, ${err} errors`);
  }catch(e){
    alert("Extraction failed: " + e);
  }
}
async function extractFiltered(){
  if (!filtered.length) { alert("No items in current filter scope."); return; }
  const names = filtered.map(v => v.name).filter(n => n.toLowerCase().endsWith('.mp4'));
  if (!names.length){ alert('No .mp4 files in the current filtered view.'); return; }
  try{
    const res = await fetch("/api/extract", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ names })
    });
    const data = await res.json();
    const ok = (data.results||[]).filter(r=>r.status==="ok").length;
    const err = (data.results||[]).length - ok;
    postKey("ExtractFiltered");
    alert(`Extracted: ${ok} OK, ${err} errors`);
  }catch(e){
    alert("Bulk extraction failed: " + e);
  }
}
document.getElementById("extract_one").addEventListener("click", extractCurrent);
document.getElementById("extract_filtered").addEventListener("click", extractFiltered);
window.addEventListener("load", loadVideos);
</script>
</body>
</html>
"""

# ---------------------------
# CLI & Startup
# ---------------------------
def main():
    global VIDEO_DIR, FILE_LIST, FILE_PATTERN

    ap = argparse.ArgumentParser(description="Video/Image Scorer (FastAPI)")
    ap.add_argument("--dir", required=False, default=str(Path.cwd()), help="Directory with media files")
    ap.add_argument("--port", type=int, default=7862, help="Port to serve")
    ap.add_argument("--host", default="127.0.0.1", help="Host to bind")
    ap.add_argument("--pattern", default="*.mp4", help="Glob pattern, union with | (e.g., *.mp4|*.png|*.jpg)")
    args = ap.parse_args()

    start_dir = Path(args.dir).expanduser().resolve()
    if not start_dir.exists() or not start_dir.is_dir():
        raise SystemExit(f"Directory not found: {start_dir}")

    FILE_PATTERN = args.pattern or "*.mp4"
    switch_directory(start_dir, FILE_PATTERN)
    uvicorn.run(APP, host=args.host, port=args.port, log_level="info")

if __name__ == "__main__":
    main()
