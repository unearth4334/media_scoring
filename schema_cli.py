#!/usr/bin/env python3
"""Command-line interface for database schema management."""

import argparse
import sys
from pathlib import Path
from typing import Optional

from app.database.schema import (
    SchemaParser, ModelGenerator, load_schema, 
    generate_models_file
)
from app.database.migration import (
    MigrationGenerator, create_migration_from_schema_files,
    update_models_from_schema
)


def validate_schema(schema_path: Path) -> bool:
    """Validate a YAML schema file."""
    try:
        parser = SchemaParser()
        schema = parser.parse_file(schema_path)
        print(f"✅ Schema validation passed: {schema_path}")
        print(f"   Database: {schema.database}")
        print(f"   Version: {schema.version}")
        print(f"   Tables: {len(schema.tables)}")
        for table_name, table_def in schema.tables.items():
            print(f"     - {table_name}: {len(table_def.columns)} columns, {len(table_def.indexes)} indexes")
        return True
    except Exception as e:
        print(f"❌ Schema validation failed: {e}", file=sys.stderr)
        return False


def generate_models(schema_path: Path, output_path: Optional[Path] = None) -> bool:
    """Generate SQLAlchemy models from schema."""
    try:
        if output_path is None:
            output_path = Path("generated_models.py")
        
        generate_models_file(schema_path, output_path)
        print(f"✅ Generated models: {output_path}")
        return True
    except Exception as e:
        print(f"❌ Model generation failed: {e}", file=sys.stderr)
        return False


def show_info(schema_path: Path) -> bool:
    """Show detailed information about a schema."""
    try:
        schema = load_schema(schema_path)
        print(f"Database Schema Information")
        print(f"=" * 40)
        print(f"Database: {schema.database}")
        print(f"Version: {schema.version}")
        if schema.description:
            print(f"Description: {schema.description}")
        print(f"\nTables ({len(schema.tables)}):")
        
        for table_name, table_def in schema.tables.items():
            print(f"\n  {table_name}:")
            if table_def.description:
                print(f"    Description: {table_def.description}")
            print(f"    Columns ({len(table_def.columns)}):")
            
            for col in table_def.columns:
                flags = []
                if col.primary_key:
                    flags.append("PK")
                if col.autoincrement:
                    flags.append("AI")
                if not col.nullable:
                    flags.append("NOT NULL")
                if col.unique:
                    flags.append("UNIQUE")
                if col.foreign_key:
                    flags.append(f"FK→{col.foreign_key}")
                
                flags_str = f" [{', '.join(flags)}]" if flags else ""
                length_str = f"({col.length})" if col.length else ""
                default_str = f" DEFAULT {col.default}" if col.default else ""
                
                print(f"      - {col.name}: {col.type.value}{length_str}{flags_str}{default_str}")
                if col.note:
                    print(f"        Note: {col.note}")
            
            if table_def.indexes:
                print(f"    Indexes ({len(table_def.indexes)}):")
                for idx in table_def.indexes:
                    unique_str = " (UNIQUE)" if idx.unique else ""
                    print(f"      - {idx.name}: [{', '.join(idx.columns)}]{unique_str}")
            
            if table_def.constraints:
                print(f"    Constraints ({len(table_def.constraints)}):")
                for const in table_def.constraints:
                    print(f"      - {const.name} ({const.type.upper()}): [{', '.join(const.columns)}]")
        
        return True
    except Exception as e:
        print(f"❌ Failed to show schema info: {e}", file=sys.stderr)
        return False


def create_migration(old_schema_path: Path, new_schema_path: Path, message: str) -> bool:
    """Create a migration between two schema files."""
    try:
        migration_file = create_migration_from_schema_files(
            old_schema_path, new_schema_path, message
        )
        if migration_file:
            print(f"✅ Created migration: {migration_file}")
            return True
        else:
            print("ℹ️  No changes detected - no migration created.")
            return True
    except Exception as e:
        print(f"❌ Migration creation failed: {e}", file=sys.stderr)
        return False


def update_models(schema_path: Path, models_path: Optional[Path] = None) -> bool:
    """Update models file from schema."""
    try:
        if models_path is None:
            models_path = Path("app/database/models.py")
        
        success = update_models_from_schema(schema_path, models_path)
        if success:
            print(f"✅ Updated models: {models_path}")
        return success
    except Exception as e:
        print(f"❌ Model update failed: {e}", file=sys.stderr)
        return False


def compare_schemas(schema1_path: Path, schema2_path: Path) -> bool:
    """Compare two schema files and show differences."""
    try:
        schema1 = load_schema(schema1_path)
        schema2 = load_schema(schema2_path)
        
        print(f"Comparing Schemas")
        print(f"=" * 40)
        print(f"Schema 1: {schema1_path} (v{schema1.version})")
        print(f"Schema 2: {schema2_path} (v{schema2.version})")
        
        # Compare tables
        all_tables = set(schema1.tables.keys()) | set(schema2.tables.keys())
        tables_only_in_1 = set(schema1.tables.keys()) - set(schema2.tables.keys())
        tables_only_in_2 = set(schema2.tables.keys()) - set(schema1.tables.keys())
        common_tables = set(schema1.tables.keys()) & set(schema2.tables.keys())
        
        if tables_only_in_1:
            print(f"\nTables only in Schema 1:")
            for table in sorted(tables_only_in_1):
                print(f"  + {table}")
        
        if tables_only_in_2:
            print(f"\nTables only in Schema 2:")
            for table in sorted(tables_only_in_2):
                print(f"  + {table}")
        
        # Compare common tables
        for table_name in sorted(common_tables):
            table1 = schema1.tables[table_name]
            table2 = schema2.tables[table_name]
            
            # Compare columns
            cols1 = {col.name: col for col in table1.columns}
            cols2 = {col.name: col for col in table2.columns}
            
            cols_only_in_1 = set(cols1.keys()) - set(cols2.keys())
            cols_only_in_2 = set(cols2.keys()) - set(cols1.keys())
            common_cols = set(cols1.keys()) & set(cols2.keys())
            
            has_differences = bool(cols_only_in_1 or cols_only_in_2)
            
            # Check for column type differences
            col_differences = []
            for col_name in common_cols:
                col1, col2 = cols1[col_name], cols2[col_name]
                if (col1.type != col2.type or 
                    col1.nullable != col2.nullable or
                    col1.primary_key != col2.primary_key or
                    col1.unique != col2.unique or
                    col1.default != col2.default):
                    col_differences.append(col_name)
                    has_differences = True
            
            if has_differences:
                print(f"\nTable: {table_name}")
                
                if cols_only_in_1:
                    for col in sorted(cols_only_in_1):
                        print(f"  - Column only in Schema 1: {col}")
                
                if cols_only_in_2:
                    for col in sorted(cols_only_in_2):
                        print(f"  + Column only in Schema 2: {col}")
                
                for col_name in sorted(col_differences):
                    col1, col2 = cols1[col_name], cols2[col_name]
                    print(f"  ~ Column {col_name}:")
                    print(f"    Schema 1: {col1.type.value} (nullable={col1.nullable}, pk={col1.primary_key})")
                    print(f"    Schema 2: {col2.type.value} (nullable={col2.nullable}, pk={col2.primary_key})")
        
        print(f"\nComparison completed.")
        return True
        
    except Exception as e:
        print(f"❌ Schema comparison failed: {e}", file=sys.stderr)
        return False


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Database Schema Management CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Validate schema
  python schema_cli.py validate schema.yml
  
  # Generate models
  python schema_cli.py generate schema.yml --output models.py
  
  # Show schema information
  python schema_cli.py info schema.yml
  
  # Compare schemas
  python schema_cli.py compare old_schema.yml new_schema.yml
  
  # Create migration
  python schema_cli.py migrate old_schema.yml new_schema.yml --message "Add new fields"
  
  # Update models from schema
  python schema_cli.py update schema.yml --models app/database/models.py
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # Validate command
    validate_parser = subparsers.add_parser('validate', help='Validate schema file')
    validate_parser.add_argument('schema', type=Path, help='Path to schema YAML file')
    
    # Generate command
    generate_parser = subparsers.add_parser('generate', help='Generate SQLAlchemy models')
    generate_parser.add_argument('schema', type=Path, help='Path to schema YAML file')
    generate_parser.add_argument('--output', '-o', type=Path, help='Output Python file (default: generated_models.py)')
    
    # Info command
    info_parser = subparsers.add_parser('info', help='Show schema information')
    info_parser.add_argument('schema', type=Path, help='Path to schema YAML file')
    
    # Compare command
    compare_parser = subparsers.add_parser('compare', help='Compare two schema files')
    compare_parser.add_argument('schema1', type=Path, help='Path to first schema YAML file')
    compare_parser.add_argument('schema2', type=Path, help='Path to second schema YAML file')
    
    # Migration command
    migration_parser = subparsers.add_parser('migrate', help='Create migration between schemas')
    migration_parser.add_argument('old_schema', type=Path, help='Path to old schema YAML file')
    migration_parser.add_argument('new_schema', type=Path, help='Path to new schema YAML file')
    migration_parser.add_argument('--message', '-m', required=True, help='Migration message')
    
    # Update command
    update_parser = subparsers.add_parser('update', help='Update models from schema')
    update_parser.add_argument('schema', type=Path, help='Path to schema YAML file')
    update_parser.add_argument('--models', type=Path, help='Path to models file (default: app/database/models.py)')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 1
    
    success = False
    
    if args.command == 'validate':
        success = validate_schema(args.schema)
    elif args.command == 'generate':
        success = generate_models(args.schema, args.output)
    elif args.command == 'info':
        success = show_info(args.schema)
    elif args.command == 'compare':
        success = compare_schemas(args.schema1, args.schema2)
    elif args.command == 'migrate':
        success = create_migration(args.old_schema, args.new_schema, args.message)
    elif args.command == 'update':
        success = update_models(args.schema, args.models)
    
    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(main())