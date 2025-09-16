"""Database schema management system for generating SQLAlchemy models from YAML definitions."""

import datetime as dt
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
import yaml
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Float, Boolean, JSON, LargeBinary,
    ForeignKey, Index, UniqueConstraint, CheckConstraint, text
)
from sqlalchemy.ext.declarative import declarative_base


class ColumnType(Enum):
    """Supported column types in schema definitions."""
    INTEGER = "integer"
    BIGINT = "bigint"
    TEXT = "text"
    REAL = "real"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    JSON = "json"
    BLOB = "blob"


@dataclass
class ColumnDefinition:
    """Definition of a database column from YAML schema."""
    name: str
    type: ColumnType
    primary_key: bool = False
    autoincrement: bool = False
    nullable: bool = True
    unique: bool = False
    default: Optional[Union[str, int, float, bool]] = None
    on_update: Optional[str] = None
    foreign_key: Optional[str] = None
    length: Optional[int] = None
    note: Optional[str] = None


@dataclass
class IndexDefinition:
    """Definition of a database index from YAML schema."""
    name: str
    columns: List[str]
    unique: bool = False


@dataclass
class ConstraintDefinition:
    """Definition of a database constraint from YAML schema."""
    name: str
    type: str  # unique, check, foreign_key
    columns: List[str]
    reference_table: Optional[str] = None
    reference_columns: Optional[List[str]] = None
    condition: Optional[str] = None


@dataclass
class TableDefinition:
    """Definition of a database table from YAML schema."""
    name: str
    description: str
    columns: List[ColumnDefinition] = field(default_factory=list)
    indexes: List[IndexDefinition] = field(default_factory=list)
    constraints: List[ConstraintDefinition] = field(default_factory=list)


@dataclass
class DatabaseSchema:
    """Complete database schema from YAML definition."""
    database: str
    version: str
    description: str = ""
    tables: Dict[str, TableDefinition] = field(default_factory=dict)


class SchemaParser:
    """Parser for YAML database schema files."""
    
    def __init__(self):
        self.type_mapping = {
            ColumnType.INTEGER: Integer,
            ColumnType.BIGINT: Integer,  # SQLAlchemy uses Integer for both
            ColumnType.TEXT: Text,
            ColumnType.REAL: Float,
            ColumnType.BOOLEAN: Boolean,
            ColumnType.DATETIME: DateTime,
            ColumnType.JSON: JSON,
            ColumnType.BLOB: LargeBinary,
        }
    
    def parse_file(self, schema_path: Path) -> DatabaseSchema:
        """Parse a YAML schema file into a DatabaseSchema object."""
        if not schema_path.exists():
            raise FileNotFoundError(f"Schema file not found: {schema_path}")
        
        with open(schema_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        return self.parse_dict(data)
    
    def parse_dict(self, data: Dict[str, Any]) -> DatabaseSchema:
        """Parse a dictionary containing schema data."""
        schema = DatabaseSchema(
            database=data.get('database', ''),
            version=str(data.get('version', '1.0')),
            description=data.get('description', '')
        )
        
        tables_data = data.get('tables', {})
        for table_name, table_data in tables_data.items():
            schema.tables[table_name] = self._parse_table(table_name, table_data)
        
        return schema
    
    def _parse_table(self, name: str, data: Dict[str, Any]) -> TableDefinition:
        """Parse table definition from YAML data."""
        table = TableDefinition(
            name=name,
            description=data.get('description', '')
        )
        
        # Parse columns
        columns_data = data.get('columns', [])
        for col_data in columns_data:
            table.columns.append(self._parse_column(col_data))
        
        # Parse indexes
        indexes_data = data.get('indexes', [])
        for idx_data in indexes_data:
            table.indexes.append(self._parse_index(idx_data))
        
        # Parse constraints
        constraints_data = data.get('constraints', [])
        for const_data in constraints_data:
            table.constraints.append(self._parse_constraint(const_data))
        
        return table
    
    def _parse_column(self, data: Dict[str, Any]) -> ColumnDefinition:
        """Parse column definition from YAML data."""
        col_type_str = data.get('type', 'text').lower()
        try:
            col_type = ColumnType(col_type_str)
        except ValueError:
            raise ValueError(f"Unsupported column type: {col_type_str}")
        
        return ColumnDefinition(
            name=data['name'],
            type=col_type,
            primary_key=data.get('primary_key', False),
            autoincrement=data.get('autoincrement', False),
            nullable=data.get('nullable', True),
            unique=data.get('unique', False),
            default=data.get('default'),
            on_update=data.get('on_update'),
            foreign_key=data.get('foreign_key'),
            length=data.get('length'),
            note=data.get('note')
        )
    
    def _parse_index(self, data: Dict[str, Any]) -> IndexDefinition:
        """Parse index definition from YAML data."""
        return IndexDefinition(
            name=data['name'],
            columns=data['columns'],
            unique=data.get('unique', False)
        )
    
    def _parse_constraint(self, data: Dict[str, Any]) -> ConstraintDefinition:
        """Parse constraint definition from YAML data."""
        return ConstraintDefinition(
            name=data['name'],
            type=data['type'],
            columns=data['columns'],
            reference_table=data.get('reference_table'),
            reference_columns=data.get('reference_columns'),
            condition=data.get('condition')
        )


class ModelGenerator:
    """Generator for SQLAlchemy models from parsed schema."""
    
    def __init__(self, base_class=None):
        self.Base = base_class or declarative_base()
        self.parser = SchemaParser()
    
    def generate_models(self, schema: DatabaseSchema) -> Dict[str, type]:
        """Generate SQLAlchemy model classes from schema."""
        models = {}
        
        for table_name, table_def in schema.tables.items():
            model_class = self._create_model_class(table_def)
            models[table_name] = model_class
        
        return models
    
    def _create_model_class(self, table_def: TableDefinition) -> type:
        """Create a SQLAlchemy model class from table definition."""
        # Create class attributes dictionary
        attrs = {
            '__tablename__': table_def.name,
            '__doc__': table_def.description
        }
        
        # Add columns
        for col_def in table_def.columns:
            attrs[col_def.name] = self._create_column(col_def)
        
        # Add indexes and constraints to __table_args__
        table_args = []
        
        # Add indexes
        for idx_def in table_def.indexes:
            index = Index(idx_def.name, *idx_def.columns, unique=idx_def.unique)
            table_args.append(index)
        
        # Add constraints
        for const_def in table_def.constraints:
            if const_def.type == 'unique':
                constraint = UniqueConstraint(*const_def.columns, name=const_def.name)
                table_args.append(constraint)
            elif const_def.type == 'check':
                constraint = CheckConstraint(const_def.condition, name=const_def.name)
                table_args.append(constraint)
        
        if table_args:
            attrs['__table_args__'] = tuple(table_args)
        
        # Create class name (convert snake_case to PascalCase)
        class_name = ''.join(word.capitalize() for word in table_def.name.split('_'))
        
        # Create the model class
        model_class = type(class_name, (self.Base,), attrs)
        
        return model_class
    
    def _create_column(self, col_def: ColumnDefinition) -> Column:
        """Create a SQLAlchemy Column from column definition."""
        # Get base SQLAlchemy type
        if col_def.type == ColumnType.TEXT and col_def.length:
            col_type = String(col_def.length)
        else:
            col_type = self.parser.type_mapping[col_def.type]()
        
        # Handle foreign key
        foreign_key = None
        if col_def.foreign_key:
            foreign_key = ForeignKey(col_def.foreign_key)
        
        # Handle default values
        default = col_def.default
        if default == "CURRENT_TIMESTAMP":
            default = dt.datetime.utcnow
        elif col_def.type == ColumnType.DATETIME and default:
            if default == "CURRENT_TIMESTAMP":
                default = dt.datetime.utcnow
        
        # Handle on_update
        onupdate = None
        if col_def.on_update == "CURRENT_TIMESTAMP":
            onupdate = dt.datetime.utcnow
        
        return Column(
            col_type,
            foreign_key,
            primary_key=col_def.primary_key,
            autoincrement=col_def.autoincrement,
            nullable=col_def.nullable,
            unique=col_def.unique,
            default=default,
            onupdate=onupdate
        )
    
    def generate_model_file(self, schema: DatabaseSchema, output_path: Path) -> None:
        """Generate a Python file containing the SQLAlchemy models."""
        # Generate imports and base class
        content = []
        content.append('"""Generated database models from YAML schema."""')
        content.append('')
        content.append('import datetime as dt')
        content.append('from sqlalchemy import (')
        content.append('    Column, Integer, String, Text, DateTime, Float, Boolean, JSON, LargeBinary,')
        content.append('    ForeignKey, Index, UniqueConstraint, CheckConstraint')
        content.append(')')
        content.append('from sqlalchemy.ext.declarative import declarative_base')
        content.append('from sqlalchemy.orm import relationship')
        content.append('')
        content.append('Base = declarative_base()')
        content.append('')
        
        # Generate each model class
        for table_name, table_def in schema.tables.items():
            class_code = self._generate_class_code(table_def)
            content.extend(class_code)
            content.append('')
        
        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(content))
    
    def _generate_class_code(self, table_def: TableDefinition) -> List[str]:
        """Generate Python code for a model class."""
        lines = []
        class_name = ''.join(word.capitalize() for word in table_def.name.split('_'))
        
        # Class definition
        lines.append(f'class {class_name}(Base):')
        lines.append(f'    """{table_def.description}"""')
        lines.append(f'    __tablename__ = "{table_def.name}"')
        lines.append('')
        
        # Add columns
        for col_def in table_def.columns:
            col_line = self._generate_column_code(col_def)
            lines.append(f'    {col_line}')
        
        # Add __table_args__ if needed
        if table_def.indexes or table_def.constraints:
            lines.append('')
            lines.append('    __table_args__ = (')
            
            # Add indexes
            for idx_def in table_def.indexes:
                unique_str = ', unique=True' if idx_def.unique else ''
                columns_str = "', '".join(idx_def.columns)
                lines.append(f"        Index('{idx_def.name}', '{columns_str}'{unique_str}),")
            
            # Add constraints
            for const_def in table_def.constraints:
                if const_def.type == 'unique':
                    columns_str = "', '".join(const_def.columns)
                    lines.append(f"        UniqueConstraint('{columns_str}', name='{const_def.name}'),")
            
            lines.append('    )')
        
        # Add __repr__ method
        lines.append('')
        lines.append(f'    def __repr__(self):')
        pk_cols = [col.name for col in table_def.columns if col.primary_key]
        if pk_cols:
            pk_repr = ', '.join(f'{col}={{self.{col}}}' for col in pk_cols[:2])
            lines.append(f'        return f"<{class_name}({pk_repr})>"')
        else:
            lines.append(f'        return f"<{class_name}()>"')
        
        return lines
    
    def _generate_column_code(self, col_def: ColumnDefinition) -> str:
        """Generate Python code for a column definition."""
        # Base type
        if col_def.type == ColumnType.TEXT and col_def.length:
            type_str = f'String({col_def.length})'
        elif col_def.type == ColumnType.INTEGER:
            type_str = 'Integer'
        elif col_def.type == ColumnType.TEXT:
            type_str = 'Text'
        elif col_def.type == ColumnType.REAL:
            type_str = 'Float'
        elif col_def.type == ColumnType.BOOLEAN:
            type_str = 'Boolean'
        elif col_def.type == ColumnType.DATETIME:
            type_str = 'DateTime'
        elif col_def.type == ColumnType.JSON:
            type_str = 'JSON'
        elif col_def.type == ColumnType.BLOB:
            type_str = 'LargeBinary'
        else:
            type_str = 'Text'  # fallback
        
        # Build column arguments
        args = [type_str]
        
        # Foreign key
        if col_def.foreign_key:
            args.append(f"ForeignKey('{col_def.foreign_key}')")
        
        # Other options
        options = []
        if col_def.primary_key:
            options.append('primary_key=True')
        if col_def.autoincrement:
            options.append('autoincrement=True')
        if not col_def.nullable:
            options.append('nullable=False')
        if col_def.unique:
            options.append('unique=True')
        if col_def.default is not None:
            if col_def.default == "CURRENT_TIMESTAMP":
                options.append('default=dt.datetime.utcnow')
            elif isinstance(col_def.default, str) and col_def.default != "CURRENT_TIMESTAMP":
                options.append(f"default='{col_def.default}'")
            else:
                options.append(f'default={col_def.default}')
        if col_def.on_update == "CURRENT_TIMESTAMP":
            options.append('onupdate=dt.datetime.utcnow')
        
        args.extend(options)
        args_str = ', '.join(args)
        
        result = f"{col_def.name} = Column({args_str})"
        
        # Add comment if present
        if col_def.note:
            result += f"  # {col_def.note}"
        
        return result


def load_schema(schema_path: Union[str, Path]) -> DatabaseSchema:
    """Load database schema from YAML file."""
    parser = SchemaParser()
    return parser.parse_file(Path(schema_path))


def generate_models_from_schema(schema_path: Union[str, Path], base_class=None) -> Dict[str, type]:
    """Generate SQLAlchemy models from YAML schema file."""
    schema = load_schema(schema_path)
    generator = ModelGenerator(base_class)
    return generator.generate_models(schema)


def generate_models_file(schema_path: Union[str, Path], output_path: Union[str, Path]) -> None:
    """Generate Python file with SQLAlchemy models from YAML schema."""
    schema = load_schema(schema_path)
    generator = ModelGenerator()
    generator.generate_model_file(schema, Path(output_path))