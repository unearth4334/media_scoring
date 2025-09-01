"""Template management for serving HTML"""
from pathlib import Path
from ..core.config import config


def get_main_template() -> str:
    """Get the main HTML template with proper CSS link"""
    template_path = Path(__file__).parent.parent.parent / "templates" / "index.html"
    
    if template_path.exists():
        # Use external template file
        content = template_path.read_text(encoding='utf-8')
        return content.replace('href="/themes/style_default.css"', f'href="/themes/{config.style}"')
    else:
        # Fallback to embedded template
        return _get_embedded_template()


def _get_embedded_template() -> str:
    """Fallback embedded HTML template"""
    # This will be populated with the extracted HTML content
    return CLIENT_HTML.replace('href="/themes/style_default.css"', f'href="/themes/{config.style}"')


# Read the embedded template from the original app.py for fallback
def _load_embedded_template() -> str:
    """Load the embedded template from templates/index.html"""
    template_path = Path(__file__).parent.parent.parent / "templates" / "index.html"
    if template_path.exists():
        return template_path.read_text(encoding='utf-8')
    else:
        # Ultimate fallback - minimal HTML
        return """<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Video Scorer</title>
  <link rel="stylesheet" href="/themes/style_default.css">
</head>
<body>
  <h1>Media Scorer</h1>
  <p>Error: Template not found. Please check your installation.</p>
</body>
</html>"""

CLIENT_HTML = _load_embedded_template()