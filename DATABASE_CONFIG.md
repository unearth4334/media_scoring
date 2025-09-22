# Database Configuration Guide

This document explains how to configure database connections for the Media Scoring application.

## Overview

The application supports both SQLite (for local development) and PostgreSQL (for production) databases. The system uses a priority-based configuration system to determine which database to use.

## Configuration Priority

Database configuration follows this priority order (highest to lowest):

1. **CLI Arguments** (`--database-url`, `--database-path`)
2. **Environment Variables** (`DATABASE_URL` or `MEDIA_DB_URL`)
3. **Configuration File** (`config/config.yml`)
4. **Default SQLite Fallback** (`<media_dir>/.scores/media.db`)

## Environment Variables

### DATABASE_URL
Primary database environment variable. Supports full database URLs:

```bash
# PostgreSQL
export DATABASE_URL="postgresql://username:password@host:port/database"

# SQLite (explicit)
export DATABASE_URL="sqlite:///path/to/database.db"
```

### MEDIA_DB_URL
Alternative database environment variable. Uses same format as `DATABASE_URL`.
If both are set, `DATABASE_URL` takes precedence.

```bash
export MEDIA_DB_URL="postgresql://media_user:password@db.example.com:5432/media_db"
```

## Command Line Usage

### Main Application
```bash
# Use environment variable
DATABASE_URL="postgresql://user:pass@host/db" python run.py --dir /media

# Override with CLI argument
python run.py --dir /media --database-url "postgresql://user:pass@host/db"

# Use SQLite explicitly
python run.py --dir /media --database-path "/custom/path/media.db"
```

### Data Mining Tool
```bash
# Use environment variable
DATABASE_URL="postgresql://user:pass@host/db" python tools/mine_data.py /media --enable-database

# Override with CLI argument
python tools/mine_data.py /media --enable-database --database-url "postgresql://user:pass@host/db"

# Use SQLite explicitly
python tools/mine_data.py /media --enable-database --database-path "/custom/path/media.db"
```

## Docker Configuration

When using Docker Compose, set the `DATABASE_URL` in your `.env` file:

```bash
# config/.env
DATABASE_URL=postgresql://media_user:media_password@postgres:5432/media_scoring
```

The Docker setup automatically passes this to the application.

## Configuration Examples

### Local Development (SQLite)
No configuration needed - SQLite is the default:
```bash
python run.py --dir /media
# Uses: sqlite:///media/.scores/media.db
```

### Production (PostgreSQL via Environment)
```bash
export DATABASE_URL="postgresql://app_user:secure_password@db.internal:5432/media_production"
python run.py --dir /media
```

### Testing Different Databases
```bash
# Test with PostgreSQL
DATABASE_URL="postgresql://test:test@localhost/test_db" python tools/mine_data.py /test_media --dry-run

# Test with SQLite in custom location
python tools/mine_data.py /test_media --database-path /tmp/test.db --dry-run
```

## Troubleshooting

### Common Issues

1. **SQLite being used instead of PostgreSQL**
   - Check that `DATABASE_URL` or `MEDIA_DB_URL` is set correctly
   - Verify the environment variable is available to the process
   - Use `--verbose` flag to see which database URL is being used

2. **Connection refused errors**
   - Verify PostgreSQL server is running and accessible
   - Check hostname, port, username, and password in the URL
   - Ensure firewall allows connections to the database port

3. **Permission denied for SQLite**
   - Ensure the media directory is writable
   - Check that `.scores` subdirectory can be created
   - Consider using `--database-path` with a writable location

### Debugging Database Configuration

Use these commands to debug database configuration:

```bash
# Check what database URL will be used (without connecting)
python test_database_config_validation.py

# Test actual database connections
python tests/test_database.py

# Verbose logging shows database initialization
python tools/mine_data.py /media --enable-database --verbose
```

## Security Notes

- Store database credentials in environment variables or secure configuration files
- Avoid putting credentials in command line arguments (visible in process lists)
- Use connection pooling and SSL for production PostgreSQL connections
- Regularly rotate database passwords and credentials

## Migration from SQLite to PostgreSQL

1. Set up PostgreSQL server and create database
2. Set `DATABASE_URL` environment variable
3. Restart the application - it will automatically use PostgreSQL
4. Existing SQLite data must be migrated manually if needed

The application will create necessary tables automatically when connecting to a new PostgreSQL database.