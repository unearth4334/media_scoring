/**
 * Search Toolbar Functionality
 * Handles the search toolbar filtering interface
 */

// Search toolbar state
let activePillEditor = null;
let searchToolbarFilters = {
  sort: 'name',
  directory: '',
  filetype: ['jpg', 'png', 'mp4'],
  rating: 'none',
  dateStart: null,
  dateEnd: null
};

// Default filter values for comparison (to detect modifications)
const defaultFilters = {
  sort: 'name',
  directory: '',
  filetype: ['jpg', 'png', 'mp4'],
  rating: 'none',
  dateStart: null,
  dateEnd: null
};

// Check if a filter value has been modified from its default
function isFilterModified(filterName) {
  const current = searchToolbarFilters[filterName];
  const defaultValue = defaultFilters[filterName];
  
  // Handle special cases for different data types
  if (filterName === 'filetype') {
    // Compare arrays - both must contain same elements in any order
    if (!Array.isArray(current) || !Array.isArray(defaultValue)) return false;
    if (current.length !== defaultValue.length) return true;
    return !current.every(item => defaultValue.includes(item)) || 
           !defaultValue.every(item => current.includes(item));
  }
  
  if (filterName === 'dateStart' || filterName === 'dateEnd') {
    // Null/empty comparison for dates
    return (current !== null && current !== '') || (defaultValue !== null && defaultValue !== '');
  }
  
  if (filterName === 'directory') {
    // Directory is only modified if it's explicitly set and different from both empty and current dir
    // We don't consider it modified if it just shows the current working directory
    return current !== '' && current !== defaultValue && current !== currentDir && current !== (currentDir || 'media');
  }
  
  // Standard comparison for other fields
  return current !== defaultValue;
}

// Initialize search toolbar functionality
function initializeSearchToolbar() {
  // Initialize pill values from current state
  updatePillValues();
  
  // Add click handlers to pills
  document.querySelectorAll('.pill').forEach(pill => {
    pill.addEventListener('click', handlePillClick);
  });
  
  // Add editor action handlers
  setupEditorActions();
  
  // Close editors when clicking outside
  document.addEventListener('click', handleOutsideClick);
  
  // Initialize backward compatibility
  syncBackwardCompatibility();
}

function handlePillClick(event) {
  event.stopPropagation();
  const pill = event.currentTarget;
  const pillType = pill.dataset.pill;
  
  if (activePillEditor === pillType) {
    closePillEditor();
    return;
  }
  
  closePillEditor();
  openPillEditor(pillType, pill);
}

function openPillEditor(pillType, pillElement) {
  activePillEditor = pillType;
  
  // Hide all editors
  document.querySelectorAll('.pill-editor').forEach(editor => {
    editor.classList.remove('active');
  });
  
  // Show the target editor
  const editor = document.getElementById(`editor-${pillType}`);
  if (editor) {
    editor.classList.add('active');
    
    // Position editor for desktop (popover style)
    if (window.innerWidth > 768) {
      positionEditorPopover(editor, pillElement);
    }
    
    // Populate editor with current values
    populateEditor(pillType);
    
    // Mark pill as active
    document.querySelectorAll('.pill').forEach(p => p.classList.remove('active'));
    pillElement.classList.add('active');
    
    // Focus first input in editor
    const firstInput = editor.querySelector('input, select');
    if (firstInput) {
      setTimeout(() => firstInput.focus(), 100);
    }
  }
}

function positionEditorPopover(editor, pillElement) {
  const pillRect = pillElement.getBoundingClientRect();
  const editorRect = editor.getBoundingClientRect();
  
  // Position below the pill
  let top = pillRect.bottom + 8;
  let left = pillRect.left;
  
  // Adjust if editor would go off-screen
  const viewportWidth = window.innerWidth;
  const viewportHeight = window.innerHeight;
  
  if (left + 280 > viewportWidth) {
    left = viewportWidth - 280 - 16;
  }
  
  if (top + 200 > viewportHeight) {
    top = pillRect.top - 200 - 8;
  }
  
  editor.style.top = `${top}px`;
  editor.style.left = `${left}px`;
}

function closePillEditor() {
  if (!activePillEditor) return;
  
  document.querySelectorAll('.pill-editor').forEach(editor => {
    editor.classList.remove('active');
  });
  
  document.querySelectorAll('.pill').forEach(pill => {
    pill.classList.remove('active');
  });
  
  activePillEditor = null;
}

function populateEditor(pillType) {
  const filter = searchToolbarFilters[pillType];
  
  switch (pillType) {
    case 'sort':
      document.getElementById('sort-select').value = filter;
      break;
      
    case 'directory':
      document.getElementById('directory-input').value = filter || currentDir;
      break;
      
    case 'filetype':
      document.querySelectorAll('.filetype-checkboxes input[type="checkbox"]').forEach(cb => {
        cb.checked = filter.includes(cb.value);
      });
      break;
      
    case 'rating':
      document.getElementById('rating-select').value = filter;
      break;
      
    case 'date':
      document.getElementById('date-start').value = searchToolbarFilters.dateStart || '';
      document.getElementById('date-end').value = searchToolbarFilters.dateEnd || '';
      break;
  }
}

function setupEditorActions() {
  // Sort editor  
  document.getElementById('sort-apply').addEventListener('click', () => applySearchToolbarFilter('sort'));
  document.getElementById('sort-close').addEventListener('click', closePillEditor);
  
  // Directory editor
  document.getElementById('directory-apply').addEventListener('click', () => applySearchToolbarFilter('directory'));
  document.getElementById('directory-close').addEventListener('click', closePillEditor);
  
  // File type editor
  document.getElementById('filetype-apply').addEventListener('click', () => applySearchToolbarFilter('filetype'));
  document.getElementById('filetype-clear').addEventListener('click', () => clearFilter('filetype'));
  document.getElementById('filetype-close').addEventListener('click', closePillEditor);
  
  // Rating editor
  document.getElementById('rating-apply').addEventListener('click', () => applySearchToolbarFilter('rating'));
  document.getElementById('rating-clear').addEventListener('click', () => clearFilter('rating'));
  document.getElementById('rating-close').addEventListener('click', closePillEditor);
  
  // Date editor
  document.getElementById('date-apply').addEventListener('click', () => applySearchToolbarFilter('date'));
  document.getElementById('date-clear').addEventListener('click', () => clearFilter('date'));
  document.getElementById('date-close').addEventListener('click', closePillEditor);
  
  // Date preset buttons
  document.querySelectorAll('.preset-btn').forEach(btn => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      applyDatePreset(btn.dataset.preset);
    });
  });
  
  // Enter key support
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && activePillEditor) {
      e.preventDefault();
      applySearchToolbarFilter(activePillEditor);
    } else if (e.key === 'Escape' && activePillEditor) {
      e.preventDefault();
      closePillEditor();
    }
  });
}

function applySearchToolbarFilter(pillType) {
  let newValue;
  
  switch (pillType) {
    case 'sort':
      newValue = document.getElementById('sort-select').value;
      searchToolbarFilters.sort = newValue;
      break;
      
    case 'directory':
      newValue = document.getElementById('directory-input').value.trim();
      searchToolbarFilters.directory = newValue;
      // Update the backend directory
      if (newValue && newValue !== currentDir) {
        document.getElementById('dir').value = newValue;
        // Trigger the load button to refresh the directory
        const loadBtn = document.getElementById('load');
        if (loadBtn) {
          loadBtn.click();
        }
      }
      break;
      
    case 'filetype':
      const selected = Array.from(document.querySelectorAll('.filetype-checkboxes input[type="checkbox"]:checked'))
        .map(cb => cb.value);
      searchToolbarFilters.filetype = selected;
      // Update pattern for backend compatibility
      const pattern = selected.map(ext => `*.${ext}`).join('|');
      document.getElementById('pattern').value = pattern;
      currentPattern = pattern;
      break;
      
    case 'rating':
      newValue = document.getElementById('rating-select').value;
      searchToolbarFilters.rating = newValue;
      // Update min filter for backend compatibility
      document.getElementById('min_filter').value = newValue;
      if (newValue === 'none') {
        minFilter = null;
      } else if (newValue === 'unrated') {
        minFilter = 'unrated';
      } else {
        minFilter = parseInt(newValue);
      }
      break;
      
    case 'date':
      searchToolbarFilters.dateStart = document.getElementById('date-start').value || null;
      searchToolbarFilters.dateEnd = document.getElementById('date-end').value || null;
      break;
  }
  
  updatePillValues();
  applyCurrentFilters();
  closePillEditor();
}

function clearFilter(pillType) {
  switch (pillType) {
    case 'filetype':
      searchToolbarFilters.filetype = [];
      document.querySelectorAll('.filetype-checkboxes input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
      });
      break;
      
    case 'rating':
      searchToolbarFilters.rating = 'none';
      document.getElementById('rating-select').value = 'none';
      document.getElementById('min_filter').value = 'none';
      minFilter = null;
      break;
      
    case 'date':
      searchToolbarFilters.dateStart = null;
      searchToolbarFilters.dateEnd = null;
      document.getElementById('date-start').value = '';
      document.getElementById('date-end').value = '';
      break;
  }
  
  updatePillValues();
  applyCurrentFilters();
}

function updatePillValues() {
  // Sort
  const sortValue = document.getElementById('sort-value');
  const sortPill = document.getElementById('pill-sort');
  const sortLabels = { name: 'Name', date: 'Date', size: 'Size', rating: 'Rating' };
  sortValue.textContent = sortLabels[searchToolbarFilters.sort] || 'Name';
  
  // Directory
  const dirValue = document.getElementById('directory-value');
  const dirPill = document.getElementById('pill-directory');
  const displayDir = searchToolbarFilters.directory || currentDir || 'media';
  const shortDir = displayDir.split('/').pop() || displayDir;
  dirValue.textContent = shortDir;
  
  // File type
  const filetypeValue = document.getElementById('filetype-value');
  const filetypePill = document.getElementById('pill-filetype');
  const types = searchToolbarFilters.filetype;
  if (types.length === 0) {
    filetypeValue.textContent = 'None';
  } else if (types.length === 3 && types.includes('jpg') && types.includes('png') && types.includes('mp4')) {
    filetypeValue.textContent = 'All';
  } else {
    filetypeValue.textContent = types.map(t => t.toUpperCase()).join(', ');
  }
  
  // Rating
  const ratingValue = document.getElementById('rating-value');
  const ratingPill = document.getElementById('pill-rating');
  const ratingLabels = {
    'none': 'All',
    'unrated': 'Unrated',
    '1': '★1+',
    '2': '★2+',
    '3': '★3+',
    '4': '★4+',
    '5': '★5'
  };
  ratingValue.textContent = ratingLabels[searchToolbarFilters.rating] || 'All';
  
  // Date
  const dateValue = document.getElementById('date-value');
  const datePill = document.getElementById('pill-date');
  if (searchToolbarFilters.dateStart || searchToolbarFilters.dateEnd) {
    let dateText = '';
    if (searchToolbarFilters.dateStart && searchToolbarFilters.dateEnd) {
      dateText = `${searchToolbarFilters.dateStart} to ${searchToolbarFilters.dateEnd}`;
    } else if (searchToolbarFilters.dateStart) {
      dateText = `From ${searchToolbarFilters.dateStart}`;
    } else if (searchToolbarFilters.dateEnd) {
      dateText = `Until ${searchToolbarFilters.dateEnd}`;
    }
    dateValue.textContent = dateText;
  } else {
    dateValue.textContent = 'All';
  }
  
  // Apply modified state classes to pills
  const pillsData = [
    { pill: sortPill, filterName: 'sort' },
    { pill: dirPill, filterName: 'directory' },
    { pill: filetypePill, filterName: 'filetype' },
    { pill: ratingPill, filterName: 'rating' },
    { pill: datePill, filterName: 'dateStart' } // Check if any date is set
  ];
  
  pillsData.forEach(({ pill, filterName }) => {
    if (pill) {
      const isModified = filterName === 'dateStart' ? 
        (searchToolbarFilters.dateStart || searchToolbarFilters.dateEnd) : 
        isFilterModified(filterName);
        
      if (isModified) {
        pill.classList.add('pill-modified');
      } else {
        pill.classList.remove('pill-modified');
      }
    }
  });
}

function applyCurrentFilters() {
  // Start with all videos
  filtered = [...videos];
  
  // Apply rating filter using existing function
  if (typeof applyFilter === 'function') {
    applyFilter();
  }
  
  // Apply sort
  applySortFilter();
  
  // Update display
  if (typeof renderSidebar === 'function') {
    renderSidebar();
  }
  
  if (filtered.length > 0) {
    show(0);
  } else {
    show(-1);
  }
}

function applySortFilter() {
  const sortBy = searchToolbarFilters.sort;
  
  filtered.sort((a, b) => {
    switch (sortBy) {
      case 'name':
        return a.name.localeCompare(b.name);
      case 'date':
        // Note: This would require metadata from the backend
        return a.name.localeCompare(b.name); // Fallback to name
      case 'size':
        // Note: This would require metadata from the backend  
        return a.name.localeCompare(b.name); // Fallback to name
      case 'rating':
        const scoreA = a.score || 0;
        const scoreB = b.score || 0;
        return scoreB - scoreA; // Highest first
      default:
        return a.name.localeCompare(b.name);
    }
  });
}

function handleOutsideClick(event) {
  if (!activePillEditor) return;
  
  // Check if click is inside search toolbar or editor
  const searchToolbar = document.querySelector('.search-toolbar');
  const activeEditor = document.querySelector('.pill-editor.active');
  
  if (searchToolbar && !searchToolbar.contains(event.target) && 
      (!activeEditor || !activeEditor.contains(event.target))) {
    closePillEditor();
  }
}

function syncBackwardCompatibility() {
  // Sync initial values from existing elements
  const dirInput = document.getElementById('dir');
  const patternInput = document.getElementById('pattern');
  const minFilterSelect = document.getElementById('min_filter');
  
  if (dirInput.value) {
    searchToolbarFilters.directory = dirInput.value;
    currentDir = dirInput.value;
  }
  
  if (patternInput.value) {
    const pattern = patternInput.value;
    const extensions = pattern.split('|').map(p => p.replace('*.', '')).filter(Boolean);
    searchToolbarFilters.filetype = extensions;
    currentPattern = pattern;
  }
  
  if (minFilterSelect.value && minFilterSelect.value !== 'none') {
    searchToolbarFilters.rating = minFilterSelect.value;
    minFilter = minFilterSelect.value;
  }
  
  updatePillValues();
}

// Window resize handler for repositioning popovers
window.addEventListener('resize', () => {
  if (activePillEditor && window.innerWidth > 768) {
    const activeEditor = document.querySelector('.pill-editor.active');
    const activePill = document.querySelector('.pill.active');
    if (activeEditor && activePill) {
      positionEditorPopover(activeEditor, activePill);
    }
  }
});

// Date preset functionality
function applyDatePreset(preset) {
  const today = new Date();
  let startDate = null;
  let endDate = null;
  
  switch (preset) {
    case 'today':
      startDate = endDate = today.toISOString().split('T')[0];
      break;
      
    case 'week':
      const startOfWeek = new Date(today);
      startOfWeek.setDate(today.getDate() - today.getDay());
      startDate = startOfWeek.toISOString().split('T')[0];
      endDate = today.toISOString().split('T')[0];
      break;
      
    case 'month':
      const startOfMonth = new Date(today.getFullYear(), today.getMonth(), 1);
      startDate = startOfMonth.toISOString().split('T')[0];
      endDate = today.toISOString().split('T')[0];
      break;
      
    case 'year':
      const startOfYear = new Date(today.getFullYear(), 0, 1);
      startDate = startOfYear.toISOString().split('T')[0];
      endDate = today.toISOString().split('T')[0];
      break;
  }
  
  document.getElementById('date-start').value = startDate || '';
  document.getElementById('date-end').value = endDate || '';
}

// Updated applyCurrentFilters to use database if available
function applyCurrentFilters() {
  // Check if database is enabled by checking for database_enabled in the last API response
  if (window.databaseEnabled) {
    applyDatabaseFilters();
  } else {
    applyClientSideFilters();
  }
}

async function applyDatabaseFilters() {
  try {
    // Build filter request
    const filterRequest = {
      file_types: searchToolbarFilters.filetype,
      start_date: searchToolbarFilters.dateStart ? `${searchToolbarFilters.dateStart}T00:00:00Z` : null,
      end_date: searchToolbarFilters.dateEnd ? `${searchToolbarFilters.dateEnd}T23:59:59Z` : null
    };
    
    // Add rating filters
    if (searchToolbarFilters.rating !== 'none') {
      if (searchToolbarFilters.rating === 'unrated') {
        filterRequest.max_score = 0;
      } else {
        filterRequest.min_score = parseInt(searchToolbarFilters.rating);
      }
    }
    
    const response = await fetch('/api/filter', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filterRequest)
    });
    
    if (response.ok) {
      const data = await response.json();
      videos = data.videos;
      
      // Apply search filter client-side
      if (searchToolbarFilters.search) {
        filtered = videos.filter(video => 
          video.name.toLowerCase().includes(searchToolbarFilters.search.toLowerCase())
        );
      } else {
        filtered = [...videos];
      }
      
      // Apply sort
      applySortFilter();
      
      // Update display
      if (typeof renderSidebar === 'function') {
        renderSidebar();
      }
      
      if (filtered.length > 0) {
        show(0);
      }
    }
  } catch (error) {
    console.error('Database filter failed:', error);
    // Fallback to client-side filtering
    applyClientSideFilters();
  }
}

function applyClientSideFilters() {
  // Start with all videos
  let currentFiltered = [...videos];
  
  // Apply rating filter
  if (minFilter !== null) {
    if (minFilter === 'unrated') {
      currentFiltered = currentFiltered.filter(v => !v.score || v.score === 0);
    } else {
      currentFiltered = currentFiltered.filter(v => (v.score||0) >= minFilter);
    }
  }
  
  // Set the filtered results
  filtered = currentFiltered;
  
  // Apply sort
  applySortFilter();
  
  // Update display
  if (typeof renderSidebar === 'function') {
    renderSidebar();
  }
  
  if (filtered.length > 0) {
    show(0);
  } else {
    show(-1);
  }
  
  // Update filter info display
  const info = document.getElementById('filter_info');
  if (info) {
    let filterParts = [];
    
    if (minFilter !== null) {
      if (minFilter === 'unrated') {
        filterParts.push('unrated only');
      } else {
        filterParts.push(`rating ≥ ${minFilter}`);
      }
    }
    
    const filterLabel = filterParts.length > 0 ? filterParts.join(', ') : 'No filter';
    info.textContent = `${filterLabel} — showing ${filtered.length}/${videos.length}`;
  }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Small delay to ensure other scripts have initialized
  setTimeout(initializeSearchToolbar, 100);
});