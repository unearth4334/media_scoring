"""Database migration system for schema changes."""

import datetime as dt
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
import importlib.util
import inspect

from sqlalchemy import Column, Index, UniqueConstraint, text
from sqlalchemy.ext.declarative import declarative_base
from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from alembic.environment import EnvironmentContext

from .schema import (
    DatabaseSchema, TableDefinition, ColumnDefinition, ColumnType,
    SchemaParser, ModelGenerator, load_schema
)


class SchemaDiff:
    """Represents differences between two database schemas."""
    
    def __init__(self):
        self.new_tables: List[str] = []
        self.dropped_tables: List[str] = []
        self.modified_tables: Dict[str, 'TableDiff'] = {}


class TableDiff:
    """Represents differences between two table definitions."""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.new_columns: List[ColumnDefinition] = []
        self.dropped_columns: List[str] = []
        self.modified_columns: Dict[str, ColumnDefinition] = {}
        self.new_indexes: List[str] = []
        self.dropped_indexes: List[str] = []


class MigrationGenerator:
    """Generates Alembic migration files from schema changes."""
    
    def __init__(self, alembic_config_path: Optional[Path] = None):
        self.alembic_config_path = alembic_config_path or Path("alembic.ini")
        self.parser = SchemaParser()
    
    def compare_schemas(self, old_schema: DatabaseSchema, new_schema: DatabaseSchema) -> SchemaDiff:
        """Compare two schemas and return differences."""
        diff = SchemaDiff()
        
        old_tables = set(old_schema.tables.keys())
        new_tables = set(new_schema.tables.keys())
        
        # Find new and dropped tables
        diff.new_tables = list(new_tables - old_tables)
        diff.dropped_tables = list(old_tables - new_tables)
        
        # Find modified tables
        common_tables = old_tables & new_tables
        for table_name in common_tables:
            table_diff = self._compare_tables(
                old_schema.tables[table_name], 
                new_schema.tables[table_name]
            )
            if self._has_table_changes(table_diff):
                diff.modified_tables[table_name] = table_diff
        
        return diff
    
    def _compare_tables(self, old_table: TableDefinition, new_table: TableDefinition) -> TableDiff:
        """Compare two table definitions."""
        table_diff = TableDiff(old_table.name)
        
        # Build column maps
        old_columns = {col.name: col for col in old_table.columns}
        new_columns = {col.name: col for col in new_table.columns}
        
        old_col_names = set(old_columns.keys())
        new_col_names = set(new_columns.keys())
        
        # Find new and dropped columns
        for col_name in new_col_names - old_col_names:
            table_diff.new_columns.append(new_columns[col_name])
        
        table_diff.dropped_columns = list(old_col_names - new_col_names)
        
        # Find modified columns
        common_columns = old_col_names & new_col_names
        for col_name in common_columns:
            old_col = old_columns[col_name]
            new_col = new_columns[col_name]
            
            if self._columns_differ(old_col, new_col):
                table_diff.modified_columns[col_name] = new_col
        
        # Compare indexes
        old_indexes = {idx.name for idx in old_table.indexes}
        new_indexes = {idx.name for idx in new_table.indexes}
        
        table_diff.new_indexes = list(new_indexes - old_indexes)
        table_diff.dropped_indexes = list(old_indexes - new_indexes)
        
        return table_diff
    
    def _columns_differ(self, old_col: ColumnDefinition, new_col: ColumnDefinition) -> bool:
        """Check if two column definitions are different."""
        return (
            old_col.type != new_col.type or
            old_col.nullable != new_col.nullable or
            old_col.unique != new_col.unique or
            old_col.default != new_col.default or
            old_col.length != new_col.length or
            old_col.foreign_key != new_col.foreign_key
        )
    
    def _has_table_changes(self, table_diff: TableDiff) -> bool:
        """Check if table has any changes."""
        return (
            table_diff.new_columns or 
            table_diff.dropped_columns or 
            table_diff.modified_columns or
            table_diff.new_indexes or 
            table_diff.dropped_indexes
        )
    
    def generate_migration_script(self, diff: SchemaDiff, message: str) -> str:
        """Generate Alembic migration script content."""
        lines = []
        
        # Migration header
        lines.append('"""Add description here')
        lines.append('')
        lines.append(f'Revision ID: {{revision}}')
        lines.append('Revises: {down_revision}')
        lines.append(f'Create Date: {dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')
        lines.append('')
        lines.append('"""')
        lines.append('from alembic import op')
        lines.append('import sqlalchemy as sa')
        lines.append('')
        lines.append('# revision identifiers')
        lines.append('revision = {revision!r}')
        lines.append('down_revision = {down_revision!r}')
        lines.append('branch_labels = {branch_labels!r}')
        lines.append('depends_on = {depends_on!r}')
        lines.append('')
        
        # Upgrade function
        lines.append('def upgrade() -> None:')
        lines.append('    """Upgrade database schema."""')
        
        if not self._has_changes(diff):
            lines.append('    pass')
        else:
            # Add new tables
            for table_name in diff.new_tables:
                lines.append(f'    # Create table {table_name}')
                lines.append(f'    op.create_table("{table_name}",')
                lines.append('        # Add columns here')
                lines.append('    )')
                lines.append('')
            
            # Modify existing tables
            for table_name, table_diff in diff.modified_tables.items():
                lines.append(f'    # Modify table {table_name}')
                
                # Add new columns
                for col in table_diff.new_columns:
                    col_def = self._generate_column_definition(col)
                    lines.append(f'    op.add_column("{table_name}", {col_def})')
                
                # Drop columns
                for col_name in table_diff.dropped_columns:
                    lines.append(f'    op.drop_column("{table_name}", "{col_name}")')
                
                # Modify columns
                for col_name, new_col in table_diff.modified_columns.items():
                    col_def = self._generate_column_definition(new_col)
                    lines.append(f'    op.alter_column("{table_name}", "{col_name}",')
                    lines.append(f'                    existing_type=sa.String(),  # Update as needed')
                    lines.append(f'                    type_={self._get_sa_type(new_col)},')
                    lines.append(f'                    nullable={new_col.nullable})')
                
                # Add indexes
                for idx_name in table_diff.new_indexes:
                    lines.append(f'    op.create_index("{idx_name}", "{table_name}", ["column_name"])')
                
                # Drop indexes
                for idx_name in table_diff.dropped_indexes:
                    lines.append(f'    op.drop_index("{idx_name}", table_name="{table_name}")')
                
                lines.append('')
            
            # Drop tables
            for table_name in diff.dropped_tables:
                lines.append(f'    op.drop_table("{table_name}")')
        
        lines.append('')
        
        # Downgrade function
        lines.append('def downgrade() -> None:')
        lines.append('    """Downgrade database schema."""')
        
        if not self._has_changes(diff):
            lines.append('    pass')
        else:
            # Reverse operations for downgrade
            lines.append('    # Reverse the upgrade operations')
            lines.append('    # This is automatically generated - review before use')
            lines.append('    pass')
        
        return '\n'.join(lines)
    
    def _has_changes(self, diff: SchemaDiff) -> bool:
        """Check if diff has any changes."""
        return (
            diff.new_tables or 
            diff.dropped_tables or 
            diff.modified_tables
        )
    
    def _generate_column_definition(self, col: ColumnDefinition) -> str:
        """Generate SQLAlchemy column definition for migration."""
        type_str = self._get_sa_type(col)
        
        args = [f'sa.{type_str}']
        
        if col.foreign_key:
            args.append(f'sa.ForeignKey("{col.foreign_key}")')
        
        options = []
        if not col.nullable:
            options.append('nullable=False')
        if col.unique:
            options.append('unique=True')
        if col.default is not None:
            if isinstance(col.default, str):
                options.append(f'server_default="{col.default}"')
            elif isinstance(col.default, (int, float)):
                options.append(f"server_default=sa.text('{col.default}')")
            elif isinstance(col.default, bool):
                # Most SQL backends expect '1' or '0' for booleans
                options.append(f"server_default=sa.text('1')" if col.default else f"server_default=sa.text('0')")
            else:
                # Fallback: treat as string
                options.append(f'server_default="{col.default}"')
        if options:
            args.extend(options)
        
        return f'sa.Column("{col.name}", {", ".join(args)})'
    
    def _get_sa_type(self, col: ColumnDefinition) -> str:
        """Get SQLAlchemy type string for column."""
        if col.type == ColumnType.INTEGER:
            return 'Integer()'
        elif col.type == ColumnType.TEXT:
            if col.length:
                return f'String({col.length})'
            return 'Text()'
        elif col.type == ColumnType.REAL:
            return 'Float()'
        elif col.type == ColumnType.BOOLEAN:
            return 'Boolean()'
        elif col.type == ColumnType.DATETIME:
            return 'DateTime()'
        elif col.type == ColumnType.JSON:
            return 'JSON()'
        elif col.type == ColumnType.BLOB:
            return 'LargeBinary()'
        else:
            return 'Text()'


def create_migration_from_schema_files(
    old_schema_path: Path, 
    new_schema_path: Path, 
    message: str,
    alembic_config_path: Optional[Path] = None
) -> Path:
    """Create a migration file from two schema files."""
    
    # Load schemas
    old_schema = load_schema(old_schema_path)
    new_schema = load_schema(new_schema_path)
    
    # Generate migration
    generator = MigrationGenerator(alembic_config_path)
    diff = generator.compare_schemas(old_schema, new_schema)
    
    if not generator._has_changes(diff):
        print("No changes detected between schemas.")
        return None
    
    # Generate migration script
    script_content = generator.generate_migration_script(diff, message)
    
    # Write to migrations directory (simplified - in real use would use Alembic)
    migrations_dir = Path("migrations")
    migrations_dir.mkdir(exist_ok=True)
    
    timestamp = dt.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_message = "".join(c for c in message if c.isalnum() or c in "_- ").strip()
    safe_message = safe_message.replace(" ", "_").lower()
    
    migration_file = migrations_dir / f"{timestamp}_{safe_message}.py"
    
    with open(migration_file, 'w', encoding='utf-8') as f:
        f.write(script_content)
    
    print(f"Generated migration: {migration_file}")
    return migration_file


def update_models_from_schema(schema_path: Path, models_path: Path) -> bool:
    """Update existing models file based on new schema."""
    try:
        # Generate new models
        from .schema import generate_models_file
        generate_models_file(schema_path, models_path)
        print(f"Updated models file: {models_path}")
        return True
    except Exception as e:
        print(f"Failed to update models: {e}")
        return False