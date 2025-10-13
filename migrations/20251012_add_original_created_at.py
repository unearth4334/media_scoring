"""Add original_created_at column to media_files table.

This migration adds a new column to store the original file creation date
extracted from filesystem metadata and EXIF data, separate from the 
database record creation date.
"""

from sqlalchemy import text
from app.database.engine import get_engine

def upgrade():
    """Add original_created_at column to media_files table."""
    engine = get_engine()
    
    with engine.connect() as conn:
        # Add the new column
        conn.execute(text("""
            ALTER TABLE media_files 
            ADD COLUMN original_created_at DATETIME
        """))
        
        # Add index for performance
        conn.execute(text("""
            CREATE INDEX idx_media_original_created_at 
            ON media_files (original_created_at)
        """))
        
        # Commit the changes
        conn.commit()
        
    print("Successfully added original_created_at column and index")

def downgrade():
    """Remove original_created_at column from media_files table."""
    engine = get_engine()
    
    with engine.connect() as conn:
        # Drop the index first
        conn.execute(text("""
            DROP INDEX IF EXISTS idx_media_original_created_at
        """))
        
        # Drop the column
        conn.execute(text("""
            ALTER TABLE media_files 
            DROP COLUMN original_created_at
        """))
        
        # Commit the changes
        conn.commit()
        
    print("Successfully removed original_created_at column and index")

if __name__ == "__main__":
    upgrade()