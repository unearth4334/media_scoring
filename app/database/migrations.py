"""Database migration utilities."""

import logging
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError

logger = logging.getLogger(__name__)


def migrate_database(engine) -> None:
    """Apply any necessary database migrations."""
    try:
        # Check if new columns exist
        inspector = inspect(engine)
        
        # Check if media_files table has new columns
        if 'media_files' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('media_files')]
            
            with engine.connect() as connection:
                # Add media_file_id column if it doesn't exist
                if 'media_file_id' not in columns:
                    logger.info("Adding media_file_id column to media_files table")
                    connection.execute(text(
                        "ALTER TABLE media_files ADD COLUMN media_file_id VARCHAR(64)"
                    ))
                    connection.commit()
                
                # Add phash column if it doesn't exist
                if 'phash' not in columns:
                    logger.info("Adding phash column to media_files table")
                    connection.execute(text(
                        "ALTER TABLE media_files ADD COLUMN phash VARCHAR(64)"
                    ))
                    connection.commit()
                
                # Create indexes if they don't exist (check index names)
                indexes = [idx['name'] for idx in inspector.get_indexes('media_files')]
                
                if 'idx_media_file_id' not in indexes:
                    logger.info("Creating index on media_file_id")
                    connection.execute(text(
                        "CREATE INDEX idx_media_file_id ON media_files (media_file_id)"
                    ))
                    connection.commit()
                
                if 'idx_media_phash' not in indexes:
                    logger.info("Creating index on phash") 
                    connection.execute(text(
                        "CREATE INDEX idx_media_phash ON media_files (phash)"
                    ))
                    connection.commit()
                    
        logger.info("Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise