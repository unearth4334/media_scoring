"""Add favourite column to media_files table.

This migration adds a new boolean column to store whether a media file
is marked as a favourite, independent of its score rating.
"""

from sqlalchemy import text
from app.database.engine import get_engine

def upgrade():
    """Add favourite column to media_files table."""
    engine = get_engine()
    
    with engine.connect() as conn:
        # Add the new column with default value False
        conn.execute(text("""
            ALTER TABLE media_files 
            ADD COLUMN favourite BOOLEAN NOT NULL DEFAULT 0
        """))
        
        # Add index for performance
        conn.execute(text("""
            CREATE INDEX idx_media_favourite 
            ON media_files (favourite)
        """))
        
        # Commit the changes
        conn.commit()
        
    print("Successfully added favourite column and index")

def downgrade():
    """Remove favourite column from media_files table."""
    engine = get_engine()
    
    with engine.connect() as conn:
        # Drop the index first
        conn.execute(text("""
            DROP INDEX IF EXISTS idx_media_favourite
        """))
        
        # Drop the column
        conn.execute(text("""
            ALTER TABLE media_files 
            DROP COLUMN favourite
        """))
        
        # Commit the changes
        conn.commit()
        
    print("Successfully removed favourite column and index")

if __name__ == "__main__":
    upgrade()
