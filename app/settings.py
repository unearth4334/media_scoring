"""Application settings using Pydantic for configuration management."""

import os
from pathlib import Path
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator
import yaml


class Settings(BaseModel):
    """Application settings with validation."""
    
    # Directory and file settings
    dir: Path = Field(default_factory=lambda: Path.cwd(), description="Directory with media files")
    pattern: str = Field(default="*.mp4", description="Glob pattern, union with | (e.g., *.mp4|*.png|*.jpg)")
    
    # Server settings
    host: str = Field(default="127.0.0.1", description="Host to bind")
    port: int = Field(default=7862, description="Port to serve")
    
    # UI settings
    style: str = Field(default="style_default.css", description="CSS style file from themes folder")
    
    # Thumbnail settings
    generate_thumbnails: bool = Field(default=False, description="Generate thumbnail previews for media files")
    thumbnail_height: int = Field(default=64, description="Height in pixels for thumbnail previews")
    
    # Toggle extensions
    toggle_extensions: List[str] = Field(default=["jpg", "png", "mp4"], description="File extensions for toggle buttons")
    
    # Directory sorting
    directory_sort_desc: bool = Field(default=True, description="Sort directory dropdown in descending order")
    
    # Database settings
    enable_database: bool = Field(default=True, description="Enable database storage for metadata and search")
    database_path: Optional[Path] = Field(default=None, description="Path to SQLite database file")
    database_url: Optional[str] = Field(default=None, description="Database URL for external database (overrides database_path)")
    
    # Schema settings
    schema_file: Optional[Path] = Field(default=None, description="YAML schema file for database structure")
    auto_migrate: bool = Field(default=False, description="Automatically apply schema migrations")
    validate_schema: bool = Field(default=True, description="Validate schema on startup")
    
    @field_validator('dir', mode='before')
    @classmethod
    def expand_dir_path(cls, v):
        """Expand and resolve directory path."""
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        return v.resolve() if isinstance(v, Path) else v
    
    @field_validator('port')
    @classmethod
    def validate_port(cls, v):
        """Validate port range."""
        if not 1 <= v <= 65535:
            raise ValueError(f"Port must be between 1 and 65535, got {v}")
        return v
    
    @field_validator('database_path', mode='before')
    @classmethod
    def expand_database_path(cls, v):
        """Expand and resolve database path."""
        if v is None:
            return None
        if isinstance(v, str):
            return Path(v).expanduser().resolve()
        return v.resolve() if isinstance(v, Path) else v
    
    @field_validator('thumbnail_height')
    @classmethod
    def validate_thumbnail_height(cls, v):
        """Validate thumbnail height."""
        if not 16 <= v <= 512:
            raise ValueError(f"Thumbnail height must be between 16 and 512, got {v}")
        return v
        
    @classmethod
    def load_from_yaml(cls, config_file: Optional[Path] = None) -> 'Settings':
        """Load settings from YAML file with CLI arg and env var override capability."""
        config_file = config_file or Path("config.yml")
        
        config_data = {}
        if config_file.exists():
            try:
                with open(config_file, 'r', encoding='utf-8') as f:
                    config_data = yaml.safe_load(f) or {}
            except Exception as e:
                print(f"Warning: Could not load {config_file}: {e}")
        
        # Override with environment variables
        if os.getenv('DATABASE_URL'):
            config_data['database_url'] = os.getenv('DATABASE_URL')
        
        return cls(**config_data)
    
    def get_database_path(self) -> Path:
        """Get the database path, defaulting to .scores/media.db in the media directory."""
        if self.database_path:
            return self.database_path
        else:
            return self.dir / ".scores" / "media.db"
    
    def get_database_url(self) -> str:
        """Get the database URL, defaulting to SQLite file if no URL specified."""
        if self.database_url:
            return self.database_url
        else:
            db_path = self.get_database_path()
            return f"sqlite:///{db_path}"