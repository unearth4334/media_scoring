/**
 * State Persistence Module
 * Handles saving and restoring UI state using cookies
 */

class StatePersistence {
  constructor() {
    this.cookiePrefix = 'media_scorer_';
    this.cookieExpireDays = 365; // Cookies expire after 1 year
    
    // Define all state keys that should be persisted
    this.stateKeys = {
      // Main app state
      'toolbarCollapsed': { type: 'boolean', default: false },
      'currentDir': { type: 'string', default: '' },
      'currentPattern': { type: 'string', default: '*.mp4' },
      'minFilter': { type: 'string', default: 'none' },
      'showThumbnails': { type: 'boolean', default: true },
      'thumbnailHeight': { type: 'number', default: 64 },
      'isMaximized': { type: 'boolean', default: false },
      'currentVideoIndex': { type: 'number', default: 0 },
      'toggleExtensions': { type: 'array', default: ['jpg', 'png', 'mp4'] },
      'userPathPrefix': { type: 'string', default: null },
      
      // Search toolbar filters
      'searchFilters_sort': { type: 'string', default: 'name' },
      'searchFilters_sortDirection': { type: 'string', default: 'asc' },
      'searchFilters_filetype': { type: 'array', default: ['jpg', 'png', 'mp4'] },
      'searchFilters_rating': { type: 'string', default: 'none' },
      'searchFilters_dateStart': { type: 'string', default: null },
      'searchFilters_dateEnd': { type: 'string', default: null },
      'searchFilters_nsfw': { type: 'string', default: 'all' },
      
      // UI state
      'activePillEditor': { type: 'string', default: null },
      'menuOverlayOpen': { type: 'boolean', default: false },
      
      // View preferences
      'videoVolume': { type: 'number', default: 0.5 },
      'videoPlaybackRate': { type: 'number', default: 1.0 },
      'autoPlayVideo': { type: 'boolean', default: false },
      'loopVideo': { type: 'boolean', default: false }
    };
  }
  
  /**
   * Set a cookie value
   */
  setCookie(name, value, days = this.cookieExpireDays) {
    const expires = new Date();
    expires.setTime(expires.getTime() + (days * 24 * 60 * 60 * 1000));
    document.cookie = `${this.cookiePrefix}${name}=${encodeURIComponent(value)};expires=${expires.toUTCString()};path=/;SameSite=Lax`;
  }
  
  /**
   * Get a cookie value
   */
  getCookie(name) {
    const nameEQ = `${this.cookiePrefix}${name}=`;
    const ca = document.cookie.split(';');
    for (let i = 0; i < ca.length; i++) {
      let c = ca[i];
      while (c.charAt(0) === ' ') c = c.substring(1, c.length);
      if (c.indexOf(nameEQ) === 0) {
        return decodeURIComponent(c.substring(nameEQ.length, c.length));
      }
    }
    return null;
  }
  
  /**
   * Delete a cookie
   */
  deleteCookie(name) {
    document.cookie = `${this.cookiePrefix}${name}=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/;`;
  }
  
  /**
   * Convert value to appropriate type based on state key definition
   */
  convertValue(key, value) {
    if (value === null || value === undefined) {
      return this.stateKeys[key]?.default || null;
    }
    
    const keyConfig = this.stateKeys[key];
    if (!keyConfig) return value;
    
    switch (keyConfig.type) {
      case 'boolean':
        return value === 'true' || value === true;
      case 'number':
        const num = parseFloat(value);
        return isNaN(num) ? keyConfig.default : num;
      case 'array':
        try {
          return Array.isArray(value) ? value : JSON.parse(value);
        } catch (e) {
          return keyConfig.default;
        }
      case 'string':
      default:
        return value === 'null' ? null : String(value);
    }
  }
  
  /**
   * Save a state value
   */
  saveState(key, value) {
    if (!this.stateKeys[key]) {
      console.warn(`Unknown state key: ${key}`);
      return;
    }
    
    let cookieValue;
    if (typeof value === 'object' && value !== null) {
      cookieValue = JSON.stringify(value);
    } else {
      cookieValue = String(value);
    }
    
    this.setCookie(key, cookieValue);
    console.debug(`Saved state: ${key} = ${cookieValue}`);
  }
  
  /**
   * Load a state value
   */
  loadState(key) {
    if (!this.stateKeys[key]) {
      console.warn(`Unknown state key: ${key}`);
      return null;
    }
    
    const cookieValue = this.getCookie(key);
    const convertedValue = this.convertValue(key, cookieValue);
    
    console.debug(`Loaded state: ${key} = ${convertedValue}`);
    return convertedValue;
  }
  
  /**
   * Load all state values and return as object
   */
  loadAllState() {
    const state = {};
    for (const key in this.stateKeys) {
      state[key] = this.loadState(key);
    }
    return state;
  }
  
  /**
   * Save multiple state values at once
   */
  saveMultipleState(stateObject) {
    for (const [key, value] of Object.entries(stateObject)) {
      this.saveState(key, value);
    }
  }
  
  /**
   * Clear all saved state (reset to defaults)
   */
  clearAllState() {
    for (const key in this.stateKeys) {
      this.deleteCookie(key);
    }
    console.info('All state cleared');
  }
  
  /**
   * Get default value for a state key
   */
  getDefault(key) {
    return this.stateKeys[key]?.default || null;
  }
  
  /**
   * Check if a state key exists
   */
  hasStateKey(key) {
    return key in this.stateKeys;
  }
  
  /**
   * Debug: Log all current state
   */
  debugState() {
    console.group('Current State');
    for (const key in this.stateKeys) {
      const value = this.loadState(key);
      const isDefault = JSON.stringify(value) === JSON.stringify(this.stateKeys[key].default);
      console.log(`${key}: ${JSON.stringify(value)} ${isDefault ? '(default)' : '(custom)'}`);
    }
    console.groupEnd();
  }
}

// Create global instance
window.statePersistence = new StatePersistence();

// Utility functions for backward compatibility
function saveState(key, value) {
  return window.statePersistence.saveState(key, value);
}

function loadState(key) {
  return window.statePersistence.loadState(key);
}

function clearAllState() {
  return window.statePersistence.clearAllState();
}

// Auto-save state when the page is about to unload
window.addEventListener('beforeunload', () => {
  // Save current UI state before leaving
  if (typeof toolbarCollapsed !== 'undefined') {
    saveState('toolbarCollapsed', toolbarCollapsed);
  }
  if (typeof currentDir !== 'undefined') {
    saveState('currentDir', currentDir);
  }
  if (typeof currentPattern !== 'undefined') {
    saveState('currentPattern', currentPattern);
  }
  if (typeof idx !== 'undefined') {
    saveState('currentVideoIndex', idx);
  }
  if (typeof showThumbnails !== 'undefined') {
    saveState('showThumbnails', showThumbnails);
  }
  if (typeof isMaximized !== 'undefined') {
    saveState('isMaximized', isMaximized);
  }
  
  // Save video state if player exists
  const player = document.getElementById('player');
  if (player) {
    saveState('videoVolume', player.volume);
    saveState('videoPlaybackRate', player.playbackRate);
  }
  
  // Save search toolbar state
  if (typeof saveSearchToolbarState === 'function') {
    saveSearchToolbarState();
  }
});

// Expose debug functions globally
window.debugState = () => window.statePersistence.debugState();
window.clearAllState = () => window.statePersistence.clearAllState();

// Add a function to export/import state (useful for debugging)
window.exportState = () => {
  const state = window.statePersistence.loadAllState();
  console.log('Exported state:', JSON.stringify(state, null, 2));
  return state;
};

window.importState = (stateObject) => {
  if (typeof stateObject === 'string') {
    stateObject = JSON.parse(stateObject);
  }
  window.statePersistence.saveMultipleState(stateObject);
  console.log('State imported successfully. Reload the page to see changes.');
};

console.info('State persistence module loaded');