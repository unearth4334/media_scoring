#!/usr/bin/env python3
"""Example of using the YAML database schema system programmatically."""

import sys
from pathlib import Path

# Add the app directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from app.database.schema import (
    load_schema, generate_models_from_schema, SchemaParser, ModelGenerator
)
from app.database.schema_integration import initialize_schema_system
from app.settings import Settings


def main():
    """Demonstrate schema system usage."""
    print("🔧 YAML Database Schema System Example")
    print("=" * 50)
    
    # Load schema from file
    schema_path = Path("config/schema.yml")
    if not schema_path.exists():
        print(f"❌ Schema file not found: {schema_path}")
        return 1
    
    print(f"📄 Loading schema from: {schema_path}")
    schema = load_schema(schema_path)
    
    print(f"   Database: {schema.database}")
    print(f"   Version: {schema.version}")
    print(f"   Tables: {len(schema.tables)}")
    
    # Generate models
    print(f"\n🏗️  Generating SQLAlchemy models...")
    models = generate_models_from_schema(schema_path)
    
    print(f"   Generated {len(models)} model classes:")
    for table_name, model_class in models.items():
        print(f"     - {table_name} -> {model_class.__name__}")
    
    # Demonstrate model usage
    print(f"\n🎯 Example model usage:")
    
    if 'media_files' in models:
        MediaFile = models['media_files']
        print(f"   MediaFile model: {MediaFile}")
        print(f"   Table name: {MediaFile.__tablename__}")
        print(f"   Columns: {[col.name for col in MediaFile.__table__.columns]}")
    
    # Show schema integration
    print(f"\n⚙️  Schema integration example:")
    settings = Settings(
        schema_file=schema_path,
        validate_schema=True,
        auto_migrate=False
    )
    
    integration = initialize_schema_system(settings)
    if integration:
        print(f"   Schema system initialized successfully")
        
        # Get all models
        all_models = integration.get_all_models()
        print(f"   Available models: {list(all_models.keys())}")
        
        # Compare with existing
        differences = integration.compare_with_existing_models()
        if differences:
            print(f"   Schema differences detected: {len(differences)} items")
        else:
            print(f"   No schema differences detected")
    
    print(f"\n✅ Schema system demonstration completed!")
    return 0


if __name__ == '__main__':
    sys.exit(main())