/**
 * Buffer Client - Interface for server-side buffered search results
 * Provides viewport-based pagination and filter state management
 */

// Buffer state management
let currentFilterHash = null;
let currentCursor = null;
let currentFilters = null;
let isLoadingPage = false;
let hasMoreItems = true;
let bufferStats = {
  totalItems: 0,
  loadedItems: 0
};

/**
 * Initialize the buffer client and restore previous state
 */
async function initializeBufferClient() {
  console.info('[Buffer] Initializing buffer client...');
  
  try {
    // Try to restore previous filter state from server
    const activeFilters = await getActiveFilters();
    
    if (activeFilters && activeFilters.filter_hash) {
      currentFilterHash = activeFilters.filter_hash;
      currentFilters = activeFilters.filters;
      
      console.info('[Buffer] Restored filter state from server:', {
        hash: currentFilterHash.substring(0, 8) + '...',
        filters: currentFilters
      });
      
      return {
        restored: true,
        filterHash: currentFilterHash,
        filters: currentFilters
      };
    }
  } catch (error) {
    console.warn('[Buffer] Could not restore filter state:', error);
  }
  
  return { restored: false };
}

/**
 * Refresh the buffer with new filter criteria
 * This triggers a buffer rebuild on the server
 * 
 * @param {Object} filters - Filter criteria
 * @returns {Promise<Object>} Response with filter_hash and item_count
 */
async function refreshBuffer(filters) {
  console.info('[Buffer] Refreshing buffer with filters:', filters);
  
  try {
    const response = await fetch('/api/search/refresh', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(filters)
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to refresh buffer');
    }
    
    const data = await response.json();
    
    // Update local state
    currentFilterHash = data.filter_hash;
    currentFilters = filters;
    currentCursor = null;
    hasMoreItems = data.item_count > 0;
    bufferStats.totalItems = data.item_count;
    bufferStats.loadedItems = 0;
    
    console.info('[Buffer] Buffer refreshed:', {
      hash: currentFilterHash.substring(0, 8) + '...',
      itemCount: data.item_count
    });
    
    return data;
  } catch (error) {
    console.error('[Buffer] Failed to refresh buffer:', error);
    throw error;
  }
}

/**
 * Get a page of items from the buffer using keyset pagination
 * 
 * @param {string} filterHash - Hash of the filter criteria
 * @param {Object|null} cursor - Cursor for pagination (null for first page)
 * @param {number} limit - Number of items per page (default: 50, max: 200)
 * @returns {Promise<Object>} Response with items, next_cursor, and has_more
 */
async function getBufferPage(filterHash, cursor = null, limit = 50) {
  if (isLoadingPage) {
    console.warn('[Buffer] Already loading a page, skipping request');
    return { items: [], next_cursor: null, has_more: false };
  }
  
  isLoadingPage = true;
  
  try {
    // Build query parameters
    const params = new URLSearchParams({
      filter_hash: filterHash,
      limit: limit.toString()
    });
    
    if (cursor) {
      if (cursor.created_at) {
        params.append('cursor_created_at', cursor.created_at);
      }
      if (cursor.id) {
        params.append('cursor_id', cursor.id.toString());
      }
    }
    
    const response = await fetch(`/api/search/page?${params.toString()}`);
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to get buffer page');
    }
    
    const data = await response.json();
    
    // Update state
    currentCursor = data.next_cursor;
    hasMoreItems = data.has_more;
    bufferStats.loadedItems += data.items.length;
    
    console.info('[Buffer] Loaded page:', {
      itemsLoaded: data.items.length,
      totalLoaded: bufferStats.loadedItems,
      hasMore: data.has_more
    });
    
    return data;
  } catch (error) {
    console.error('[Buffer] Failed to get buffer page:', error);
    throw error;
  } finally {
    isLoadingPage = false;
  }
}

/**
 * Get the active filter state from the server
 * 
 * @returns {Promise<Object|null>} Active filter state or null
 */
async function getActiveFilters() {
  try {
    const response = await fetch('/api/search/filters/active');
    
    if (!response.ok) {
      if (response.status === 404) {
        // No active filters set
        return null;
      }
      throw new Error('Failed to get active filters');
    }
    
    const data = await response.json();
    return data;
  } catch (error) {
    console.warn('[Buffer] Failed to get active filters:', error);
    return null;
  }
}

/**
 * Set the active filter state on the server
 * This persists the filter state for restoration on page reload
 * 
 * @param {Object} filters - Filter criteria to persist
 * @returns {Promise<void>}
 */
async function setActiveFilters(filters) {
  try {
    const response = await fetch('/api/search/filters/active', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(filters)
    });
    
    if (!response.ok) {
      throw new Error('Failed to set active filters');
    }
    
    console.info('[Buffer] Active filters saved to server');
  } catch (error) {
    console.error('[Buffer] Failed to set active filters:', error);
    throw error;
  }
}

/**
 * Get buffer statistics from the server
 * 
 * @returns {Promise<Object>} Buffer statistics
 */
async function getBufferStats() {
  try {
    const response = await fetch('/api/search/buffer/stats');
    
    if (!response.ok) {
      throw new Error('Failed to get buffer stats');
    }
    
    return await response.json();
  } catch (error) {
    console.error('[Buffer] Failed to get buffer stats:', error);
    throw error;
  }
}

/**
 * Clear a specific buffer by its hash
 * 
 * @param {string} filterHash - Hash of the buffer to clear
 * @returns {Promise<void>}
 */
async function clearBuffer(filterHash) {
  try {
    const response = await fetch(`/api/search/buffer/${filterHash}`, {
      method: 'DELETE'
    });
    
    if (!response.ok) {
      throw new Error('Failed to clear buffer');
    }
    
    console.info('[Buffer] Buffer cleared:', filterHash.substring(0, 8) + '...');
  } catch (error) {
    console.error('[Buffer] Failed to clear buffer:', error);
    throw error;
  }
}

/**
 * Clear all buffers
 * 
 * @returns {Promise<void>}
 */
async function clearAllBuffers() {
  try {
    const response = await fetch('/api/search/buffer', {
      method: 'DELETE'
    });
    
    if (!response.ok) {
      throw new Error('Failed to clear all buffers');
    }
    
    console.info('[Buffer] All buffers cleared');
  } catch (error) {
    console.error('[Buffer] Failed to clear all buffers:', error);
    throw error;
  }
}

/**
 * Reset buffer client state
 */
function resetBufferState() {
  currentFilterHash = null;
  currentCursor = null;
  currentFilters = null;
  hasMoreItems = true;
  bufferStats.totalItems = 0;
  bufferStats.loadedItems = 0;
}

/**
 * Check if we're currently using buffered mode
 * 
 * @returns {boolean} True if buffer is active
 */
function isBufferActive() {
  return currentFilterHash !== null;
}

/**
 * Get current buffer information
 * 
 * @returns {Object} Current buffer state
 */
function getBufferInfo() {
  return {
    filterHash: currentFilterHash,
    filters: currentFilters,
    cursor: currentCursor,
    hasMore: hasMoreItems,
    stats: { ...bufferStats },
    isActive: isBufferActive()
  };
}

// Export functions for use in other modules
if (typeof window !== 'undefined') {
  window.BufferClient = {
    initialize: initializeBufferClient,
    refresh: refreshBuffer,
    getPage: getBufferPage,
    getActiveFilters: getActiveFilters,
    setActiveFilters: setActiveFilters,
    getStats: getBufferStats,
    clearBuffer: clearBuffer,
    clearAll: clearAllBuffers,
    reset: resetBufferState,
    isActive: isBufferActive,
    getInfo: getBufferInfo
  };
}
