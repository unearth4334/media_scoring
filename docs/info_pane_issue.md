# Feature Request: Info Pane Overlay

## Overview
Add an info pane overlay that displays detailed information about the currently selected media file. The overlay should be accessible from the action-button menu (⋯) on both desktop and mobile interfaces.

## Requirements

### 1. Configuration (config/config.yml)
Add a new `info_pane` section to allow users to configure what information is displayed:

```yaml
# Info pane settings
info_pane:
  enabled: true  # Enable or disable the info pane overlay
  categories:
    # List of all available information categories
    - filename       # Display the filename of the media
    - file_size      # Display the file size (formatted, e.g., "2.5 MB")
    - dimensions     # Display the dimensions (e.g., "1920x1080")
    - duration       # Display the duration (for videos, e.g., "00:02:34")
    - creation_date  # Display the original creation date
    - modified_date  # Display the last modified date
    - file_path      # Display the full file path
    - file_type      # Display the file type/extension
    - resolution     # Display resolution details
    - aspect_ratio   # Display aspect ratio (e.g., "16:9")
    - frame_rate     # Display frame rate (for videos)
    - bitrate        # Display bitrate (for videos)
    - codec          # Display codec information
    - score          # Display the current score/rating
    - metadata       # Display additional metadata (EXIF, workflow, etc.)
  
  # Default categories to show (user can customize)
  default_categories:
    - filename
    - file_size
    - dimensions
    - creation_date
    - score
```

### 2. User Interface

#### Desktop Implementation
- Add an info pane overlay that appears when triggered from the desktop action menu (⋯ button)
- Position: Fixed overlay, positioned to the right side of the viewport (top-right corner)
- Size: Responsive width (300-400px), with scrollable content if needed
- Style: Match the application's theme (dark theme with cyan accents)
- Components:
  - Header with title "Media Information" and close button (×)
  - Scrollable content area with formatted information items
  - Each information item should have a label and value displayed clearly

#### Mobile Implementation
- Add a full-screen or bottom-sheet overlay for mobile devices
- Triggered from the mobile action menu (⋯ button in mobile-scorebar)
- Style: Full-width overlay with touch-friendly controls
- Components:
  - Header with title and close button
  - Scrollable content area optimized for mobile screens
  - Larger touch targets and font sizes for readability

### 3. Information Display Format

Each information category should be displayed in a user-friendly format:

| Category | Display Format | Example |
|----------|---------------|---------|
| filename | Plain text | `sunset_photo.jpg` |
| file_size | Formatted bytes | `2.5 MB` |
| dimensions | Width × Height | `1920×1080` |
| duration | HH:MM:SS | `00:02:34` |
| creation_date | Formatted date/time | `October 12, 2025, 3:45 PM` |
| modified_date | Formatted date/time | `October 13, 2025, 10:30 AM` |
| file_path | Truncated path with copy button | `/media/photos/...` |
| file_type | Extension with icon | `JPEG Image` |
| resolution | Megapixels | `2.1 MP` |
| aspect_ratio | Ratio | `16:9` |
| frame_rate | FPS | `30 fps` |
| bitrate | Formatted bitrate | `5.2 Mbps` |
| codec | Codec name | `H.264` |
| score | Star rating | `★★★★☆ (4/5)` |
| metadata | Expandable sections | See details below |

#### Metadata Subsections
The metadata category should support expandable subsections for:
- **EXIF Data** (for images): Camera model, ISO, aperture, shutter speed, etc.
- **ComfyUI Workflow** (if available): Workflow JSON or formatted display
- **Generation Parameters**: Model, prompts, seed, steps, CFG, sampler, etc.
- **Custom Metadata**: Any additional key-value pairs

### 4. JavaScript Implementation

#### Core Functionality
```javascript
// Function to fetch media information from backend
async function fetchMediaInfo(filename) {
  const response = await fetch(`/api/media/${filename}/info`);
  return await response.json();
}

// Function to toggle info pane
function toggleInfoPane() {
  const infoPane = document.getElementById('info-pane');
  if (infoPane.classList.contains('visible')) {
    closeInfoPane();
  } else {
    openInfoPane();
  }
}

// Function to populate info pane with media data
function populateInfoPane(mediaData, config) {
  // Filter data based on config.categories
  // Format each category according to specifications
  // Dynamically build HTML content
  // Handle missing data gracefully
}

// Function to format values
function formatFileSize(bytes) { /* ... */ }
function formatDuration(seconds) { /* ... */ }
function formatDate(timestamp) { /* ... */ }
// ... other formatters
```

#### Event Handlers
- Desktop menu button (⋯) click → toggle info pane
- Mobile menu button (⋯) click → show mobile menu with "View Info" option
- Close button (×) click → hide info pane
- Outside click (optional) → close info pane
- ESC key → close info pane

### 5. Backend API Endpoint

Create a new API endpoint to provide media information:

**Endpoint**: `GET /api/media/{filename}/info`

**Response Format**:
```json
{
  "filename": "sunset_photo.jpg",
  "file_size": 2621440,
  "dimensions": {
    "width": 1920,
    "height": 1080
  },
  "duration": null,
  "creation_date": "2025-10-12T15:45:00Z",
  "modified_date": "2025-10-13T10:30:00Z",
  "file_path": "/media/photos/sunset_photo.jpg",
  "file_type": "jpeg",
  "resolution": 2073600,
  "aspect_ratio": "16:9",
  "frame_rate": null,
  "bitrate": null,
  "codec": null,
  "score": 4,
  "metadata": {
    "exif": {
      "Make": "Canon",
      "Model": "EOS R5",
      "ISO": 100,
      "FNumber": 2.8,
      "ExposureTime": "1/250"
    },
    "workflow": null,
    "generation_params": null
  }
}
```

### 6. CSS Styling Requirements

#### Desktop Styles
```css
.info-pane {
  /* Fixed overlay positioned top-right */
  position: fixed;
  top: 80px;
  right: 20px;
  width: 350px;
  max-height: calc(100vh - 100px);
  background: #1a1a1a;
  border: 1px solid #00bcd4;
  border-radius: 8px;
  box-shadow: 0 4px 16px rgba(0, 188, 212, 0.3);
  z-index: 1000;
  overflow: hidden;
  display: none;
}

.info-pane.visible {
  display: block;
  animation: slideInRight 0.3s ease-out;
}

.info-pane-header {
  /* Header styling */
  background: linear-gradient(135deg, #00bcd4, #0097a7);
  padding: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.info-pane-content {
  /* Scrollable content area */
  padding: 15px;
  max-height: calc(100vh - 160px);
  overflow-y: auto;
}

.info-item {
  /* Individual information item */
  margin-bottom: 12px;
  padding-bottom: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.info-label {
  font-weight: bold;
  color: #00bcd4;
  font-size: 12px;
  text-transform: uppercase;
  margin-bottom: 4px;
}

.info-value {
  color: #e0e0e0;
  font-size: 14px;
  word-wrap: break-word;
}
```

#### Mobile Styles
```css
@media (max-width: 768px) {
  .info-pane {
    /* Full-screen or bottom-sheet on mobile */
    top: 0;
    right: 0;
    left: 0;
    bottom: 0;
    width: 100%;
    max-height: 100vh;
    border-radius: 0;
  }
  
  .info-pane.visible {
    animation: slideInUp 0.3s ease-out;
  }
}
```

### 7. Configuration Handling

The implementation should:
- Read the `info_pane` configuration from `config.yml`
- Validate that requested categories are available
- Use `default_categories` if user hasn't customized
- Gracefully handle missing data (show "N/A" or hide category)
- Allow easy addition of new categories in the future

### 8. Robustness Requirements

#### Handle Edge Cases
- Media file without metadata
- Video without duration/codec information
- Image without EXIF data
- Missing or invalid configuration
- Very long values (truncate with "..." and tooltip)
- Special characters in filenames/paths
- Empty or null values

#### Performance Considerations
- Lazy load metadata (don't fetch until info pane is opened)
- Cache metadata for current media
- Debounce API calls if user rapidly switches media
- Optimize for large metadata objects (workflow JSON)

#### Accessibility
- Keyboard navigation support (Tab, ESC)
- ARIA labels for screen readers
- Focus management (trap focus in overlay when open)
- Clear visual focus indicators

### 9. Future Extensibility

Create documentation for developers to add new categories:

**File**: `docs/INFO_PANE_DEVELOPER_GUIDE.md`

Should include:
1. How to add a new category to the configuration schema
2. How to add backend support for the new category
3. How to add frontend formatting/display logic
4. How to handle special data types (arrays, objects, nested data)
5. Best practices for naming and organizing categories
6. Examples of implementing different display formats

### 10. Testing Checklist

- [ ] Info pane opens/closes correctly on desktop
- [ ] Info pane opens/closes correctly on mobile
- [ ] All configured categories are displayed
- [ ] Missing data is handled gracefully
- [ ] File size formatting is correct (KB, MB, GB)
- [ ] Duration formatting is correct (HH:MM:SS)
- [ ] Date formatting matches locale/preferences
- [ ] Metadata expands/collapses correctly
- [ ] Close button works
- [ ] ESC key closes the pane
- [ ] Outside click closes the pane (if implemented)
- [ ] Configuration changes are reflected
- [ ] Performance is acceptable with large metadata
- [ ] Responsive design works on various screen sizes
- [ ] Works with videos and images
- [ ] Works with different file types

### 11. Implementation Steps

1. **Phase 1: Configuration & Backend**
   - Add `info_pane` section to `config/config.yml`
   - Update config schema validation
   - Create API endpoint `/api/media/{filename}/info`
   - Implement data gathering from filesystem and database

2. **Phase 2: Frontend Structure**
   - Add HTML structure for info pane overlay
   - Add CSS styles for desktop and mobile
   - Implement basic show/hide functionality

3. **Phase 3: Data Display**
   - Implement formatters for each category type
   - Implement dynamic content population
   - Add configuration filtering logic

4. **Phase 4: Advanced Features**
   - Add metadata expansion/collapse
   - Add copy-to-clipboard for file paths
   - Implement keyboard navigation
   - Add animations and transitions

5. **Phase 5: Testing & Documentation**
   - Test all categories with various media files
   - Test responsive design on different devices
   - Write developer documentation
   - Update user documentation

### 12. Success Criteria

- Users can view detailed media information in a clean overlay
- Configuration allows full customization of displayed categories
- Implementation is robust and handles edge cases gracefully
- Design is consistent with existing UI/UX patterns
- Code is well-documented for future maintenance
- Performance impact is minimal (< 100ms to open pane)

## Notes

- Ensure the info pane integrates seamlessly with existing mobile menu
- Match the visual style of existing overlays (mobile-score-popover, mobile-menu-popover)
- Consider adding tooltips for technical terms (e.g., "codec", "bitrate")
- Consider adding a settings icon to quickly toggle categories on/off
- Future enhancement: Allow users to reorder categories via drag-and-drop
