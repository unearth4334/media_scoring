"""Integration module for schema-based database initialization."""

import logging
from pathlib import Path
from typing import Optional, Dict, Type
from sqlalchemy.ext.declarative import declarative_base

from .schema import (
    load_schema, generate_models_from_schema, SchemaParser, ModelGenerator
)
from .models import Base as ExistingBase
from ..settings import Settings


logger = logging.getLogger(__name__)


class SchemaIntegration:
    """Handles integration of YAML schema with existing database system."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.parser = SchemaParser()
        self.models = {}
        self._schema = None
    
    def initialize(self) -> bool:
        """Initialize schema system based on configuration."""
        try:
            if not self.settings.schema_file:
                logger.info("No schema file configured, using existing models")
                return True
            
            schema_path = Path(self.settings.schema_file)
            if not schema_path.exists():
                logger.warning(f"Schema file not found: {schema_path}")
                return True
            
            if self.settings.validate_schema:
                if not self.validate_schema_file(schema_path):
                    logger.error(f"Schema validation failed: {schema_path}")
                    return False
            
            # Load and apply schema
            self._schema = load_schema(schema_path)
            self.models = generate_models_from_schema(schema_path, ExistingBase)
            
            logger.info(f"Successfully loaded schema from {schema_path}")
            logger.info(f"Generated {len(self.models)} models: {list(self.models.keys())}")
            
            return True
            
        except Exception as e:
            logger.error(f"Schema initialization failed: {e}")
            return False
    
    def validate_schema_file(self, schema_path: Path) -> bool:
        """Validate a schema file."""
        try:
            schema = self.parser.parse_file(schema_path)
            
            # Basic validation
            if not schema.database:
                logger.error("Schema missing database name")
                return False
            
            if not schema.tables:
                logger.error("Schema has no tables defined")
                return False
            
            # Validate each table
            for table_name, table_def in schema.tables.items():
                if not table_def.columns:
                    logger.error(f"Table {table_name} has no columns")
                    return False
                
                # Check for primary key
                has_pk = any(col.primary_key for col in table_def.columns)
                if not has_pk:
                    logger.warning(f"Table {table_name} has no primary key")
                
                # Validate foreign key references
                for col in table_def.columns:
                    if col.foreign_key:
                        ref_parts = col.foreign_key.split('.')
                        if len(ref_parts) != 2:
                            logger.error(f"Invalid foreign key format: {col.foreign_key}")
                            return False
                        
                        ref_table, ref_column = ref_parts
                        if ref_table not in schema.tables:
                            logger.error(f"Foreign key references unknown table: {ref_table}")
                            return False
            
            logger.info(f"Schema validation passed for {schema_path}")
            return True
            
        except Exception as e:
            logger.error(f"Schema validation error: {e}")
            return False
    
    def get_model_class(self, table_name: str) -> Optional[Type]:
        """Get a model class by table name."""
        return self.models.get(table_name)
    
    def get_all_models(self) -> Dict[str, Type]:
        """Get all generated model classes."""
        return self.models.copy()
    
    def get_schema(self):
        """Get the loaded schema object."""
        return self._schema
    
    def compare_with_existing_models(self) -> Dict[str, str]:
        """Compare schema-generated models with existing models."""
        differences = {}
        
        if not self._schema:
            return differences
        
        # Import existing models for comparison
        try:
            from . import models as existing_models
            
            # Get all model classes from existing models module
            existing_classes = {}
            for name in dir(existing_models):
                obj = getattr(existing_models, name)
                if (isinstance(obj, type) and 
                    hasattr(obj, '__tablename__') and 
                    obj != existing_models.Base):
                    existing_classes[obj.__tablename__] = obj
            
            # Compare with schema tables
            for table_name in self._schema.tables:
                if table_name in existing_classes:
                    # Table exists in both - could check column differences here
                    differences[table_name] = "exists_in_both"
                else:
                    differences[table_name] = "only_in_schema"
            
            # Check for tables only in existing models
            for table_name in existing_classes:
                if table_name not in self._schema.tables:
                    differences[table_name] = "only_in_existing"
                    
        except Exception as e:
            logger.warning(f"Could not compare with existing models: {e}")
        
        return differences
    
    def sync_schema_to_database(self) -> bool:
        """Synchronize schema changes to the database."""
        if not self.settings.auto_migrate:
            logger.info("Auto-migration disabled, skipping schema sync")
            return True
        
        try:
            # This would integrate with Alembic for real migrations
            logger.info("Schema sync would run migrations here")
            return True
            
        except Exception as e:
            logger.error(f"Schema sync failed: {e}")
            return False


def initialize_schema_system(settings: Settings) -> SchemaIntegration:
    """Initialize the schema system with given settings."""
    integration = SchemaIntegration(settings)
    
    if integration.initialize():
        logger.info("Schema system initialized successfully")
    else:
        logger.error("Schema system initialization failed")
    
    return integration