# Configuration

This directory contains configuration files for the media scoring application.

## Configuration Files

- `config.yml` - Main application configuration
- `schema.yml` - Database schema definition
- `.env.example` - Environment variables template
- `.env` - Environment variables (create from .env.example)

## Usage

### Main Configuration (config.yml)
Contains settings for:
- Media directory paths
- Server host and port
- File patterns
- UI theme settings
- Thumbnail generation options

### Environment Variables (.env)
Create from `.env.example` and customize:
```bash
cp config/.env.example config/.env
# Edit config/.env with your settings
```

### Schema Configuration (schema.yml)
Defines the database schema structure for:
- Media files table
- Keywords and metadata
- User scores and ratings

## Loading Configuration

The application automatically loads configuration from:
1. `config/config.yml` (main settings)
2. `config/.env` (environment overrides)
3. Command line arguments (highest priority)