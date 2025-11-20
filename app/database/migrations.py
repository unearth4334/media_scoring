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
        
        # Create daily_contributions table if it doesn't exist
        if 'daily_contributions' not in inspector.get_table_names():
            logger.info("Creating daily_contributions table")
            with engine.connect() as connection:
                connection.execute(text("""
                    CREATE TABLE daily_contributions (
                        id INTEGER PRIMARY KEY,
                        date TIMESTAMP NOT NULL UNIQUE,
                        count INTEGER NOT NULL DEFAULT 0,
                        created_at TIMESTAMP,
                        updated_at TIMESTAMP
                    )
                """))
                connection.execute(text(
                    "CREATE INDEX idx_daily_contribution_date ON daily_contributions (date)"
                ))
                connection.commit()
                logger.info("Created daily_contributions table successfully")
        
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
            _migrate_to_json_columns(engine, inspector)
                    
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


def _migrate_to_json_columns(engine, inspector) -> None:
    """Migrate existing individual columns to new JSON columns."""
    metadata_columns = [col['name'] for col in inspector.get_columns('media_metadata')]
    
    with engine.connect() as connection:
        # Add JSON columns if they don't exist
        if 'hires_config' not in metadata_columns:
            logger.info("Adding hires_config JSON column to media_metadata table")
            connection.execute(text(
                "ALTER TABLE media_metadata ADD COLUMN hires_config JSON"
            ))
            connection.commit()
        
        if 'dynthres_config' not in metadata_columns:
            logger.info("Adding dynthres_config JSON column to media_metadata table")
            connection.execute(text(
                "ALTER TABLE media_metadata ADD COLUMN dynthres_config JSON"
            ))
            connection.commit()
        
        # Migrate existing data to JSON columns
        logger.info("Migrating existing Hires and DynThres data to JSON columns")
        
        # Get all records with existing individual columns
        result = connection.execute(text("""
            SELECT id, 
                   hires_module_1, hires_cfg_scale, hires_upscale, hires_upscaler,
                   dynthres_enabled, dynthres_mimic_scale, dynthres_threshold_percentile,
                   dynthres_mimic_mode, dynthres_mimic_scale_min, dynthres_cfg_mode,
                   dynthres_cfg_scale_min, dynthres_sched_val, dynthres_separate_feature_channels,
                   dynthres_scaling_startpoint, dynthres_variability_measure, dynthres_interpolate_phi
            FROM media_metadata 
            WHERE (hires_module_1 IS NOT NULL OR hires_cfg_scale IS NOT NULL OR 
                   hires_upscale IS NOT NULL OR hires_upscaler IS NOT NULL OR
                   dynthres_enabled IS NOT NULL OR dynthres_mimic_scale IS NOT NULL)
        """))
        
        import json
        
        for row in result:
            row_id = row[0]
            
            # Build hires_config JSON
            hires_config = {}
            if row[1] is not None:  # hires_module_1
                hires_config['module_1'] = row[1]
            if row[2] is not None:  # hires_cfg_scale
                hires_config['cfg_scale'] = row[2]
            if row[3] is not None:  # hires_upscale
                hires_config['upscale'] = row[3]
            if row[4] is not None:  # hires_upscaler
                hires_config['upscaler'] = row[4]
            
            # Build dynthres_config JSON
            dynthres_config = {}
            if row[5] is not None:  # dynthres_enabled
                dynthres_config['enabled'] = bool(row[5])
            if row[6] is not None:  # dynthres_mimic_scale
                dynthres_config['mimic_scale'] = row[6]
            if row[7] is not None:  # dynthres_threshold_percentile
                dynthres_config['threshold_percentile'] = row[7]
            if row[8] is not None:  # dynthres_mimic_mode
                dynthres_config['mimic_mode'] = row[8]
            if row[9] is not None:  # dynthres_mimic_scale_min
                dynthres_config['mimic_scale_min'] = row[9]
            if row[10] is not None:  # dynthres_cfg_mode
                dynthres_config['cfg_mode'] = row[10]
            if row[11] is not None:  # dynthres_cfg_scale_min
                dynthres_config['cfg_scale_min'] = row[11]
            if row[12] is not None:  # dynthres_sched_val
                dynthres_config['sched_val'] = row[12]
            if row[13] is not None:  # dynthres_separate_feature_channels
                dynthres_config['separate_feature_channels'] = row[13]
            if row[14] is not None:  # dynthres_scaling_startpoint
                dynthres_config['scaling_startpoint'] = row[14]
            if row[15] is not None:  # dynthres_variability_measure
                dynthres_config['variability_measure'] = row[15]
            if row[16] is not None:  # dynthres_interpolate_phi
                dynthres_config['interpolate_phi'] = row[16]
            
            # Update the record with JSON data
            updates = []
            params = {'row_id': row_id}
            
            if hires_config:
                updates.append("hires_config = :hires_config")
                params['hires_config'] = json.dumps(hires_config)
            
            if dynthres_config:
                updates.append("dynthres_config = :dynthres_config")
                params['dynthres_config'] = json.dumps(dynthres_config)
            
            if updates:
                update_sql = f"UPDATE media_metadata SET {', '.join(updates)} WHERE id = :row_id"
                connection.execute(text(update_sql), params)
                connection.commit()
        
        logger.info("Migration to JSON columns completed")