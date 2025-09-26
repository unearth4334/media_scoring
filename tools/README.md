# Tools

This directory contains CLI tools and utilities for the media scoring application.

## Tool Files

- `ingest_data.py` - Data ingesting and extraction tool
- `schema_cli.py` - Database schema management CLI
- `extract_comfyui_workflow.py` - ComfyUI workflow extraction
- `read_config.py` - Configuration file reader utility

## Usage

### Data Ingesting Tool
Extract metadata from existing media archives:
```bash
python tools/ingest_data.py --help
python tools/ingest_data.py /path/to/archive --pattern "*.png|*.jpg"
```

### Schema CLI
Manage database schemas:
```bash
python tools/schema_cli.py validate config/schema.yml
python tools/schema_cli.py generate config/schema.yml --output models.py
```

### Config Reader
Read configuration files in various formats:
```bash
python tools/read_config.py --file config/config.yml --format json
python tools/read_config.py --file config/config.yml --format sh
```

### ComfyUI Workflow Extractor
Extract workflows from ComfyUI generated images:
```bash
python tools/extract_comfyui_workflow.py image.png
```

## Dependencies

All tools require the main project dependencies from `requirements.txt`.