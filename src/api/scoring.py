"""Scoring API endpoints"""
from fastapi import APIRouter, HTTPException, Request
from pathlib import Path

from ..core.state import state
from ..core.scoring import write_score

router = APIRouter()


@router.post("/api/score")
async def api_score(req: Request):
    """Update score for a media file"""
    data = await req.json()
    name = str(data.get("name", ""))
    score = int(data.get("score", 0))
    
    if not name:
        raise HTTPException(400, "name required")
    
    media_path = (state.video_dir / name).resolve()
    try:
        media_path.relative_to(state.video_dir)
    except ValueError:
        raise HTTPException(404, "File not found")
    
    if not media_path.exists():
        raise HTTPException(404, "File not found")
    
    write_score(media_path, score)
    if state.logger:
        state.logger.info(f"SCORE file={name} score={score}")
    
    return {"ok": True}


@router.post("/api/key")
async def api_key(req: Request):
    """Log key press events"""
    data = await req.json()
    key = str(data.get("key"))
    fname = str(data.get("name"))
    if state.logger:
        state.logger.info(f"KEY key={key} file={fname}")
    return {"ok": True}