"""Root-level routes for media serving, downloads, and thumbnails."""

from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from ..state import get_state
from ..services.thumbnails import (
    get_thumbnail_path_for, 
    generate_thumbnail_for_image, 
    generate_thumbnail_for_video
)

try:
    from PIL import Image
except ImportError:
    Image = None


router = APIRouter()


@router.get("/maximize/{name:path}")
def maximize_media(name: str):
    """Serve maximized media view for mobile devices."""
    state = get_state()
    target = (state.video_dir / name).resolve()
    
    # Security: ensure the resolved path is within video directory
    try:
        target.relative_to(state.video_dir)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
    
    # Determine if it's a video or image
    ext = target.suffix.lower()
    is_video = ext == ".mp4"
    media_url = f"/media/{name}"
    
    # Generate HTML for maximized view
    html_content = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Maximized View - {name}</title>
    <style>
        body {{ 
            margin: 0; 
            padding: 0; 
            background: #000; 
            display: flex; 
            flex-direction: column; 
            height: 100vh; 
            font-family: system-ui, sans-serif; 
        }}
        .close-btn {{ 
            position: fixed; 
            top: 16px; 
            right: 16px; 
            width: 44px; 
            height: 44px; 
            background: rgba(0,0,0,0.7); 
            color: white; 
            border: 2px solid #fff; 
            border-radius: 50%; 
            font-size: 24px; 
            font-weight: bold; 
            cursor: pointer; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            z-index: 1000;
            text-decoration: none;
        }}
        .close-btn:hover {{ background: rgba(255,255,255,0.2); }}
        .media-container {{ 
            flex: 1; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            padding: 16px; 
            box-sizing: border-box; 
        }}
        video, img {{ 
            max-width: 100%; 
            max-height: 100%; 
            object-fit: contain; 
        }}
    </style>
</head>
<body>
    <a href="javascript:window.close(); history.back();" class="close-btn" title="Close" onclick="if(window.history.length > 1) history.back(); else window.close();">&times;</a>
    <div class="media-container">
        {'<video controls autoplay><source src="' + media_url + '" type="video/mp4"></video>' if is_video else '<img src="' + media_url + '" alt="' + name + '">'}
    </div>
</body>
</html>"""
    
    return HTMLResponse(content=html_content)


@router.get("/media/{name:path}")
def serve_media(name: str):
    """Serve media files."""
    state = get_state()
    
    # Try database first if enabled
    if state.database_enabled:
        try:
            with state.get_database_service() as db:
                # Find the media file by filename in database
                from ..database.models import MediaFile
                media_file = db.session.query(MediaFile).filter(
                    MediaFile.filename == name
                ).first()
                
                if media_file:
                    target = Path(media_file.file_path).resolve()
                    if target.exists() and target.is_file():
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
        except Exception as e:
            state.logger.error(f"Database media serving failed: {e}")
    
    # Fallback to original behavior - serve from current video directory
    target = (state.video_dir / name).resolve()
    
    # Security: ensure the resolved path is within video directory
    try:
        target.relative_to(state.video_dir)
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


@router.get("/download/{name:path}")
def download_media(name: str):
    """Download a media file."""
    state = get_state()
    target = (state.video_dir / name).resolve()
    
    try:
        target.relative_to(state.video_dir)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "File not found")
    
    # Force download via Content-Disposition
    return FileResponse(target, media_type="application/octet-stream", filename=name)


@router.get("/thumbnail/{name:path}")
def serve_thumbnail(name: str):
    """Serve thumbnail image for a media file."""
    state = get_state()
    
    if not state.settings.generate_thumbnails:
        raise HTTPException(404, "Thumbnails not enabled")
    
    # Find the original media file
    target = (state.video_dir / name).resolve()
    try:
        target.relative_to(state.video_dir)
    except Exception:
        raise HTTPException(403, "Forbidden path")
    
    if not target.exists() or not target.is_file():
        raise HTTPException(404, "Media file not found")
    
    # Get thumbnail path
    thumb_path = get_thumbnail_path_for(target)
    
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