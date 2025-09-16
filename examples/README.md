# Examples

This directory contains example files and demonstrations for the media scoring application.

## Example Files

- `schema_example.py` - Database schema usage examples
- `demo_mining_results.html` - Sample mining results display

## Usage

### Schema Example
Demonstrates how to use the database schema system:
```bash
python examples/schema_example.py
```

This example shows:
- Loading schema from YAML files
- Generating SQLAlchemy models
- Validating schema definitions
- Creating database tables

### Demo Mining Results
Static HTML file showing sample output from the data mining tool. Open in a web browser to view:
```bash
# Open in browser
open examples/demo_mining_results.html
# or
firefox examples/demo_mining_results.html
```

## Purpose

These examples help developers understand:
- How to use the various components
- Expected input/output formats
- Integration patterns
- Best practices for extending the system