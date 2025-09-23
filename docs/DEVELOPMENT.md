# Database Quick Start Guide

## For Developers Building Upon the Database System

This guide helps developers understand and extend the database functionality in the Media Scoring application.

## Getting Started

### 1. Enable Database in Your Development Environment

```bash
# Start the application with database enabled
python run.py --enable-database --dir ./your-media-directory

# Or configure via config.yml
echo "enable_database: true" >> config.yml
```

### 2. Basic Database Operations

```python
from app.database import DatabaseService
from pathlib import Path

# Create a database service context
with DatabaseService() as db:
    # Add a media file to the database
    file_path = Path("example.png")
    media_file = db.get_or_create_media_file(file_path)
    
    # Update the score
    db.update_media_file_score(file_path, 5)
    
    # Add searchable keywords
    db.add_keywords(file_path, ["portrait", "anime", "detailed"], keyword_type="user")
    
    # Search for files
    results = db.search_by_keywords(["portrait"])
    print(f"Found {len(results)} files with 'portrait' keyword")
```

### 3. Test the New API Endpoints

```bash
# Search for files with keywords
curl -X POST http://localhost:7862/api/search/files \
  -H "Content-Type: application/json" \
  -d '{"keywords": ["portrait"], "min_score": 3}'

# Add keywords to a file
curl -X POST http://localhost:7862/api/search/keywords \
  -H "Content-Type: application/json" \
  -d '{"filename": "image.png", "keywords": ["art", "detailed"]}'

# Get database statistics
curl http://localhost:7862/api/search/stats

# Sync current directory to database
curl -X POST http://localhost:7862/api/search/sync
```

## Key Extension Points

### 1. Adding Custom Metadata Extractors

Create a new metadata extractor in `app/services/metadata.py`:

```python
def extract_custom_metadata(file_path: Path) -> Dict[str, Any]:
    """Extract custom metadata from your specific file types."""
    metadata = {}
    
    # Your custom extraction logic here
    if file_path.suffix.lower() == '.custom':
        # Extract custom information
        metadata['custom_field'] = 'custom_value'
    
    return metadata

# Register in extract_metadata function
def extract_metadata(file_path: Path) -> Dict[str, Any]:
    # ... existing code ...
    
    # Add your custom extractor
    if file_path.suffix.lower() == '.custom':
        metadata.update(extract_custom_metadata(file_path))
    
    return metadata
```

### 2. Adding New Database Fields

Extend the database models in `app/database/models.py`:

```python
class MediaMetadata(Base):
    # ... existing fields ...
    
    # Add your new fields
    custom_field = Column(String(256))
    processing_status = Column(String(50), default='pending')
    quality_score = Column(Float)
```

Then create a migration:

```bash
# Future: Use Alembic for migrations
alembic revision --autogenerate -m "Add custom fields"
alembic upgrade head
```

### 3. Custom Keyword Types

Add new keyword types for specialized tagging:

```python
# In your service code
with DatabaseService() as db:
    # Add different types of keywords
    db.add_keywords(file_path, ["cat", "dog"], keyword_type="detected_objects")
    db.add_keywords(file_path, ["happy", "sad"], keyword_type="emotions") 
    db.add_keywords(file_path, ["professional"], keyword_type="quality")
```

### 4. Advanced Search Features

Extend the search service for complex queries:

```python
class DatabaseService:
    def search_by_metadata(self, filters: Dict[str, Any]) -> List[MediaFile]:
        """Search files by metadata criteria."""
        query = self.session.query(MediaFile).join(MediaMetadata)
        
        if 'min_width' in filters:
            query = query.filter(MediaMetadata.width >= filters['min_width'])
        
        if 'model_name' in filters:
            query = query.filter(MediaMetadata.model_name.contains(filters['model_name']))
        
        return query.all()
    
    def search_similar_files(self, file_path: Path, similarity_threshold: float = 0.8) -> List[MediaFile]:
        """Find files with similar metadata."""
        # Implement similarity logic
        pass
```

### 5. Adding New API Endpoints

Create custom search endpoints in `app/routers/search.py`:

```python
@router.get("/advanced")
async def advanced_search(
    min_width: Optional[int] = None,
    max_width: Optional[int] = None,
    model_name: Optional[str] = None,
    has_prompt: Optional[bool] = None
):
    """Advanced search with multiple metadata criteria."""
    state = get_state()
    
    if not state.database_enabled:
        raise HTTPException(503, "Database functionality is disabled")
    
    with state.get_database_service() as db:
        # Build complex query
        query = db.session.query(MediaFile).join(MediaMetadata)
        
        if min_width:
            query = query.filter(MediaMetadata.width >= min_width)
        if max_width:
            query = query.filter(MediaMetadata.width <= max_width)
        if model_name:
            query = query.filter(MediaMetadata.model_name.contains(model_name))
        if has_prompt is not None:
            if has_prompt:
                query = query.filter(MediaMetadata.prompt.isnot(None))
            else:
                query = query.filter(MediaMetadata.prompt.is_(None))
        
        results = query.all()
        
        return {
            "results": [{"name": f.filename, "score": f.score} for f in results],
            "total": len(results)
        }
```

## Common Development Patterns

### 1. Safe Database Operations

Always use context managers for database operations:

```python
# Good: Automatic transaction handling
with DatabaseService() as db:
    db.update_media_file_score(file_path, 5)
    db.add_keywords(file_path, ["updated"])
    # Automatically commits or rolls back on exception

# Avoid: Manual session management
db = DatabaseService()
db.session = get_session()  # Don't do this
```

### 2. Error Handling

Handle database errors gracefully:

```python
def safe_database_operation(file_path: Path):
    state = get_state()
    
    if not state.database_enabled:
        return None  # Graceful degradation
    
    try:
        with state.get_database_service() as db:
            return db.get_or_create_media_file(file_path)
    except Exception as e:
        state.logger.error(f"Database operation failed: {e}")
        return None  # Don't crash the application
```

### 3. Performance Optimization

For bulk operations, use batch processing:

```python
def bulk_import_files(file_paths: List[Path]):
    with DatabaseService() as db:
        media_files = []
        for file_path in file_paths:
            media_file = db.get_or_create_media_file(file_path)
            media_files.append(media_file)
        
        # Batch commit happens automatically at context exit
        return media_files
```

### 4. Testing Database Code

```python
import tempfile
from app.database.engine import init_database

def test_database_operations():
    # Use temporary database for testing
    with tempfile.NamedTemporaryFile(suffix='.db') as tmp_db:
        init_database(Path(tmp_db.name))
        
        with DatabaseService() as db:
            # Test your database operations
            media_file = db.get_or_create_media_file(Path("test.png"))
            assert media_file.filename == "test.png"
```

## Integration Examples

### 1. Custom Workflow Analysis

```python
def analyze_comfyui_workflow(file_path: Path):
    """Extract detailed workflow information."""
    with DatabaseService() as db:
        metadata = db.get_media_metadata(file_path)
        
        if metadata and metadata.workflow_data:
            workflow = json.loads(metadata.workflow_data)
            
            # Extract node types
            node_types = [node.get('class_type') for node in workflow.values()]
            db.add_keywords(file_path, node_types, keyword_type="workflow_nodes")
            
            # Extract model information
            for node in workflow.values():
                if node.get('class_type') == 'CheckpointLoaderSimple':
                    model_name = node['inputs'].get('ckpt_name', '')
                    if model_name:
                        db.add_keywords(file_path, [model_name], keyword_type="models")
```

### 2. Automatic Quality Assessment

```python
def assess_image_quality(file_path: Path):
    """Automatically assess and tag image quality."""
    # Your quality assessment logic
    quality_metrics = analyze_image_quality(file_path)
    
    with DatabaseService() as db:
        # Store quality metrics
        metadata = {
            'quality_score': quality_metrics['overall_score'],
            'sharpness': quality_metrics['sharpness'],
            'noise_level': quality_metrics['noise']
        }
        db.store_media_metadata(file_path, metadata)
        
        # Add quality keywords
        if quality_metrics['overall_score'] > 0.8:
            db.add_keywords(file_path, ["high_quality"], keyword_type="quality")
        elif quality_metrics['overall_score'] < 0.3:
            db.add_keywords(file_path, ["low_quality"], keyword_type="quality")
```

### 3. Duplicate Detection

```python
def find_duplicates():
    """Find potential duplicate files."""
    with DatabaseService() as db:
        # Group by dimensions and file size
        files = db.session.query(MediaFile).join(MediaMetadata).all()
        
        duplicates = {}
        for file in files:
            if file.media_metadata:
                key = (file.file_size, file.media_metadata.width, file.media_metadata.height)
                if key not in duplicates:
                    duplicates[key] = []
                duplicates[key].append(file)
        
        # Return groups with multiple files
        return {k: v for k, v in duplicates.items() if len(v) > 1}
```

## Debugging Tips

### 1. Enable SQL Logging

For development, enable SQL query logging in `app/database/engine.py`:

```python
_engine = create_engine(
    database_url,
    echo=True,  # Enable SQL logging
    # ... other parameters
)
```

### 2. Inspect Database Content

```bash
# Connect to the database directly
psql $DATABASE_URL

# Useful queries
\dt  -- List tables
SELECT COUNT(*) FROM media_files;
SELECT keyword_type, COUNT(*) FROM media_keywords GROUP BY keyword_type;
SELECT * FROM media_metadata WHERE prompt IS NOT NULL LIMIT 5;
```

### 3. Monitor Performance

```python
import time

def timed_database_operation():
    start_time = time.time()
    
    with DatabaseService() as db:
        results = db.search_by_keywords(["portrait"])
    
    elapsed = time.time() - start_time
    print(f"Search took {elapsed:.2f} seconds, found {len(results)} results")
```

## Next Steps

1. **Study the existing code** in `app/database/` to understand the current implementation
2. **Try the API endpoints** to see how search and metadata work
3. **Add custom metadata extraction** for your specific file types
4. **Extend the search functionality** with new query types
5. **Create specialized keyword types** for your domain
6. **Build UI components** that leverage the search capabilities

The database system is designed to be extensible while maintaining backward compatibility. Start with small additions and gradually build more complex features as needed.

## Need Help?

- Check `DATABASE.md` for comprehensive architecture documentation
- Look at existing code in `app/database/` for patterns
- Test with small examples before implementing large features
- Use the API endpoints to understand data flow