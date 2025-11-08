"""Database engine and session management."""

import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool, StaticPool

from .models import Base
from .migrations import migrate_database

logger = logging.getLogger(__name__)

# Global variables for engine and session
_engine = None
_session_factory = None


def init_database(database_url: str) -> None:
    """Initialize the database with the given URL.
    
    Supports both PostgreSQL and SQLite databases.
    """
    global _engine, _session_factory
    
    logger.info(f"Initializing database with URL: {database_url}")
    
    # Configure engine based on database type
    if database_url.startswith("postgresql://"):
        # PostgreSQL configuration
        _engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=10,
            max_overflow=20,
            pool_pre_ping=True,
            echo=False
        )
    elif database_url.startswith("sqlite://"):
        # SQLite configuration
        from sqlalchemy.pool import StaticPool
        
        # Extract connect_args for SQLite
        connect_args = {}
        if "/:memory:" not in database_url and "///:memory:" not in database_url:
            # File-based SQLite
            connect_args = {"check_same_thread": False}
        
        _engine = create_engine(
            database_url,
            connect_args=connect_args,
            poolclass=StaticPool if "memory" in database_url else QueuePool,
            echo=False
        )
    else:
        raise ValueError(f"Unsupported database URL. Must start with 'postgresql://' or 'sqlite://'. Got: {database_url[:20]}")
    
    # Create session factory
    _session_factory = sessionmaker(bind=_engine)
    
    # Create all tables
    Base.metadata.create_all(bind=_engine)
    
    # Run migrations for existing databases
    migrate_database(_engine)
    
    logger.info(f"Database initialized successfully")


def get_engine():
    """Get the database engine."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _engine


def get_session() -> Session:
    """Get a new database session."""
    if _session_factory is None:
        raise RuntimeError("Database not initialized. Call init_database() first.")
    return _session_factory()


def close_database():
    """Close the database connection."""
    global _engine, _session_factory
    if _engine:
        _engine.dispose()
        _engine = None
        _session_factory = None
        logger.info("Database connection closed")