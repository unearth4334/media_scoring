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
        
        # Check if media_metadata table has new columns
        if 'media_metadata' in inspector.get_table_names():
            _migrate_media_metadata_table(engine, inspector)
                    
        logger.info("Database migration completed successfully")
        
    except Exception as e:
        logger.error(f"Database migration failed: {e}")
        raise


def _migrate_media_metadata_table(engine, inspector) -> None:
    """Migrate the media_metadata table to add new PNG parameter columns."""
    metadata_columns = [col['name'] for col in inspector.get_columns('media_metadata')]
    
    # Define all the new columns we need to add
    new_columns = [
        # Basic parameters that were missing
        ("model_hash", "VARCHAR(64)"),
        ("size", "VARCHAR(20)"),
        ("schedule_type", "VARCHAR(50)"),
        
        # Hires fix parameters
        ("denoising_strength", "FLOAT"),
        ("hires_module_1", "VARCHAR(100)"),
        ("hires_cfg_scale", "FLOAT"),
        ("hires_upscale", "FLOAT"),
        ("hires_upscaler", "VARCHAR(200)"),
        
        # Dynamic Thresholding extension parameters
        ("dynthres_enabled", "BOOLEAN"),
        ("dynthres_mimic_scale", "FLOAT"),
        ("dynthres_threshold_percentile", "FLOAT"),
        ("dynthres_mimic_mode", "VARCHAR(50)"),
        ("dynthres_mimic_scale_min", "FLOAT"),
        ("dynthres_cfg_mode", "VARCHAR(50)"),
        ("dynthres_cfg_scale_min", "FLOAT"),
        ("dynthres_sched_val", "FLOAT"),
        ("dynthres_separate_feature_channels", "VARCHAR(50)"),
        ("dynthres_scaling_startpoint", "VARCHAR(50)"),
        ("dynthres_variability_measure", "VARCHAR(50)"),
        ("dynthres_interpolate_phi", "FLOAT"),
        
        # Version and hashes
        ("version", "VARCHAR(100)"),
        ("lora_hashes", "TEXT"),
    ]
    
    with engine.connect() as connection:
        # Add each missing column
        for column_name, column_type in new_columns:
            if column_name not in metadata_columns:
                logger.info(f"Adding {column_name} column to media_metadata table")
                connection.execute(text(
                    f"ALTER TABLE media_metadata ADD COLUMN {column_name} {column_type}"
                ))
                connection.commit()
        
        # Create new indexes
        indexes = [idx['name'] for idx in inspector.get_indexes('media_metadata')]
        
        new_indexes = [
            ('idx_metadata_model_hash', 'model_hash'),
            ('idx_metadata_sampler', 'sampler'),
            ('idx_metadata_steps', 'steps'),
            ('idx_metadata_cfg_scale', 'cfg_scale'),
        ]
        
        for index_name, column_name in new_indexes:
            if index_name not in indexes:
                logger.info(f"Creating index {index_name} on {column_name}")
                connection.execute(text(
                    f"CREATE INDEX {index_name} ON media_metadata ({column_name})"
                ))
                connection.commit()