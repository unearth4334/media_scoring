/**
 * Viewport Loader - Manages viewport-based lazy loading of media items
 * Uses Intersection Observer to detect when items enter the viewport
 */

// Viewport loader state
let viewportObserver = null;
let sidebarScrollContainer = null;
let isAutoLoadEnabled = true;
let autoLoadThreshold = 200; // Pixels from bottom to trigger load
let pendingLoadOperation = null;

/**
 * Initialize the viewport loader with intersection observer
 */
function initializeViewportLoader() {
  console.info('[Viewport] Initializing viewport loader...');
  
  // Get the sidebar scroll container
  sidebarScrollContainer = document.getElementById('sidebar_list');
  
  if (!sidebarScrollContainer) {
    console.warn('[Viewport] Sidebar list container not found');
    return false;
  }
  
  // Create intersection observer for detecting items in viewport
  const observerOptions = {
    root: sidebarScrollContainer,
    rootMargin: '100px', // Load items 100px before they enter viewport
    threshold: 0.01
  };
  
  viewportObserver = new IntersectionObserver(handleItemIntersection, observerOptions);
  
  // Add scroll listener for auto-loading more pages
  sidebarScrollContainer.addEventListener('scroll', handleSidebarScroll);
  
  console.info('[Viewport] Viewport loader initialized');
  return true;
}

/**
 * Handle intersection of items with viewport
 * This triggers loading of thumbnails and metadata for visible items
 */
function handleItemIntersection(entries) {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      const itemElement = entry.target;
      
      // Load thumbnail if not already loaded
      const thumbnailImg = itemElement.querySelector('img[data-thumbnail-src]');
      if (thumbnailImg) {
        const thumbnailSrc = thumbnailImg.getAttribute('data-thumbnail-src');
        if (thumbnailSrc) {
          thumbnailImg.src = thumbnailSrc;
          thumbnailImg.removeAttribute('data-thumbnail-src');
        }
      }
      
      // Load metadata if not already loaded
      const metadataPlaceholder = itemElement.querySelector('[data-metadata-placeholder]');
      if (metadataPlaceholder) {
        loadItemMetadata(itemElement);
      }
      
      // Stop observing this item once loaded
      viewportObserver.unobserve(itemElement);
    }
  });
}

/**
 * Load metadata for a specific item
 * @param {HTMLElement} itemElement - The sidebar item element
 */
async function loadItemMetadata(itemElement) {
  const filename = itemElement.getAttribute('data-filename');
  if (!filename) return;
  
  try {
    // Check if metadata is already loaded
    if (itemElement.getAttribute('data-metadata-loaded') === 'true') {
      return;
    }
    
    // Mark as loading to prevent duplicate requests
    itemElement.setAttribute('data-metadata-loading', 'true');
    
    const response = await fetch(`/api/meta/${encodeURIComponent(filename)}`);
    if (!response.ok) {
      throw new Error('Failed to load metadata');
    }
    
    const metadata = await response.json();
    
    // Store metadata in element
    itemElement.setAttribute('data-metadata', JSON.stringify(metadata));
    itemElement.setAttribute('data-metadata-loaded', 'true');
    itemElement.removeAttribute('data-metadata-loading');
    itemElement.removeAttribute('data-metadata-placeholder');
    
    // Update resolution display if available
    if (metadata.width && metadata.height) {
      const resolutionSpan = itemElement.querySelector('.resolution');
      if (resolutionSpan) {
        resolutionSpan.textContent = `[${metadata.width}×${metadata.height}]`;
      }
    }
  } catch (error) {
    console.warn('[Viewport] Failed to load metadata for', filename, error);
    itemElement.removeAttribute('data-metadata-loading');
  }
}

/**
 * Handle sidebar scroll events for auto-loading more pages
 */
function handleSidebarScroll() {
  if (!isAutoLoadEnabled) return;
  if (!window.BufferClient || !window.BufferClient.isActive()) return;
  
  const scrollTop = sidebarScrollContainer.scrollTop;
  const scrollHeight = sidebarScrollContainer.scrollHeight;
  const clientHeight = sidebarScrollContainer.clientHeight;
  
  // Check if we're near the bottom
  const distanceFromBottom = scrollHeight - (scrollTop + clientHeight);
  
  if (distanceFromBottom < autoLoadThreshold) {
    loadNextBufferPage();
  }
}

/**
 * Load the next page from the buffer
 */
async function loadNextBufferPage() {
  // Prevent duplicate load operations
  if (pendingLoadOperation) {
    return;
  }
  
  const bufferInfo = window.BufferClient.getInfo();
  
  if (!bufferInfo.hasMore) {
    console.info('[Viewport] No more items to load');
    return;
  }
  
  console.info('[Viewport] Loading next page from buffer...');
  
  pendingLoadOperation = (async () => {
    try {
      const pageData = await window.BufferClient.getPage(
        bufferInfo.filterHash,
        bufferInfo.cursor,
        50 // Load 50 items at a time
      );
      
      if (pageData.items && pageData.items.length > 0) {
        // Append items to the current list
        appendItemsToSidebar(pageData.items);
        
        console.info('[Viewport] Loaded', pageData.items.length, 'items');
      }
    } catch (error) {
      console.error('[Viewport] Failed to load next page:', error);
      // Show user-friendly error
      showLoadError('Failed to load more items. Please try refreshing.');
    } finally {
      pendingLoadOperation = null;
    }
  })();
  
  return pendingLoadOperation;
}

/**
 * Append items to the sidebar
 * @param {Array} items - Items to append
 */
function appendItemsToSidebar(items) {
  // This function will be called from the main app.js
  // It needs to integrate with the existing renderSidebar logic
  
  if (typeof appendSidebarItems === 'function') {
    appendSidebarItems(items);
  } else {
    console.warn('[Viewport] appendSidebarItems function not available');
  }
}

/**
 * Observe a sidebar item for lazy loading
 * @param {HTMLElement} itemElement - The item to observe
 */
function observeItem(itemElement) {
  if (viewportObserver && itemElement) {
    viewportObserver.observe(itemElement);
  }
}

/**
 * Unobserve a sidebar item
 * @param {HTMLElement} itemElement - The item to stop observing
 */
function unobserveItem(itemElement) {
  if (viewportObserver && itemElement) {
    viewportObserver.unobserve(itemElement);
  }
}

/**
 * Observe all items in the sidebar
 */
function observeAllItems() {
  if (!viewportObserver) return;
  
  const items = document.querySelectorAll('#sidebar_list .sidebar_item');
  items.forEach(item => observeItem(item));
  
  console.info('[Viewport] Observing', items.length, 'items');
}

/**
 * Enable or disable auto-loading of pages
 * @param {boolean} enabled - Whether to enable auto-loading
 */
function setAutoLoadEnabled(enabled) {
  isAutoLoadEnabled = enabled;
  console.info('[Viewport] Auto-load', enabled ? 'enabled' : 'disabled');
}

/**
 * Set the threshold for auto-loading (pixels from bottom)
 * @param {number} threshold - Threshold in pixels
 */
function setAutoLoadThreshold(threshold) {
  autoLoadThreshold = threshold;
  console.info('[Viewport] Auto-load threshold set to', threshold, 'px');
}

/**
 * Show a loading error message
 * @param {string} message - Error message to display
 */
function showLoadError(message) {
  // This should integrate with the existing UI error display system
  console.error('[Viewport]', message);
  
  // Try to display in UI if available
  if (typeof showNotification === 'function') {
    showNotification(message, 'error');
  }
}

/**
 * Reset viewport loader state
 */
function resetViewportLoader() {
  if (viewportObserver) {
    viewportObserver.disconnect();
  }
  pendingLoadOperation = null;
  console.info('[Viewport] Viewport loader reset');
}

/**
 * Clean up viewport loader
 */
function cleanupViewportLoader() {
  resetViewportLoader();
  
  if (sidebarScrollContainer) {
    sidebarScrollContainer.removeEventListener('scroll', handleSidebarScroll);
  }
  
  viewportObserver = null;
  sidebarScrollContainer = null;
  
  console.info('[Viewport] Viewport loader cleaned up');
}

// Export functions for use in other modules
if (typeof window !== 'undefined') {
  window.ViewportLoader = {
    initialize: initializeViewportLoader,
    observeItem: observeItem,
    unobserveItem: unobserveItem,
    observeAll: observeAllItems,
    loadNextPage: loadNextBufferPage,
    setAutoLoadEnabled: setAutoLoadEnabled,
    setAutoLoadThreshold: setAutoLoadThreshold,
    reset: resetViewportLoader,
    cleanup: cleanupViewportLoader
  };
}
