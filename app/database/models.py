"""Database models for media scoring application."""

import datetime as dt
from typing import Optional, List
from pathlib import Path

from sqlalchemy import (
    Column, Integer, String, DateTime, Text, Float, Boolean,
    ForeignKey, Index, UniqueConstraint, JSON
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, Session

Base = declarative_base()


class MediaFile(Base):
    """Model for media files."""
    __tablename__ = "media_files"
    
    id = Column(Integer, primary_key=True)
    filename = Column(String(512), nullable=False)
    directory = Column(String(1024), nullable=False)
    file_path = Column(String(1536), nullable=False, unique=True)
    file_size = Column(Integer)
    file_type = Column(String(50))  # 'video', 'image'
    extension = Column(String(10))
    score = Column(Integer, default=0)  # -1 to 5
    # NSFW detection fields
    nsfw = Column(Boolean, nullable=False, default=False)  # Main NSFW boolean flag
    nsfw_score = Column(Float, nullable=True)  # NSFW probability score (0.0-1.0)
    nsfw_label = Column(Boolean, nullable=True)  # True for NSFW, False for SFW
    nsfw_model = Column(String(128), nullable=True)  # Model name used for detection
    nsfw_model_version = Column(String(64), nullable=True)  # Model version
    nsfw_threshold = Column(Float, nullable=True)  # Threshold used for classification
    media_file_id = Column(String(64), nullable=True)  # SHA256 hash of exact pixel content
    phash = Column(String(64), nullable=True)  # Perceptual hash for similarity detection
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    last_accessed = Column(DateTime)
    
    # Relationships
    media_metadata = relationship("MediaMetadata", back_populates="media_file", cascade="all, delete-orphan")
    keywords = relationship("MediaKeyword", back_populates="media_file", cascade="all, delete-orphan")
    thumbnails = relationship("MediaThumbnail", back_populates="media_file", cascade="all, delete-orphan")
    
    # Indexes for performance
    __table_args__ = (
        Index('idx_media_file_path', 'file_path'),
        Index('idx_media_directory', 'directory'),
        Index('idx_media_score', 'score'),
        Index('idx_media_type', 'file_type'),
        Index('idx_media_updated', 'updated_at'),
        Index('idx_media_file_id', 'media_file_id'),
        Index('idx_media_phash', 'phash'),
        # Enhanced indexes for sorting performance
        Index('idx_media_created_at', 'created_at'),
        Index('idx_media_file_size', 'file_size'),
        Index('idx_media_filename', 'filename'),
        Index('idx_media_nsfw', 'nsfw'),
        Index('idx_media_nsfw_score', 'nsfw_score'),
        Index('idx_media_nsfw_label', 'nsfw_label'),
    )
    
    def __repr__(self):
        return f"<MediaFile(id={self.id}, filename='{self.filename}', score={self.score})>"


class MediaMetadata(Base):
    """Model for media file metadata."""
    __tablename__ = "media_metadata"
    
    id = Column(Integer, primary_key=True)
    media_file_id = Column(Integer, ForeignKey('media_files.id'), nullable=False)
    
    # Video/Image dimensions
    width = Column(Integer)
    height = Column(Integer)
    duration = Column(Float)  # Video duration in seconds
    frame_rate = Column(Float)  # Video frame rate
    
    # Image-specific metadata
    color_mode = Column(String(50))  # RGB, RGBA, etc.
    has_alpha = Column(Boolean, default=False)
    
    # PNG text parameters (for AI-generated images)
    png_text = Column(Text)  # JSON string of PNG text chunks
    
    # ComfyUI/AI workflow data
    workflow_data = Column(Text)  # JSON string of workflow
    prompt = Column(Text)
    negative_prompt = Column(Text)
    model_name = Column(String(256))
    model_hash = Column(String(64))  # Model hash
    sampler = Column(String(100))
    steps = Column(Integer)
    cfg_scale = Column(Float)
    seed = Column(String(50))
    size = Column(String(20))  # e.g., "1152x896"
    schedule_type = Column(String(50))  # e.g., "Karras"
    
    # Hires fix parameters (consolidated into JSON)
    denoising_strength = Column(Float)  # Keep this separate as it's commonly used standalone
    hires_config = Column(JSON)  # JSON object containing: module_1, cfg_scale, upscale, upscaler
    
    # Dynamic Thresholding extension parameters (consolidated into JSON)
    dynthres_config = Column(JSON)  # JSON object containing all dynthres parameters
    
    # Version and hashes
    version = Column(String(100))
    lora_hashes = Column(Text)  # JSON string of LoRA hashes
    
    # Parsed prompt data with attention weights
    positive_prompt_keywords = Column(JSON)  # Array of {text: str, weight: float} objects
    negative_prompt_keywords = Column(JSON)  # Array of {text: str, weight: float} objects
    loras = Column(JSON)  # Array of {name: str, weight: float} objects
    
    # File modification tracking
    file_modified_at = Column(DateTime)  # When the actual file was last modified
    metadata_extracted_at = Column(DateTime, default=dt.datetime.utcnow)
    
    # Relationship
    media_file = relationship("MediaFile", back_populates="media_metadata")
    
    # Indexes
    __table_args__ = (
        Index('idx_metadata_media_file', 'media_file_id'),
        Index('idx_metadata_dimensions', 'width', 'height'),
        Index('idx_metadata_model', 'model_name'),
        Index('idx_metadata_model_hash', 'model_hash'),
        Index('idx_metadata_sampler', 'sampler'),
        Index('idx_metadata_steps', 'steps'),
        Index('idx_metadata_cfg_scale', 'cfg_scale'),
    )
    
    def __repr__(self):
        return f"<MediaMetadata(id={self.id}, media_file_id={self.media_file_id}, dimensions={self.width}x{self.height})>"


class MediaKeyword(Base):
    """Model for searchable keywords/tags associated with media files."""
    __tablename__ = "media_keywords"
    
    id = Column(Integer, primary_key=True)
    media_file_id = Column(Integer, ForeignKey('media_files.id'), nullable=False)
    keyword = Column(String(256), nullable=False)
    keyword_type = Column(String(50), default='user')  # 'user', 'prompt', 'auto', 'workflow'
    confidence = Column(Float, default=1.0)  # Confidence score for auto-generated keywords
    source = Column(String(100))  # Where this keyword came from
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    
    # Relationship
    media_file = relationship("MediaFile", back_populates="keywords")
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_keyword_media_file', 'media_file_id'),
        Index('idx_keyword_search', 'keyword'),
        Index('idx_keyword_type', 'keyword_type'),
        UniqueConstraint('media_file_id', 'keyword', 'keyword_type', name='uq_media_keyword'),
    )
    
    def __repr__(self):
        return f"<MediaKeyword(id={self.id}, keyword='{self.keyword}', type='{self.keyword_type}')>"


class MediaThumbnail(Base):
    """Model for thumbnail data storage."""
    __tablename__ = "media_thumbnails"
    
    id = Column(Integer, primary_key=True)
    media_file_id = Column(Integer, ForeignKey('media_files.id'), nullable=False)
    thumbnail_size = Column(String(20), nullable=False)  # e.g., '64x64', '128x128'
    thumbnail_data = Column(Text)  # Base64 encoded thumbnail data
    mime_type = Column(String(50), default='image/jpeg')
    file_path = Column(String(1024))  # Path to thumbnail file (alternative to storing data)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    
    # Relationship
    media_file = relationship("MediaFile", back_populates="thumbnails")
    
    # Indexes and constraints
    __table_args__ = (
        Index('idx_thumbnail_media_file', 'media_file_id'),
        Index('idx_thumbnail_size', 'thumbnail_size'),
        UniqueConstraint('media_file_id', 'thumbnail_size', name='uq_media_thumbnail_size'),
    )
    
    def __repr__(self):
        return f"<MediaThumbnail(id={self.id}, media_file_id={self.media_file_id}, size='{self.thumbnail_size}')>"