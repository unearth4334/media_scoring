# Viewer.js Integration

This document describes the integration of [Viewer.js](https://fengyuanchen.github.io/viewerjs/) library for enhanced image viewing in the Media Scoring application.

## Overview

Viewer.js provides a feature-rich image viewing experience with:
- **Touch Gestures**: Pinch-to-zoom, drag-to-move on mobile devices
- **Mouse Controls**: Mouse wheel zoom, click-and-drag on desktop
- **Zoom Controls**: Zoom in/out, reset, one-to-one size
- **Rotation**: Rotate images left or right
- **Keyboard Shortcuts**: Navigate with arrow keys, zoom with +/-, etc.

## Files Added

### Library Files
- `app/static/vendor/viewerjs/viewer.min.js` - Viewer.js library (v1.11.6)
- `app/static/vendor/viewerjs/viewer.min.css` - Viewer.js styles

### Integration Files
- `app/static/js/viewer-integration.js` - Integration layer for Viewer.js
- `docs/VIEWERJS_INTEGRATION.md` - This documentation file

## Files Modified

### `app/templates/index.html`
Added CSS and JavaScript references:
```html
<!-- In <head> -->
<link rel="stylesheet" href="/static/vendor/viewerjs/viewer.min.css">

<!-- Before closing </body> -->
<script src="/static/vendor/viewerjs/viewer.min.js"></script>
<script src="/static/js/viewer-integration.js"></script>
```

### `app/static/js/app.js`
Modified the `showMedia()` function to initialize Viewer.js when images load:
```javascript
// Initialize Viewer.js integration if available
if (window.imageViewerIntegration) {
  window.imageViewerIntegration.initialize();
}
```

## Usage

### Desktop
- **Double-click** on any image to open it in Viewer.js
- Use toolbar buttons to zoom, rotate, or reset the view
- Press **Escape** to close the viewer
- Use mouse wheel to zoom
- Click and drag to pan when zoomed in

### Mobile
- **Tap the zoom button (🔍)** in the mobile bottom bar to open Viewer.js
- **Double-tap** on image to open Viewer.js
- Use **pinch gesture** to zoom in/out
- **Drag** to pan when zoomed in
- Use toolbar buttons for precise control
- **Tap outside** the image or press back to close

## Configuration

The Viewer.js instance is configured in `app/static/js/viewer-integration.js` with the following options:

```javascript
{
  inline: false,          // Modal mode for better mobile UX
  button: false,          // Hide default close button
  navbar: false,          // Hide navbar
  title: false,           // Hide title bar
  toolbar: {
    zoomIn: true,
    zoomOut: true,
    oneToOne: true,
    reset: true,
    rotateLeft: true,
    rotateRight: true,
  },
  tooltip: true,          // Show zoom percentage
  movable: true,          // Enable drag to move
  zoomable: true,         // Enable zoom
  rotatable: true,        // Enable rotation
  keyboard: true,         // Enable keyboard shortcuts
  zoomRatio: 0.1,        // Zoom increment (10%)
  minZoomRatio: 0.1,     // Minimum zoom (10%)
  maxZoomRatio: 5,       // Maximum zoom (500%)
}
```

## API Reference

The integration exposes the following global API via `window.imageViewerIntegration`:

### `initialize()`
Initializes Viewer.js for the current image element. Called automatically when images load.

### `show()`
Updates the viewer with the current image.

### `view()`
Programmatically opens the viewer for the current image.

### `destroy()`
Destroys the Viewer.js instance and cleans up resources.

## Browser Compatibility

Viewer.js supports all modern browsers:
- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- iOS Safari (iOS 10+)
- Chrome for Android (latest)

## Touch Gesture Support

Mobile devices benefit from native touch gestures:
- **Pinch**: Zoom in/out
- **Drag**: Pan image when zoomed
- **Double-tap**: Toggle zoom
- **Swipe**: Navigate (when enabled)

## Fallback Behavior

The old mobile zoom implementation remains available as a fallback. Users can still access the old zoom controls via the mobile zoom popover if needed.

## Known Limitations

1. Viewer.js only activates for image files (PNG, JPG, JPEG)
2. Video files continue to use the native video player
3. The old maximize feature and Viewer.js work independently

## Troubleshooting

### Images don't open in Viewer.js
- Check browser console for JavaScript errors
- Ensure Viewer.js library files are loaded correctly
- Verify the image element has loaded successfully

### Touch gestures not working
- Ensure you're testing on a real touch device or proper mobile emulation
- Check that `movable` and `zoomable` options are enabled
- Verify touch events are not being intercepted by other handlers

### Zoom controls not visible
- Check if the toolbar configuration is correct
- Ensure Viewer.js CSS is loaded properly
- Verify no CSS conflicts with custom styles

## Future Enhancements

Potential improvements for future versions:
- Gallery mode with left/right navigation
- Thumbnail preview in viewer
- Share/download buttons in viewer toolbar
- Custom transition effects
- Image comparison mode
- Annotation support

## References

- [Viewer.js Official Documentation](https://github.com/fengyuanchen/viewerjs)
- [Viewer.js Demo](https://fengyuanchen.github.io/viewerjs/)
- [Viewer.js API Reference](https://github.com/fengyuanchen/viewerjs#options)
