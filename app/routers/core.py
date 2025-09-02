"""Core router for serving the main application template."""

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

from ..state import get_state


router = APIRouter()

# Initialize Jinja2 templates
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Serve the main application page."""
    state = get_state()
    return templates.TemplateResponse(
        "index.html", 
        {
            "request": request, 
            "settings": state.settings
        }
    )