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
import threading
import tempfile
import zipfile

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
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

# Mount static files to serve CSS and other assets
APP.mount("/static", StaticFiles(directory=Path(__file__).parent), name="static")
APP.mount("/themes", StaticFiles(directory=Path(__file__).parent / "themes"), name="themes")
VIDEO_DIR: Path = Path.cwd()
LOGGER: logging.Logger = logging.getLogger("video_scorer_fastapi")
FILE_LIST: List[Path] = []
FILE_PATTERN: str = "*.mp4"
STYLE_FILE: str = "style_default.css"
GENERATE_THUMBNAILS: bool = False
THUMBNAIL_HEIGHT: int = 64
TOGGLE_EXTENSIONS: List[str] = ["jpg", "png", "mp4"]
DIRECTORY_SORT_DESC: bool = True

# Thumbnail generation progress tracking
THUMBNAIL_PROGRESS = {
    "generating": False,
    "current": 0,
    "total": 0,
    "current_file": ""
}

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
    
    # Generate thumbnails if enabled (in background thread)
    if GENERATE_THUMBNAILS:
        # Start thumbnail generation in background thread
        thumbnail_thread = threading.Thread(
            target=generate_thumbnails_for_directory, 
            args=(VIDEO_DIR, FILE_LIST),
            daemon=True
        )
        thumbnail_thread.start()


# ---------------------------
# Thumbnail generation
# ---------------------------

def thumbnails_dir_for(directory: Path) -> Path:
    """Get thumbnails directory for a media directory"""
    thumb_dir = directory / ".thumbnails"
    thumb_dir.mkdir(exist_ok=True, parents=True)
    return thumb_dir

def thumbnail_path_for(media_path: Path) -> Path:
    """Get thumbnail path for a media file"""
    thumb_dir = thumbnails_dir_for(media_path.parent)
    return thumb_dir / f"{media_path.stem}_thumbnail.jpg"

def generate_thumbnail_for_image(image_path: Path, output_path: Path) -> bool:
    """Generate thumbnail for an image file"""
    try:
        if Image is None:
            LOGGER.warning("PIL not available, cannot generate image thumbnails")
            return False
        
        with Image.open(image_path) as img:
            # Calculate width to maintain aspect ratio
            aspect_ratio = img.width / img.height
            width = int(THUMBNAIL_HEIGHT * aspect_ratio)
            
            # Resize image
            img.thumbnail((width, THUMBNAIL_HEIGHT), Image.Resampling.LANCZOS)
            
            # Convert to RGB if needed (for RGBA images)
            if img.mode in ('RGBA', 'P'):
                rgb_img = Image.new('RGB', img.size, (255, 255, 255))
                rgb_img.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = rgb_img
            
            # Save as JPEG
            img.save(output_path, 'JPEG', quality=85, optimize=True)
            return True
    except Exception as e:
        LOGGER.error(f"Failed to generate thumbnail for {image_path}: {e}")
        return False

def generate_thumbnail_for_video(video_path: Path, output_path: Path) -> bool:
    """Generate thumbnail for a video file by extracting first frame"""
    try:
        # Use ffmpeg to extract first frame
        cmd = [
            "ffmpeg", "-y", "-i", str(video_path), 
            "-vf", f"scale=-1:{THUMBNAIL_HEIGHT}",
            "-vframes", "1", "-q:v", "2",
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            return True
        else:
            LOGGER.error(f"ffmpeg failed for {video_path}: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        LOGGER.error(f"ffmpeg timeout for {video_path}")
        return False
    except Exception as e:
        LOGGER.error(f"Failed to generate video thumbnail for {video_path}: {e}")
        return False

def generate_thumbnails_for_directory(directory: Path, file_list: List[Path]) -> None:
    """Generate thumbnails for all media files in the directory"""
    global THUMBNAIL_PROGRESS
    
    if not GENERATE_THUMBNAILS:
        return
    
    # Initialize progress tracking
    files_needing_thumbnails = []
    for media_file in file_list:
        thumb_path = thumbnail_path_for(media_file)
        if not thumb_path.exists():
            files_needing_thumbnails.append(media_file)
    
    total_files = len(files_needing_thumbnails)
    if total_files == 0:
        LOGGER.info("All thumbnails already exist, no generation needed")
        return
    
    THUMBNAIL_PROGRESS.update({
        "generating": True,
        "current": 0,
        "total": total_files,
        "current_file": ""
    })
    
    LOGGER.info(f"Generating thumbnails for {total_files} files...")
    generated = 0
    
    try:
        for i, media_file in enumerate(files_needing_thumbnails):
            # Update progress
            THUMBNAIL_PROGRESS.update({
                "current": i + 1,
                "current_file": media_file.name
            })
            
            thumb_path = thumbnail_path_for(media_file)
            
            # Generate thumbnail based on file type
            success = False
            name_lower = media_file.name.lower()
            if name_lower.endswith(('.png', '.jpg', '.jpeg')):
                success = generate_thumbnail_for_image(media_file, thumb_path)
            elif name_lower.endswith('.mp4'):
                success = generate_thumbnail_for_video(media_file, thumb_path)
            
            if success:
                generated += 1
                
    finally:
        # Reset progress tracking
        THUMBNAIL_PROGRESS.update({
            "generating": False,
            "current": 0,
            "total": 0,
            "current_file": ""
        })
        
    LOGGER.info(f"Thumbnail generation complete: {generated} generated, {len(file_list) - total_files} skipped")


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
    return HTMLResponse(CLIENT_HTML.replace('href="/themes/style_default.css"', f'href="/themes/{STYLE_FILE}"'))

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
    return {
        "dir": str(VIDEO_DIR), 
        "pattern": FILE_PATTERN, 
        "videos": items,
        "thumbnails_enabled": GENERATE_THUMBNAILS,
        "thumbnail_height": THUMBNAIL_HEIGHT,
        "toggle_extensions": TOGGLE_EXTENSIONS
    }

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

@APP.get("/api/thumbnail-progress")
def get_thumbnail_progress():
    """Get current thumbnail generation progress"""
    return THUMBNAIL_PROGRESS.copy()

@APP.get("/thumbnail/{name:path}")
def serve_thumbnail(name: str):
    """Serve thumbnail image for a media file"""
    if not GENERATE_THUMBNAILS:
        raise HTTPException(404, "Thumbnails not enabled")
    
    # Find the original media file
    target = (VIDEO_DIR / name).resolve()
    try:
        target.relative_to(VIDEO_DIR)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "Media file not found")
    
    # Get thumbnail path
    thumb_path = thumbnail_path_for(target)
    
    if not thumb_path.exists():
        # Try to generate thumbnail on demand
        name_lower = target.name.lower()
        if name_lower.endswith(('.png', '.jpg', '.jpeg')):
            generate_thumbnail_for_image(target, thumb_path)
        elif name_lower.endswith('.mp4'):
            generate_thumbnail_for_video(target, thumb_path)
    
    if not thumb_path.exists():
        raise HTTPException(404, "Thumbnail not available")
    
    return FileResponse(thumb_path, media_type="image/jpeg")

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

@APP.get("/api/directories")
async def api_directories(path: str = ""):
    """List directories in the given path, excluding dot folders"""
    try:
        if not path:
            target_path = VIDEO_DIR
        else:
            target_path = Path(path).expanduser().resolve()
        
        # Security check: ensure we're not accessing forbidden paths
        if not target_path.exists() or not target_path.is_dir():
            raise HTTPException(404, "Directory not found")
        
        directories = []
        for item in target_path.iterdir():
            if item.is_dir() and not item.name.startswith('.'):
                directories.append({
                    "name": item.name,
                    "path": str(item)
                })
        
        # Sort directories alphabetically
        directories.sort(key=lambda x: x["name"].lower(), reverse=DIRECTORY_SORT_DESC)
        
        return {"directories": directories, "current_path": str(target_path)}
    except Exception as e:
        raise HTTPException(500, f"Failed to list directories: {str(e)}")

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

@APP.post("/api/export-filtered")
async def api_export_filtered(req: Request):
    """Export all filtered files as a zip archive for download.
    JSON body: { "names": ["file1.mp4", "file2.png", ...] }
    """
    data = await req.json()
    names = data.get("names") or []
    if not isinstance(names, list):
        raise HTTPException(400, "names must be a list of filenames")
    
    if not names:
        raise HTTPException(400, "No files to export")
    
    # Create a temporary zip file
    temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
    temp_zip.close()
    
    try:
        with zipfile.ZipFile(temp_zip.name, 'w', zipfile.ZIP_DEFLATED) as zf:
            for name in names:
                file_path = (VIDEO_DIR / name).resolve()
                try:
                    file_path.relative_to(VIDEO_DIR)
                except Exception:
                    continue  # Skip forbidden paths
                
                if file_path.exists() and file_path.is_file():
                    # Add file to zip with just the filename (no path)
                    zf.write(file_path, name)
        
        # Return the zip file
        return FileResponse(
            temp_zip.name, 
            media_type="application/zip", 
            filename="filtered_media.zip",
            headers={"Content-Disposition": "attachment; filename=filtered_media.zip"}
        )
    except Exception as e:
        # Clean up temp file on error
        Path(temp_zip.name).unlink(missing_ok=True)
        raise HTTPException(500, f"Failed to create zip archive: {str(e)}")

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
  <link rel="stylesheet" href="/themes/style_default.css">
  <style>
    /* Simple spinner animation */
    .spinner {
      display: inline-block;
      width: 16px;
      height: 16px;
      vertical-align: middle;
      border: 2px solid #ccc;
      border-top: 2px solid #333;
      border-radius: 50%;
      animation: spin 0.7s linear infinite;
      margin-left: 6px;
    }
    @keyframes spin {
      to { transform: rotate(360deg); }
    }
    
    /* Toggle button styles */
    .toggle-container {
      display: flex;
      gap: 4px;
      align-items: center;
    }
    
    .toggle-btn {
      padding: 4px 8px;
      border: 1px solid #666;
      background: #333;
      color: #fff;
      border-radius: 4px;
      cursor: pointer;
      font-size: 11px;
      text-transform: uppercase;
      min-width: 35px;
      text-align: center;
      transition: all 0.2s ease;
    }
    
    .toggle-btn.active {
      background: #4CAF50;
      border-color: #45a049;
      color: white;
    }
    
    .toggle-btn.inactive {
      background: #555;
      border-color: #444;
      color: #999;
      opacity: 0.6;
    }
    
    .toggle-btn:hover {
      opacity: 0.8;
    }
    
    .refresh-btn {
      padding: 6px 8px;
      border: 1px solid #666;
      background: #333;
      color: #fff;
      border-radius: 4px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
    }
    
    .refresh-btn:hover {
      background: #444;
    }
    
    /* Collapsible toolbar styles */
    .toolbar-toggle {
      position: fixed;
      top: 8px;
      right: 8px;
      z-index: 1000;
      background: #333;
      color: #fff;
      border: 1px solid #666;
      border-radius: 4px;
      padding: 6px 8px;
      cursor: pointer;
      font-size: 12px;
      transition: all 0.2s ease;
    }
    
    .toolbar-toggle:hover {
      background: #444;
    }
    
    .toolbar-container {
      transition: all 0.3s ease;
      overflow: visible;
    }
    
    .toolbar-container.collapsed {
      max-height: 0;
      opacity: 0;
      margin: 0;
      padding: 0;
    }
    
    .toolbar-container.collapsed header {
      margin: 0;
      padding: 0;
    }
    
    .toolbar-container.collapsed .toolbar-rows {
      display: none;
    }
    
    /* Adjust body spacing when toolbar is collapsed */
    body.toolbar-collapsed main {
      padding-top: 8px;
      transition: padding-top 0.3s ease;
    }

    /* Directory navigation buttons */
    .nav-btn {
      background: #2f2f2f;
      color: #eee;
      border: 1px solid #666;
      padding: 8px;
      border-radius: 6px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      min-width: 32px;
      height: 32px;
    }
    .nav-btn:hover {
      background: #3a3a3a;
    }

    /* Directory dropdown */
    .dir-dropdown-container {
      position: relative;
    }
    .dropdown-menu {
      position: absolute;
      top: 100%;
      left: 0;
      background: #2f2f2f;
      border: 1px solid #666;
      border-radius: 6px;
      box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
      z-index: 1000;
      min-width: 200px;
      max-height: 300px;
      overflow-y: auto;
      margin-top: 2px;
    }
    .dropdown-item {
      padding: 8px 12px;
      cursor: pointer;
      color: #eee;
      border-bottom: 1px solid #444;
    }
    .dropdown-item:hover {
      background: #3a3a3a;
    }
    .dropdown-item:last-child {
      border-bottom: none;
    }
    .dropdown-empty {
      padding: 8px 12px;
      color: #999;
      font-style: italic;
    }
  </style>
</head>
<body>
  <button class="toolbar-toggle" id="toolbar-toggle" title="Toggle Toolbar">⌄</button>
  <div class="toolbar-container" id="toolbar-container">
    <header>
      <h1>🎬 Video/Image Scorer (FastAPI)</h1>
      <div class="pill">Keys: ←/→ navigate • Space play/pause (video) • 1–5 rate • R reject • C clear</div>
    </header>
    <div class="toolbar-rows">
      <div class="row">
        <button id="dir_up" class="nav-btn" title="Go up one directory">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M18 15l-6-6-6 6"/>
          </svg>
        </button>
        <div class="dir-dropdown-container">
          <button id="dir_browse" class="nav-btn" title="Browse directories">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
            </svg>
          </button>
          <div id="dir_dropdown" class="dropdown-menu" style="display: none;"></div>
        </div>
        <input id="dir" type="text" style="min-width:200px; flex:1;" placeholder="/path/to/folder"/>
        <div id="toggle_buttons" class="toggle-container"></div>
        <input id="pattern" type="text" style="min-width:180px" placeholder="glob pattern (e.g. *.mp4|*.png|*.jpg)" />
        <button id="pat_help" class="helpbtn">?</button>
        <button id="load" class="refresh-btn" title="Load/Refresh">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
            <path d="M21 3v5h-5"/>
            <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
            <path d="M3 21v-5h5"/>
          </svg>
        </button>
        <div id="dir_display" class="filename"></div>
      </div>
      <div class="row">
        <label for="min_filter">Rating ≥</label>
        <select id="min_filter">
          <option value="none" selected>No filter</option>
          <option value="unrated">Unrated</option>
          <option value="1">1</option>
          <option value="2">2</option>
          <option value="3">3</option>
          <option value="4">4</option>
          <option value="5">5</option>
        </select>
        <div id="filter_info" class="filename"></div>
        <div class="controls">
          <button id="prev">Prev</button>
          <button id="next">Next</button>
          <button id="reject">Reject</button>
          <button id="clear">Clear</button>
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
      </div>
    </div>
  </div>
  <main class="layout">
    <aside id="sidebar">
      <div id="sidebar_controls" style="display:none;">
        <div class="button-row">
          <button id="toggle_thumbnails" class="pill">Toggle Thumbnails</button>
          <button id="export_filtered_btn" class="pill" title="Export all filtered files as ZIP">
            <!-- ZIP folder icon SVG -->
            <svg width="16" height="12" viewBox="0 0 24 24" fill="none" style="margin-right: 2px;">
              <path d="M16 22H8C6.9 22 6 21.1 6 20V4C6 2.9 6.9 2 8 2H14L18 6V20C18 21.1 17.1 22 16 22Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M14 2V6H18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M10 12H14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
              <path d="M10 16H14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            Export Filtered
          </button>
        </div>
        <div style="margin-top: 4px;">
          <span id="progress_status" style="font-size: 12px; opacity: 0.8; display: none;"></span>
        </div>
      </div>
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
    </section>
  </main>
<script>
// Toolbar collapse functionality
let toolbarCollapsed = false;

function toggleToolbar() {
  const container = document.getElementById('toolbar-container');
  const toggleBtn = document.getElementById('toolbar-toggle');
  const body = document.body;
  
  toolbarCollapsed = !toolbarCollapsed;
  
  if (toolbarCollapsed) {
    container.classList.add('collapsed');
    body.classList.add('toolbar-collapsed');
    toggleBtn.textContent = '⌃';
    toggleBtn.title = 'Show Toolbar';
  } else {
    container.classList.remove('collapsed');
    body.classList.remove('toolbar-collapsed');
    toggleBtn.textContent = '⌄';
    toggleBtn.title = 'Hide Toolbar';
  }
}

// Add toolbar toggle event listener
document.addEventListener('DOMContentLoaded', function() {
  const toggleBtn = document.getElementById('toolbar-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', toggleToolbar);
  }
});

let videos = [];
let filtered = [];
let idx = 0;
let currentDir = "";
let currentPattern = "*.mp4";
let minFilter = null; // null means no filter; otherwise 1..5
let thumbnailsEnabled = false;
let thumbnailHeight = 64;
let showThumbnails = true; // user preference for showing thumbnails
let toggleExtensions = ["jpg", "png", "mp4"]; // configurable extensions for toggle buttons

// Thumbnail progress tracking
let thumbnailProgressInterval = null;

// Progress status management functions
function showProgress(message) {
  const statusElement = document.getElementById('progress_status');
  if (statusElement) {
    statusElement.style.display = 'inline';
    statusElement.innerHTML = `${message} <span class="spinner"></span>`;
  }
}

function hideProgress() {
  const statusElement = document.getElementById('progress_status');
  if (statusElement) {
    statusElement.style.display = 'none';
    statusElement.innerHTML = '';
  }
}

// Toggle button functionality
function initializeToggleButtons() {
  const container = document.getElementById('toggle_buttons');
  if (!container) return;
  
  container.innerHTML = '';
  
  toggleExtensions.forEach(ext => {
    const btn = document.createElement('button');
    btn.className = 'toggle-btn';
    btn.textContent = ext.toUpperCase();
    btn.dataset.extension = ext;
    btn.onclick = () => toggleExtension(ext);
    container.appendChild(btn);
  });
  
  // Update button states based on current pattern
  updateToggleButtonStates();
  
  // Add pattern input listener
  const patternInput = document.getElementById('pattern');
  if (patternInput) {
    patternInput.addEventListener('input', updateToggleButtonStates);
  }
}

function toggleExtension(extension) {
  const patternInput = document.getElementById('pattern');
  if (!patternInput) return;
  
  const currentPattern = patternInput.value.trim();
  const extPattern = `*.${extension}`;
  
  let newPattern;
  if (isExtensionInPattern(extension, currentPattern)) {
    // Remove the extension
    newPattern = removeExtensionFromPattern(extension, currentPattern);
  } else {
    // Add the extension
    newPattern = addExtensionToPattern(extension, currentPattern);
  }
  
  patternInput.value = newPattern;
  updateToggleButtonStates();
}

function isExtensionInPattern(extension, pattern) {
  const extPattern = `*.${extension}`;
  return pattern.split('|').some(part => part.trim() === extPattern);
}

function removeExtensionFromPattern(extension, pattern) {
  const extPattern = `*.${extension}`;
  const parts = pattern.split('|').map(p => p.trim()).filter(p => p !== extPattern);
  return parts.length > 0 ? parts.join('|') : '*.mp4';
}

function addExtensionToPattern(extension, pattern) {
  const extPattern = `*.${extension}`;
  if (!pattern.trim()) {
    return extPattern;
  }
  
  const parts = pattern.split('|').map(p => p.trim()).filter(p => p && p !== extPattern);
  parts.push(extPattern);
  return parts.join('|');
}

function updateToggleButtonStates() {
  const patternInput = document.getElementById('pattern');
  if (!patternInput) return;
  
  const currentPattern = patternInput.value.trim();
  
  toggleExtensions.forEach(ext => {
    const btn = document.querySelector(`[data-extension="${ext}"]`);
    if (btn) {
      if (isExtensionInPattern(ext, currentPattern)) {
        btn.className = 'toggle-btn active';
      } else {
        btn.className = 'toggle-btn inactive';
      }
    }
  });
}

function updateThumbnailStatus() {
  fetch('/api/thumbnail-progress')
    .then(r => r.json())
    .then(progress => {
      if (progress.generating && progress.total > 0) {
        showProgress(`Generating thumbnails (${progress.current}/${progress.total})`);
        // Start polling if not already started
        if (!thumbnailProgressInterval) {
          thumbnailProgressInterval = setInterval(updateThumbnailStatus, 500);
        }
      } else {
        hideProgress();
        // Stop polling when done
        if (thumbnailProgressInterval) {
          clearInterval(thumbnailProgressInterval);
          thumbnailProgressInterval = null;
        }
      }
    })
    .catch(() => {
      // Hide progress on error
      hideProgress();
      // Stop polling on error
      if (thumbnailProgressInterval) {
        clearInterval(thumbnailProgressInterval);
        thumbnailProgressInterval = null;
      }
    });
}

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
  if (e.target && e.target.id === 'pnginfo_btn'){ 
    togglePngInfo();   // <-- toggles open/close
  }
  if (e.target && e.target.id === 'pnginfo_copy'){ 
    const text = (document.getElementById('pnginfo_text').textContent)||'';
    if (!navigator.clipboard){ 
      const ta = document.createElement('textarea'); 
      ta.value = text; 
      document.body.appendChild(ta); 
      ta.select(); 
      document.execCommand('copy'); 
      document.body.removeChild(ta);
    } else {
      navigator.clipboard.writeText(text).catch(()=>{});
    }
  }
  if (e.target && e.target.id === 'toggle_thumbnails'){ 
    showThumbnails = !showThumbnails;
    renderSidebar();
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
  const circleFill = selected ? "var(--reject-fill-selected)" : "var(--reject-fill-unselected)";
  const xColor = selected ? "var(--reject-x-selected)" : "var(--reject-x-unselected)";
  const r = 16, cx=20, cy=20;
  return `
<svg width="40" height="40" viewBox="0 0 40 40">
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="${circleFill}" stroke="var(--reject-stroke-color)" stroke-width="2" />
  <line x1="${cx-10}" y1="${cy-10}" x2="${cx+10}" y2="${cy+10}" stroke="${xColor}" stroke-width="4" stroke-linecap="round" />
  <line x1="${cx-10}" y1="${cy+10}" x2="${cx+10}" y2="${cy-10}" stroke="${xColor}" stroke-width="4" stroke-linecap="round" />
</svg>`;
}
function svgStar(filled){
  const fill = filled ? "var(--star-fill-selected)" : "var(--star-fill-unselected)";
  return `
<svg width="40" height="40" viewBox="0 0 40 40">
  <polygon points="20,4 24,16 36,16 26,24 30,36 20,28 10,36 14,24 4,16 16,16"
    fill="${fill}" stroke="var(--star-stroke-color)" stroke-width="2"/>
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
    
    let thumbHtml = '';
    if (thumbnailsEnabled && showThumbnails) {
      thumbHtml = `<div class="thumbnail"><img src="/thumbnail/${encodeURIComponent(v.name)}" alt="" style="height:${thumbnailHeight}px" onerror="this.style.display='none'"></div>`;
      classes.push('with-thumbnails');
    }
    
    html += `<div class="${classes.join(' ')}" data-name="${v.name}" ${inFiltered ? '' : 'data-disabled="1"'}>` +
            thumbHtml +
            `<div class="content">` +
            `<div class="name" title="${v.name}">${v.name}</div>` +
            `<div class="score">${s}</div>` +
            `</div>` +
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
  if (minFilter === null) {
    filtered = videos.slice();
  } else if (minFilter === 'unrated') {
    filtered = videos.filter(v => !v.score || v.score === 0);
  } else {
    filtered = videos.filter(v => (v.score||0) >= minFilter);
  }
  const info = document.getElementById('filter_info');
  let label;
  if (minFilter === null) {
    label = 'No filter';
  } else if (minFilter === 'unrated') {
    label = 'Unrated only';
  } else {
    label = 'rating ≥ ' + minFilter;
  }
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
  thumbnailsEnabled = data.thumbnails_enabled || false;
  thumbnailHeight = data.thumbnail_height || 64;
  toggleExtensions = data.toggle_extensions || ["jpg", "png", "mp4"];
  
  document.getElementById('dir_display').textContent = currentDir + '  •  ' + currentPattern;
  const dirInput = document.getElementById('dir');
  if (dirInput && !dirInput.value) dirInput.value = currentDir;
  const patInput = document.getElementById('pattern');
  if (patInput && !patInput.value) patInput.value = currentPattern;
  
  // Initialize toggle buttons
  initializeToggleButtons();
  
  // Show/hide thumbnail controls
  const sidebarControls = document.getElementById('sidebar_controls');
  if (sidebarControls) {
    sidebarControls.style.display = thumbnailsEnabled ? 'block' : 'none';
  }
  
  // Start monitoring thumbnail progress if thumbnails are enabled
  if (thumbnailsEnabled) {
    updateThumbnailStatus();
  }
  
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
  if (path) {
    // Start monitoring thumbnail progress immediately if thumbnails are enabled
    if (thumbnailsEnabled) {
      updateThumbnailStatus();
    }
    scanDir(path);
  }
});
document.getElementById('min_filter').addEventListener('change', () => {
  const val = document.getElementById('min_filter').value;
  if (val === 'none') {
    minFilter = null;
  } else if (val === 'unrated') {
    minFilter = 'unrated';
  } else {
    minFilter = parseInt(val);
  }
  fetch('/api/key', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ key: 'Filter=' + (minFilter===null?'none':(minFilter==='unrated'?'unrated':('>='+minFilter))), name: '' })});
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

// Directory navigation functions
async function goUpDirectory() {
  const dirInput = document.getElementById('dir');
  const currentPath = dirInput.value.trim();
  if (!currentPath) return;
  
  const path = new Path(currentPath);
  const parentPath = path.parent;
  if (parentPath && parentPath !== currentPath) {
    dirInput.value = parentPath;
    // Optionally trigger scan immediately
    // scanDir(parentPath);
  }
}

async function loadDirectories(basePath) {
  try {
    const response = await fetch(`/api/directories?path=${encodeURIComponent(basePath)}`);
    if (!response.ok) {
      throw new Error(`Failed to load directories: ${response.statusText}`);
    }
    const data = await response.json();
    return data.directories;
  } catch (error) {
    console.error('Error loading directories:', error);
    return [];
  }
}

function showDirectoryDropdown() {
  const dirInput = document.getElementById('dir');
  const dropdown = document.getElementById('dir_dropdown');
  const currentPath = dirInput.value.trim() || './';
  
  // Clear existing dropdown content
  dropdown.innerHTML = '<div class="dropdown-item" style="opacity: 0.6;">Loading...</div>';
  dropdown.style.display = 'block';
  
  loadDirectories(currentPath).then(directories => {
    dropdown.innerHTML = '';
    
    if (directories.length === 0) {
      dropdown.innerHTML = '<div class="dropdown-empty">No directories found</div>';
    } else {
      directories.forEach(dir => {
        const item = document.createElement('div');
        item.className = 'dropdown-item';
        item.textContent = dir.name;
        item.title = dir.path;
        item.addEventListener('click', () => {
          const currentValue = dirInput.value.trim();
          let newPath;
          if (currentValue.endsWith('/')) {
            newPath = currentValue + dir.name;
          } else {
            newPath = currentValue + '/' + dir.name;
          }
          dirInput.value = newPath;
          hideDirectoryDropdown();
        });
        dropdown.appendChild(item);
      });
    }
  }).catch(error => {
    dropdown.innerHTML = '<div class="dropdown-empty">Error loading directories</div>';
  });
}

function hideDirectoryDropdown() {
  const dropdown = document.getElementById('dir_dropdown');
  dropdown.style.display = 'none';
}

// Simple Path utility for JavaScript (since we don't have Node.js path module)
class Path {
  constructor(pathStr) {
    this.path = pathStr.replace(/\\/g, '/'); // Normalize to forward slashes
  }
  
  get parent() {
    const normalizedPath = this.path.replace(/\/+$/, ''); // Remove trailing slashes
    const lastSlash = normalizedPath.lastIndexOf('/');
    if (lastSlash <= 0) return '/';
    return normalizedPath.substring(0, lastSlash);
  }
}

// Add event listeners for directory navigation
document.getElementById('dir_up').addEventListener('click', goUpDirectory);
document.getElementById('dir_browse').addEventListener('click', showDirectoryDropdown);

// Hide dropdown when clicking outside
document.addEventListener('click', (e) => {
  const dropdownContainer = document.querySelector('.dir-dropdown-container');
  const dropdown = document.getElementById('dir_dropdown');
  
  if (!dropdownContainer.contains(e.target)) {
    hideDirectoryDropdown();
  }
});

document.getElementById('prev').addEventListener('click', () => { show(idx-1); });
document.getElementById('next').addEventListener('click', () => { show(idx+1); });
document.getElementById("reject").addEventListener("click", () => { postScore(-1); });
document.getElementById("clear").addEventListener("click", () => { postScore(0); });
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
  if (e.key === "c" || e.key === "C"){ e.preventDefault(); postKey("C"); postScore(0); return; }
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
async function exportFiltered(){
  if (!filtered.length) { alert("No items in current filter scope."); return; }
  const names = filtered.map(v => v.name);
  if (!names.length){ alert('No files in the current filtered view.'); return; }
  
  // Show progress
  showProgress('Exporting...');
  
  try{
    const res = await fetch("/api/export-filtered", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ names })
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    // Create a blob from the response and trigger download
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = 'media.zip';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    postKey("ExportFiltered");
  }catch(e){
    alert("Export failed: " + e);
  } finally {
    // Hide progress
    hideProgress();
  }
}
document.getElementById("extract_one").addEventListener("click", extractCurrent);
document.getElementById("extract_filtered").addEventListener("click", extractFiltered);
document.getElementById("export_filtered_btn").addEventListener("click", exportFiltered);
window.addEventListener("load", loadVideos);
</script>
</body>
</html>
"""

# ---------------------------
# CLI & Startup
# ---------------------------
def main():
    global VIDEO_DIR, FILE_LIST, FILE_PATTERN, STYLE_FILE, GENERATE_THUMBNAILS, THUMBNAIL_HEIGHT, TOGGLE_EXTENSIONS, DIRECTORY_SORT_DESC

    # Load config from file first
    config_file = Path("config.yml")
    if config_file.exists():
        try:
            import yaml
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            # Apply config defaults to global variables
            global_dir = cfg.get('dir', str(Path.cwd()))
            global_pattern = cfg.get('pattern', '*.mp4')
            global_style = cfg.get('style', 'style_default.css')
            global_thumbnails = bool(cfg.get('generate_thumbnails', False))
            global_thumb_height = int(cfg.get('thumbnail_height', 64))
            global_toggle_ext = cfg.get('toggle_extensions', ['jpg', 'png', 'mp4'])
            DIRECTORY_SORT_DESC = bool(cfg.get('directory_sort_desc', True))
        except Exception as e:
            print(f"Warning: Could not load config.yml: {e}", file=sys.stderr)
            global_dir = str(Path.cwd())
            global_pattern = '*.mp4'
            global_style = 'style_default.css'
            global_thumbnails = False
            global_thumb_height = 64
            global_toggle_ext = ['jpg', 'png', 'mp4']
    else:
        global_dir = str(Path.cwd())
        global_pattern = '*.mp4'
        global_style = 'style_default.css'
        global_thumbnails = False
        global_thumb_height = 64
        global_toggle_ext = ['jpg', 'png', 'mp4']

    ap = argparse.ArgumentParser(description="Video/Image Scorer (FastAPI)")
    ap.add_argument("--dir", required=False, default=global_dir, help="Directory with media files")
    ap.add_argument("--port", type=int, default=7862, help="Port to serve")
    ap.add_argument("--host", default="127.0.0.1", help="Host to bind")
    ap.add_argument("--pattern", default=global_pattern, help="Glob pattern, union with | (e.g., *.mp4|*.png|*.jpg)")
    ap.add_argument("--style", default=global_style, help="CSS style file from themes folder (e.g., style_default.css, style_pastelcore.css, style_darkpastelcore.css, or style_darkcandy.css)")
    ap.add_argument("--generate-thumbnails", action="store_true", default=global_thumbnails, help="Generate thumbnail previews for media files")
    ap.add_argument("--thumbnail-height", type=int, default=global_thumb_height, help="Height in pixels for thumbnail previews")
    ap.add_argument("--toggle-extensions", nargs='*', default=global_toggle_ext, help="File extensions for toggle buttons")
    ap.add_argument("--directory-sort-desc", action="store_true", help="Sort directory dropdown in descending order")
    ap.add_argument("--directory-sort-asc", action="store_true", help="Sort directory dropdown in ascending order")
    args = ap.parse_args()

    start_dir = Path(args.dir).expanduser().resolve()
    if not start_dir.exists() or not start_dir.is_dir():
        raise SystemExit(f"Directory not found: {start_dir}")

    FILE_PATTERN = args.pattern or "*.mp4"
    STYLE_FILE = args.style or "style_default.css"
    GENERATE_THUMBNAILS = args.generate_thumbnails
    THUMBNAIL_HEIGHT = args.thumbnail_height
    TOGGLE_EXTENSIONS = args.toggle_extensions or ["jpg", "png", "mp4"]
    # Handle directory sort direction - CLI args can override config default
    if args.directory_sort_asc:
        DIRECTORY_SORT_DESC = False
    elif args.directory_sort_desc:
        DIRECTORY_SORT_DESC = True
    # If neither CLI arg is specified, DIRECTORY_SORT_DESC keeps its global default (set from config or True)
    switch_directory(start_dir, FILE_PATTERN)
    uvicorn.run(APP, host=args.host, port=args.port, log_level="info")

if __name__ == "__main__":
    main()
