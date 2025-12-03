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
  nsfw: 'all'
};

// Track if filters have changed and need refresh
let filtersChanged = false;

/**
 * Mark filters as changed and show refresh indicator
 */
function markFiltersChanged() {
  filtersChanged = true;
  const indicator = document.getElementById('refresh-indicator');
  const refreshBtn = document.getElementById('refresh-content');
  
  if (indicator) {
    indicator.style.display = 'inline-block';
    indicator.classList.add('visible');
  }
  
  if (refreshBtn) {
    refreshBtn.style.borderColor = '#ff9800';
    refreshBtn.style.boxShadow = '0 0 10px rgba(255, 152, 0, 0.5)';
  }
}

/**
 * Clear filters changed state
 */
function clearFiltersChanged() {
  filtersChanged = false;
  const indicator = document.getElementById('refresh-indicator');
  const refreshBtn = document.getElementById('refresh-content');
  
  if (indicator) {
    indicator.style.display = 'none';
    indicator.classList.remove('visible');
  }
  
  if (refreshBtn) {
    refreshBtn.style.borderColor = '';
    refreshBtn.style.boxShadow = '';
  }
}

/**
 * Apply server-side filter state to search toolbar
 * This is called when buffer state is restored on page load
 * 
 * @param {Object} filters - Filter object from server
 */
function applyServerFilters(filters) {
  if (!filters) {
    console.warn('[SearchToolbar] No server filters to apply');
    return;
  }
  
  console.info('[SearchToolbar] Applying server-side filters:', filters);
  
  // Map server filter format to toolbar format
  
  // Sort field and direction
  if (filters.sort_field) {
    // Map server sort field names to toolbar values
    const sortFieldMap = {
      'name': 'name',
      'date': 'date',
      'created_at': 'date',
      'original_created_at': 'date',
      'score': 'rating',
      'file_size': 'size'
    };
    searchToolbarFilters.sort = sortFieldMap[filters.sort_field] || filters.sort_field;
  }
  
  if (filters.sort_direction) {
    searchToolbarFilters.sortDirection = filters.sort_direction;
  }
  
  // File types
  if (filters.file_types && Array.isArray(filters.file_types)) {
    searchToolbarFilters.filetype = filters.file_types;
  }
  
  // Rating (min_score)
  if (filters.min_score !== null && filters.min_score !== undefined) {
    if (filters.min_score === -1) {
      searchToolbarFilters.rating = 'rejected';
    } else if (filters.min_score === 0) {
      searchToolbarFilters.rating = 'unrated';
    } else {
      searchToolbarFilters.rating = filters.min_score.toString();
    }
  } else {
    searchToolbarFilters.rating = 'none';
  }
  
  // Date range
  if (filters.start_date) {
    searchToolbarFilters.dateStart = filters.start_date;
  }
  if (filters.end_date) {
    searchToolbarFilters.dateEnd = filters.end_date;
  }
  
  // NSFW filter
  if (filters.nsfw_filter) {
    searchToolbarFilters.nsfw = filters.nsfw_filter;
  }
  
  console.info('[SearchToolbar] Filters applied:', searchToolbarFilters);
  
  // Update UI to reflect the applied filters
  // Use a small delay to ensure DOM elements are ready
  setTimeout(() => {
    updateSearchToolbarUI();
    updatePillValues();
  }, 50);
}

/**
 * Update UI elements to reflect current searchToolbarFilters state
 */
function updateSearchToolbarUI() {
  // Update sort selection
  const sortSelect = document.getElementById('sort-select');
  if (sortSelect) {
    sortSelect.value = searchToolbarFilters.sort;
  }
  
  // Update sort direction buttons
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
  
  // Update file type checkboxes
  document.querySelectorAll('.filetype-checkboxes input[type="checkbox"]').forEach(cb => {
    cb.checked = searchToolbarFilters.filetype.includes(cb.value);
  });
  
  // Update rating selection
  const ratingSelect = document.getElementById('rating-select');
  if (ratingSelect) {
    ratingSelect.value = searchToolbarFilters.rating;
  }
  
  // Update date inputs
  const dateStart = document.getElementById('date-start');
  const dateEnd = document.getElementById('date-end');
  if (dateStart && searchToolbarFilters.dateStart) {
    dateStart.value = searchToolbarFilters.dateStart;
  }
  if (dateEnd && searchToolbarFilters.dateEnd) {
    dateEnd.value = searchToolbarFilters.dateEnd;
  }
  
  // Update NSFW filter buttons
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
  
  console.info('Search toolbar UI updated');
}


// Default filter values for comparison (to detect modifications)
const defaultFilters = {
  sort: 'name',
  sortDirection: 'asc',
  filetype: ['jpg', 'png', 'mp4'],
  rating: 'none',
  dateStart: null,
  dateEnd: null,
  nsfw: 'all'
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
    const currentValue = (current === null || current === '') ? null : current;
    const defaultVal = (defaultValue === null || defaultValue === '') ? null : defaultValue;
    return currentValue !== defaultVal;
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
      // Restore selected date in contribution graph if available
      if (typeof loadContributionGraphData === 'function' && !contributionGraphData) {
        loadContributionGraphData();
      }
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

  // Sort field select - update state only
  const sortSelect = document.getElementById('sort-select');
  if (sortSelect) {
    sortSelect.addEventListener('change', () => {
      searchToolbarFilters.sort = sortSelect.value;
      updatePillValues();
    });
  }

  // Sort direction toggle buttons - update state only
  const ascBtn = document.getElementById('sort-asc-btn');
  const descBtn = document.getElementById('sort-desc-btn');
  if (ascBtn && descBtn) {
    ascBtn.addEventListener('click', () => {
      searchToolbarFilters.sortDirection = 'asc';
      ascBtn.classList.add('active');
      descBtn.classList.remove('active');
      updatePillValues();
    });
    descBtn.addEventListener('click', () => {
      searchToolbarFilters.sortDirection = 'desc';
      descBtn.classList.add('active');
      ascBtn.classList.remove('active');
      updatePillValues();
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
  
  // Date editor - updated for contribution graph
  const dateClearBtn = document.getElementById('date-clear');
  const dateCloseBtn = document.getElementById('date-close');
  
  if (dateClearBtn) {
    dateClearBtn.addEventListener('click', () => {
      // Call the contribution graph's clear function if available
      if (typeof clearDateFilter === 'function') {
        clearDateFilter();
      } else {
        clearFilter('date');
      }
    });
  }
  
  if (dateCloseBtn) {
    dateCloseBtn.addEventListener('click', closePillEditor);
  }
  
  // NSFW editor
  document.getElementById('nsfw-apply').addEventListener('click', () => applySearchToolbarFilter('nsfw'));
  document.getElementById('nsfw-clear').addEventListener('click', () => clearFilter('nsfw'));
  document.getElementById('nsfw-close').addEventListener('click', closePillEditor);
  
  // NSFW filter toggle buttons - update state only
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
    });
    nsfwSfwBtn.addEventListener('click', () => {
      searchToolbarFilters.nsfw = 'sfw';
      nsfwSfwBtn.classList.add('active');
      nsfwAllBtn.classList.remove('active');
      nsfwNsfwBtn.classList.remove('active');
      updatePillValues();
    });
    nsfwNsfwBtn.addEventListener('click', () => {
      searchToolbarFilters.nsfw = 'nsfw';
      nsfwNsfwBtn.classList.add('active');
      nsfwAllBtn.classList.remove('active');
      nsfwSfwBtn.classList.remove('active');
      updatePillValues();
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
      // Date filtering is now handled by contribution graph click events
      // This case is kept for compatibility but shouldn't be called
      break;
      
    case 'nsfw':
      // NSFW filter is already set by the toggle buttons
      // Just need to trigger the update
      break;
  }
  
  updatePillValues();
  closePillEditor();
  
  // Mark filters as changed if using buffer mode
  if (window.databaseEnabled && window.BufferClient && window.BufferClient.isActive()) {
    markFiltersChanged();
    // Save filter state to server for persistence
    if (typeof buildFilterCriteria === 'function') {
      window.BufferClient.setActiveFilters(buildFilterCriteria()).catch(err => {
        console.error('Failed to save filter state:', err);
      });
    }
  } else {
    // Apply filters immediately in non-buffer mode
    if (typeof applyCurrentFilters === 'function') {
      applyCurrentFilters();
    }
  }
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
      // Clear selection in contribution graph
      if (typeof selectedDate !== 'undefined') {
        selectedDate = null;
        const days = document.querySelectorAll('.graph-day[data-date]');
        days.forEach(day => {
          day.classList.remove('selected');
        });
      }
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
  }
  
  updatePillValues();
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
  
  // Date - use the function from contribution-graph.js if available
  const datePill = document.getElementById('pill-date');
  if (typeof updateDatePillValue === 'function') {
    updateDatePillValue();
  } else {
    // Fallback to old behavior if contribution-graph.js not loaded
    const dateValue = document.getElementById('date-value');
    if (searchToolbarFilters.dateStart || searchToolbarFilters.dateEnd) {
      let dateText = '';
      if (searchToolbarFilters.dateStart && searchToolbarFilters.dateEnd) {
        if (searchToolbarFilters.dateStart === searchToolbarFilters.dateEnd) {
          dateText = searchToolbarFilters.dateStart;
        } else {
          dateText = `${searchToolbarFilters.dateStart} to ${searchToolbarFilters.dateEnd}`;
        }
      } else if (searchToolbarFilters.dateStart) {
        dateText = `From ${searchToolbarFilters.dateStart}`;
      } else if (searchToolbarFilters.dateEnd) {
        dateText = `Until ${searchToolbarFilters.dateEnd}`;
      }
      dateValue.textContent = dateText;
    } else {
      dateValue.textContent = 'All';
    }
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
  
  // Apply modified state classes to pills
  const pillsData = [
    { pill: sortPill, filterName: 'sort' },
    { pill: filetypePill, filterName: 'filetype' },
    { pill: ratingPill, filterName: 'rating' },
    { pill: datePill, filterName: 'dateStart' }, // Check if any date is set
    { pill: nsfwPill, filterName: 'nsfw' }
  ];
  
  pillsData.forEach(({ pill, filterName }) => {
    if (pill) {
      // Special handling for date pill - check both dateStart and dateEnd
      const isModified = filterName === 'dateStart' ? 
        (isFilterModified('dateStart') || isFilterModified('dateEnd')) : 
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
    updatePillValues(); // Update UI to reflect current state
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