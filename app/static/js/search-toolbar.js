/**
 * Search Toolbar Functionality
 * Handles the search toolbar filtering interface
 */

// Search toolbar state
let activePillEditor = null;
let searchToolbarFilters = {
  sort: 'name',
  sortDirection: 'asc',
  filetype: ['jpg', 'png', 'mp4'],
  rating: 'none',
  dateStart: null,
  dateEnd: null,
  nsfw: 'all',
  similar: {
    active: false,
    searchImage: null,
    phash: null,
    maxResults: 10,
    maxDistance: 10
  }
};

// Function to restore search toolbar state from cookies
function restoreSearchToolbarState() {
  if (typeof loadState !== 'function') {
    console.warn('State persistence not available for search toolbar, will retry...');
    setTimeout(restoreSearchToolbarState, 100);
    return;
  }
  
  console.info('Restoring search toolbar state...');
  
  // Restore search filters
  searchToolbarFilters.sort = loadState('searchFilters_sort') || 'name';
  searchToolbarFilters.sortDirection = loadState('searchFilters_sortDirection') || 'asc';
  
  const savedFiletype = loadState('searchFilters_filetype');
  if (savedFiletype && Array.isArray(savedFiletype)) {
    searchToolbarFilters.filetype = savedFiletype;
  }
  
  searchToolbarFilters.rating = loadState('searchFilters_rating') || 'none';
  
  const savedDateStart = loadState('searchFilters_dateStart');
  if (savedDateStart && savedDateStart !== 'null') {
    searchToolbarFilters.dateStart = savedDateStart;
  }
  
  const savedDateEnd = loadState('searchFilters_dateEnd');
  if (savedDateEnd && savedDateEnd !== 'null') {
    searchToolbarFilters.dateEnd = savedDateEnd;
  }
  
  searchToolbarFilters.nsfw = loadState('searchFilters_nsfw') || 'all';
  
  // Restore active pill editor
  const savedActivePill = loadState('activePillEditor');
  if (savedActivePill && savedActivePill !== 'null') {
    activePillEditor = savedActivePill;
  }
  
  console.info('Search toolbar state restored successfully');
  
  // Apply the restored state to UI elements
  restoreSearchToolbarUI();
}

// Function to restore UI elements based on loaded state
function restoreSearchToolbarUI() {
  // Restore sort selection
  const sortSelect = document.getElementById('sort-select');
  if (sortSelect) {
    sortSelect.value = searchToolbarFilters.sort;
  }
  
  // Restore sort direction buttons
  const ascBtn = document.getElementById('sort-asc-btn');
  const descBtn = document.getElementById('sort-desc-btn');
  if (ascBtn && descBtn) {
    if (searchToolbarFilters.sortDirection === 'asc') {
      ascBtn.classList.add('active');
      descBtn.classList.remove('active');
    } else {
      descBtn.classList.add('active');
      ascBtn.classList.remove('active');
    }
  }
  
  // Restore file type checkboxes
  document.querySelectorAll('.filetype-checkboxes input[type="checkbox"]').forEach(cb => {
    cb.checked = searchToolbarFilters.filetype.includes(cb.value);
  });
  
  // Restore rating selection
  const ratingSelect = document.getElementById('rating-select');
  if (ratingSelect) {
    ratingSelect.value = searchToolbarFilters.rating;
  }
  
  // Restore date inputs
  const dateStart = document.getElementById('date-start');
  const dateEnd = document.getElementById('date-end');
  if (dateStart && searchToolbarFilters.dateStart) {
    dateStart.value = searchToolbarFilters.dateStart;
  }
  if (dateEnd && searchToolbarFilters.dateEnd) {
    dateEnd.value = searchToolbarFilters.dateEnd;
  }
  
  // Restore NSFW filter buttons
  const nsfwAllBtn = document.getElementById('nsfw-all-btn');
  const nsfwSfwBtn = document.getElementById('nsfw-sfw-btn');
  const nsfwNsfwBtn = document.getElementById('nsfw-nsfw-btn');
  if (nsfwAllBtn && nsfwSfwBtn && nsfwNsfwBtn) {
    // Clear all active states first
    nsfwAllBtn.classList.remove('active');
    nsfwSfwBtn.classList.remove('active');
    nsfwNsfwBtn.classList.remove('active');
    
    // Set active state based on filter value
    switch (searchToolbarFilters.nsfw) {
      case 'all':
        nsfwAllBtn.classList.add('active');
        break;
      case 'sfw':
        nsfwSfwBtn.classList.add('active');
        break;
      case 'nsfw':
        nsfwNsfwBtn.classList.add('active');
        break;
    }
  }
  
  console.info('Search toolbar UI state restored');
}

// Function to save search toolbar state to cookies
function saveSearchToolbarState() {
  if (typeof saveState !== 'function') return;
  
  // Save all search filter state
  saveState('searchFilters_sort', searchToolbarFilters.sort);
  saveState('searchFilters_sortDirection', searchToolbarFilters.sortDirection);
  saveState('searchFilters_filetype', searchToolbarFilters.filetype);
  saveState('searchFilters_rating', searchToolbarFilters.rating);
  saveState('searchFilters_dateStart', searchToolbarFilters.dateStart);
  saveState('searchFilters_dateEnd', searchToolbarFilters.dateEnd);
  saveState('searchFilters_nsfw', searchToolbarFilters.nsfw);
  saveState('activePillEditor', activePillEditor);
}

// Default filter values for comparison (to detect modifications)
const defaultFilters = {
  sort: 'name',
  sortDirection: 'asc',
  filetype: ['jpg', 'png', 'mp4'],
  rating: 'none',
  dateStart: null,
  dateEnd: null,
  nsfw: 'all',
  similar: {
    active: false,
    searchImage: null,
    phash: null,
    maxResults: 10,
    maxDistance: 10
  }
};

// Check if a filter value has been modified from its default
function isFilterModified(filterName) {
  const current = searchToolbarFilters[filterName];
  const defaultValue = defaultFilters[filterName];
  
  // Handle special cases for different data types
  if (filterName === 'sort') {
    // Check both sort field and direction
    return searchToolbarFilters.sort !== defaultFilters.sort || 
           searchToolbarFilters.sortDirection !== defaultFilters.sortDirection;
  }
  
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
  
  if (filterName === 'similar') {
    // Check if similar search is active
    return searchToolbarFilters.similar.active === true;
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
  
  // Save active pill editor state
  if (typeof saveState === 'function') {
    saveState('activePillEditor', activePillEditor);
  }
  
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
    } else {
      // Mobile: For sort editor, position below search toolbar
      if (pillType === 'sort') {
        const searchToolbar = document.querySelector('.search-toolbar');
        if (searchToolbar) {
          const rect = searchToolbar.getBoundingClientRect();
          editor.style.position = 'absolute';
          editor.style.top = `${rect.bottom + window.scrollY + 8}px`;
          editor.style.left = '8px';
          editor.style.right = '8px';
        }
      }
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
  
  // Save active pill editor state
  if (typeof saveState === 'function') {
    saveState('activePillEditor', null);
  }
}

function populateEditor(pillType) {
  const filter = searchToolbarFilters[pillType];
  
  switch (pillType) {
    case 'sort':
      document.getElementById('sort-select').value = filter;
      const direction = searchToolbarFilters.sortDirection;
      const ascBtn = document.getElementById('sort-asc-btn');
      const descBtn = document.getElementById('sort-desc-btn');
      if (ascBtn && descBtn) {
        ascBtn.classList.toggle('active', direction === 'asc');
        descBtn.classList.toggle('active', direction === 'desc');
      }
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
      
    case 'nsfw':
      const nsfwFilter = searchToolbarFilters.nsfw;
      const allBtn = document.getElementById('nsfw-all-btn');
      const sfwBtn = document.getElementById('nsfw-sfw-btn');
      const nsfwBtn = document.getElementById('nsfw-nsfw-btn');
      if (allBtn && sfwBtn && nsfwBtn) {
        allBtn.classList.toggle('active', nsfwFilter === 'all');
        sfwBtn.classList.toggle('active', nsfwFilter === 'sfw');
        nsfwBtn.classList.toggle('active', nsfwFilter === 'nsfw');
      }
      break;
  }
}

function setupEditorActions() {
  // Sort editor - no Apply/Clear buttons, just instant updates  
  const sortCloseIcon = document.getElementById('sort-close-icon');
  if (sortCloseIcon) {
    sortCloseIcon.addEventListener('click', closePillEditor);
  }

  // Sort field select - apply instantly
  const sortSelect = document.getElementById('sort-select');
  if (sortSelect) {
    sortSelect.addEventListener('change', () => {
      searchToolbarFilters.sort = sortSelect.value;
      updatePillValues();
      applyCurrentFilters();
    });
  }

  // Sort direction toggle buttons - apply instantly
  const ascBtn = document.getElementById('sort-asc-btn');
  const descBtn = document.getElementById('sort-desc-btn');
  if (ascBtn && descBtn) {
    ascBtn.addEventListener('click', () => {
      searchToolbarFilters.sortDirection = 'asc';
      ascBtn.classList.add('active');
      descBtn.classList.remove('active');
      updatePillValues();
      applyCurrentFilters();
      saveSearchToolbarState();
    });
    descBtn.addEventListener('click', () => {
      searchToolbarFilters.sortDirection = 'desc';
      descBtn.classList.add('active');
      ascBtn.classList.remove('active');
      updatePillValues();
      applyCurrentFilters();
      saveSearchToolbarState();
    });
  }
  
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
  
  // NSFW editor
  document.getElementById('nsfw-apply').addEventListener('click', () => applySearchToolbarFilter('nsfw'));
  document.getElementById('nsfw-clear').addEventListener('click', () => clearFilter('nsfw'));
  document.getElementById('nsfw-close').addEventListener('click', closePillEditor);
  
  // NSFW filter toggle buttons
  const nsfwAllBtn = document.getElementById('nsfw-all-btn');
  const nsfwSfwBtn = document.getElementById('nsfw-sfw-btn');
  const nsfwNsfwBtn = document.getElementById('nsfw-nsfw-btn');
  if (nsfwAllBtn && nsfwSfwBtn && nsfwNsfwBtn) {
    nsfwAllBtn.addEventListener('click', () => {
      searchToolbarFilters.nsfw = 'all';
      nsfwAllBtn.classList.add('active');
      nsfwSfwBtn.classList.remove('active');
      nsfwNsfwBtn.classList.remove('active');
      updatePillValues();
      applyCurrentFilters();
      saveSearchToolbarState();
    });
    nsfwSfwBtn.addEventListener('click', () => {
      searchToolbarFilters.nsfw = 'sfw';
      nsfwSfwBtn.classList.add('active');
      nsfwAllBtn.classList.remove('active');
      nsfwNsfwBtn.classList.remove('active');
      updatePillValues();
      applyCurrentFilters();
      saveSearchToolbarState();
    });
    nsfwNsfwBtn.addEventListener('click', () => {
      searchToolbarFilters.nsfw = 'nsfw';
      nsfwNsfwBtn.classList.add('active');
      nsfwAllBtn.classList.remove('active');
      nsfwSfwBtn.classList.remove('active');
      updatePillValues();
      applyCurrentFilters();
      saveSearchToolbarState();
    });
  }
  
  // Similar Images editor
  document.getElementById('similar-apply').addEventListener('click', () => applySearchToolbarFilter('similar'));
  document.getElementById('similar-clear').addEventListener('click', () => clearFilter('similar'));
  document.getElementById('similar-close').addEventListener('click', closePillEditor);
  
  // Similar Images - User path submit
  const similarPathSubmit = document.getElementById('similar-path-submit');
  const similarUserPath = document.getElementById('similar-user-path');
  if (similarPathSubmit && similarUserPath) {
    similarPathSubmit.addEventListener('click', async () => {
      const userPath = similarUserPath.value.trim();
      if (!userPath) {
        alert('Please enter a user path');
        return;
      }
      await loadSearchImageByPath(userPath);
    });
    
    // Also allow Enter key in the user path input
    similarUserPath.addEventListener('keydown', async (e) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        const userPath = similarUserPath.value.trim();
        if (userPath) {
          await loadSearchImageByPath(userPath);
        }
      }
    });
  }
  
  // Similar Images - Upload button
  const similarUploadBtn = document.getElementById('similar-upload-btn');
  const similarUploadInput = document.getElementById('similar-upload-input');
  if (similarUploadBtn && similarUploadInput) {
    similarUploadBtn.addEventListener('click', () => {
      similarUploadInput.click();
    });
    
    similarUploadInput.addEventListener('change', async (e) => {
      const file = e.target.files[0];
      if (file) {
        await uploadSearchImage(file);
      }
    });
  }
  
  // Similar Images - Results slider
  const similarMaxResults = document.getElementById('similar-max-results');
  const similarMaxResultsValue = document.getElementById('similar-max-results-value');
  if (similarMaxResults && similarMaxResultsValue) {
    similarMaxResults.addEventListener('input', () => {
      similarMaxResultsValue.textContent = similarMaxResults.value;
      searchToolbarFilters.similar.maxResults = parseInt(similarMaxResults.value);
    });
  }
  
  // Similar Images - Distance slider
  const similarMaxDistance = document.getElementById('similar-max-distance');
  const similarMaxDistanceValue = document.getElementById('similar-max-distance-value');
  if (similarMaxDistance && similarMaxDistanceValue) {
    similarMaxDistance.addEventListener('input', () => {
      similarMaxDistanceValue.textContent = similarMaxDistance.value;
      searchToolbarFilters.similar.maxDistance = parseInt(similarMaxDistance.value);
    });
  }
  
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
  // Read direction from state (set by toggle buttons)
  const sortDirection = searchToolbarFilters.sortDirection || 'asc';
      searchToolbarFilters.sort = newValue;
      searchToolbarFilters.sortDirection = sortDirection;
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
      } else if (newValue === 'rejected') {
        minFilter = 'rejected';
      } else if (newValue === 'unrated') {
        minFilter = 'unrated';
      } else if (newValue === 'unrated_and_above') {
        minFilter = 'unrated_and_above';
      } else {
        minFilter = parseInt(newValue);
      }
      break;
      
    case 'date':
      searchToolbarFilters.dateStart = document.getElementById('date-start').value || null;
      searchToolbarFilters.dateEnd = document.getElementById('date-end').value || null;
      break;
      
    case 'nsfw':
      // NSFW filter is already set by the toggle buttons
      // Just need to trigger the update
      break;
      
    case 'similar':
      // Similar filter state is already set when loading search image
      // Just activate the filter if we have a search image
      if (searchToolbarFilters.similar.searchImage && searchToolbarFilters.similar.phash) {
        searchToolbarFilters.similar.active = true;
      }
      break;
  }
  
  updatePillValues();
  applyCurrentFilters();
  closePillEditor();
  
  // Save search toolbar state
  saveSearchToolbarState();
}

function clearFilter(pillType) {
  switch (pillType) {
    case 'sort':
      searchToolbarFilters.sort = 'name';
      searchToolbarFilters.sortDirection = 'asc';
      document.getElementById('sort-select').value = 'name';
      const ascBtn2 = document.getElementById('sort-asc-btn');
      const descBtn2 = document.getElementById('sort-desc-btn');
      if (ascBtn2 && descBtn2) {
        ascBtn2.classList.add('active');
        descBtn2.classList.remove('active');
      }
      break;
      
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
      
    case 'nsfw':
      searchToolbarFilters.nsfw = 'all';
      const nsfwAllBtn = document.getElementById('nsfw-all-btn');
      const nsfwSfwBtn = document.getElementById('nsfw-sfw-btn');
      const nsfwNsfwBtn = document.getElementById('nsfw-nsfw-btn');
      if (nsfwAllBtn && nsfwSfwBtn && nsfwNsfwBtn) {
        nsfwAllBtn.classList.add('active');
        nsfwSfwBtn.classList.remove('active');
        nsfwNsfwBtn.classList.remove('active');
      }
      break;
      
    case 'similar':
      searchToolbarFilters.similar = {
        active: false,
        searchImage: null,
        phash: null,
        maxResults: 10,
        maxDistance: 10
      };
      // Clear UI
      document.getElementById('similar-user-path').value = '';
      document.getElementById('similar-upload-input').value = '';
      document.getElementById('similar-search-image-info').style.display = 'none';
      document.getElementById('similar-results-slider').style.display = 'none';
      document.getElementById('similar-distance-slider').style.display = 'none';
      document.getElementById('similar-max-results').value = '10';
      document.getElementById('similar-max-results-value').textContent = '10';
      document.getElementById('similar-max-distance').value = '10';
      document.getElementById('similar-max-distance-value').textContent = '10';
      break;
  }
  
  updatePillValues();
  applyCurrentFilters();
  
  // Save search toolbar state
  saveSearchToolbarState();
}

function updatePillValues() {
  // Sort
  const sortValue = document.getElementById('sort-value');
  const sortPill = document.getElementById('pill-sort');
  const sortLabels = { name: 'Name', date: 'Date', size: 'Size', rating: 'Rating' };
  const directionLabels = { asc: '↑', desc: '↓' };
  const sortLabel = sortLabels[searchToolbarFilters.sort] || 'Name';
  const directionLabel = directionLabels[searchToolbarFilters.sortDirection] || '↑';
  sortValue.textContent = `${sortLabel} ${directionLabel}`;
  
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
    'rejected': 'Rejected',
    'unrated': 'Unrated',
    'unrated_and_above': 'Unrated+',
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
  
  // NSFW
  const nsfwValue = document.getElementById('nsfw-value');
  const nsfwPill = document.getElementById('pill-nsfw');
  const nsfwLabels = {
    'all': 'All',
    'sfw': 'SFW Only',
    'nsfw': 'NSFW Only'
  };
  if (nsfwValue) {
    nsfwValue.textContent = nsfwLabels[searchToolbarFilters.nsfw] || 'All';
  }
  
  // Similar Images
  const similarValue = document.getElementById('similar-value');
  const similarPill = document.getElementById('pill-similar');
  if (similarValue) {
    if (searchToolbarFilters.similar.active && searchToolbarFilters.similar.phash) {
      similarValue.textContent = `Top ${searchToolbarFilters.similar.maxResults}`;
    } else {
      similarValue.textContent = 'Off';
    }
  }
  
  // Apply modified state classes to pills
  const pillsData = [
    { pill: sortPill, filterName: 'sort' },
    { pill: filetypePill, filterName: 'filetype' },
    { pill: ratingPill, filterName: 'rating' },
    { pill: datePill, filterName: 'dateStart' }, // Check if any date is set
    { pill: nsfwPill, filterName: 'nsfw' },
    { pill: similarPill, filterName: 'similar' }
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
  const sortDirection = searchToolbarFilters.sortDirection;
  
  filtered.sort((a, b) => {
    let result;
    
    switch (sortBy) {
      case 'name':
        result = a.name.localeCompare(b.name);
        break;
      case 'date':
        // Note: This would require metadata from the backend
        result = a.name.localeCompare(b.name); // Fallback to name
        break;
      case 'size':
        // Note: This would require metadata from the backend  
        result = a.name.localeCompare(b.name); // Fallback to name
        break;
      case 'rating':
        const scoreA = a.score || 0;
        const scoreB = b.score || 0;
        result = scoreA - scoreB; // For consistent asc/desc logic
        break;
      default:
        result = a.name.localeCompare(b.name);
        break;
    }
    
    // Apply sort direction
    return sortDirection === 'desc' ? -result : result;
  });
}

function handleOutsideClick(event) {
  if (!activePillEditor) return;
  
  // Check if click is inside search toolbar, sidebar controls, or editor
  const searchToolbar = document.querySelector('.search-toolbar');
  const sidebarControls = document.getElementById('sidebar_controls');
  const activeEditor = document.querySelector('.pill-editor.active');
  
  if (searchToolbar && !searchToolbar.contains(event.target) && 
      sidebarControls && !sidebarControls.contains(event.target) &&
      (!activeEditor || !activeEditor.contains(event.target))) {
    closePillEditor();
  }
}

function syncBackwardCompatibility() {
  // Sync initial values from existing elements
  const dirInput = document.getElementById('dir');
  const patternInput = document.getElementById('pattern');
  const minFilterSelect = document.getElementById('min_filter');
  
  if (patternInput.value) {
    const pattern = patternInput.value;
    const extensions = pattern.split('|').map(p => p.replace('*.', '')).filter(Boolean);
    searchToolbarFilters.filetype = extensions;
    currentPattern = pattern;
  }
  
  if (minFilterSelect.value && minFilterSelect.value !== 'none') {
    searchToolbarFilters.rating = minFilterSelect.value;
    
    // Properly convert minFilter value with type checking
    const val = minFilterSelect.value;
    if (val === 'none') {
      minFilter = null;
    } else if (val === 'rejected') {
      minFilter = 'rejected';
    } else if (val === 'unrated') {
      minFilter = 'unrated';
    } else if (val === 'unrated_and_above') {
      minFilter = 'unrated_and_above';
    } else if (!isNaN(parseInt(val))) {
      minFilter = parseInt(val);
    } else {
      minFilter = null; // Default fallback
    }
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

// Similar Images - Load search image by user path
async function loadSearchImageByPath(userPath) {
  try {
    const response = await fetch(`/api/search/file-info-by-path?user_path=${encodeURIComponent(userPath)}`);
    
    if (!response.ok) {
      const error = await response.json();
      alert(`Error: ${error.detail || 'Failed to load image'}`);
      return;
    }
    
    const data = await response.json();
    
    // Update search image state
    searchToolbarFilters.similar.searchImage = {
      name: data.name,
      path: data.path,
      source: 'path',
      userPath: userPath
    };
    searchToolbarFilters.similar.phash = data.phash;
    
    // Display search image info
    displaySearchImageInfo(data.path, data.phash);
    
  } catch (error) {
    console.error('Failed to load search image by path:', error);
    alert('Failed to load search image. Please check the path and try again.');
  }
}

// Similar Images - Upload search image
async function uploadSearchImage(file) {
  try {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('max_results', searchToolbarFilters.similar.maxResults);
    formData.append('max_distance', searchToolbarFilters.similar.maxDistance);
    
    const response = await fetch('/api/search/similar/by-upload', {
      method: 'POST',
      body: formData
    });
    
    if (!response.ok) {
      const error = await response.json();
      alert(`Error: ${error.detail || 'Failed to upload image'}`);
      return;
    }
    
    const data = await response.json();
    
    // Update search image state
    searchToolbarFilters.similar.searchImage = {
      filename: data.search_image.filename,
      temp_path: data.search_image.temp_path,
      source: 'upload'
    };
    searchToolbarFilters.similar.phash = data.search_image.phash;
    
    // Create object URL for uploaded file to display
    const imageUrl = URL.createObjectURL(file);
    
    // Display search image info
    displaySearchImageInfo(imageUrl, data.search_image.phash);
    
  } catch (error) {
    console.error('Failed to upload search image:', error);
    alert('Failed to upload search image. Please try again.');
  }
}

// Similar Images - Display search image info
function displaySearchImageInfo(imagePath, phash) {
  const infoContainer = document.getElementById('similar-search-image-info');
  const thumbnail = document.getElementById('similar-thumbnail');
  const phashValue = document.getElementById('similar-phash-value');
  const resultsSlider = document.getElementById('similar-results-slider');
  const distanceSlider = document.getElementById('similar-distance-slider');
  
  // Set thumbnail - use media endpoint for database paths, or direct URL for uploads
  if (imagePath.startsWith('blob:')) {
    thumbnail.src = imagePath;
  } else {
    // Extract filename from path for media endpoint
    const filename = imagePath.split('/').pop();
    thumbnail.src = `/media/${filename}`;
  }
  
  phashValue.textContent = phash;
  
  // Show the info container and sliders
  infoContainer.style.display = 'block';
  resultsSlider.style.display = 'block';
  distanceSlider.style.display = 'block';
}

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
  console.log('Applying database filters with sort...', searchToolbarFilters);
  
  try {
    // Check if Similar Images search is active
    if (searchToolbarFilters.similar.active && searchToolbarFilters.similar.phash) {
      await applySimilarImagesSearch();
      return;
    }
    
    // Build comprehensive filter request
    const filterRequest = {
      // Existing filters
      file_types: searchToolbarFilters.filetype,
      start_date: searchToolbarFilters.dateStart ? `${searchToolbarFilters.dateStart}T00:00:00Z` : null,
      end_date: searchToolbarFilters.dateEnd ? `${searchToolbarFilters.dateEnd}T23:59:59Z` : null,
      
      // NEW: Add sorting parameters
      sort_field: searchToolbarFilters.sort,      // 'name', 'date', 'size', 'rating'
      sort_direction: searchToolbarFilters.sortDirection,  // 'asc' or 'desc'
      
      // NEW: Add NSFW filter
      nsfw_filter: searchToolbarFilters.nsfw,  // 'all', 'sfw', 'nsfw'
      
      // NEW: Add pagination (future-proofing)
      offset: null,
      limit: null  // null for all results
    };
    
    console.log('Filter request:', filterRequest);
    
    // Add rating filters
    if (searchToolbarFilters.rating !== 'none') {
      if (searchToolbarFilters.rating === 'rejected') {
        filterRequest.min_score = -1;
        filterRequest.max_score = -1;
      } else if (searchToolbarFilters.rating === 'unrated') {
        filterRequest.max_score = 0;
      } else if (searchToolbarFilters.rating === 'unrated_and_above') {
        filterRequest.min_score = 0;
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
      console.log('Filter response received:', data);
      videos = data.videos;
      
      // Apply search filter client-side
      if (searchToolbarFilters.search) {
        filtered = videos.filter(video => 
          video.name.toLowerCase().includes(searchToolbarFilters.search.toLowerCase())
        );
      } else {
        filtered = [...videos];
      }
      
      console.log('Filtered results:', filtered.length);
      
      // NO client-side sorting needed - backend did it!
      // applySortFilter(); ← REMOVED: Backend handles sorting
      
      // Update display
      if (typeof renderSidebar === 'function') {
        renderSidebar();
      }
      
      if (filtered.length > 0) {
        show(0);
      }
    } else {
      console.error('Filter request failed:', response.status, response.statusText);
      const errorText = await response.text();
      console.error('Error response:', errorText);
    }
  } catch (error) {
    console.error('Database filter failed:', error);
    // Fallback to client-side filtering
    applyClientSideFilters();
  }
}

// Similar Images Search - Apply PHASH similarity search with filters
async function applySimilarImagesSearch() {
  console.log('Applying Similar Images search...', searchToolbarFilters.similar);
  
  try {
    // Build request with current filters
    const searchRequest = {
      max_results: searchToolbarFilters.similar.maxResults,
      max_distance: searchToolbarFilters.similar.maxDistance,
      file_types: searchToolbarFilters.filetype,
      date_start: searchToolbarFilters.dateStart ? `${searchToolbarFilters.dateStart}T00:00:00Z` : null,
      date_end: searchToolbarFilters.dateEnd ? `${searchToolbarFilters.dateEnd}T23:59:59Z` : null,
      nsfw_filter: searchToolbarFilters.nsfw
    };
    
    // Add rating filters
    if (searchToolbarFilters.rating !== 'none') {
      if (searchToolbarFilters.rating === 'rejected') {
        searchRequest.min_score = -1;
        searchRequest.max_score = -1;
      } else if (searchToolbarFilters.rating === 'unrated') {
        searchRequest.max_score = 0;
      } else if (searchToolbarFilters.rating === 'unrated_and_above') {
        searchRequest.min_score = 0;
      } else {
        searchRequest.min_score = parseInt(searchToolbarFilters.rating);
      }
    }
    
    let response;
    
    // Call the appropriate endpoint based on search source
    if (searchToolbarFilters.similar.searchImage.source === 'path') {
      searchRequest.user_path = searchToolbarFilters.similar.searchImage.userPath;
      response = await fetch('/api/search/similar/by-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchRequest)
      });
    } else {
      // For upload, we need to re-upload or use stored PHASH
      // For now, use the PHASH directly if available
      searchRequest.phash = searchToolbarFilters.similar.phash;
      searchRequest.user_path = searchToolbarFilters.similar.searchImage.path || '';
      response = await fetch('/api/search/similar/by-path', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(searchRequest)
      });
    }
    
    if (response.ok) {
      const data = await response.json();
      console.log('Similar Images search response:', data);
      
      // Convert results to video list format
      videos = data.results.map(result => ({
        name: result.name,
        path: result.path,
        score: result.score,
        phash: result.phash,
        distance: result.distance
      }));
      
      filtered = [...videos];
      
      console.log('Similar Images results:', filtered.length);
      
      // Update display
      if (typeof renderSidebar === 'function') {
        renderSidebar();
      }
      
      if (filtered.length > 0) {
        show(0);
      } else {
        show(-1);
      }
    } else {
      console.error('Similar Images search failed:', response.status, response.statusText);
      const errorText = await response.text();
      console.error('Error response:', errorText);
      alert('Similar Images search failed. Please try again.');
    }
  } catch (error) {
    console.error('Similar Images search error:', error);
    alert('Similar Images search failed. Please try again.');
  }
}

function applyClientSideFilters() {
  // Start with all videos
  let currentFiltered = [...videos];
  
  // Apply rating filter
  if (minFilter !== null) {
    if (minFilter === 'rejected') {
      currentFiltered = currentFiltered.filter(v => v.score === -1);
    } else if (minFilter === 'unrated') {
      currentFiltered = currentFiltered.filter(v => !v.score || v.score === 0);
    } else if (minFilter === 'unrated_and_above') {
      currentFiltered = currentFiltered.filter(v => !v.score || v.score >= 0);
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
      if (minFilter === 'rejected') {
        filterParts.push('rejected only');
      } else if (minFilter === 'unrated') {
        filterParts.push('unrated only');
      } else if (minFilter === 'unrated_and_above') {
        filterParts.push('unrated and above');
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
  setTimeout(() => {
    initializeSearchToolbar();
    restoreSearchToolbarState();
    updatePillValues(); // Update UI to reflect restored state
    
    // Restore active pill editor if one was open
    if (activePillEditor) {
      const pillElement = document.getElementById(`pill-${activePillEditor}`);
      if (pillElement) {
        setTimeout(() => {
          openPillEditor(activePillEditor, pillElement);
        }, 200);
      }
    }
  }, 100);
  
  // Initialize menu functionality
  initializeMenu();
});

/**
 * Menu overlay functionality
 */
function initializeMenu() {
  const menuBtn = document.getElementById('menu-btn');
  const menuOverlay = document.getElementById('menu-overlay');
  const menuCloseBtn = document.getElementById('menu-close-btn');
  
  if (!menuBtn || !menuOverlay || !menuCloseBtn) return;
  
  // Open menu
  menuBtn.addEventListener('click', () => {
    menuOverlay.classList.add('active');
  });
  
  // Close menu via close button
  menuCloseBtn.addEventListener('click', () => {
    menuOverlay.classList.remove('active');
  });
  
  // Close menu when clicking outside the panel
  menuOverlay.addEventListener('click', (e) => {
    if (e.target === menuOverlay) {
      menuOverlay.classList.remove('active');
    }
  });
  
  // Close menu with Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && menuOverlay.classList.contains('active')) {
      menuOverlay.classList.remove('active');
    }
  });
}