# Database Configuration Guide

This document explains how to configure database connections for the Media Scoring application.

## Overview

The application supports PostgreSQL database.

## Configuration Priority

Database configuration follows this priority order (highest to lowest):

1. **CLI Arguments** (`--database-url`, `--database-path`)
2. **Environment Variables** (`DATABASE_URL` or `MEDIA_DB_URL`)
3. **Configuration File** (`config/config.yml`)

## Environment Variables

### DATABASE_URL
Primary database environment variable. Supports full database URLs:

```bash
# PostgreSQL
export DATABASE_URL="postgresql://username:password@host:port/database"
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
```

### Data Mining Tool
```bash
# Use environment variable
DATABASE_URL="postgresql://user:pass@host/db" python tools/mine_data.py /media --enable-database

# Override with CLI argument
python tools/mine_data.py /media --enable-database --database-url "postgresql://user:pass@host/db"
```

## Docker Configuration

When using Docker Compose, set the `DATABASE_URL` in your `.env` file:

```bash
# config/.env
DATABASE_URL=postgresql://media_user:media_password@postgres:5432/media_scoring
```

The Docker setup automatically passes this to the application.

## Configuration Examples

### Production (PostgreSQL via Environment)
```bash
export DATABASE_URL="postgresql://app_user:secure_password@db.internal:5432/media_production"
python run.py --dir /media
```

### Testing Different Databases
```bash
# Test with PostgreSQL
DATABASE_URL="postgresql://test:test@localhost/test_db" python tools/mine_data.py /test_media --dry-run
```

## Troubleshooting

### Common Issues

1. **Connection refused errors**
   - Verify PostgreSQL server is running and accessible
   - Check hostname, port, username, and password in the URL
   - Ensure firewall allows connections to the database port

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


The application will create necessary tables automatically when connecting to a new PostgreSQL database.