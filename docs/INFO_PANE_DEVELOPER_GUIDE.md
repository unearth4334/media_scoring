# Info Pane Developer Guide

## Overview
This guide explains how to extend the info pane functionality by adding new information categories. The info pane displays detailed information about media files in a configurable overlay interface.

## Architecture

The info pane system consists of three main components:

1. **Configuration** (`config/config.yml`) - Defines available categories
2. **Backend API** (`app/routers/media.py`) - Gathers and provides data
3. **Frontend** (`app/static/js/app.js` + CSS) - Displays formatted information

## Adding a New Category

### Step 1: Configuration

Add your new category to `config/config.yml`:

```yaml
info_pane:
  enabled: true
  categories:
    - filename
    - file_size
    # ... existing categories ...
    - your_new_category  # Add your category here with a comment
```

**Naming Convention:**
- Use lowercase with underscores (snake_case)
- Be descriptive but concise
- Examples: `creation_date`, `frame_rate`, `color_profile`

### Step 2: Backend Implementation

#### 2.1 Gather the Data

In `app/routers/media.py`, locate the `get_media_info()` function and add code to gather your data:

```python
@router.get("/info/{name:path}")
def get_media_info(name: str):
    # ... existing code ...
    
    # Add your new category data gathering
    if ext in {".png", ".jpg", ".jpeg"}:
        try:
            # Example: Getting color profile
            with Image.open(target) as im:
                if hasattr(im, 'info') and 'icc_profile' in im.info:
                    info["color_profile"] = "Embedded ICC Profile"
                else:
                    info["color_profile"] = "sRGB (default)"
        except Exception as e:
            state.logger.error(f"Failed to get color profile: {e}")
    
    return info
```

#### 2.2 Data Format Guidelines

**Simple Values:**
```python
info["your_category"] = "simple string value"
info["your_category"] = 12345  # numeric value
info["your_category"] = True  # boolean
```

**Complex Values (dimensions, coordinates, etc.):**
```python
info["your_category"] = {
    "width": 1920,
    "height": 1080
}
```

**Lists:**
```python
info["your_category"] = ["item1", "item2", "item3"]
```

**Nested Metadata:**
```python
if "metadata" not in info:
    info["metadata"] = {}
info["metadata"]["your_section"] = {
    "key1": "value1",
    "key2": "value2"
}
```

### Step 3: Frontend Display Logic

#### 3.1 Add Formatter Function (if needed)

In `app/static/js/app.js`, add a formatter for your data type:

```javascript
// Format your new category
function formatYourCategory(value) {
  if (!value) return 'N/A';
  // Add your formatting logic
  return formattedValue;
}
```

**Common Formatter Patterns:**

```javascript
// Percentage formatter
function formatPercentage(value) {
  return `${(value * 100).toFixed(1)}%`;
}

// Temperature formatter
function formatTemperature(value, unit = 'C') {
  return `${value}°${unit}`;
}

// List formatter
function formatList(items) {
  return items.join(', ');
}

// Coordinate formatter
function formatCoordinates(lat, lon) {
  return `${lat.toFixed(6)}, ${lon.toFixed(6)}`;
}
```

#### 3.2 Add Display Case

In the `populateInfoPane()` function, add a case for your category:

```javascript
function populateInfoPane(mediaData) {
  // ... existing code ...
  
  const categories = [
    // ... existing categories ...
    'your_new_category'
  ];
  
  for (const category of categories) {
    // ... existing code ...
    
    switch (category) {
      // ... existing cases ...
      
      case 'your_new_category':
        label = 'Your Category Label';  // Human-readable label
        value = formatYourCategory(mediaData.your_new_category);
        break;
      
      // If it's a complex nested object:
      case 'your_complex_category':
        if (mediaData.your_complex_category) {
          // Option 1: Format as string
          value = `${mediaData.your_complex_category.field1} × ${mediaData.your_complex_category.field2}`;
          
          // Option 2: Add to metadata section for expandable view
          if (!mediaData.metadata) mediaData.metadata = {};
          mediaData.metadata.your_section = mediaData.your_complex_category;
          continue;
        } else {
          continue;  // Skip if not available
        }
        break;
    }
  }
}
```

### Step 4: Special Display Types

#### Custom Rendering

For categories that need special HTML rendering:

```javascript
case 'your_special_category':
  const item = document.createElement('div');
  item.className = 'info-item';
  
  const labelDiv = document.createElement('div');
  labelDiv.className = 'info-label';
  labelDiv.textContent = 'Your Label';
  
  const valueDiv = document.createElement('div');
  valueDiv.className = 'info-value';
  // Add custom HTML
  valueDiv.innerHTML = `<div class="custom-display">...</div>`;
  
  item.appendChild(labelDiv);
  item.appendChild(valueDiv);
  content.appendChild(item);
  continue;  // Skip default rendering
```

#### Expandable Metadata Section

For categories with lots of detailed information:

```javascript
case 'your_detailed_category':
  if (mediaData.your_detailed_category) {
    // Add to metadata for expandable view
    if (!mediaData.metadata) {
      mediaData.metadata = {};
    }
    mediaData.metadata.your_section = mediaData.your_detailed_category;
  }
  continue;  // Don't show in main list
```

The data will automatically appear as an expandable section in the metadata area.

## Data Type Handling

### Handling Missing/Null Data

Always check for missing data and handle gracefully:

```javascript
case 'your_category':
  if (!mediaData.your_category) {
    continue;  // Skip entirely (recommended)
    // OR
    value = 'N/A';  // Show as Not Available
    // OR
    value = 'Unknown';  // Show as Unknown
  } else {
    value = formatYourCategory(mediaData.your_category);
  }
  break;
```

### Conditional Categories

For categories that only apply to certain file types:

```javascript
case 'frame_rate':
  if (mediaData.frame_rate) {
    value = `${Math.round(mediaData.frame_rate)} fps`;
  } else {
    continue;  // Skip if not a video
  }
  break;
```

### Arrays and Lists

```javascript
case 'tags':
  if (mediaData.tags && Array.isArray(mediaData.tags)) {
    value = mediaData.tags.join(', ');
  } else {
    continue;
  }
  break;
```

## CSS Styling

### Adding Custom Styles

If your category needs special styling, add CSS to `app/static/themes/style_default.css`:

```css
/* Custom category styling */
.info-value-your-category {
  background: rgba(0, 188, 212, 0.1);
  padding: 8px;
  border-radius: 4px;
  font-family: monospace;
}
```

Apply the class in JavaScript:

```javascript
valueDiv.className = 'info-value info-value-your-category';
```

### Icon Support

Add icons to your category:

```javascript
const item = createInfoItem(label, value);
const icon = document.createElement('span');
icon.textContent = '📊';  // Your icon
icon.style.marginRight = '8px';
item.querySelector('.info-label').prepend(icon);
content.appendChild(item);
```

## Testing Your Category

### 1. Backend Testing

Test that your endpoint returns the correct data:

```bash
# Test the info endpoint
curl http://localhost:7862/api/media/info/your_test_file.jpg | jq '.your_new_category'
```

### 2. Frontend Testing

1. Open the web interface
2. Select a media file
3. Click the "..." menu button
4. Click "View Info"
5. Verify your category appears with correct formatting

### 3. Edge Cases to Test

- Files without your category data (should skip or show N/A)
- Very long values (should wrap or truncate properly)
- Special characters in values
- Different file types (images vs videos)
- Missing or corrupted data

## Best Practices

### 1. Performance

- **Lazy Load**: Only fetch data when info pane is opened
- **Cache**: Store fetched data in `currentMediaInfo`
- **Debounce**: Don't fetch on rapid file switching

### 2. Error Handling

Always wrap data gathering in try-catch:

```python
try:
    info["your_category"] = get_your_data()
except Exception as e:
    state.logger.error(f"Failed to get your_category: {e}")
    # Don't add to info, let frontend skip it
```

### 3. User Experience

- **Readable Labels**: Use proper capitalization and spacing
- **Appropriate Units**: Include units (MB, fps, pixels, etc.)
- **Sensible Defaults**: Use 'N/A' or skip missing data
- **Tooltips**: Add titles for technical terms

### 4. Configuration

- **Optional by Default**: New categories should be optional
- **Document**: Add comments in config.yml explaining what the category shows

## Examples

### Example 1: Simple Text Category

**Backend:**
```python
# In get_media_info()
info["camera_model"] = "Canon EOS R5"  # From EXIF
```

**Frontend:**
```javascript
case 'camera_model':
  value = mediaData.camera_model || 'N/A';
  break;
```

### Example 2: Formatted Numeric Category

**Backend:**
```python
info["iso_speed"] = 6400  # From EXIF
```

**Frontend:**
```javascript
case 'iso_speed':
  label = 'ISO Speed';
  value = mediaData.iso_speed ? `ISO ${mediaData.iso_speed}` : 'N/A';
  break;
```

### Example 3: Complex Object Category

**Backend:**
```python
info["gps_location"] = {
    "latitude": 37.7749,
    "longitude": -122.4194,
    "altitude": 16.0
}
```

**Frontend:**
```javascript
case 'gps_location':
  if (mediaData.gps_location) {
    const loc = mediaData.gps_location;
    value = `${loc.latitude.toFixed(6)}, ${loc.longitude.toFixed(6)}`;
    if (loc.altitude) {
      value += ` (${loc.altitude}m)`;
    }
  } else {
    continue;
  }
  break;
```

### Example 4: Expandable Metadata Section

**Backend:**
```python
info["metadata"] = {
    "camera_settings": {
        "aperture": "f/2.8",
        "shutter_speed": "1/250",
        "iso": 100,
        "focal_length": "50mm",
        "white_balance": "Auto"
    }
}
```

This will automatically create an expandable "Camera Settings" section in the metadata area.

## Troubleshooting

### Category Not Appearing

1. **Check backend**: Verify data is in API response
2. **Check frontend**: Verify category is in the `categories` array
3. **Check config**: Verify category is in `config.yml`
4. **Check console**: Look for JavaScript errors

### Formatting Issues

1. **Check formatter**: Ensure your format function handles all cases
2. **Check CSS**: Verify styles are applied correctly
3. **Check data types**: Ensure backend sends expected format

### Performance Issues

1. **Profile**: Use browser dev tools to measure rendering time
2. **Optimize**: Move complex calculations to backend
3. **Lazy load**: Defer loading of heavy data until expanded

## Version History

- **v1.0** (2025-10-13): Initial implementation with core categories
- **v1.1** (Future): Add user-customizable category ordering

## Contributing

When adding new categories:

1. Test with multiple file types
2. Update this documentation
3. Add to default configuration with comments
4. Test mobile and desktop views
5. Consider accessibility (screen readers, keyboard navigation)
