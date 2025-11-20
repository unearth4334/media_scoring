# Repository Structure

This document describes the organization of files in this repository.

## Directory Structure

```
media_scoring/
├── app/                    # Main application code
│   ├── database/          # Database models and services
│   ├── routers/           # FastAPI route handlers
│   ├── services/          # Business logic
│   ├── static/            # Static assets (CSS, JS, images)
│   ├── templates/         # HTML templates
│   └── utils/             # Utility functions
├── config/                # Configuration files
├── docs/                  # Documentation files
├── examples/              # Example scripts and demos
├── media/                 # Production media directory (runtime)
├── migrations/            # Database migrations
├── scripts/               # Deployment and utility scripts
├── tests/                 # Test suite
│   └── fixtures/          # Test resources (images, videos, etc.)
└── tools/                 # CLI utilities
```

## File Organization

### Documentation (`docs/`)
All documentation files are organized in the `docs/` directory:
- Implementation guides and summaries
- Feature documentation (database, NSFW detection, ingestion, etc.)
- Architecture diagrams and proposals
- Development guides

### Test Resources (`tests/fixtures/`)
Test media files and test-related resources are stored in `tests/fixtures/`:
- Test images: `blue.jpg`, `green.jpeg`, `red.png`
- Test videos: `test.mp4`
- Test directories: `test_dir1/`, `test_dir2/`, `test_dir3/`
- Test results: `mining_test_results.html`

### Production Media (`media/`)
The `media/` directory is for runtime-generated content and user media:
- User-provided media files during development
- Auto-generated thumbnails (`.thumbnails_large/`)

Note: Test media files should NOT be placed in `media/` - use `tests/fixtures/` instead.

## Recent Changes

**2024-11-20**: Repository cleanup
- Moved 6 implementation documentation files from root to `docs/`
- Moved test resources from `media/` to `tests/fixtures/`
- Removed empty `authorized_keys` file
- Updated `.gitignore` to fix typo and clarify test fixture handling
