"""
Add NSFW detection fields to MediaFile model

Revision ID: add_nsfw_fields
Created: 2025-10-08
"""

from datetime import datetime
from pathlib import Path
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from sqlalchemy import text
from app.database.engine import get_session


def upgrade():
    """Add NSFW detection fields to media_files table."""
    
    with get_session() as session:
        # Add NSFW score column (probability 0.0-1.0)
        session.execute(text("""
            ALTER TABLE media_files 
            ADD COLUMN IF NOT EXISTS nsfw_score REAL
        """))
        
        # Add NSFW label column ('sfw' or 'nsfw')
        session.execute(text("""
            ALTER TABLE media_files 
            ADD COLUMN IF NOT EXISTS nsfw_label VARCHAR(10)
        """))
        
        # Add index for NSFW score for efficient filtering
        session.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_media_nsfw_score 
            ON media_files(nsfw_score)
        """))
        
        session.commit()
        print("✅ Added NSFW detection fields to media_files table")


def downgrade():
    """Remove NSFW detection fields from media_files table."""
    
    with get_session() as session:
        # Drop index first
        session.execute(text("""
            DROP INDEX IF EXISTS idx_media_nsfw_score
        """))
        
        # Drop columns
        session.execute(text("""
            ALTER TABLE media_files 
            DROP COLUMN IF EXISTS nsfw_score,
            DROP COLUMN IF EXISTS nsfw_label
        """))
        
        session.commit()
        print("✅ Removed NSFW detection fields from media_files table")


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="NSFW fields migration")
    parser.add_argument("action", choices=["upgrade", "downgrade"], 
                       help="Migration action to perform")
    parser.add_argument("--database-url", help="Database URL (if not in environment)")
    
    args = parser.parse_args()
    
    # Set database URL if provided
    if args.database_url:
        import os
        os.environ["DATABASE_URL"] = args.database_url
    
    # Initialize database
    from app.database.engine import init_database
    init_database()
    
    # Run migration
    if args.action == "upgrade":
        upgrade()
    else:
        downgrade()