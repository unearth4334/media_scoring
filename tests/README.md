# Tests

This directory contains all test files for the media scoring application.

## Test Files

- `test_database.py` - Database functionality tests
- `test_full_integration.py` - Full integration tests
- `test_mining_tool.py` - Data mining tool tests  
- `test_prompt_parser.py` - Prompt parsing tests
- `test_schema.py` - Database schema tests

## Running Tests

From the project root directory:

```bash
# Run all tests
python -m pytest tests/

# Run specific test file
python tests/test_schema.py

# Run with virtual environment
source .venv/bin/activate
python -m pytest tests/
```

## Test Requirements

All tests require the dependencies listed in `requirements.txt` to be installed.