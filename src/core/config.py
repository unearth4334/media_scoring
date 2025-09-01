"""Configuration management for Media Scorer"""
from pathlib import Path
from typing import List, Optional
import sys
try:
    import yaml
except ImportError:
    yaml = None


class Config:
    """Configuration container for the application"""
    def __init__(self):
        # Default values
        self.dir: str = str(Path.cwd())
        self.host: str = "127.0.0.1"
        self.port: int = 7862
        self.pattern: str = "*.mp4"
        self.style: str = "style_default.css"
        self.generate_thumbnails: bool = False
        self.thumbnail_height: int = 64
        self.toggle_extensions: List[str] = ["jpg", "png", "mp4"]
        self.directory_sort_desc: bool = True

    def load_from_file(self, config_file: Path = None) -> None:
        """Load configuration from YAML file"""
        if config_file is None:
            config_file = Path("config.yml")
        
        if not config_file.exists():
            return
            
        if yaml is None:
            print(f"Warning: PyYAML not available, skipping {config_file}", file=sys.stderr)
            return
            
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                cfg = yaml.safe_load(f) or {}
            
            # Apply config values
            self.dir = cfg.get('dir', self.dir)
            self.pattern = cfg.get('pattern', self.pattern)
            self.style = cfg.get('style', self.style)
            self.generate_thumbnails = bool(cfg.get('generate_thumbnails', self.generate_thumbnails))
            self.thumbnail_height = int(cfg.get('thumbnail_height', self.thumbnail_height))
            self.toggle_extensions = cfg.get('toggle_extensions', self.toggle_extensions)
            self.directory_sort_desc = bool(cfg.get('directory_sort_desc', self.directory_sort_desc))
            
        except Exception as e:
            print(f"Warning: Could not load {config_file}: {e}", file=sys.stderr)


# Global config instance
config = Config()