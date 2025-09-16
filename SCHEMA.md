# Database Schema System

A comprehensive YAML-based database schema definition and management system for the Media Scoring application. This system allows you to define database structure in YAML format and automatically generate SQLAlchemy models and migration scripts.

## Overview

The schema system provides:
- **YAML Schema Definition**: Define database structure in human-readable YAML format
- **Model Generation**: Automatically generate SQLAlchemy models from schema
- **Migration Support**: Create migration scripts for schema changes
- **Validation**: Comprehensive schema validation and error checking
- **CLI Tools**: Command-line interface for all schema operations

## Quick Start

### 1. Define Your Schema

Create a `schema.yml` file with your database structure:

```yaml
database: my_application
version: 1.0
description: "Application database schema"

tables:
  users:
    description: "User accounts"
    columns:
      - name: id
        type: integer
        primary_key: true
        autoincrement: true
      - name: username
        type: text
        length: 50
        nullable: false
        unique: true
      - name: email
        type: text
        length: 255
        nullable: false
      - name: created_at
        type: datetime
        default: CURRENT_TIMESTAMP
    
    indexes:
      - name: idx_users_email
        columns: [email]
        unique: true
```

### 2. Validate Schema

```bash
python schema_cli.py validate schema.yml
```

### 3. Generate Models

```bash
python schema_cli.py generate schema.yml --output models.py
```

### 4. View Schema Information

```bash
python schema_cli.py info schema.yml
```

## Schema Format Reference

### Database-Level Settings

```yaml
database: string          # Database name
version: string          # Schema version (e.g., "1.0", "2.1.3")
description: string      # Optional description
```

### Table Definition

```yaml
tables:
  table_name:
    description: string           # Table description
    columns: []                   # List of column definitions
    indexes: []                   # List of index definitions (optional)
    constraints: []               # List of constraint definitions (optional)
```

### Column Definition

```yaml
columns:
  - name: string                 # Column name (required)
    type: string                 # Data type (required)
    primary_key: boolean         # Is primary key (default: false)
    autoincrement: boolean       # Auto-increment (default: false)
    nullable: boolean            # Can be null (default: true)
    unique: boolean              # Unique constraint (default: false)
    default: any                 # Default value (optional)
    on_update: string           # On update value (optional)
    foreign_key: string         # Foreign key reference (optional)
    length: integer             # Length for text types (optional)
    note: string                # Comment/documentation (optional)
```

### Supported Data Types

| Type | Description | Example |
|------|-------------|---------|
| `integer` | Integer numbers | `42` |
| `bigint` | Large integers | `9223372036854775807` |
| `text` | Variable length text | `"Hello World"` |
| `real` | Floating point numbers | `3.14159` |
| `boolean` | True/false values | `true`, `false` |
| `datetime` | Date and time | `2024-01-15 10:30:00` |
| `json` | JSON data | `{"key": "value"}` |
| `blob` | Binary data | Binary content |

### Index Definition

```yaml
indexes:
  - name: string                # Index name (required)
    columns: [string]           # List of column names (required)
    unique: boolean             # Unique index (default: false)
```

### Constraint Definition

```yaml
constraints:
  - name: string                # Constraint name (required)
    type: string                # Constraint type: unique, check, foreign_key
    columns: [string]           # List of column names (required)
    reference_table: string     # For foreign key constraints
    reference_columns: [string] # For foreign key constraints  
    condition: string           # For check constraints
```

## Special Values

### Default Values

- `CURRENT_TIMESTAMP`: Sets default to current timestamp
- Literal values: `0`, `"default"`, `true`, `false`

### Foreign Key References

Format: `table_name.column_name`

Example: `users.id`

## CLI Reference

### Validate Schema

```bash
python schema_cli.py validate <schema_file>
```

Validates a schema file for correctness and reports any errors.

### Generate Models

```bash
python schema_cli.py generate <schema_file> [--output <output_file>]
```

Generates SQLAlchemy models from schema. Default output: `generated_models.py`

### Show Schema Info

```bash
python schema_cli.py info <schema_file>
```

Displays detailed information about the schema structure.

### Compare Schemas

```bash
python schema_cli.py compare <old_schema> <new_schema>
```

Compares two schema files and shows differences.

### Create Migration

```bash
python schema_cli.py migrate <old_schema> <new_schema> --message "Description"
```

Creates a migration script between two schema versions.

### Update Models

```bash
python schema_cli.py update <schema_file> [--models <models_file>]
```

Updates an existing models file from schema.

## Configuration Integration

Add schema settings to your `config.yml`:

```yaml
# Schema management settings
schema_file: schema.yml       # YAML file defining database schema structure
auto_migrate: false           # Automatically apply schema migrations
validate_schema: true         # Validate schema file on startup
```

## Example: Complete Media Application Schema

Here's the complete schema for the media scoring application:

```yaml
database: media_scoring
version: 1.0
description: "Database schema for media scoring application"

tables:
  media_files:
    description: "Primary entity representing media files in the system"
    columns:
      - name: id
        type: integer
        primary_key: true
        autoincrement: true
      - name: filename
        type: text
        nullable: false
        length: 512
      - name: directory
        type: text
        nullable: false
        length: 1024
      - name: file_path
        type: text
        nullable: false
        unique: true
        length: 1536
      - name: file_size
        type: integer
      - name: file_type
        type: text
        length: 50
        note: "video, image"
      - name: score
        type: integer
        default: 0
        note: "-1 to 5 (-1=rejected, 0=unrated, 1-5=stars)"
      - name: created_at
        type: datetime
        default: CURRENT_TIMESTAMP
      - name: updated_at
        type: datetime
        default: CURRENT_TIMESTAMP
        on_update: CURRENT_TIMESTAMP

    indexes:
      - name: idx_media_file_path
        columns: [file_path]
        unique: true
      - name: idx_media_score
        columns: [score]

  media_keywords:
    description: "Searchable keywords and tags associated with media files"
    columns:
      - name: id
        type: integer
        primary_key: true
        autoincrement: true
      - name: media_file_id
        type: integer
        nullable: false
        foreign_key: media_files.id
      - name: keyword
        type: text
        nullable: false
        length: 256
      - name: keyword_type
        type: text
        length: 50
        default: user
        note: "user, prompt, auto, workflow"
      - name: created_at
        type: datetime
        default: CURRENT_TIMESTAMP

    indexes:
      - name: idx_keyword_media_file
        columns: [media_file_id]
      - name: idx_keyword_search
        columns: [keyword]
    
    constraints:
      - name: uq_media_keyword
        type: unique
        columns: [media_file_id, keyword, keyword_type]
```

## Migration Workflow

### 1. Update Schema

Modify your `schema.yml` file with desired changes.

### 2. Generate Migration

```bash
python schema_cli.py migrate old_schema.yml schema.yml --message "Add new fields"
```

### 3. Review Migration

Check the generated migration file in `migrations/` directory.

### 4. Apply Migration

Use Alembic to apply the migration:

```bash
alembic upgrade head
```

### 5. Update Models

```bash
python schema_cli.py update schema.yml --models app/database/models.py
```

## Best Practices

### Schema Design

1. **Use descriptive names** for tables and columns
2. **Add comments** using the `note` field for complex fields
3. **Define proper indexes** for query performance
4. **Use foreign keys** to maintain referential integrity
5. **Version your schema** files for change tracking

### Development Workflow

1. **Validate early** - always validate schema before committing
2. **Test migrations** on development database first
3. **Keep migrations small** - prefer incremental changes
4. **Document changes** with descriptive migration messages
5. **Backup production** databases before applying migrations

### Performance Considerations

1. **Index frequently queried columns**
2. **Use appropriate data types** (e.g., `integer` vs `bigint`)
3. **Consider column length limits** for text fields
4. **Add constraints** to ensure data quality
5. **Monitor migration time** for large tables

## Troubleshooting

### Common Errors

**Schema validation failed**
- Check YAML syntax with a YAML validator
- Ensure all required fields are present
- Verify foreign key references exist

**Model generation failed**
- Check for Python reserved words in column names
- Verify data types are supported
- Ensure foreign key format is correct

**Migration creation failed**
- Verify both schema files are valid
- Check that table/column names match between versions
- Ensure you have write permissions to migrations directory

### Debug Mode

Enable detailed logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Getting Help

- Check the CLI help: `python schema_cli.py --help`
- Validate schema: `python schema_cli.py validate schema.yml`
- Run tests: `python test_schema.py`

## API Reference

For programmatic access, use the schema API:

```python
from app.database.schema import load_schema, generate_models_from_schema

# Load schema
schema = load_schema("schema.yml")

# Generate models
models = generate_models_from_schema("schema.yml")

# Access a specific model
UserModel = models['users']
```

## Integration with Existing Code

The schema system is designed to work alongside existing SQLAlchemy models:

```python
from app.database.schema_integration import initialize_schema_system
from app.settings import Settings

settings = Settings.load_from_yaml()
schema_integration = initialize_schema_system(settings)

# Use generated models
models = schema_integration.get_all_models()
MediaFile = models.get('media_files')
```