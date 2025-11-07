// Toolbar collapse functionality
let toolbarCollapsed = false;

function toggleToolbar() {
  const container = document.getElementById('toolbar-container');
  const toggleBtn = document.getElementById('toolbar-toggle');
  const body = document.body;
  
  toolbarCollapsed = !toolbarCollapsed;
  
  if (toolbarCollapsed) {
    container.classList.add('collapsed');
    body.classList.add('toolbar-collapsed');
    toggleBtn.textContent = '⌃';
    toggleBtn.title = 'Show Toolbar';
  } else {
    container.classList.remove('collapsed');
    body.classList.remove('toolbar-collapsed');
    toggleBtn.textContent = '⌄';
    toggleBtn.title = 'Hide Toolbar';
  }
  
  // Save toolbar state
  if (typeof saveState === 'function') {
    saveState('toolbarCollapsed', toolbarCollapsed);
  }
}

// State restoration function
function restoreAppState() {
  if (typeof loadState !== 'function') {
    console.warn('State persistence not available yet, will retry...');
    setTimeout(restoreAppState, 100);
    return;
  }
  
  console.info('Restoring app state from cookies...');
  
  // Restore basic app state
  toolbarCollapsed = loadState('toolbarCollapsed') || false;
  currentDir = loadState('currentDir') || '';
  currentPattern = loadState('currentPattern') || '*.mp4';
  
  // Properly restore minFilter with type conversion
  const savedMinFilter = loadState('minFilter');
  if (savedMinFilter === 'none' || savedMinFilter === null) {
    minFilter = null;
  } else if (savedMinFilter === 'rejected') {
    minFilter = 'rejected';
  } else if (savedMinFilter === 'unrated') {
    minFilter = 'unrated';
  } else if (savedMinFilter === 'unrated_and_above') {
    minFilter = 'unrated_and_above';
  } else if (!isNaN(parseInt(savedMinFilter))) {
    minFilter = parseInt(savedMinFilter);
  } else {
    minFilter = null; // Default fallback
  }
  
  showThumbnails = loadState('showThumbnails') !== false; // Default to true
  thumbnailHeight = loadState('thumbnailHeight') || 64;
  isMaximized = loadState('isMaximized') || false;
  idx = loadState('currentVideoIndex') || 0;
  
  const savedExtensions = loadState('toggleExtensions');
  if (savedExtensions && Array.isArray(savedExtensions)) {
    toggleExtensions = savedExtensions;
  }
  
  const savedUserPath = loadState('userPathPrefix');
  if (savedUserPath && savedUserPath !== 'null') {
    userPathPrefix = savedUserPath;
  }
  
  // Apply toolbar state
  if (toolbarCollapsed) {
    const container = document.getElementById('toolbar-container');
    const toggleBtn = document.getElementById('toolbar-toggle');
    const body = document.body;
    
    if (container && toggleBtn && body) {
      container.classList.add('collapsed');
      body.classList.add('toolbar-collapsed');
      toggleBtn.textContent = '⌃';
      toggleBtn.title = 'Show Toolbar';
    }
  }
  
  // Apply maximized state
  if (isMaximized) {
    document.body.classList.add('maximized');
  }
  
  console.info('App state restored successfully');
}

// Initialize video state persistence
function initializeVideoStatePersistence() {
  const player = document.getElementById('player');
  if (!player) return;
  
  // Save volume changes
  player.addEventListener('volumechange', function() {
    if (typeof saveState === 'function') {
      saveState('videoVolume', player.volume);
    }
  });
  
  // Save playback rate changes
  player.addEventListener('ratechange', function() {
    if (typeof saveState === 'function') {
      saveState('videoPlaybackRate', player.playbackRate);
    }
  });
  
  console.info('Video state persistence initialized');
}

// Add toolbar toggle event listener
document.addEventListener('DOMContentLoaded', function() {
  const toggleBtn = document.getElementById('toolbar-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', toggleToolbar);
  }
  
  // Restore state after DOM is ready
  setTimeout(restoreAppState, 50);
  
  // Add video state persistence listeners
  setTimeout(initializeVideoStatePersistence, 100);
  
  // Initialize mobile score bar
  setTimeout(initializeMobileScoreBar, 100);
});

let videos = [];
let filtered = [];
let idx = 0;
let currentDir = "";
let currentPattern = "*.mp4";
let minFilter = null; // null means no filter; otherwise 1..5
let thumbnailsEnabled = false;
let thumbnailHeight = 64;
let isMaximized = false;
let showThumbnails = true; // user preference for showing thumbnails
let toggleExtensions = ["jpg", "png", "mp4"]; // configurable extensions for toggle buttons
let userPathPrefix = null; // User's local mount path for NAS (for clipboard path translation)
let currentZoom = 100; // Current zoom level for mobile image viewing (percentage)
let currentRotation = 0; // Current rotation angle for mobile image viewing (0 or -90 degrees)

// Thumbnail progress tracking
let thumbnailProgressInterval = null;

// Thumbnail lazy loading with Intersection Observer
let thumbnailObserver = null;

// Initialize the Intersection Observer for lazy loading thumbnails
function initThumbnailObserver() {
  // Disconnect existing observer if any
  if (thumbnailObserver) {
    thumbnailObserver.disconnect();
  }
  
  // Create new observer with options for detecting visibility in sidebar
  const observerOptions = {
    root: document.getElementById('sidebar_list'), // Use sidebar_list as the viewport
    rootMargin: '50px', // Load thumbnails 50px before they enter viewport
    threshold: 0.01 // Trigger when even 1% is visible
  };
  
  thumbnailObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        const img = entry.target;
        const thumbnailSrc = img.getAttribute('data-thumbnail-src');
        
        // Only load if not already loaded
        if (thumbnailSrc && !img.src) {
          img.src = thumbnailSrc;
          img.removeAttribute('data-thumbnail-src'); // Remove data attribute after loading
        }
        
        // Stop observing this image once loaded
        thumbnailObserver.unobserve(img);
      }
    });
  }, observerOptions);
}

// Observe all thumbnail images for lazy loading
function observeThumbnails() {
  if (!thumbnailObserver) {
    initThumbnailObserver();
  }
  
  // Find all thumbnail images with data-thumbnail-src (not yet loaded)
  const thumbnailImages = document.querySelectorAll('.thumbnail img[data-thumbnail-src]');
  thumbnailImages.forEach(img => {
    thumbnailObserver.observe(img);
  });
}

// Path translation function for clipboard
function translatePathForUser(containerPath) {
  if (!containerPath || !userPathPrefix) {
    return containerPath; // No translation needed/possible
  }
  
  // Replace container path prefix "/media" with user path prefix
  if (containerPath.startsWith("/media/")) {
    return userPathPrefix + containerPath.substring(6); // Remove "/media" and prepend user prefix
  }
  
  return containerPath; // Return as-is if no translation needed
}

// Progress status management functions
function showProgress(message) {
  const statusElement = document.getElementById('progress_status');
  if (statusElement) {
    statusElement.style.display = 'inline';
    statusElement.innerHTML = `${message} <span class="spinner"></span>`;
  }
}

function hideProgress() {
  const statusElement = document.getElementById('progress_status');
  if (statusElement) {
    statusElement.style.display = 'none';
    statusElement.innerHTML = '';
  }
}

// Toggle button functionality
function initializeToggleButtons() {
  const container = document.getElementById('toggle_buttons');
  if (!container) return;
  
  container.innerHTML = '';
  
  toggleExtensions.forEach(ext => {
    const btn = document.createElement('button');
    btn.className = 'toggle-btn';
    btn.textContent = ext.toUpperCase();
    btn.dataset.extension = ext;
    btn.onclick = () => toggleExtension(ext);
    container.appendChild(btn);
  });
  
  // Update button states based on current pattern
  updateToggleButtonStates();
  
  // Add pattern input listener
  const patternInput = document.getElementById('pattern');
  if (patternInput) {
    patternInput.addEventListener('input', updateToggleButtonStates);
  }
}

function toggleExtension(extension) {
  const patternInput = document.getElementById('pattern');
  if (!patternInput) return;
  
  const currentPattern = patternInput.value.trim();
  const extPattern = `*.${extension}`;
  
  let newPattern;
  if (isExtensionInPattern(extension, currentPattern)) {
    // Remove the extension
    newPattern = removeExtensionFromPattern(extension, currentPattern);
  } else {
    // Add the extension
    newPattern = addExtensionToPattern(extension, currentPattern);
  }
  
  patternInput.value = newPattern;
  updateToggleButtonStates();
}

function isExtensionInPattern(extension, pattern) {
  const extPattern = `*.${extension}`;
  return pattern.split('|').some(part => part.trim() === extPattern);
}

function removeExtensionFromPattern(extension, pattern) {
  const extPattern = `*.${extension}`;
  const parts = pattern.split('|').map(p => p.trim()).filter(p => p !== extPattern);
  return parts.length > 0 ? parts.join('|') : '*.mp4';
}

function addExtensionToPattern(extension, pattern) {
  const extPattern = `*.${extension}`;
  if (!pattern.trim()) {
    return extPattern;
  }
  
  const parts = pattern.split('|').map(p => p.trim()).filter(p => p && p !== extPattern);
  parts.push(extPattern);
  return parts.join('|');
}

function updateToggleButtonStates() {
  const patternInput = document.getElementById('pattern');
  if (!patternInput) return;
  
  const currentPattern = patternInput.value.trim();
  
  toggleExtensions.forEach(ext => {
    const btn = document.querySelector(`[data-extension="${ext}"]`);
    if (btn) {
      if (isExtensionInPattern(ext, currentPattern)) {
        btn.className = 'toggle-btn active';
      } else {
        btn.className = 'toggle-btn inactive';
      }
    }
  });
}

function updateThumbnailStatus() {
  fetch('/api/thumbnail-progress')
    .then(r => r.json())
    .then(progress => {
      if (progress.generating && progress.total > 0) {
        showProgress(`Generating thumbnails (${progress.current}/${progress.total})`);
        // Start polling if not already started
        if (!thumbnailProgressInterval) {
          thumbnailProgressInterval = setInterval(updateThumbnailStatus, 500);
        }
      } else {
        hideProgress();
        // Stop polling when done
        if (thumbnailProgressInterval) {
          clearInterval(thumbnailProgressInterval);
          thumbnailProgressInterval = null;
        }
      }
    })
    .catch(() => {
      // Hide progress on error
      hideProgress();
      // Stop polling on error
      if (thumbnailProgressInterval) {
        clearInterval(thumbnailProgressInterval);
        thumbnailProgressInterval = null;
      }
    });
}

let currentMeta = null;
function togglePngInfo(show){
  const panel = document.getElementById('pnginfo_panel');
  if (!panel) return;
  if (show === undefined){ panel.style.display = (panel.style.display==='none' || panel.style.display==='') ? 'block' : 'none'; }
  else { panel.style.display = show ? 'block' : 'none'; }
}
function setupPngInfo(meta, name){
  currentMeta = meta || null;
  const controls = document.getElementById('pnginfo_controls');
  const textDiv = document.getElementById('pnginfo_text');
  togglePngInfo(false);
  if (meta && meta.png_text && isImageName(name) && name.toLowerCase().endsWith('.png')){
    controls.style.display = 'flex';
    textDiv.textContent = meta.png_text;
  } else {
    controls.style.display = 'none';
    textDiv.textContent = '';
  }
}
document.addEventListener('click', (e)=>{
  if (e.target && e.target.id === 'pnginfo_btn'){ 
    togglePngInfo();   // <-- toggles open/close
  }
  if (e.target && e.target.id === 'pnginfo_copy'){ 
    const text = (document.getElementById('pnginfo_text').textContent)||'';
    if (!navigator.clipboard){ 
      const ta = document.createElement('textarea'); 
      ta.value = text; 
      document.body.appendChild(ta); 
      ta.select(); 
      document.execCommand('copy'); 
      document.body.removeChild(ta);
    } else {
      navigator.clipboard.writeText(text).catch(()=>{});
    }
  }
  if (e.target && e.target.id === 'toggle_thumbnails'){ 
    showThumbnails = e.target.checked;
    renderSidebar();
  }
});

// Helper function to detect mobile devices
function isMobileDevice() {
  return window.innerWidth <= 768 || /Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i.test(navigator.userAgent);
}

function toggleMaximize(){
  const videoWrap = document.querySelector('.video-wrap');
  const player = document.getElementById('player');
  const imgview = document.getElementById('imgview');
  const maximizeBtn = document.getElementById('maximize-btn');
  
  if (!videoWrap || !maximizeBtn) return;
  
  // On mobile, open in new page instead of overlay
  if (isMobileDevice() && !isMaximized) {
    const currentVideo = videos[idx];
    if (currentVideo) {
      const mediaUrl = '/media/' + encodeURIComponent(currentVideo.name);
      // Create a URL for the maximized view
      const maximizedUrl = '/maximize/' + encodeURIComponent(currentVideo.name);
      
      // Navigate to the maximized view page
      window.location.href = maximizedUrl;
    }
    return;
  }
  
  isMaximized = !isMaximized;
  
  if (isMaximized) {
    // Calculate available space
    const viewportWidth = window.innerWidth;
    const viewportHeight = window.innerHeight;
    
    // Get current media dimensions
    let mediaWidth, mediaHeight;
    if (player && player.style.display !== 'none') {
      mediaWidth = player.videoWidth || 960;
      mediaHeight = player.videoHeight || 540;
    } else if (imgview && imgview.style.display !== 'none') {
      mediaWidth = imgview.naturalWidth || 960;
      mediaHeight = imgview.naturalHeight || 540;
    } else {
      mediaWidth = 960;
      mediaHeight = 540;
    }
    
    // Calculate scale to fit screen while maintaining aspect ratio
    const scaleX = (viewportWidth - 32) / mediaWidth; // 32px for padding
    const scaleY = (viewportHeight - 120) / mediaHeight; // 120px for UI elements
    const scale = Math.min(scaleX, scaleY, 3); // Cap at 3x zoom
    
    // Apply maximized styles
    videoWrap.style.position = 'fixed';
    videoWrap.style.top = '50%';
    videoWrap.style.left = '50%';
    videoWrap.style.transform = 'translate(-50%, -50%)';
    videoWrap.style.zIndex = '1000';
    videoWrap.style.background = '#000';
    videoWrap.style.maxWidth = 'none';
    videoWrap.style.maxHeight = 'none';
    
    if (player && player.style.display !== 'none') {
      player.style.width = (mediaWidth * scale) + 'px';
      player.style.height = (mediaHeight * scale) + 'px';
      player.style.maxWidth = 'none';
      player.style.maxHeight = 'none';
    }
    
    if (imgview && imgview.style.display !== 'none') {
      imgview.style.width = (mediaWidth * scale) + 'px';
      imgview.style.height = (mediaHeight * scale) + 'px';
      imgview.style.maxWidth = 'none';
      imgview.style.maxHeight = 'none';
    }
    
    // Update button icon and title
    maximizeBtn.innerHTML = svgMinimize();
    maximizeBtn.title = 'Return to actual size';
    
    // Add backdrop
    const backdrop = document.createElement('div');
    backdrop.id = 'maximize-backdrop';
    backdrop.style.position = 'fixed';
    backdrop.style.top = '0';
    backdrop.style.left = '0';
    backdrop.style.width = '100%';
    backdrop.style.height = '100%';
    backdrop.style.backgroundColor = 'rgba(0,0,0,0.8)';
    backdrop.style.zIndex = '999';
    backdrop.addEventListener('click', toggleMaximize);
    document.body.appendChild(backdrop);
    
  } else {
    // Reset to normal size
    videoWrap.style.position = '';
    videoWrap.style.top = '';
    videoWrap.style.left = '';
    videoWrap.style.transform = '';
    videoWrap.style.zIndex = '';
    videoWrap.style.background = '';
    videoWrap.style.maxWidth = '';
    videoWrap.style.maxHeight = '';
    
    if (player && player.style.display !== 'none') {
      player.style.width = '960px';
      player.style.height = '540px';
      player.style.maxWidth = '';
      player.style.maxHeight = '';
    }
    
    if (imgview && imgview.style.display !== 'none') {
      imgview.style.width = '';
      imgview.style.height = '';
      imgview.style.maxWidth = '960px';
      imgview.style.maxHeight = '540px';
    }
    
    // Update button icon and title
    maximizeBtn.innerHTML = svgMaximize();
    maximizeBtn.title = 'Maximize media';
    
    // Remove backdrop
    const backdrop = document.getElementById('maximize-backdrop');
    if (backdrop) backdrop.remove();
  }
  
  // Save maximized state
  if (typeof saveState === 'function') {
    saveState('isMaximized', isMaximized);
  }
  
  // Update mobile score bar maximize button
  const currentVideo = filtered[idx];
  if (currentVideo) {
    updateMobileScoreBar(currentVideo.score || 0);
  }
}

function updateDownloadButton(name){
  const db = document.getElementById('download_btn');
  if (!db) return;
  if (!name){ db.disabled = true; return; }
  db.disabled = false;
  db.onclick = () => {
    try { window.location.href = '/download/' + encodeURIComponent(name); }
    catch(e){ alert('Download failed to start: ' + e); }
  };
}

function updateMediaDownloadButton(name){
  const db = document.getElementById('media-download-btn');
  if (!db) return;
  if (!name){ db.disabled = true; return; }
  db.disabled = false;
  db.onclick = () => {
    try { window.location.href = '/download/' + encodeURIComponent(name); }
    catch(e){ alert('Download failed to start: ' + e); }
  };
}


function updateThumbnailToggleButton(){
  const checkbox = document.getElementById('toggle_thumbnails');
  const icon = document.querySelector('.thumbnail-icon');
  if (!checkbox || !icon) return;
  
  checkbox.checked = showThumbnails;
  icon.innerHTML = svgThumbnail();
  icon.title = showThumbnails ? 'Hide thumbnails' : 'Show thumbnails';
}
function renderScoreBar(score){
  const bar = document.getElementById("scorebar");
  let html = `<div style="display:flex; gap:8px; align-items:center; justify-content:space-between;">`;
  html += `<div style="display:flex; gap:8px; align-items:center;">`;
  
  // Make reject icon clickable
  html += `<button id="scorebar-reject" class="scorebar-icon-btn" title="Reject media" style="background:none; border:none; padding:0; cursor:pointer;">`;
  html += svgReject(score === -1);
  html += `</button>`;
  
  // Add clear button (vertical pipe)
  html += `<button id="scorebar-clear" class="scorebar-icon-btn" title="Clear score (no rating)" style="background:none; border:none; padding:0; cursor:pointer;">`;
  html += svgClear(score === 0);
  html += `</button>`;
  
  // Make star icons clickable  
  const stars = (score === -1) ? 0 : Math.max(0, score||0);
  for (let i=0;i<5;i++) {
    html += `<button id="scorebar-star-${i+1}" class="scorebar-icon-btn" data-star="${i+1}" title="Rate ${i+1} star${i > 0 ? 's' : ''}" style="background:none; border:none; padding:0; cursor:pointer;">`;
    html += svgStar(i<stars);
    html += `</button>`;
  }
  
  html += `</div>`;
  html += `<div style="display:flex; gap:8px; align-items:center;">`;
  html += `<button id="media-download-btn" class="maximize-btn" title="Download current media" disabled>`;
  html += svgDownload();
  html += `</button>`;
  html += `<button id="maximize-btn" class="maximize-btn" title="${isMaximized ? 'Return to actual size' : 'Maximize media'}">`;
  html += isMaximized ? svgMinimize() : svgMaximize();
  html += `</button>`;
  html += `</div>`;
  html += `</div>`;
  bar.innerHTML = html;
  
  // Update mobile score bar
  updateMobileScoreBar(score);
  
  // Attach event listeners to the new buttons
  const maximizeBtn = document.getElementById('maximize-btn');
  if (maximizeBtn) {
    maximizeBtn.addEventListener('click', toggleMaximize);
  }
  
  // Attach event listener to clickable reject icon
  const rejectBtn = document.getElementById('scorebar-reject');
  if (rejectBtn) {
    rejectBtn.addEventListener('click', () => {
      postScore(-1);
    });
  }
  
  // Attach event listener to clickable clear icon
  const clearBtn = document.getElementById('scorebar-clear');
  if (clearBtn) {
    clearBtn.addEventListener('click', () => {
      postScore(0);
    });
  }
  
  // Attach event listeners to clickable star icons
  for (let i = 1; i <= 5; i++) {
    const starBtn = document.getElementById(`scorebar-star-${i}`);
    if (starBtn) {
      starBtn.addEventListener('click', () => {
        postScore(i);
      });
    }
  }
}

// Mobile Score Bar Functions
function updateMobileScoreBar(score) {
  const mobileScoreBtn = document.getElementById('mobile-score-btn');
  const mobileDownloadBtn = document.getElementById('mobile-download-btn');
  const mobileMaximizeBtn = document.getElementById('mobile-maximize-btn');
  const mobilePrevBtn = document.getElementById('mobile-prev-btn');
  const mobileNextBtn = document.getElementById('mobile-next-btn');
  
  if (!mobileScoreBtn) return; // Mobile score bar not present
  
  // Update score button display with SVG icons
  if (score === -1) {
    mobileScoreBtn.innerHTML = svgMobileReject();
    mobileScoreBtn.className = 'mobile-score-btn active';
    mobileScoreBtn.title = 'Rejected';
  } else if (score === 0 || !score) {
    mobileScoreBtn.innerHTML = svgMobileStarEmpty();
    mobileScoreBtn.className = 'mobile-score-btn';
    mobileScoreBtn.title = 'Rate media';
  } else {
    mobileScoreBtn.innerHTML = svgMobileStarFilled(score);
    mobileScoreBtn.className = 'mobile-score-btn active';
    mobileScoreBtn.title = `${score} star${score > 1 ? 's' : ''}`;
  }
  
  // Update download button state
  if (mobileDownloadBtn) {
    const currentVideo = filtered[idx];
    if (currentVideo) {
      mobileDownloadBtn.disabled = false;
      mobileDownloadBtn.title = 'Download current media';
    } else {
      mobileDownloadBtn.disabled = true;
      mobileDownloadBtn.title = 'No media to download';
    }
  }
  
  // Update maximize button
  if (mobileMaximizeBtn) {
    if (isMaximized) {
      mobileMaximizeBtn.textContent = '⤡';
      mobileMaximizeBtn.title = 'Return to actual size';
    } else {
      mobileMaximizeBtn.textContent = '⤢';
      mobileMaximizeBtn.title = 'Maximize media';
    }
  }
  
  // Update navigation buttons
  if (mobilePrevBtn) {
    mobilePrevBtn.disabled = (idx <= 0);
    mobilePrevBtn.style.opacity = (idx <= 0) ? '0.4' : '1';
  }
  if (mobileNextBtn) {
    mobileNextBtn.disabled = (idx >= filtered.length - 1);
    mobileNextBtn.style.opacity = (idx >= filtered.length - 1) ? '0.4' : '1';
  }
  
  // Update popover selected state
  updateMobileScorePopover(score);
  
  // Update mobile menu state
  updateMobileMenuState();
}

function updateMobileMenuState() {
  const currentVideo = filtered[idx];
  const nsfwToggle = document.getElementById('mobile-nsfw-toggle');
  
  if (!nsfwToggle || !currentVideo) return;
  
  // Update NSFW toggle state based on current video
  nsfwToggle.checked = currentVideo.nsfw || false;
}

function updateMobileScorePopover(score) {
  const popover = document.getElementById('mobile-score-popover');
  if (!popover) return;
  
  // Clear all selected states
  popover.querySelectorAll('.mobile-score-option').forEach(btn => {
    btn.classList.remove('selected');
  });
  
  // Set selected state for current score
  const selectedBtn = popover.querySelector(`[data-score="${score || 0}"]`);
  if (selectedBtn) {
    selectedBtn.classList.add('selected');
  }
  
  // Update star buttons filled/unfilled states
  const starButtons = popover.querySelectorAll('.mobile-score-option.star-btn');
  const currentScore = score > 0 ? score : 0;
  
  starButtons.forEach((btn, index) => {
    const starValue = index + 1; // stars are 1-5
    btn.classList.remove('filled');
    
    if (starValue <= currentScore) {
      btn.classList.add('filled');
      btn.textContent = '★'; // Filled star
    } else {
      btn.textContent = '☆'; // Unfilled star
    }
  });
}

function initializeMobileScoreBar() {
  const mobileScoreBtn = document.getElementById('mobile-score-btn');
  const mobilePopover = document.getElementById('mobile-score-popover');
  const mobilePrevBtn = document.getElementById('mobile-prev-btn');
  const mobileNextBtn = document.getElementById('mobile-next-btn');
  const mobileDownloadBtn = document.getElementById('mobile-download-btn');
  const mobileMaximizeBtn = document.getElementById('mobile-maximize-btn');
  const mobileMenuBtn = document.getElementById('mobile-menu-btn');
  const mobileMenuPopover = document.getElementById('mobile-menu-popover');
  const mobileNsfwToggle = document.getElementById('mobile-nsfw-toggle');
  
  if (!mobileScoreBtn || !mobilePopover) return;
  
  // Score button toggle popover
  mobileScoreBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    // Close menu popover if open
    if (mobileMenuPopover) {
      mobileMenuPopover.classList.remove('active');
    }
    mobilePopover.classList.toggle('active');
  });
  
  // Score option buttons
  mobilePopover.querySelectorAll('.mobile-score-option').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.stopPropagation();
      const score = parseInt(btn.dataset.score);
      postScore(score);
      mobilePopover.classList.remove('active');
    });
  });
  
  // Navigation buttons
  if (mobilePrevBtn) {
    mobilePrevBtn.addEventListener('click', () => {
      if (idx > 0) {
        show(idx - 1);
      }
    });
  }
  
  if (mobileNextBtn) {
    mobileNextBtn.addEventListener('click', () => {
      if (idx < filtered.length - 1) {
        show(idx + 1);
      }
    });
  }
  
  // Download button
  if (mobileDownloadBtn) {
    mobileDownloadBtn.addEventListener('click', () => {
      const currentVideo = filtered[idx];
      if (currentVideo) {
        const link = document.createElement('a');
        link.href = '/media/' + encodeURIComponent(currentVideo.name);
        link.download = currentVideo.name;
        link.click();
      }
    });
  }
  
  // Maximize button
  if (mobileMaximizeBtn) {
    mobileMaximizeBtn.addEventListener('click', toggleMaximize);
  }
  
  // Menu button toggle popover
  if (mobileMenuBtn && mobileMenuPopover) {
    mobileMenuBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Close score popover if open
      mobilePopover.classList.remove('active');
      mobileMenuPopover.classList.toggle('active');
    });
  }
  
  // NSFW toggle handler
  if (mobileNsfwToggle) {
    mobileNsfwToggle.addEventListener('change', (e) => {
      const currentVideo = filtered[idx];
      if (currentVideo) {
        const nsfw = e.target.checked;
        updateNsfwStatus(currentVideo.name, nsfw);
      }
    });
  }
  
  // Zoom functionality for mobile images
  const mobileZoomBtn = document.getElementById('mobile-zoom-btn');
  const mobileZoomPopover = document.getElementById('mobile-zoom-popover');
  const mobileZoomSlider = document.getElementById('mobile-zoom-slider');
  const mobileZoomFitBtn = document.getElementById('mobile-zoom-fit-btn');
  const mobileZoomAspectBtn = document.getElementById('mobile-zoom-aspect-btn');
  const mobileZoomRotateBtn = document.getElementById('mobile-zoom-rotate-btn');
  const mobileZoomMain = document.getElementById('mobile-zoom-main');
  const mobileZoomAspect = document.getElementById('mobile-zoom-aspect');
  const mobileZoomAspectClose = document.getElementById('mobile-zoom-aspect-close');
  const mobileZoomAspectPills = document.getElementById('mobile-zoom-aspect-pills');
  
  if (mobileZoomBtn && mobileZoomPopover && mobileZoomSlider) {
    // Zoom button toggle popover
    mobileZoomBtn.addEventListener('click', (e) => {
      e.stopPropagation();
      // Close other popovers
      mobilePopover.classList.remove('active');
      if (mobileMenuPopover) {
        mobileMenuPopover.classList.remove('active');
      }
      mobileZoomPopover.classList.toggle('active');
      // Reset to main view when opening
      if (mobileZoomPopover.classList.contains('active')) {
        showZoomMainView();
      }
    });
    
    // Zoom slider handler
    mobileZoomSlider.addEventListener('input', (e) => {
      const zoomValue = parseInt(e.target.value);
      currentZoom = zoomValue;
      applyImageZoom(zoomValue);
    });
    
    // Fit to pane button handler
    if (mobileZoomFitBtn) {
      mobileZoomFitBtn.addEventListener('click', () => {
        // Calculate the zoom needed to fit the image width (or height if rotated) to the pane
        const fitZoom = calculateFitToWidthZoom();
        currentZoom = fitZoom;
        mobileZoomSlider.value = fitZoom;
        applyImageZoom(fitZoom);
      });
    }
    
    // Aspect ratio button handler
    if (mobileZoomAspectBtn) {
      mobileZoomAspectBtn.addEventListener('click', () => {
        showZoomAspectView();
      });
    }
    
    // Rotation button handler
    if (mobileZoomRotateBtn) {
      mobileZoomRotateBtn.addEventListener('click', () => {
        toggleImageRotation();
      });
    }
    
    // Aspect ratio close button handler
    if (mobileZoomAspectClose) {
      mobileZoomAspectClose.addEventListener('click', () => {
        showZoomMainView();
      });
    }
    
    // Aspect ratio pill handlers
    if (mobileZoomAspectPills) {
      mobileZoomAspectPills.querySelectorAll('.aspect-pill').forEach(pill => {
        pill.addEventListener('click', () => {
          // Update active state
          mobileZoomAspectPills.querySelectorAll('.aspect-pill').forEach(p => p.classList.remove('active'));
          pill.classList.add('active');
          
          // Apply aspect ratio
          const aspectRatio = pill.dataset.aspect;
          applyAspectRatio(aspectRatio);
        });
      });
    }
  }
  
  // Helper function to show main zoom view
  function showZoomMainView() {
    if (mobileZoomMain && mobileZoomAspect) {
      mobileZoomMain.style.display = 'block';
      mobileZoomAspect.style.display = 'none';
    }
  }
  
  // Helper function to show aspect ratio view
  function showZoomAspectView() {
    if (mobileZoomMain && mobileZoomAspect) {
      mobileZoomMain.style.display = 'none';
      mobileZoomAspect.style.display = 'block';
    }
  }
  
  // Close popovers when clicking outside
  document.addEventListener('click', (e) => {
    if (!mobilePopover.contains(e.target) && !mobileScoreBtn.contains(e.target)) {
      mobilePopover.classList.remove('active');
    }
    if (mobileMenuPopover && !mobileMenuPopover.contains(e.target) && !mobileMenuBtn.contains(e.target)) {
      mobileMenuPopover.classList.remove('active');
    }
    if (mobileZoomPopover && !mobileZoomPopover.contains(e.target) && mobileZoomBtn && !mobileZoomBtn.contains(e.target)) {
      mobileZoomPopover.classList.remove('active');
    }
  });
  
  // Close popovers on escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (mobilePopover.classList.contains('active')) {
        mobilePopover.classList.remove('active');
      }
      if (mobileMenuPopover && mobileMenuPopover.classList.contains('active')) {
        mobileMenuPopover.classList.remove('active');
      }
      if (mobileZoomPopover && mobileZoomPopover.classList.contains('active')) {
        mobileZoomPopover.classList.remove('active');
      }
    }
  });
}

// Helper function to check if current media is a valid image for zoom/rotation operations
function isCurrentMediaAnImage() {
  const currentMedia = filtered[idx];
  return currentMedia && isImageName(currentMedia.name);
}

function calculateFitToWidthZoom() {
  const imgview = document.getElementById('imgview');
  const videoWrap = document.querySelector('.video-wrap');
  
  if (!imgview || imgview.style.display === 'none') return 100;
  if (!isMobileDevice()) return 100;
  if (!isCurrentMediaAnImage()) return 100;
  
  // Get the natural image dimensions
  const imageWidth = imgview.naturalWidth;
  const imageHeight = imgview.naturalHeight;
  
  if (!imageWidth || !imageHeight) return 100;
  
  // Get the video-wrap dimensions (excluding padding)
  const videoWrapRect = videoWrap.getBoundingClientRect();
  const computedStyle = window.getComputedStyle(videoWrap);
  const paddingLeft = parseFloat(computedStyle.paddingLeft) || 0;
  const paddingRight = parseFloat(computedStyle.paddingRight) || 0;
  const wrapWidth = videoWrapRect.width - paddingLeft - paddingRight;
  
  // Get the current rendered dimensions of the image (after CSS scaling)
  const imgRect = imgview.getBoundingClientRect();
  const currentRenderedWidth = imgRect.width;
  const currentRenderedHeight = imgRect.height;
  
  // Determine which rendered dimension will be the horizontal dimension after rotation
  let horizontalRenderedDimension;
  if (currentRotation === -90) {
    // When rotated -90 degrees, the rendered height becomes the horizontal dimension
    horizontalRenderedDimension = currentRenderedHeight;
  } else {
    // Normal orientation: rendered width is the horizontal dimension
    horizontalRenderedDimension = currentRenderedWidth;
  }
  
  // Calculate zoom percentage needed to fit the horizontal dimension to the wrap width
  // We need to scale relative to the current rendered size (which is already at 100% in our zoom scale)
  const zoomPercent = (wrapWidth / horizontalRenderedDimension) * 100;
  
  // Clamp to reasonable values (min 50%, max 500%)
  return Math.max(50, Math.min(500, zoomPercent));
}

function applyImageZoom(zoomPercent) {
  const imgview = document.getElementById('imgview');
  const videoWrap = document.querySelector('.video-wrap');
  
  if (!imgview || imgview.style.display === 'none') return;
  if (!isMobileDevice()) return; // Only apply zoom on mobile
  if (!isCurrentMediaAnImage()) return; // Ensure we're working with an image, not a video
  
  const scale = zoomPercent / 100;
  
  // Apply transform for zoom and rotation with transform-origin at center
  imgview.style.transformOrigin = 'center';
  imgview.style.transform = `scale(${scale}) rotate(${currentRotation}deg)`;
  
  // Enable touch panning when zoomed in
  if (scale > 1) {
    if (videoWrap) {
      videoWrap.style.overflow = 'auto';
      videoWrap.style.touchAction = 'pan-x pan-y';
    }
  } else {
    if (videoWrap) {
      videoWrap.style.overflow = 'hidden';
      videoWrap.style.touchAction = 'auto';
    }
  }
}

function toggleImageRotation() {
  const imgview = document.getElementById('imgview');
  const mobileZoomRotateBtn = document.getElementById('mobile-zoom-rotate-btn');
  
  if (!imgview || imgview.style.display === 'none') return;
  if (!isMobileDevice()) return; // Only apply on mobile
  if (!isCurrentMediaAnImage()) return; // Ensure we're working with an image, not a video
  
  // Toggle rotation between 0 and -90 degrees (counterclockwise)
  currentRotation = currentRotation === 0 ? -90 : 0;
  
  // Update button state
  if (mobileZoomRotateBtn) {
    if (currentRotation === -90) {
      mobileZoomRotateBtn.classList.add('rotated');
    } else {
      mobileZoomRotateBtn.classList.remove('rotated');
    }
  }
  
  // Apply the rotation with current zoom
  applyImageZoom(currentZoom);
}

function applyAspectRatio(aspectRatio) {
  const videoWrap = document.querySelector('.video-wrap');
  if (!videoWrap) return;
  if (!isMobileDevice()) return; // Only apply on mobile
  
  // Remove any existing aspect ratio class
  videoWrap.classList.remove('aspect-free', 'aspect-1-1', 'aspect-4-3', 'aspect-16-9', 'aspect-21-9', 'aspect-9-16', 'aspect-3-4');
  
  // Add the new aspect ratio class (CSS handles the styling)
  if (aspectRatio === 'free') {
    videoWrap.classList.add('aspect-free');
    // Calculate and apply the aspect ratio of the current media
    updateFreeAspectRatio();
  } else {
    // Clear any inline aspect ratio when using preset ratios
    videoWrap.style.aspectRatio = '';
    const className = 'aspect-' + aspectRatio.replace(':', '-');
    videoWrap.classList.add(className);
  }
}

// Helper function to update aspect ratio when "free" is selected
function updateFreeAspectRatio() {
  const videoWrap = document.querySelector('.video-wrap');
  if (!videoWrap) return;
  if (!isMobileDevice()) return; // Only apply on mobile
  if (!videoWrap.classList.contains('aspect-free')) return; // Only update if free aspect is selected
  
  const player = document.getElementById('player');
  const imgview = document.getElementById('imgview');
  
  let width, height;
  
  // Get dimensions from the currently visible media element
  if (player && player.style.display !== 'none' && player.readyState >= 1) {
    // Video element - check readyState to ensure metadata is loaded
    width = player.videoWidth;
    height = player.videoHeight;
  } else if (imgview && imgview.style.display !== 'none' && imgview.complete) {
    // Image element - check complete to ensure image is loaded
    width = imgview.naturalWidth;
    height = imgview.naturalHeight;
  }
  
  // Apply the calculated aspect ratio to the video-wrap only if dimensions are valid
  if (width && height && width > 0 && height > 0) {
    videoWrap.style.aspectRatio = `${width} / ${height}`;
  }
}

function scoreBadge(s){
  if (s === -1) return 'R';
  if (!s || s < 1) return '—';
  return s + '★';
}
function formatDatePill(isoDateString){
  if (!isoDateString) return '';
  try {
    const date = new Date(isoDateString);
    if (isNaN(date.getTime())) return '';
    const year = String(date.getFullYear() % 100).padStart(2, '0');
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}/${month}/${day}`;
  } catch (e) {
    return '';
  }
}
function renderSidebar(){
  const list = document.getElementById('sidebar_list');
  if (!list) return;
  let html = '';
  const namesInFiltered = new Set(filtered.map(v => v.name));
  videos.forEach((v) => {
    const inFiltered = namesInFiltered.has(v.name);
    const s = scoreBadge(v.score || 0);
    const classes = ['item'];
    if (!inFiltered) classes.push('disabled');
    if (filtered.length && filtered[idx] && filtered[idx].name === v.name) classes.push('current');
    
    let thumbHtml = '';
    if (thumbnailsEnabled && showThumbnails) {
      // Use data-thumbnail-src for lazy loading instead of src
      // This prevents immediate loading of all thumbnails
      thumbHtml = `<div class="thumbnail"><img data-thumbnail-src="/thumbnail/${encodeURIComponent(v.name)}" alt="" style="height:${thumbnailHeight}px" onerror="this.style.display='none'"></div>`;
      classes.push('with-thumbnails');
    }
    
    const datePill = formatDatePill(v.original_created_at);
    
    html += `<div class="${classes.join(' ')}" data-name="${v.name}" ${inFiltered ? '' : 'data-disabled="1"'}>` +
            thumbHtml +
            `<div class="content">` +
            `<div class="name" title="${v.name}">${v.name}</div>` +
            `<div class="meta-row">` +
            `<div class="score">${s}</div>` +
            (datePill ? `<div class="date-pill">${datePill}</div>` : '') +
            `</div>` +
            `</div>` +
            `</div>`;
  });
  list.innerHTML = html;
  list.querySelectorAll('.item').forEach(el => {
    if (el.getAttribute('data-disabled') === '1') return;
    el.addEventListener('click', () => {
      const name = el.getAttribute('data-name');
      const j = filtered.findIndex(x => x.name === name);
      if (j >= 0) show(j);
    });
  });
  
  // Initialize lazy loading for thumbnails after rendering
  if (thumbnailsEnabled && showThumbnails) {
    // Use setTimeout to defer observation until after DOM updates
    setTimeout(() => observeThumbnails(), 0);
  }
}
function applyFilter(){
  if (minFilter === null) {
    filtered = videos.slice();
  } else if (minFilter === 'rejected') {
    filtered = videos.filter(v => v.score === -1);
  } else if (minFilter === 'unrated') {
    filtered = videos.filter(v => !v.score || v.score === 0);
  } else if (minFilter === 'unrated_and_above') {
    filtered = videos.filter(v => !v.score || v.score >= 0);
  } else {
    filtered = videos.filter(v => (v.score||0) >= minFilter);
  }
  const info = document.getElementById('filter_info');
  let label;
  if (minFilter === null) {
    label = 'No filter';
  } else if (minFilter === 'rejected') {
    label = 'Rejected only';
  } else if (minFilter === 'unrated') {
    label = 'Unrated only';
  } else if (minFilter === 'unrated_and_above') {
    label = 'Unrated and above';
  } else {
    label = 'rating ≥ ' + minFilter;
  }
  info.textContent = `${label} — showing ${filtered.length}/${videos.length}`;
}
function isVideoName(n){ return n.toLowerCase().endsWith('.mp4'); }
function isImageName(n){ const s=n.toLowerCase(); return s.endsWith('.png')||s.endsWith('.jpg')||s.endsWith('.jpeg'); }
function showMedia(url, name){
  const vtag = document.getElementById('player');
  const itag = document.getElementById('imgview');
  const mobileZoomBtn = document.getElementById('mobile-zoom-btn');
  const mobileZoomRotateBtn = document.getElementById('mobile-zoom-rotate-btn');
  const videoWrap = document.querySelector('.video-wrap');
  
  // Reset zoom and rotation state when switching media
  currentZoom = 100;
  currentRotation = 0;
  const mobileZoomSlider = document.getElementById('mobile-zoom-slider');
  const mobileZoomValue = document.getElementById('mobile-zoom-value');
  if (mobileZoomSlider) mobileZoomSlider.value = 100;
  if (mobileZoomValue) mobileZoomValue.textContent = '100%';
  if (mobileZoomRotateBtn) mobileZoomRotateBtn.classList.remove('rotated');
  
  if (isVideoName(name)){
    itag.style.display = 'none'; itag.removeAttribute('src');
    vtag.style.display = ''; vtag.src = url + '#t=0.001';
    
    // Hide zoom button for videos
    if (mobileZoomBtn) mobileZoomBtn.style.display = 'none';
    
    // Restore video state when video loads
    vtag.addEventListener('loadedmetadata', function restoreVideoState() {
      if (typeof loadState === 'function') {
        const savedVolume = loadState('videoVolume');
        const savedPlaybackRate = loadState('videoPlaybackRate');
        
        if (savedVolume !== null && savedVolume !== undefined) {
          vtag.volume = Math.max(0, Math.min(1, savedVolume));
        }
        if (savedPlaybackRate !== null && savedPlaybackRate !== undefined) {
          vtag.playbackRate = Math.max(0.25, Math.min(4, savedPlaybackRate));
        }
      }
      
      // Update aspect ratio if "free" is selected
      if (videoWrap && videoWrap.classList.contains('aspect-free')) {
        updateFreeAspectRatio();
      }
      
      // Remove the event listener to avoid multiple calls
      vtag.removeEventListener('loadedmetadata', restoreVideoState);
    }, { once: true });
    
  } else if (isImageName(name)){
    vtag.pause && vtag.pause(); vtag.removeAttribute('src'); vtag.load && vtag.load(); vtag.style.display='none';
    itag.style.display = ''; itag.src = url;
    
    // Reset image transform
    itag.style.transform = '';
    itag.style.transformOrigin = '';
    if (videoWrap) {
      videoWrap.style.overflow = 'hidden';
      videoWrap.style.touchAction = 'auto';
    }
    
    // Initialize Viewer.js for this image when it loads
    itag.addEventListener('load', function initViewerOnLoad() {
      // Initialize Viewer.js integration if available
      if (window.imageViewerIntegration) {
        window.imageViewerIntegration.initialize();
      }
      
      // Update aspect ratio if "free" is selected
      if (videoWrap && videoWrap.classList.contains('aspect-free')) {
        updateFreeAspectRatio();
      }
    }, { once: true });
    
    // Keep old mobile zoom button visible on mobile as a backup/alternative
    // Viewer.js will be the primary method, but old zoom is still available
    if (mobileZoomBtn && isMobileDevice()) {
      mobileZoomBtn.style.display = '';
    }
    
  } else {
    vtag.style.display='none'; vtag.removeAttribute('src');
    itag.style.display=''; itag.src = url;
    
    // Hide zoom button for unknown types
    if (mobileZoomBtn) mobileZoomBtn.style.display = 'none';
  }
  const b1 = document.getElementById('extract_one'); const b2 = document.getElementById('extract_filtered');
  if (b1 && b2){ const enable = isVideoName(name); b1.disabled = !enable; b2.disabled = !enable; }
}
function show(i){
  const filenameTextEl = document.getElementById('filename-text');
  const clipboardBtn = document.getElementById('filename-clipboard');
  
  if (filtered.length === 0){
    filenameTextEl.textContent = '(no items match filter)';
    clipboardBtn.style.display = 'none';
    const player = document.getElementById('player');
    player.removeAttribute('src'); player.load();
    renderScoreBar(0);
    updateDownloadButton(null);
    updateMediaDownloadButton(null);
    const controls = document.getElementById('pnginfo_controls'); if (controls) controls.style.display='none';
    const panel = document.getElementById('pnginfo_panel'); if (panel) panel.style.display='none';
    renderSidebar();
    return;
  }
  idx = Math.max(0, Math.min(i, filtered.length-1));
  const v = filtered[idx];
  showMedia(v.url, v.name);
  
  // Save current video index
  if (typeof saveState === 'function') {
    saveState('currentVideoIndex', idx);
  }
  
  // Find the file extension to position clipboard icon correctly
  const extensionMatch = v.name.match(/\.([\w]+)$/i);
  const extension = extensionMatch ? extensionMatch[0] : '';
  const nameWithoutExt = extension ? v.name.slice(0, -extension.length) : v.name;
  
  let displayText = `${idx+1}/${filtered.length}  •  ../${nameWithoutExt}`;
  if (extension) {
    displayText += extension;
  }
  
  filenameTextEl.textContent = displayText;
  
  // Set up clipboard functionality
  clipboardBtn.innerHTML = svgClipboard();
  clipboardBtn.style.display = 'inline-block';
  clipboardBtn.onclick = () => {
    const containerPath = v.path || (currentDir + '/' + v.name);
    const userPath = translatePathForUser(containerPath);
    if (!navigator.clipboard) {
      const ta = document.createElement('textarea');
      ta.value = userPath;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    } else {
      navigator.clipboard.writeText(userPath).catch(() => {});
    }
  };
  
  fetch('/api/meta/' + encodeURIComponent(v.name))
    .then(r => r.ok ? r.json() : null)
    .then(meta => {
      if (meta && meta.width && meta.height) {
        // Insert resolution before clipboard icon
        filenameTextEl.textContent += ` [${meta.width}x${meta.height}]`;
      }
      setupPngInfo(meta, v.name);
    }).catch(()=>{ setupPngInfo(null, v.name); });

  updateDownloadButton(v.name);
  renderScoreBar(v.score || 0);
  updateMediaDownloadButton(v.name);
  renderSidebar();
}
// Function to estimate text width
function estimateTextWidth(text, element) {
  const canvas = document.createElement('canvas');
  const context = canvas.getContext('2d');
  const computedStyle = window.getComputedStyle(element);
  context.font = `${computedStyle.fontSize} ${computedStyle.fontFamily}`;
  return context.measureText(text).width;
}

// Function to resize directory input based on dir_display width
function resizeDirectoryInput() {
  const dirDisplay = document.getElementById('dir_display');
  const dirInput = document.getElementById('dir');
  const refreshBtn = document.getElementById('load');
  
  if (dirDisplay && dirInput && refreshBtn && dirDisplay.textContent) {
    const row = dirDisplay.closest('.row');
    if (!row) return;
    
    const rowWidth = row.offsetWidth;
    const displayWidth = dirDisplay.offsetWidth;
    
    // Calculate widths of other elements in the row
    const otherElements = row.querySelectorAll('button, input, select, .toggle-container');
    let otherElementsWidth = 0;
    
    otherElements.forEach(el => {
      if (el !== dirInput && el !== dirDisplay) {
        otherElementsWidth += el.offsetWidth;
      }
    });
    
    // Account for gaps (12px each) - count the number of direct children in the row
    const childCount = row.children.length;
    const gapWidth = (childCount - 1) * 12; // 12px gap between elements
    
    // Calculate available width for directory input
    // Row width - other elements - gaps - dir_display width - some padding
    const availableWidth = rowWidth - otherElementsWidth - gapWidth - displayWidth - 40; // 40px extra padding
    
    // Set reasonable bounds
    const minWidth = 200;
    const maxWidth = 600;
    const finalWidth = Math.max(minWidth, Math.min(availableWidth, maxWidth));
    
    dirInput.style.width = `${finalWidth}px`;
    dirInput.style.maxWidth = `${finalWidth}px`;
    
    console.log('Resize calculation:', {
      rowWidth,
      displayWidth,
      otherElementsWidth,
      gapWidth,
      availableWidth,
      finalWidth
    });
  }
}

async function loadVideos(){
  const res = await fetch("/api/videos");
  const data = await res.json();
  videos = data.videos || [];
  currentDir = data.dir || "";
  currentPattern = data.pattern || currentPattern;
  thumbnailsEnabled = data.thumbnails_enabled || false;
  thumbnailHeight = data.thumbnail_height || 64;
  toggleExtensions = data.toggle_extensions || ["jpg", "png", "mp4"];
  userPathPrefix = data.user_path_prefix || null;
  
  // Store database flag globally for search toolbar to use
  window.databaseEnabled = data.database_enabled || false;
  
  document.getElementById('dir_display').textContent = currentDir + '  •  ' + currentPattern;
  const dirInput = document.getElementById('dir');
  if (dirInput && !dirInput.value) dirInput.value = currentDir;
  const patInput = document.getElementById('pattern');
  if (patInput && !patInput.value) patInput.value = currentPattern;
  
  // Resize directory input after updating dir_display
  resizeDirectoryInput();
  
  // Initialize toggle buttons
  initializeToggleButtons();
  
  // Show/hide thumbnail controls
  const sidebarControls = document.getElementById('sidebar_controls');
  if (sidebarControls) {
    sidebarControls.style.display = thumbnailsEnabled ? 'block' : 'none';
  }
  
  // Initialize thumbnail toggle button icon
  updateThumbnailToggleButton();
  
  // Start monitoring thumbnail progress if thumbnails are enabled
  if (thumbnailsEnabled) {
    updateThumbnailStatus();
  }
  
  applyFilter();
  renderSidebar();
  show(0);
}
async function postScore(score){
  const v = filtered[idx];
  if (!v) return;
  
  try {
    const response = await fetch('/api/score', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({ name: v.name, score: score })
    });
    
    if (!response.ok) {
      console.error('Failed to update score:', response.status, response.statusText);
      return; // Don't update local state if API call failed
    }
    
    const result = await response.json();
    if (!result.ok) {
      console.error('Score update failed:', result);
      return; // Don't update local state if API returned error
    }
    
    // Only update local state if API call succeeded
    const source = videos.find(x => x.name === v.name);
    if (source) source.score = score;
    v.score = score;
    const curName = v.name;
    applyFilter();
    const newIndex = filtered.findIndex(x => x.name === curName);
    if (newIndex >= 0) {
      show(newIndex);
    } else {
      show(idx);
    }
    renderSidebar();
  } catch (error) {
    console.error('Network error updating score:', error);
  }
}

async function updateNsfwStatus(filename, nsfw) {
  try {
    const response = await fetch('/api/nsfw', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ name: filename, nsfw: nsfw })
    });
    
    if (!response.ok) {
      console.error('Failed to update NSFW status:', response.status, response.statusText);
      // Revert toggle on failure
      const toggle = document.getElementById('mobile-nsfw-toggle');
      if (toggle) toggle.checked = !nsfw;
      return;
    }
    
    const result = await response.json();
    if (!result.ok) {
      console.error('NSFW update failed:', result);
      // Revert toggle on failure
      const toggle = document.getElementById('mobile-nsfw-toggle');
      if (toggle) toggle.checked = !nsfw;
      return;
    }
    
    // Update local state if API call succeeded
    const source = videos.find(x => x.name === filename);
    if (source) source.nsfw = nsfw;
    const v = filtered[idx];
    if (v && v.name === filename) {
      v.nsfw = nsfw;
    }
    
    console.log('NSFW status updated:', filename, nsfw);
  } catch (error) {
    console.error('Network error updating NSFW status:', error);
    // Revert toggle on failure
    const toggle = document.getElementById('mobile-nsfw-toggle');
    if (toggle) toggle.checked = !nsfw;
  }
}

async function postKey(key){
  const v = filtered[idx];
  await fetch("/api/key", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ key: key, name: v ? v.name : "" })
  });
}
async function scanDir(path){
  const pattern = (document.getElementById('pattern')?.value || '').trim();
  const res = await fetch("/api/scan", {
    method: "POST",
    headers: {"Content-Type":"application/json"},
    body: JSON.stringify({ dir: path, pattern: pattern })
  });
  if (!res.ok){
    const t = await res.text();
    alert("Scan failed: " + t);
    return;
  }
  await loadVideos();
}
document.getElementById("pat_help").addEventListener("click", () => {
  alert("Glob syntax:\\n- Use * and ? wildcards (e.g., *.mp4, image??.png)\\n- Union with | (e.g., *.mp4|*.png|*.jpg)\\n- Examples:\\n  *.mp4\\n  image*.png\\n  *.mp4|*.png|*.jpg");
});
document.getElementById("load").addEventListener("click", () => {
  const path = (document.getElementById("dir").value || "").trim();
  if (path) {
    // Start monitoring thumbnail progress immediately if thumbnails are enabled
    if (thumbnailsEnabled) {
      updateThumbnailStatus();
    }
    scanDir(path);
  }
  // Resize directory input after refresh
  setTimeout(resizeDirectoryInput, 100); // Small delay to ensure DOM updates
});

// Refresh content button - reloads all data then applies current filters  
document.getElementById("refresh-content").addEventListener("click", async () => {
  // First, reload all videos from the server (like initial page load)
  await loadVideos();
  
  // Then apply current filters if available
  if (typeof applyCurrentFilters === 'function') {
    applyCurrentFilters();
  } else {
    // Fallback to basic filtering if search toolbar not available
    applyFilter();
    renderSidebar();
    show(0);
  }
});

document.getElementById('min_filter').addEventListener('change', () => {
  const val = document.getElementById('min_filter').value;
  if (val === 'none') {
    minFilter = null;
  } else if (val === 'rejected') {
    minFilter = 'rejected';
  } else if (val === 'unrated') {
    minFilter = 'unrated';
  } else if (val === 'unrated_and_above') {
    minFilter = 'unrated_and_above';
  } else {
    minFilter = parseInt(val);
  }
  
  // Save the filter state to cookies
  const filterValue = minFilter === null ? 'none' : (typeof minFilter === 'string' ? minFilter : String(minFilter));
  saveState('minFilter', filterValue);
  
  fetch('/api/key', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ key: 'Filter=' + (minFilter===null?'none':(typeof minFilter === 'string'?minFilter:('>='+minFilter))), name: '' })});
  applyFilter(); renderSidebar(); show(0);
});
document.getElementById('dir').addEventListener('keydown', (e) => {
  if (e.key === "Enter"){
    const path = (document.getElementById("dir").value || "").trim();
    if (path) scanDir(path);
  }
});
document.getElementById('pattern').addEventListener('keydown', (e) => {
  if (e.key === "Enter"){
    const path = (document.getElementById("dir").value || "").trim();
    if (path) scanDir(path);
  }
});

// Directory navigation functions
async function goUpDirectory() {
  const dirInput = document.getElementById('dir');
  const currentPath = dirInput.value.trim();
  if (!currentPath) return;
  
  const path = new Path(currentPath);
  const parentPath = path.parent;
  if (parentPath && parentPath !== currentPath) {
    dirInput.value = parentPath;
    // Optionally trigger scan immediately
    // scanDir(parentPath);
  }
}

async function loadDirectories(basePath) {
  try {
    const response = await fetch(`/api/directories?path=${encodeURIComponent(basePath)}`);
    if (!response.ok) {
      throw new Error(`Failed to load directories: ${response.statusText}`);
    }
    const data = await response.json();
    return data.directories;
  } catch (error) {
    console.error('Error loading directories:', error);
    return [];
  }
}

function showDirectoryDropdown() {
  const dirInput = document.getElementById('dir');
  const dropdown = document.getElementById('dir_dropdown');
  const currentPath = dirInput.value.trim() || './';
  
  // Clear existing dropdown content
  dropdown.innerHTML = '<div class="dropdown-item" style="opacity: 0.6;">Loading...</div>';
  dropdown.style.display = 'block';
  
  loadDirectories(currentPath).then(directories => {
    dropdown.innerHTML = '';
    
    if (directories.length === 0) {
      dropdown.innerHTML = '<div class="dropdown-empty">No directories found</div>';
    } else {
      directories.forEach(dir => {
        const item = document.createElement('div');
        item.className = 'dropdown-item';
        item.textContent = dir.name;
        item.title = dir.path;
        item.addEventListener('click', () => {
          const currentValue = dirInput.value.trim();
          let newPath;
          if (currentValue.endsWith('/')) {
            newPath = currentValue + dir.name;
          } else {
            newPath = currentValue + '/' + dir.name;
          }
          dirInput.value = newPath;
          hideDirectoryDropdown();
        });
        dropdown.appendChild(item);
      });
    }
  }).catch(error => {
    dropdown.innerHTML = '<div class="dropdown-empty">Error loading directories</div>';
  });
}

function hideDirectoryDropdown() {
  const dropdown = document.getElementById('dir_dropdown');
  dropdown.style.display = 'none';
}

// Sibling directory functions
async function loadSiblingDirectories(currentPath) {
  try {
    const response = await fetch(`/api/sibling-directories?path=${encodeURIComponent(currentPath)}`);
    if (!response.ok) {
      throw new Error(`Failed to load sibling directories: ${response.statusText}`);
    }
    const data = await response.json();
    return data.directories;
  } catch (error) {
    console.error('Error loading sibling directories:', error);
    return [];
  }
}

function showSiblingDirectoryDropdown() {
  const dirInput = document.getElementById('dir');
  const dropdown = document.getElementById('dir_siblings_dropdown');
  const currentPath = dirInput.value.trim() || './';
  
  // Clear existing dropdown content
  dropdown.innerHTML = '<div class="dropdown-item" style="opacity: 0.6;">Loading...</div>';
  dropdown.style.display = 'block';
  
  loadSiblingDirectories(currentPath).then(directories => {
    dropdown.innerHTML = '';
    
    if (directories.length === 0) {
      dropdown.innerHTML = '<div class="dropdown-empty">No sibling directories found</div>';
    } else {
      directories.forEach(dir => {
        const item = document.createElement('div');
        item.className = 'dropdown-item';
        item.textContent = dir.name;
        item.title = dir.path;
        item.addEventListener('click', () => {
          dirInput.value = dir.path;
          hideSiblingDirectoryDropdown();
        });
        dropdown.appendChild(item);
      });
    }
  }).catch(error => {
    dropdown.innerHTML = '<div class="dropdown-empty">Error loading sibling directories</div>';
  });
}

function hideSiblingDirectoryDropdown() {
  const dropdown = document.getElementById('dir_siblings_dropdown');
  dropdown.style.display = 'none';
}

// Simple Path utility for JavaScript (since we don't have Node.js path module)
class Path {
  constructor(pathStr) {
    this.path = pathStr.replace(/\\/g, '/'); // Normalize to forward slashes
  }
  
  get parent() {
    const normalizedPath = this.path.replace(/\/+$/, ''); // Remove trailing slashes
    const lastSlash = normalizedPath.lastIndexOf('/');
    if (lastSlash <= 0) return '/';
    return normalizedPath.substring(0, lastSlash);
  }
}

// Add event listeners for directory navigation
document.getElementById('dir_up').addEventListener('click', goUpDirectory);
document.getElementById('dir_browse').addEventListener('click', showDirectoryDropdown);
document.getElementById('dir_siblings').addEventListener('click', showSiblingDirectoryDropdown);

// Hide dropdown when clicking outside
document.addEventListener('click', (e) => {
  const dropdownContainer = document.querySelector('.dir-dropdown-container');
  const dropdown = document.getElementById('dir_dropdown');
  const siblingContainer = document.querySelector('.dir-input-container');
  const siblingDropdown = document.getElementById('dir_siblings_dropdown');
  
  if (dropdownContainer && !dropdownContainer.contains(e.target)) {
    hideDirectoryDropdown();
  }
  
  if (siblingContainer && !siblingContainer.contains(e.target)) {
    hideSiblingDirectoryDropdown();
  }
});

// Add event listeners to removed control buttons only if they exist
const prevBtn = document.getElementById('prev');
if (prevBtn) prevBtn.addEventListener('click', () => { show(idx-1); });

const nextBtn = document.getElementById('next');
if (nextBtn) nextBtn.addEventListener('click', () => { show(idx+1); });

const rejectBtn = document.getElementById("reject");
if (rejectBtn) rejectBtn.addEventListener("click", () => { postScore(-1); });

const clearBtn = document.getElementById("clear");
if (clearBtn) clearBtn.addEventListener("click", () => { postScore(0); });
document.querySelectorAll("[data-star]").forEach(btn => {
  btn.addEventListener("click", () => {
    const n = parseInt(btn.getAttribute("data-star"));
    postScore(n);
  });
});
document.addEventListener("keydown", (e) => {
  if (["INPUT","TEXTAREA"].includes((e.target.tagName||"").toUpperCase())) return;
  const player = document.getElementById("player");
  function togglePlay(){ if (!player || player.style.display==='none') return; if (player.paused) { player.play(); } else { player.pause(); } }
  if (e.key === "Escape" && isMaximized){ e.preventDefault(); postKey("Escape"); toggleMaximize(); return; }
  if (e.key === "ArrowLeft"){ e.preventDefault(); postKey("ArrowLeft"); show(idx-1); return; }
  if (e.key === "ArrowRight"){ e.preventDefault(); postKey("ArrowRight"); show(idx+1); return; }
  if (e.key === " "){ e.preventDefault(); postKey("Space"); togglePlay(); return; }
  if (e.key === "1"){ e.preventDefault(); postKey("1"); postScore(1); return; }
  if (e.key === "2"){ e.preventDefault(); postKey("2"); postScore(2); return; }
  if (e.key === "3"){ e.preventDefault(); postKey("3"); postScore(3); return; }
  if (e.key === "4"){ e.preventDefault(); postKey("4"); postScore(4); return; }
  if (e.key === "5"){ e.preventDefault(); postKey("5"); postScore(5); return; }
  if (e.key === "r" || e.key === "R"){ e.preventDefault(); postKey("R"); postScore(-1); return; }
  if (e.key === "c" || e.key === "C"){ e.preventDefault(); postKey("C"); postScore(0); return; }
});
async function extractCurrent(){
  if (!filtered.length) { alert("No item selected."); return; }
  const v = filtered[idx];
  if (!v.name.toLowerCase().endsWith('.mp4')){ alert('Extractor only works for .mp4'); return; }
  try{
    const res = await fetch("/api/extract", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ names: [v.name] })
    });
    const data = await res.json();
    const ok = (data.results||[]).filter(r=>r.status==="ok").length;
    const err = (data.results||[]).length - ok;
    postKey("ExtractOne");
    alert(`Extracted: ${ok} OK, ${err} errors`);
  }catch(e){
    alert("Extraction failed: " + e);
  }
}
async function extractFiltered(){
  if (!filtered.length) { alert("No items in current filter scope."); return; }
  const names = filtered.map(v => v.name).filter(n => n.toLowerCase().endsWith('.mp4'));
  if (!names.length){ alert('No .mp4 files in the current filtered view.'); return; }
  try{
    const res = await fetch("/api/extract", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ names })
    });
    const data = await res.json();
    const ok = (data.results||[]).filter(r=>r.status==="ok").length;
    const err = (data.results||[]).length - ok;
    postKey("ExtractFiltered");
    alert(`Extracted: ${ok} OK, ${err} errors`);
  }catch(e){
    alert("Bulk extraction failed: " + e);
  }
}
async function exportFiltered(){
  if (!filtered.length) { alert("No items in current filter scope."); return; }
  const names = filtered.map(v => v.name);
  if (!names.length){ alert('No files in the current filtered view.'); return; }
  
  // Show progress
  showProgress('Exporting...');
  
  try{
    const res = await fetch("/api/export-filtered", {
      method: "POST",
      headers: {"Content-Type":"application/json"},
      body: JSON.stringify({ names })
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    }
    // Create a blob from the response and trigger download
    const blob = await res.blob();
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.style.display = 'none';
    a.href = url;
    a.download = 'media.zip';
    document.body.appendChild(a);
    a.click();
    window.URL.revokeObjectURL(url);
    document.body.removeChild(a);
    postKey("ExportFiltered");
  }catch(e){
    alert("Export failed: " + e);
  } finally {
    // Hide progress
    hideProgress();
  }
}
// Add event listeners to extraction buttons only if they exist
const extractOneBtn = document.getElementById("extract_one");
if (extractOneBtn) extractOneBtn.addEventListener("click", extractCurrent);

const extractFilteredBtn = document.getElementById("extract_filtered");
if (extractFilteredBtn) extractFilteredBtn.addEventListener("click", extractFiltered);
document.getElementById("export_filtered_btn").addEventListener("click", exportFiltered);
window.addEventListener("load", loadVideos);

/* =========================================================
   INFO PANE FUNCTIONALITY
   --------------------------------------------------------- */

// Current media info cache
let currentMediaInfo = null;

// Fetch media information from backend
async function fetchMediaInfo(filename) {
  try {
    const response = await fetch(`/api/media/${encodeURIComponent(filename)}/info`);
    if (!response.ok) {
      throw new Error(`Failed to fetch media info: ${response.status}`);
    }
    return await response.json();
  } catch (error) {
    console.error('Error fetching media info:', error);
    return null;
  }
}

// Format file size
function formatFileSize(bytes) {
  if (!bytes || bytes === 0) return 'N/A';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = bytes;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex++;
  }
  return `${size.toFixed(2)} ${units[unitIndex]}`;
}

// Format duration (seconds to HH:MM:SS)
function formatDuration(seconds) {
  if (!seconds || seconds === 0) return 'N/A';
  const hours = Math.floor(seconds / 3600);
  const minutes = Math.floor((seconds % 3600) / 60);
  const secs = Math.floor(seconds % 60);
  
  if (hours > 0) {
    return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  }
  return `${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

// Format date
function formatDate(dateString) {
  if (!dateString) return 'N/A';
  try {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
      year: 'numeric',
      month: 'long',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit'
    });
  } catch (error) {
    return dateString;
  }
}

// Format resolution (pixels to megapixels)
function formatResolution(pixels) {
  if (!pixels || pixels === 0) return 'N/A';
  const mp = (pixels / 1000000).toFixed(2);
  return `${mp} MP`;
}

// Format bitrate
function formatBitrate(bitrate) {
  if (!bitrate || bitrate === 0) return 'N/A';
  const mbps = (bitrate / 1000000).toFixed(2);
  return `${mbps} Mbps`;
}

// Format frame rate
function formatFrameRate(fps) {
  if (!fps || fps === 0) return 'N/A';
  return `${fps.toFixed(2)} fps`;
}

// Generate star rating display
function formatStarRating(score) {
  if (!score || score === 0) return '<span style="color: #888;">Not rated</span>';
  const stars = '★'.repeat(score) + '☆'.repeat(5 - score);
  return `<span class="info-score-stars">${stars}</span> <span style="color: #888;">(${score}/5)</span>`;
}

// Populate info pane with media data
function populateInfoPane(mediaData) {
  const contentDiv = document.getElementById('info-pane-content');
  if (!contentDiv) return;
  
  // Clear loading state
  contentDiv.innerHTML = '';
  
  // Get default categories (for now, using hardcoded defaults - could be fetched from config)
  const defaultCategories = [
    'filename', 'file_size', 'dimensions', 'creation_date', 'score'
  ];
  
  // Build HTML for each category
  defaultCategories.forEach(category => {
    let itemHtml = '';
    
    switch (category) {
      case 'filename':
        itemHtml = `
          <div class="info-item">
            <span class="info-label">Filename</span>
            <span class="info-value info-value-code">${escapeHtml(mediaData.filename || 'N/A')}</span>
          </div>
        `;
        break;
        
      case 'file_size':
        itemHtml = `
          <div class="info-item">
            <span class="info-label">File Size</span>
            <span class="info-value">${formatFileSize(mediaData.file_size)}</span>
          </div>
        `;
        break;
        
      case 'dimensions':
        if (mediaData.dimensions) {
          itemHtml = `
            <div class="info-item">
              <span class="info-label">Dimensions</span>
              <span class="info-value">${mediaData.dimensions.width} × ${mediaData.dimensions.height}</span>
            </div>
          `;
        }
        break;
        
      case 'duration':
        if (mediaData.duration) {
          itemHtml = `
            <div class="info-item">
              <span class="info-label">Duration</span>
              <span class="info-value">${formatDuration(mediaData.duration)}</span>
            </div>
          `;
        }
        break;
        
      case 'creation_date':
        itemHtml = `
          <div class="info-item">
            <span class="info-label">Creation Date</span>
            <span class="info-value">${formatDate(mediaData.creation_date)}</span>
          </div>
        `;
        break;
        
      case 'modified_date':
        itemHtml = `
          <div class="info-item">
            <span class="info-label">Modified Date</span>
            <span class="info-value">${formatDate(mediaData.modified_date)}</span>
          </div>
        `;
        break;
        
      case 'file_path':
        itemHtml = `
          <div class="info-item">
            <span class="info-label">File Path</span>
            <span class="info-value info-value-code" style="word-break: break-all;">${escapeHtml(mediaData.file_path || 'N/A')}</span>
          </div>
        `;
        break;
        
      case 'file_type':
        itemHtml = `
          <div class="info-item">
            <span class="info-label">File Type</span>
            <span class="info-value">${mediaData.file_type || 'N/A'}</span>
          </div>
        `;
        break;
        
      case 'resolution':
        if (mediaData.resolution) {
          itemHtml = `
            <div class="info-item">
              <span class="info-label">Resolution</span>
              <span class="info-value">${formatResolution(mediaData.resolution)}</span>
            </div>
          `;
        }
        break;
        
      case 'aspect_ratio':
        if (mediaData.aspect_ratio) {
          itemHtml = `
            <div class="info-item">
              <span class="info-label">Aspect Ratio</span>
              <span class="info-value">${mediaData.aspect_ratio}</span>
            </div>
          `;
        }
        break;
        
      case 'frame_rate':
        if (mediaData.frame_rate) {
          itemHtml = `
            <div class="info-item">
              <span class="info-label">Frame Rate</span>
              <span class="info-value">${formatFrameRate(mediaData.frame_rate)}</span>
            </div>
          `;
        }
        break;
        
      case 'bitrate':
        if (mediaData.bitrate) {
          itemHtml = `
            <div class="info-item">
              <span class="info-label">Bitrate</span>
              <span class="info-value">${formatBitrate(mediaData.bitrate)}</span>
            </div>
          `;
        }
        break;
        
      case 'codec':
        if (mediaData.codec) {
          itemHtml = `
            <div class="info-item">
              <span class="info-label">Codec</span>
              <span class="info-value">${mediaData.codec}</span>
            </div>
          `;
        }
        break;
        
      case 'score':
        itemHtml = `
          <div class="info-item">
            <span class="info-label">Score</span>
            <span class="info-value">${formatStarRating(mediaData.score)}</span>
          </div>
        `;
        break;
        
      case 'metadata':
        if (mediaData.metadata && Object.keys(mediaData.metadata).length > 0) {
          let metadataHtml = '<div class="info-metadata">';
          
          // PNG text / generation parameters
          if (mediaData.metadata.generation_params) {
            const params = mediaData.metadata.generation_params;
            metadataHtml += `
              <div class="info-metadata-section">
                <div class="info-metadata-title">Generation Parameters</div>
                <div class="info-metadata-content">
                  ${params.prompt ? `<div><strong>Prompt:</strong> ${escapeHtml(params.prompt)}</div>` : ''}
                  ${params.negative_prompt ? `<div><strong>Negative:</strong> ${escapeHtml(params.negative_prompt)}</div>` : ''}
                  ${params.model_name ? `<div><strong>Model:</strong> ${params.model_name}</div>` : ''}
                  ${params.sampler ? `<div><strong>Sampler:</strong> ${params.sampler}</div>` : ''}
                  ${params.steps ? `<div><strong>Steps:</strong> ${params.steps}</div>` : ''}
                  ${params.cfg_scale ? `<div><strong>CFG Scale:</strong> ${params.cfg_scale}</div>` : ''}
                  ${params.seed ? `<div><strong>Seed:</strong> ${params.seed}</div>` : ''}
                </div>
              </div>
            `;
          }
          
          // EXIF data
          if (mediaData.metadata.exif) {
            metadataHtml += `
              <div class="info-metadata-section">
                <div class="info-metadata-title">EXIF Data</div>
                <div class="info-metadata-content">
                  ${Object.entries(mediaData.metadata.exif).map(([key, value]) => 
                    `<div><strong>${key}:</strong> ${escapeHtml(String(value))}</div>`
                  ).join('')}
                </div>
              </div>
            `;
          }
          
          // PNG text
          if (mediaData.metadata.png_text && typeof mediaData.metadata.png_text === 'string') {
            metadataHtml += `
              <div class="info-metadata-section">
                <div class="info-metadata-title">PNG Metadata</div>
                <div class="info-metadata-content" style="white-space: pre-wrap; font-family: monospace; font-size: 11px; max-height: 200px; overflow-y: auto;">
                  ${escapeHtml(mediaData.metadata.png_text)}
                </div>
              </div>
            `;
          }
          
          metadataHtml += '</div>';
          itemHtml = `
            <div class="info-item">
              <span class="info-label">Metadata</span>
              ${metadataHtml}
            </div>
          `;
        }
        break;
    }
    
    if (itemHtml) {
      contentDiv.innerHTML += itemHtml;
    }
  });
  
  // If no content was added, show a message
  if (contentDiv.innerHTML === '') {
    contentDiv.innerHTML = '<div class="info-loading">No information available</div>';
  }
}

// Helper function to escape HTML
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Toggle info pane
async function toggleInfoPane() {
  const infoPane = document.getElementById('info-pane');
  if (!infoPane) return;
  
  if (infoPane.classList.contains('visible')) {
    closeInfoPane();
  } else {
    await openInfoPane();
  }
}

// Open info pane
async function openInfoPane() {
  const infoPane = document.getElementById('info-pane');
  if (!infoPane) return;
  
  // Get current media filename
  if (filtered.length === 0 || idx < 0 || idx >= filtered.length) {
    console.warn('No media selected');
    return;
  }
  
  const currentMedia = filtered[idx];
  const filename = currentMedia.name;
  
  // Show loading state
  infoPane.classList.add('visible');
  const contentDiv = document.getElementById('info-pane-content');
  if (contentDiv) {
    contentDiv.innerHTML = '<div class="info-loading">Loading...</div>';
  }
  
  // Fetch and populate data
  const mediaInfo = await fetchMediaInfo(filename);
  if (mediaInfo) {
    currentMediaInfo = mediaInfo;
    populateInfoPane(mediaInfo);
  } else {
    if (contentDiv) {
      contentDiv.innerHTML = '<div class="info-loading">Failed to load media information</div>';
    }
  }
}

// Close info pane
function closeInfoPane() {
  const infoPane = document.getElementById('info-pane');
  if (!infoPane) return;
  infoPane.classList.remove('visible');
  currentMediaInfo = null;
}

// Event listeners for info pane
document.addEventListener('DOMContentLoaded', function() {
  // Desktop: close button
  const closeBtn = document.getElementById('info-pane-close');
  if (closeBtn) {
    closeBtn.addEventListener('click', closeInfoPane);
  }
  
  // Desktop: menu item
  const desktopViewInfo = document.getElementById('desktop-view-info');
  if (desktopViewInfo) {
    desktopViewInfo.addEventListener('click', async function() {
      // Close desktop menu
      const menuOverlay = document.getElementById('menu-overlay');
      if (menuOverlay) {
        menuOverlay.classList.remove('active');
      }
      // Open info pane
      await openInfoPane();
    });
  }
  
  // Mobile: menu item
  const mobileViewInfo = document.getElementById('mobile-view-info');
  if (mobileViewInfo) {
    mobileViewInfo.addEventListener('click', async function() {
      // Close mobile menu
      const mobileMenuPopover = document.getElementById('mobile-menu-popover');
      if (mobileMenuPopover) {
        mobileMenuPopover.classList.remove('visible');
      }
      // Open info pane
      await openInfoPane();
    });
  }
  
  // ESC key to close
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      const infoPane = document.getElementById('info-pane');
      if (infoPane && infoPane.classList.contains('visible')) {
        closeInfoPane();
      }
    }
  });
});

/* =========================================================
   TILE VIEW FUNCTIONALITY
   --------------------------------------------------------- */

// Constants for tile view
const TILE_VIEW_LANDSCAPE_THRESHOLD = 1.3; // Width/height ratio to determine landscape orientation
const TILE_VIEW_VIDEO_PLACEHOLDER_COLOR = '#333'; // Background color for video placeholders

// Open tile view
function openTileView() {
  const tileViewOverlay = document.getElementById('tile-view-overlay');
  if (!tileViewOverlay) return;
  
  // Show overlay
  tileViewOverlay.classList.add('visible');
  
  // Populate with media items
  populateTileView();
  
  // Disable body scroll
  document.body.style.overflow = 'hidden';
}

// Close tile view
function closeTileView() {
  const tileViewOverlay = document.getElementById('tile-view-overlay');
  if (!tileViewOverlay) return;
  
  tileViewOverlay.classList.remove('visible');
  
  // Re-enable body scroll
  document.body.style.overflow = '';
}

// Populate tile view with current filtered media
function populateTileView() {
  const gridContainer = document.getElementById('tile-view-grid');
  if (!gridContainer) return;
  
  // Clear existing content
  gridContainer.innerHTML = '';
  
  // Check if we have any filtered items
  if (!filtered || filtered.length === 0) {
    gridContainer.innerHTML = '<div class="tile-view-loading">No media items to display</div>';
    return;
  }
  
  // Create tile for each filtered item
  filtered.forEach((item, index) => {
    const tile = createTileViewItem(item, index);
    gridContainer.appendChild(tile);
  });
}

// Create a single tile view item
function createTileViewItem(item, index) {
  const tile = document.createElement('div');
  tile.className = 'tile-view-item';
  
  // Check if current item
  if (filtered[idx] && filtered[idx].name === item.name) {
    tile.classList.add('current');
  }
  
  // Create image element
  const img = document.createElement('img');
  img.className = 'tile-view-item-image';
  
  // Use thumbnail if available, otherwise use the full media
  if (thumbnailsEnabled) {
    img.src = `/thumbnail/${encodeURIComponent(item.name)}`;
    // Fallback to full media if thumbnail fails
    img.onerror = function() {
      if (isImageName(item.name)) {
        img.src = `/media/${encodeURIComponent(item.name)}`;
      } else {
        // For videos, show a placeholder
        img.style.backgroundColor = TILE_VIEW_VIDEO_PLACEHOLDER_COLOR;
        img.alt = 'Video: ' + item.name;
      }
    };
  } else {
    if (isImageName(item.name)) {
      img.src = `/media/${encodeURIComponent(item.name)}`;
    } else {
      // For videos without thumbnails, show placeholder
      img.style.backgroundColor = TILE_VIEW_VIDEO_PLACEHOLDER_COLOR;
      img.alt = 'Video: ' + item.name;
    }
  }
  
  // When image loads, check its dimensions to determine if landscape
  img.onload = function() {
    if (img.naturalWidth > img.naturalHeight * TILE_VIEW_LANDSCAPE_THRESHOLD) {
      tile.classList.add('landscape');
    }
  };
  
  tile.appendChild(img);
  
  // Create info section
  const info = document.createElement('div');
  info.className = 'tile-view-item-info';
  
  // Filename
  const name = document.createElement('div');
  name.className = 'tile-view-item-name';
  name.textContent = item.name;
  name.title = item.name;
  info.appendChild(name);
  
  // Meta info (score, date)
  const meta = document.createElement('div');
  meta.className = 'tile-view-item-meta';
  
  // Score badge
  const score = document.createElement('span');
  score.className = 'tile-view-item-score';
  if (item.score === -1) {
    score.textContent = 'R';
    score.classList.add('rejected');
  } else if (item.score && item.score > 0) {
    score.textContent = item.score + '★';
    score.classList.add('rated');
  } else {
    score.textContent = '—';
  }
  meta.appendChild(score);
  
  // Date if available
  if (item.original_created_at) {
    const date = document.createElement('span');
    date.className = 'tile-view-item-date';
    date.textContent = formatDatePill(item.original_created_at);
    meta.appendChild(date);
  }
  
  info.appendChild(meta);
  tile.appendChild(info);
  
  // Click handler
  tile.addEventListener('click', () => {
    // Close tile view
    closeTileView();
    
    // Navigate to this item
    show(index);
    
    // Scroll sidebar to show this item
    const sidebarItem = document.querySelector(`.item[data-name="${item.name}"]`);
    if (sidebarItem) {
      sidebarItem.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  });
  
  return tile;
}

// Event listeners for tile view
document.addEventListener('DOMContentLoaded', function() {
  // Tile view button
  const tileViewBtn = document.getElementById('tile_view_btn');
  if (tileViewBtn) {
    tileViewBtn.addEventListener('click', openTileView);
  }
  
  // Close button
  const tileViewClose = document.getElementById('tile-view-close');
  if (tileViewClose) {
    tileViewClose.addEventListener('click', closeTileView);
  }
  
  // ESC key to close tile view
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
      const tileViewOverlay = document.getElementById('tile-view-overlay');
      if (tileViewOverlay && tileViewOverlay.classList.contains('visible')) {
        closeTileView();
      }
    }
  });
  
  // Click overlay background to close
  const tileViewOverlay = document.getElementById('tile-view-overlay');
  if (tileViewOverlay) {
    tileViewOverlay.addEventListener('click', function(e) {
      if (e.target === tileViewOverlay) {
        closeTileView();
      }
    });
  }
});
