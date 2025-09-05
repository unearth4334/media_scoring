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
}

// Add toolbar toggle event listener
document.addEventListener('DOMContentLoaded', function() {
  const toggleBtn = document.getElementById('toolbar-toggle');
  if (toggleBtn) {
    toggleBtn.addEventListener('click', toggleToolbar);
  }
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

// Thumbnail progress tracking
let thumbnailProgressInterval = null;

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

function toggleMaximize(){
  const videoWrap = document.querySelector('.video-wrap');
  const player = document.getElementById('player');
  const imgview = document.getElementById('imgview');
  const maximizeBtn = document.getElementById('maximize-btn');
  
  if (!videoWrap || !maximizeBtn) return;
  
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
  html += svgReject(score === -1);
  const stars = (score === -1) ? 0 : Math.max(0, score||0);
  for (let i=0;i<5;i++) html += svgStar(i<stars);
  html += `</div>`;
  html += `<button id="maximize-btn" class="maximize-btn" title="${isMaximized ? 'Return to actual size' : 'Maximize media'}">`;
  html += isMaximized ? svgMinimize() : svgMaximize();
  html += `</button>`;
  html += `</div>`;
  bar.innerHTML = html;
  
  // Attach event listener to the new button
  const maximizeBtn = document.getElementById('maximize-btn');
  if (maximizeBtn) {
    maximizeBtn.addEventListener('click', toggleMaximize);
  }
}
function scoreBadge(s){
  if (s === -1) return 'R';
  if (!s || s < 1) return '—';
  return s + '★';
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
      thumbHtml = `<div class="thumbnail"><img src="/thumbnail/${encodeURIComponent(v.name)}" alt="" style="height:${thumbnailHeight}px" onerror="this.style.display='none'"></div>`;
      classes.push('with-thumbnails');
    }
    
    html += `<div class="${classes.join(' ')}" data-name="${v.name}" ${inFiltered ? '' : 'data-disabled="1"'}>` +
            thumbHtml +
            `<div class="content">` +
            `<div class="name" title="${v.name}">${v.name}</div>` +
            `<div class="score">${s}</div>` +
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
}
function applyFilter(){
  if (minFilter === null) {
    filtered = videos.slice();
  } else if (minFilter === 'unrated') {
    filtered = videos.filter(v => !v.score || v.score === 0);
  } else {
    filtered = videos.filter(v => (v.score||0) >= minFilter);
  }
  const info = document.getElementById('filter_info');
  let label;
  if (minFilter === null) {
    label = 'No filter';
  } else if (minFilter === 'unrated') {
    label = 'Unrated only';
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
  if (isVideoName(name)){
    itag.style.display = 'none'; itag.removeAttribute('src');
    vtag.style.display = ''; vtag.src = url + '#t=0.001';
  } else if (isImageName(name)){
    vtag.pause && vtag.pause(); vtag.removeAttribute('src'); vtag.load && vtag.load(); vtag.style.display='none';
    itag.style.display = ''; itag.src = url;
  } else {
    vtag.style.display='none'; vtag.removeAttribute('src');
    itag.style.display=''; itag.src = url;
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
    const controls = document.getElementById('pnginfo_controls'); if (controls) controls.style.display='none';
    const panel = document.getElementById('pnginfo_panel'); if (panel) panel.style.display='none';
    renderSidebar();
    return;
  }
  idx = Math.max(0, Math.min(i, filtered.length-1));
  const v = filtered[idx];
  showMedia(v.url, v.name);
  
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
    const fullPath = currentDir + '/' + v.name;
    if (!navigator.clipboard) {
      const ta = document.createElement('textarea');
      ta.value = fullPath;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
    } else {
      navigator.clipboard.writeText(fullPath).catch(() => {});
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
  await fetch('/api/score', {
    method: 'POST',
    headers: {'Content-Type':'application/json'},
    body: JSON.stringify({ name: v.name, score: score })
  });
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
document.getElementById('min_filter').addEventListener('change', () => {
  const val = document.getElementById('min_filter').value;
  if (val === 'none') {
    minFilter = null;
  } else if (val === 'unrated') {
    minFilter = 'unrated';
  } else {
    minFilter = parseInt(val);
  }
  fetch('/api/key', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({ key: 'Filter=' + (minFilter===null?'none':(minFilter==='unrated'?'unrated':('>='+minFilter))), name: '' })});
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
  
  if (!dropdownContainer.contains(e.target)) {
    hideDirectoryDropdown();
  }
  
  if (!siblingContainer.contains(e.target)) {
    hideSiblingDirectoryDropdown();
  }
});

document.getElementById('prev').addEventListener('click', () => { show(idx-1); });
document.getElementById('next').addEventListener('click', () => { show(idx+1); });
document.getElementById("reject").addEventListener("click", () => { postScore(-1); });
document.getElementById("clear").addEventListener("click", () => { postScore(0); });
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
document.getElementById("extract_one").addEventListener("click", extractCurrent);
document.getElementById("extract_filtered").addEventListener("click", extractFiltered);
document.getElementById("export_filtered_btn").addEventListener("click", exportFiltered);
window.addEventListener("load", loadVideos);
