/**
 * Viewer.js Integration for Image Viewing
 * 
 * This module integrates Viewer.js library to provide enhanced image viewing
 * capabilities including zoom, pan, and touch gestures for mobile devices.
 * 
 * Key Features:
 * - Touch gestures (pinch-to-zoom, drag-to-move)
 * - Mouse wheel zoom
 * - Double-click to toggle zoom
 * - Keyboard navigation
 * - Mobile-friendly interface
 * 
 * Documentation: https://fengyuanchen.github.io/viewerjs/
 */

// Global Viewer.js instance
let imageViewer = null;

/**
 * Initialize Viewer.js for the image element
 * This is called when the page loads or when switching to an image
 */
function initializeImageViewer() {
  const imgElement = document.getElementById('imgview');
  
  if (!imgElement) {
    console.warn('Image element #imgview not found');
    return;
  }
  
  // Destroy existing viewer instance if it exists
  if (imageViewer) {
    imageViewer.destroy();
    imageViewer = null;
  }
  
  // Initialize Viewer.js with configuration
  imageViewer = new Viewer(imgElement, {
    // Viewer options for optimal mobile and desktop experience
    inline: false,          // Use modal mode for better mobile experience
    button: false,          // Hide default close button (we have our own UI)
    navbar: false,          // Hide navbar (we have our own navigation)
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
    scalable: false,        // Disable scaling (we use zoom instead)
    transition: true,       // Smooth transitions
    fullscreen: false,      // Disable fullscreen (conflicts with our maximize feature)
    keyboard: true,         // Enable keyboard shortcuts
    
    // Touch gesture support for mobile
    backdrop: 'static',     // Click backdrop to close
    
    // Zoom configuration
    zoomRatio: 0.1,        // Zoom increment (10%)
    minZoomRatio: 0.1,     // Minimum zoom (10%)
    maxZoomRatio: 5,       // Maximum zoom (500%)
    
    // Event handlers
    viewed: function() {
      // Image has been viewed (loaded into viewer)
      console.log('Viewer.js: Image loaded');
    },
    
    show: function() {
      // Viewer is shown
      // Disable old mobile zoom controls when Viewer.js is active
      disableOldMobileZoom();
    },
    
    hide: function() {
      // Viewer is hidden
      // Re-enable old mobile zoom controls
      enableOldMobileZoom();
    }
  });
  
  console.log('Viewer.js initialized for image viewer');
}

/**
 * Show the current image in Viewer.js
 * This is called when switching to a new image
 */
function showImageInViewer() {
  const imgElement = document.getElementById('imgview');
  
  if (!imgElement || imgElement.style.display === 'none') {
    // Not an image, skip
    return;
  }
  
  // Initialize viewer if not already done
  if (!imageViewer) {
    initializeImageViewer();
  }
  
  // Update the viewer with the current image
  if (imageViewer) {
    imageViewer.update();
  }
}

/**
 * Disable old mobile zoom implementation when Viewer.js is active
 */
function disableOldMobileZoom() {
  const mobileZoomBtn = document.getElementById('mobile-zoom-btn');
  const mobileZoomPopover = document.getElementById('mobile-zoom-popover');
  
  // Hide old mobile zoom button when Viewer.js is active
  if (mobileZoomBtn) {
    mobileZoomBtn.style.display = 'none';
  }
  
  // Hide old mobile zoom popover
  if (mobileZoomPopover) {
    mobileZoomPopover.classList.remove('active');
  }
}

/**
 * Re-enable old mobile zoom implementation when Viewer.js is hidden
 */
function enableOldMobileZoom() {
  const mobileZoomBtn = document.getElementById('mobile-zoom-btn');
  const imgElement = document.getElementById('imgview');
  
  // Show old mobile zoom button if we're viewing an image on mobile
  if (mobileZoomBtn && imgElement && imgElement.style.display !== 'none' && isMobileDevice()) {
    mobileZoomBtn.style.display = '';
  }
}

/**
 * View current image in Viewer.js (programmatic trigger)
 * This can be called from external code to open the viewer
 */
function viewCurrentImage() {
  if (imageViewer) {
    imageViewer.show();
  } else {
    initializeImageViewer();
    if (imageViewer) {
      imageViewer.show();
    }
  }
}

/**
 * Cleanup Viewer.js instance
 * Called when switching away from images or on page unload
 */
function destroyImageViewer() {
  if (imageViewer) {
    imageViewer.destroy();
    imageViewer = null;
    console.log('Viewer.js destroyed');
  }
}

// Initialize Viewer.js when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
  console.log('Viewer.js integration module loaded');
  
  // Initialize on first load if image is visible
  const imgElement = document.getElementById('imgview');
  if (imgElement && imgElement.style.display !== 'none') {
    initializeImageViewer();
  }
  
  // Add double-click handler to open images in Viewer.js (desktop)
  if (imgElement) {
    imgElement.addEventListener('dblclick', function(e) {
      e.preventDefault();
      viewCurrentImage();
    });
    
    // Add cursor pointer on hover to indicate it's clickable
    imgElement.style.cursor = 'pointer';
    imgElement.title = 'Double-click to view in full screen';
  }
  
  // Add mobile zoom button handler to trigger Viewer.js
  const mobileZoomBtn = document.getElementById('mobile-zoom-btn');
  if (mobileZoomBtn) {
    // Store the original click handler
    const originalZoomHandler = mobileZoomBtn.onclick;
    
    // Add new handler that opens Viewer.js for images
    mobileZoomBtn.addEventListener('click', function(e) {
      const imgElement = document.getElementById('imgview');
      
      // If image is visible, open in Viewer.js instead of old zoom popover
      if (imgElement && imgElement.style.display !== 'none' && window.imageViewerIntegration) {
        e.preventDefault();
        e.stopPropagation();
        viewCurrentImage();
      }
      // Otherwise, let the original handler run (if any)
    }, true); // Use capture phase to run before old handler
  }
});

// Cleanup on page unload
window.addEventListener('beforeunload', function() {
  destroyImageViewer();
});

// Export functions for use in app.js
window.imageViewerIntegration = {
  initialize: initializeImageViewer,
  show: showImageInViewer,
  view: viewCurrentImage,
  destroy: destroyImageViewer
};
