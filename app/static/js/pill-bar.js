/**
 * Pill Bar Functionality
 * Handles the new pill-based filtering interface
 */

// Pill bar state
let activePillEditor = null;
let pillBarFilters = {
  search: '',
  sort: 'name',
  directory: '',
  filetype: ['jpg', 'png', 'mp4'],
  rating: 'none'
};

// Initialize pill bar functionality
function initializePillBar() {
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
  const filter = pillBarFilters[pillType];
  
  switch (pillType) {
    case 'search':
      document.getElementById('search-input').value = filter;
      break;
      
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
  }
}

function setupEditorActions() {
  // Search editor
  document.getElementById('search-apply').addEventListener('click', () => applyFilter('search'));
  document.getElementById('search-clear').addEventListener('click', () => clearFilter('search'));
  document.getElementById('search-close').addEventListener('click', closePillEditor);
  
  // Sort editor  
  document.getElementById('sort-apply').addEventListener('click', () => applyFilter('sort'));
  document.getElementById('sort-close').addEventListener('click', closePillEditor);
  
  // Directory editor
  document.getElementById('directory-apply').addEventListener('click', () => applyFilter('directory'));
  document.getElementById('directory-close').addEventListener('click', closePillEditor);
  
  // File type editor
  document.getElementById('filetype-apply').addEventListener('click', () => applyFilter('filetype'));
  document.getElementById('filetype-clear').addEventListener('click', () => clearFilter('filetype'));
  document.getElementById('filetype-close').addEventListener('click', closePillEditor);
  
  // Rating editor
  document.getElementById('rating-apply').addEventListener('click', () => applyFilter('rating'));
  document.getElementById('rating-clear').addEventListener('click', () => clearFilter('rating'));
  document.getElementById('rating-close').addEventListener('click', closePillEditor);
  
  // Enter key support
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && activePillEditor) {
      e.preventDefault();
      applyFilter(activePillEditor);
    } else if (e.key === 'Escape' && activePillEditor) {
      e.preventDefault();
      closePillEditor();
    }
  });
}

function applyFilter(pillType) {
  let newValue;
  
  switch (pillType) {
    case 'search':
      newValue = document.getElementById('search-input').value.trim();
      pillBarFilters.search = newValue;
      break;
      
    case 'sort':
      newValue = document.getElementById('sort-select').value;
      pillBarFilters.sort = newValue;
      break;
      
    case 'directory':
      newValue = document.getElementById('directory-input').value.trim();
      pillBarFilters.directory = newValue;
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
      pillBarFilters.filetype = selected;
      // Update pattern for backend compatibility
      const pattern = selected.map(ext => `*.${ext}`).join('|');
      document.getElementById('pattern').value = pattern;
      currentPattern = pattern;
      break;
      
    case 'rating':
      newValue = document.getElementById('rating-select').value;
      pillBarFilters.rating = newValue;
      // Update min filter for backend compatibility
      document.getElementById('min_filter').value = newValue;
      minFilter = newValue === 'none' ? null : newValue;
      break;
  }
  
  updatePillValues();
  applyCurrentFilters();
  closePillEditor();
}

function clearFilter(pillType) {
  switch (pillType) {
    case 'search':
      pillBarFilters.search = '';
      document.getElementById('search-input').value = '';
      break;
      
    case 'filetype':
      pillBarFilters.filetype = [];
      document.querySelectorAll('.filetype-checkboxes input[type="checkbox"]').forEach(cb => {
        cb.checked = false;
      });
      break;
      
    case 'rating':
      pillBarFilters.rating = 'none';
      document.getElementById('rating-select').value = 'none';
      document.getElementById('min_filter').value = 'none';
      minFilter = null;
      break;
  }
  
  updatePillValues();
  applyCurrentFilters();
}

function updatePillValues() {
  // Search
  const searchValue = document.getElementById('search-value');
  searchValue.textContent = pillBarFilters.search || '';
  
  // Sort
  const sortValue = document.getElementById('sort-value');
  const sortLabels = { name: 'Name', date: 'Date', size: 'Size', rating: 'Rating' };
  sortValue.textContent = sortLabels[pillBarFilters.sort] || 'Name';
  
  // Directory
  const dirValue = document.getElementById('directory-value');
  const displayDir = pillBarFilters.directory || currentDir || 'media';
  const shortDir = displayDir.split('/').pop() || displayDir;
  dirValue.textContent = shortDir;
  
  // File type
  const filetypeValue = document.getElementById('filetype-value');
  const types = pillBarFilters.filetype;
  if (types.length === 0) {
    filetypeValue.textContent = 'None';
  } else if (types.length === 3 && types.includes('jpg') && types.includes('png') && types.includes('mp4')) {
    filetypeValue.textContent = 'All';
  } else {
    filetypeValue.textContent = types.map(t => t.toUpperCase()).join(', ');
  }
  
  // Rating
  const ratingValue = document.getElementById('rating-value');
  const ratingLabels = {
    'none': 'All',
    'unrated': 'Unrated',
    '1': '★1+',
    '2': '★2+',
    '3': '★3+',
    '4': '★4+',
    '5': '★5'
  };
  ratingValue.textContent = ratingLabels[pillBarFilters.rating] || 'All';
}

function applyCurrentFilters() {
  // Apply search filter
  if (pillBarFilters.search) {
    filtered = videos.filter(video => 
      video.name.toLowerCase().includes(pillBarFilters.search.toLowerCase())
    );
  } else {
    filtered = [...videos];
  }
  
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
  const sortBy = pillBarFilters.sort;
  
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
  
  // Check if click is inside pill bar or editor
  const pillBar = document.querySelector('.pill-bar');
  const activeEditor = document.querySelector('.pill-editor.active');
  
  if (!pillBar.contains(event.target) && 
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
    pillBarFilters.directory = dirInput.value;
    currentDir = dirInput.value;
  }
  
  if (patternInput.value) {
    const pattern = patternInput.value;
    const extensions = pattern.split('|').map(p => p.replace('*.', '')).filter(Boolean);
    pillBarFilters.filetype = extensions;
    currentPattern = pattern;
  }
  
  if (minFilterSelect.value && minFilterSelect.value !== 'none') {
    pillBarFilters.rating = minFilterSelect.value;
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

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  // Small delay to ensure other scripts have initialized
  setTimeout(initializePillBar, 100);
});