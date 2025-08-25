#!/usr/bin/env python3
"""
Gradio Video Scorer
- Browse a directory of .mp4 files
- Navigate with buttons or keyboard:
    • Left/Right Arrow: previous/next video
    • Keys 1..5: set 1..5 stars
    • Key R: mark Reject
- Scores are saved to sidecar JSON files in a ".scores" folder beside the videos.

Score legend (rendered below the video):
- Leftmost icon: "Reject" (X in a circle). Default: white X on black circle. If selected (reject), inverts: black X on white circle.
- Five stars to the right: Filled (white) up to the selected rating, otherwise black fill. All icons have white outlines.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

import gradio as gr
import logging

LOGGER = None
CURRENT_DIR = None

def _get_logger(directory: Path):
    global LOGGER, CURRENT_DIR
    if directory is None:
        directory = Path.cwd()
    if LOGGER is not None and CURRENT_DIR == str(directory):
        return LOGGER
    LOGGER = logging.getLogger('video_scorer')
    LOGGER.setLevel(logging.DEBUG)
    # Clear prior handlers
    for h in list(LOGGER.handlers):
        LOGGER.removeHandler(h)
    log_dir = directory / '.scores' / '.log'
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_dir / 'video_scorer.log', encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(message)s'))
    LOGGER.addHandler(fh)
    CURRENT_DIR = str(directory)
    LOGGER.debug(f'Logger initialized for directory: {CURRENT_DIR}')
    return LOGGER

# ------------------------------
# Helpers for file & score I/O
# ------------------------------

def discover_videos(directory: Path) -> List[Path]:
    exts = {".mp4"}
    files = [p for p in sorted(directory.glob("*.mp4")) if p.suffix.lower() in exts]
    return files

def scores_dir_for(directory: Path) -> Path:
    sdir = directory / ".scores"
    sdir.mkdir(exist_ok=True, parents=True)
    return sdir

def sidecar_path_for(video_path: Path) -> Path:
    # Sidecar lives in <dir>/.scores/<filename>.json
    sdir = scores_dir_for(video_path.parent)
    return sdir / f"{video_path.name}.json"

def read_score_for(video_path: Path) -> Optional[int]:
    """Return score int: -1 (reject) or 0 (unset) or 1..5. None if no record."""
    sc = sidecar_path_for(video_path)
    if not sc.exists():
        return None
    try:
        data = json.loads(sc.read_text(encoding="utf-8"))
        val = int(data.get("score", 0))
        # clamp
        if val < -1 or val > 5: 
            return 0
        return val
    except Exception:
        return None

def write_score_for(video_path: Path, score: int) -> None:
    sc = sidecar_path_for(video_path)
    payload = {
        "file": str(video_path.name),
        "score": int(score),
        "updated": dt.datetime.now().isoformat(timespec="seconds"),
    }
    sc.write_text(json.dumps(payload, indent=2), encoding="utf-8")


# ------------------------------
# SVG Badge Rendering
# ------------------------------

def _svg_star(cx: float, cy: float, r: float, filled: bool) -> str:
    """Return an SVG path for a 5-point star centered at (cx, cy)."""
    # Simple parametric star (10 points alternating outer/inner radius)
    import math
    points = []
    outer = r
    inner = r * 0.5
    for i in range(10):
        angle = math.pi/2 + i * (math.pi / 5)  # start pointing up
        rad = outer if i % 2 == 0 else inner
        x = cx + rad * math.cos(angle)
        y = cy - rad * math.sin(angle)
        points.append(f"{x:.2f},{y:.2f}")
    fill = "white" if filled else "black"
    return f'<polygon points="{" ".join(points)}" fill="{fill}" stroke="white" stroke-width="2" />'

def _svg_reject(cx: float, cy: float, r: float, selected: bool) -> str:
    """
    X in a circle.
    - Default (not selected): white X in a circle with black fill and white outline
    - Selected (reject): black X in a white circle with a white outline
    """
    circle_fill = "white" if selected else "black"
    x_color = "black" if selected else "white"
    parts = []
    parts.append(f'<circle cx="{cx}" cy="{cy}" r="{r}" fill="{circle_fill}" stroke="white" stroke-width="2" />')
    # X lines
    arm = r * 0.6
    parts.append(f'<line x1="{cx-arm}" y1="{cy-arm}" x2="{cx+arm}" y2="{cy+arm}" stroke="{x_color}" stroke-width="4" stroke-linecap="round" />')
    parts.append(f'<line x1="{cx-arm}" y1="{cy+arm}" x2="{cx+arm}" y2="{cy-arm}" stroke="{x_color}" stroke-width="4" stroke-linecap="round" />')
    return "".join(parts)

def render_score_svg(score: int) -> str:
    """
    score: -1 (reject), 0 (none), 1..5 stars
    Layout: [Reject badge][star x5], left to right
    """
    width = 520
    height = 80
    padding = 12
    icon_size = 28
    gap = 12

    svg_parts = [f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg" style="background:#222;border-radius:10px">']
    # Title overlay
    svg_parts.append('<text x="12" y="18" fill="white" font-size="12" font-family="monospace">Score: '
                     + ('Reject' if score == -1 else (str(score) if score > 0 else '—'))
                     + '</text>')

    x = padding + icon_size
    y = height/2 + 8

    # Reject icon
    selected_reject = (score == -1)
    svg_parts.append(_svg_reject(x, y-8, icon_size, selected_reject))
    x += icon_size*2 + gap

    # Stars
    selected_stars = max(0, score) if score != -1 else 0
    for i in range(5):
        filled = i < selected_stars
        svg_parts.append(_svg_star(x, y-8, icon_size*0.9, filled))
        x += icon_size*2 - 2  # overlap tweak

    svg_parts.append("</svg>")
    return "".join(svg_parts)


# ------------------------------
# Core Logic for Gradio
# ------------------------------

def _safe_index(idx: int, n: int) -> int:
    if n == 0:
        return 0
    return max(0, min(idx, n-1))

def present_video(files: List[str], idx: int, scores: Dict[str,int]) -> Tuple[str, str, str, str]:
    """Return (video_path, filename, score_str, svg_html) for display."""
    if not files:
        return "", "(no files)", "Score: —", render_score_svg(0)
    idx = _safe_index(idx, len(files))
    path = files[idx]
    sc = scores.get(path, read_score_for(Path(path)) or 0)
    svg = render_score_svg(sc if sc is not None else 0)
    score_label = "Reject" if sc == -1 else (str(sc) if sc and sc > 0 else "—")
    try:
        log = _get_logger(Path(path).parent)
        log.debug(f'PRESENT index={idx} file={Path(path).name} score={score_label}')
    except Exception:
        pass
    return path, Path(path).name, f"Score: {score_label}", svg

def load_directory(dir_text: str, st_files, st_index, st_scores):
    directory = Path(dir_text).expanduser().resolve()
    log = _get_logger(directory)
    log.info(f'LOAD directory: {directory}')
    if not directory.exists() or not directory.is_dir():
        return gr.update(value=""), "(no files)", "Score: —", render_score_svg(0), [], 0, {}
    vids = [str(p) for p in discover_videos(directory)]
    log.info(f'Discovered {len(vids)} videos')
    # preload known scores
    scmap: Dict[str,int] = {}
    for p in vids:
        s = read_score_for(Path(p))
        if s is not None:
            scmap[p] = s
    vid, name, score_str, svg = present_video(vids, 0, scmap)
    return vid, name, score_str, svg, vids, 0, scmap

def nav_prev(st_files, st_index, st_scores):
    if not st_files:
        return present_video([], 0, {})
    idx = _safe_index(st_index - 1, len(st_files))
    log = _get_logger(Path(st_files[0]).parent if st_files else Path.cwd())
    log.info(f'NAV prev -> index {idx}')
    return present_video(st_files, idx, st_scores) + (idx,)

def nav_next(st_files, st_index, st_scores):
    if not st_files:
        return present_video([], 0, {})
    idx = _safe_index(st_index + 1, len(st_files))
    log = _get_logger(Path(st_files[0]).parent if st_files else Path.cwd())
    log.info(f'NAV next -> index {idx}')
    return present_video(st_files, idx, st_scores) + (idx,)

def set_reject(st_files, st_index, st_scores):
    if not st_files:
        return present_video([], 0, {})
    idx = _safe_index(st_index, len(st_files))
    path = Path(st_files[idx])
    log = _get_logger(path.parent)
    log.info(f'SET reject: {path.name}')
    write_score_for(path, -1)
    st_scores[st_files[idx]] = -1
    return present_video(st_files, idx, st_scores)

def set_stars(n: int, st_files, st_index, st_scores):
    if not st_files:
        return present_video([], 0, {})
    idx = _safe_index(st_index, len(st_files))
    path = Path(st_files[idx])
    log = _get_logger(path.parent)
    log.info(f'SET stars={n}: {path.name}')
    write_score_for(path, n)
    st_scores[st_files[idx]] = n
    return present_video(st_files, idx, st_scores)


def log_keystroke(payload: str, st_files, st_index):
    """payload is a JSON string like {"key":"1","ts":"..."}"""
    try:
        data = json.loads(payload) if payload else {}
    except Exception:
        data = {"raw": payload}
    # Determine directory for logger
    directory = Path(st_files[0]).parent if st_files else Path.cwd()
    log = _get_logger(directory)
    # Resolve current file name if any
    fname = Path(st_files[_safe_index(st_index, len(st_files))]).name if st_files else "(none)"
    log.info(f"KEY key={data.get('key')} ts={data.get('ts')} file={fname}")
    # return something to keep gradio happy
    return payload


def launch(initial_dir: Optional[str] = None, server_name: Optional[str] = None, server_port: Optional[int] = None):
    with gr.Blocks(css="""
    .vid-scorer .controls-row button { font-weight: 600; }
    .vid-scorer .filename { font-family: monospace; }
    """, analytics_enabled=False) as demo:
        gr.Markdown("# 🎬 Video Scorer (Gradio)\nUse Arrow keys ←/→ to navigate • 1–5 to rate • R to reject")

        with gr.Row():
            dir_text = gr.Textbox(label="Directory of MP4 files", value=initial_dir or str(Path.cwd()), scale=4, placeholder="/path/to/folder")
            load_btn = gr.Button("Load")
        with gr.Row():
            video = gr.Video(label="Video", interactive=False, height=420)
        with gr.Row():
            filename = gr.Markdown(" ", elem_classes=["filename"])
        with gr.Row():
            svg_html = gr.HTML(render_score_svg(0))


        # Hidden keystroke reporting
        keystream = gr.Textbox(value="", visible=False, elem_id="keystream", label="keystream")
        keystream_sink = gr.Textbox(value="", visible=False, elem_id="keystream_sink")

        with gr.Row(elem_classes=["controls-row"]):
            prev_btn = gr.Button("← Prev", elem_id="btn_prev")
            next_btn = gr.Button("Next →", elem_id="btn_next")
            reject_btn = gr.Button("Reject (R)", variant="stop", elem_id="btn_reject")
            star1_btn = gr.Button("★1", elem_id="btn_star1")
            star2_btn = gr.Button("★2", elem_id="btn_star2")
            star3_btn = gr.Button("★3", elem_id="btn_star3")
            star4_btn = gr.Button("★4", elem_id="btn_star4")
            star5_btn = gr.Button("★5", elem_id="btn_star5")

        # States
        st_files = gr.State([])       # List[str]
        st_index = gr.State(0)        # int
        st_scores = gr.State({})      # Dict[str,int]

        # Wiring
        load_btn.click(
            load_directory,
            inputs=[dir_text, st_files, st_index, st_scores],
            outputs=[video, filename, gr.Textbox(visible=False), svg_html, st_files, st_index, st_scores],  # we don't show the score label textbox
        )

        # On load, auto-load current dir
        demo.load(
            load_directory,
            inputs=[dir_text, st_files, st_index, st_scores],
            outputs=[video, filename, gr.Textbox(visible=False), svg_html, st_files, st_index, st_scores],
        )

        # Navigation
        prev_btn.click(
            nav_prev, inputs=[st_files, st_index, st_scores],
            outputs=[video, filename, gr.Textbox(visible=False), svg_html, st_index]
        )
        next_btn.click(
            nav_next, inputs=[st_files, st_index, st_scores],
            outputs=[video, filename, gr.Textbox(visible=False), svg_html, st_index]
        )

        # Keystroke logging
        keystream.change(log_keystroke, inputs=[keystream, st_files, st_index], outputs=[keystream_sink])

        # Scoring
        reject_btn.click(
            set_reject, inputs=[st_files, st_index, st_scores],
            outputs=[video, filename, gr.Textbox(visible=False), svg_html]
        )
        star1_btn.click(lambda *s: set_stars(1, *s), inputs=[st_files, st_index, st_scores],
                        outputs=[video, filename, gr.Textbox(visible=False), svg_html])
        star2_btn.click(lambda *s: set_stars(2, *s), inputs=[st_files, st_index, st_scores],
                        outputs=[video, filename, gr.Textbox(visible=False), svg_html])
        star3_btn.click(lambda *s: set_stars(3, *s), inputs=[st_files, st_index, st_scores],
                        outputs=[video, filename, gr.Textbox(visible=False), svg_html])
        star4_btn.click(lambda *s: set_stars(4, *s), inputs=[st_files, st_index, st_scores],
                        outputs=[video, filename, gr.Textbox(visible=False), svg_html])
        star5_btn.click(lambda *s: set_stars(5, *s), inputs=[st_files, st_index, st_scores],
                        outputs=[video, filename, gr.Textbox(visible=False), svg_html])

        # Inject small JS to bind keyboard shortcuts to buttons by elem_id.
        gr.HTML(
            """


<script>
(function(){
  function clickInside(id){
    const host = document.getElementById(id);
    if (!host) return;
    const btn = host.querySelector('button') || host;
    btn.click();
  }
  function sendKeyLog(key){
    const host = document.getElementById('keystream');
    if (!host) return;
    const ta = host.querySelector('textarea');
    if (!ta) return;
    const payload = JSON.stringify({ key: key, ts: new Date().toISOString() });
    ta.value = payload;
    ta.dispatchEvent(new Event('input', { bubbles: true }));
  }
  document.addEventListener('keydown', function(e){
    const tag = (e.target && e.target.tagName || '').toLowerCase();
    if (tag === 'input' || tag === 'textarea') return;
    if (e.key === 'ArrowLeft')  { e.preventDefault(); sendKeyLog('ArrowLeft');  clickInside('btn_prev'); return; }
    if (e.key === 'ArrowRight') { e.preventDefault(); sendKeyLog('ArrowRight'); clickInside('btn_next'); return; }
    if (e.key === '1') { e.preventDefault(); sendKeyLog('1'); clickInside('btn_star1'); return; }
    if (e.key === '2') { e.preventDefault(); sendKeyLog('2'); clickInside('btn_star2'); return; }
    if (e.key === '3') { e.preventDefault(); sendKeyLog('3'); clickInside('btn_star3'); return; }
    if (e.key === '4') { e.preventDefault(); sendKeyLog('4'); clickInside('btn_star4'); return; }
    if (e.key === '5') { e.preventDefault(); sendKeyLog('5'); clickInside('btn_star5'); return; }
    if (e.key === 'r' || e.key === 'R') { e.preventDefault(); sendKeyLog('R'); clickInside('btn_reject'); return; }
  }, { passive:false });
})();
</script>


            """
        )

    demo.queue()
    demo.launch(
    server_name=server_name or "0.0.0.0",
    server_port=server_port,
    allowed_paths=[str(Path(initial_dir).resolve()), "/mnt/qnap-sd"]
)

def main():
    ap = argparse.ArgumentParser(description="Gradio Video Scorer")
    ap.add_argument("--dir", dest="directory", default=str(Path.cwd()), help="Initial directory containing .mp4 files")
    ap.add_argument("--host", dest="host", default="0.0.0.0", help="Server host (default 0.0.0.0)")
    ap.add_argument("--port", dest="port", type=int, default=7860, help="Server port (default 7860)")
    args = ap.parse_args()
    launch(initial_dir=args.directory, server_name=args.host, server_port=args.port)

if __name__ == "__main__":
    main()
