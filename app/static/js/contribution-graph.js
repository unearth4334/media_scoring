/**
 * Contribution Graph for Date Filtering
 * GitHub-style activity calendar for media creation dates
 */

let contributionGraphData = null;
let selectedDates = new Set(); // Changed from single to multiple dates
let pendingSelectedDates = new Set(); // Track changes before Apply

/**
 * Initialize the contribution graph
 */
async function initContributionGraph() {
  console.log('Initializing contribution graph...');
  
  // Load data when date editor is opened
  const datePill = document.getElementById('pill-date');
  if (datePill) {
    datePill.addEventListener('click', async () => {
      if (!contributionGraphData) {
        await loadContributionGraphData();
      } else {
        // Reset pending changes to match current selection
        pendingSelectedDates = new Set(selectedDates);
        renderContributionGraph();
      }
    });
  }
}

/**
 * Load daily media counts from API
 */
async function loadContributionGraphData() {
  const graphContainer = document.getElementById('contribution-graph');
  if (!graphContainer) return;
  
  try {
    graphContainer.innerHTML = '<div class="graph-loading">Loading activity data...</div>';
    
    const response = await fetch('/api/media/daily-counts');
    if (!response.ok) {
      throw new Error(`Failed to load data: ${response.statusText}`);
    }
    
    const data = await response.json();
    contributionGraphData = data.daily_counts || {};
    
    console.log(`Loaded ${data.total_files} files across ${data.total_days} days`);
    console.log('Daily counts sample:', Object.entries(contributionGraphData).slice(0, 5));
    console.log('Total entries in contributionGraphData:', Object.keys(contributionGraphData).length);
    
    // Debug: Check what dates are in the data
    const sampleDates = Object.keys(contributionGraphData).slice(0, 10);
    console.log('Sample dates in data:', sampleDates);
    
    // Initialize pending dates to match current selection
    pendingSelectedDates = new Set(selectedDates);
    
    renderContributionGraph();
  } catch (error) {
    console.error('Error loading contribution graph data:', error);
    graphContainer.innerHTML = '<div class="graph-loading" style="color: #ff6b6b;">Failed to load activity data</div>';
  }
}

/**
 * Render the contribution graph
 */
function renderContributionGraph() {
  const graphContainer = document.getElementById('contribution-graph');
  if (!graphContainer || !contributionGraphData) return;
  
  // Calculate date range (last 12 months)
  const endDate = new Date();
  const startDate = new Date();
  startDate.setMonth(startDate.getMonth() - 12);
  startDate.setDate(1); // Start from beginning of month
  
  // Adjust to start on Sunday for calendar grid
  const dayOfWeek = startDate.getDay();
  if (dayOfWeek !== 0) {
    startDate.setDate(startDate.getDate() - dayOfWeek);
  }
  
  console.log('Graph date range:', formatDate(startDate), 'to', formatDate(endDate));
  console.log('contributionGraphData has', Object.keys(contributionGraphData).length, 'dates');
  
  // Calculate max count for color scaling
  const counts = Object.values(contributionGraphData);
  const maxCount = Math.max(...counts, 1);
  
  // Build the graph HTML
  const weeks = [];
  const months = [];
  let currentDate = new Date(startDate);
  let currentWeek = [];
  let lastMonth = -1;
  
  while (currentDate <= endDate) {
    const dateStr = formatDate(currentDate);
    const count = contributionGraphData[dateStr] || 0;
    const level = getActivityLevel(count, maxCount);
    
    // Debug: Log first few days with their counts AND what's in data
    if (weeks.length === 0 && currentWeek.length < 5) {
      console.log(`Date: ${dateStr}, Count: ${count}, In data: ${contributionGraphData[dateStr] !== undefined}, Value in data: ${contributionGraphData[dateStr]}`);
    }
    
    // Track month labels
    const month = currentDate.getMonth();
    if (month !== lastMonth && currentDate.getDate() <= 7) {
      months.push({
        name: currentDate.toLocaleDateString('en-US', { month: 'short' }),
        week: weeks.length
      });
      lastMonth = month;
    }
    
    // Create day cell with a copy of the date string to avoid reference issues
    currentWeek.push({
      date: String(dateStr),  // Explicitly convert to string
      count: count,
      level: level,
      dayName: currentDate.toLocaleDateString('en-US', { weekday: 'short' })
    });
    
    // Start new week on Saturday
    if (currentDate.getDay() === 6) {
      weeks.push(currentWeek);
      currentWeek = [];
    }
    
    currentDate.setDate(currentDate.getDate() + 1);
  }
  
  // Add remaining days
  if (currentWeek.length > 0) {
    // Pad the week with empty cells
    while (currentWeek.length < 7) {
      currentWeek.push({ empty: true });
    }
    weeks.push(currentWeek);
  }
  
  // Build HTML
  let html = '<div class="graph-content">';
  
  // Month labels
  html += '<div class="graph-months">';
  let lastWeekIndex = 0;
  for (const monthInfo of months) {
    const weekSpan = monthInfo.week - lastWeekIndex;
    const width = weekSpan * 14; // 12px + 2px gap
    if (width > 0) {
      html += `<div class="graph-month" style="min-width: ${width}px;">${monthInfo.name}</div>`;
    }
    lastWeekIndex = monthInfo.week;
  }
  html += '</div>';
  
  // Grid container
  html += '<div class="graph-grid-container" style="display: grid; grid-template-columns: auto 1fr; gap: 8px;">';
  
  // Day labels (Sun, Mon, etc.)
  html += '<div class="graph-days-labels">';
  const dayLabels = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
  for (let i = 0; i < 7; i++) {
    // Only show Mon, Wed, Fri to reduce clutter
    const label = (i === 1 || i === 3 || i === 5) ? dayLabels[i] : '';
    html += `<div class="graph-day-label">${label}</div>`;
  }
  html += '</div>';
  
  // Weeks grid
  html += '<div class="graph-weeks">';
  for (const week of weeks) {
    html += '<div class="graph-week">';
    for (const day of week) {
      if (day.empty) {
        html += '<div class="graph-day" style="opacity: 0; pointer-events: none;"></div>';
      } else {
        const selectedClass = pendingSelectedDates.has(day.date) ? 'selected' : '';
        html += `<div class="graph-day ${selectedClass}" data-date="${day.date}" data-count="${day.count}" data-level="${day.level}"></div>`;
      }
    }
    html += '</div>';
  }
  html += '</div>'; // graph-weeks
  html += '</div>'; // graph-grid-container
  html += '</div>'; // graph-content
  
  graphContainer.innerHTML = html;
  
  // Add event listeners
  attachGraphEventListeners();
}

/**
 * Get activity level (0-4) based on count
 */
function getActivityLevel(count, maxCount) {
  if (count === 0) return 0;
  if (maxCount === 0) return 0;
  
  const percentage = count / maxCount;
  if (percentage >= 0.75) return 4;
  if (percentage >= 0.50) return 3;
  if (percentage >= 0.25) return 2;
  return 1;
}

/**
 * Format date as YYYY-MM-DD
 */
function formatDate(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Attach event listeners to graph days
 */
function attachGraphEventListeners() {
  const days = document.querySelectorAll('.graph-day[data-date]');
  const tooltip = document.getElementById('graph-tooltip');
  
  days.forEach(day => {
    // Hover - show tooltip
    day.addEventListener('mouseenter', (e) => {
      const date = day.getAttribute('data-date');
      const count = parseInt(day.getAttribute('data-count'));
      
      if (!tooltip) return;
      
      const tooltipDate = tooltip.querySelector('.tooltip-date');
      const tooltipCount = tooltip.querySelector('.tooltip-count');
      
      if (tooltipDate && tooltipCount) {
        tooltipDate.textContent = date;
        tooltipCount.textContent = `${count} ${count === 1 ? 'item' : 'items'}`;
        
        // Debug: Log what we're showing
        if (count > 0) {
          console.log(`Tooltip for ${date}: showing ${count} items (attribute value: "${day.getAttribute('data-count')}")`);
        }
        
        tooltip.style.display = 'block';
        updateTooltipPosition(e, tooltip);
      }
    });
    
    day.addEventListener('mousemove', (e) => {
      if (tooltip && tooltip.style.display === 'block') {
        updateTooltipPosition(e, tooltip);
      }
    });
    
    day.addEventListener('mouseleave', () => {
      if (tooltip) {
        tooltip.style.display = 'none';
      }
    });
    
    // Click - toggle date selection
    day.addEventListener('click', () => {
      const date = day.getAttribute('data-date');
      toggleDateSelection(date);
    });
  });
}

/**
 * Update tooltip position
 */
function updateTooltipPosition(event, tooltip) {
  const x = event.clientX;
  const y = event.clientY;
  
  tooltip.style.left = (x + 10) + 'px';
  tooltip.style.top = (y - 40) + 'px';
}

/**
 * Toggle date selection (add/remove from pending set)
 */
function toggleDateSelection(date) {
  if (pendingSelectedDates.has(date)) {
    pendingSelectedDates.delete(date);
  } else {
    pendingSelectedDates.add(date);
  }
  
  // Update visual selection immediately
  const day = document.querySelector(`.graph-day[data-date="${date}"]`);
  if (day) {
    if (pendingSelectedDates.has(date)) {
      day.classList.add('selected');
    } else {
      day.classList.remove('selected');
    }
  }
  
  console.log(`Toggled date: ${date}, pending selection: ${Array.from(pendingSelectedDates).join(', ')}`);
}

/**
 * Apply date filter (called when Apply button is clicked)
 */
function applyDateFilter() {
  // Copy pending selection to active selection
  selectedDates = new Set(pendingSelectedDates);
  
  // Update filter based on selected dates
  if (selectedDates.size === 0) {
    searchToolbarFilters.dateStart = null;
    searchToolbarFilters.dateEnd = null;
  } else {
    // Sort dates to find range
    const sortedDates = Array.from(selectedDates).sort();
    searchToolbarFilters.dateStart = sortedDates[0];
    searchToolbarFilters.dateEnd = sortedDates[sortedDates.length - 1];
  }
  
  // Update pill value and apply filter
  updateDatePillValue();
  applyCurrentFilters();
  
  // Save state
  saveSearchToolbarState();
  
  // Close the editor
  closePillEditor();
  
  console.log(`Applied date filter: ${selectedDates.size} date(s) selected`);
}

/**
 * Update the date pill value based on selection
 */
function updateDatePillValue() {
  const pillValue = document.getElementById('date-value');
  if (!pillValue) return;
  
  if (selectedDates.size === 0) {
    pillValue.textContent = 'All';
  } else if (selectedDates.size === 1) {
    pillValue.textContent = Array.from(selectedDates)[0];
  } else {
    pillValue.textContent = 'Multiple dates';
  }
}

/**
 * Select a date and filter media (DEPRECATED - keeping for compatibility)
 */
function selectDate(date) {
  // This function is deprecated but kept for backward compatibility
  pendingSelectedDates.clear();
  if (date) {
    pendingSelectedDates.add(date);
  }
  
  // Update UI
  const days = document.querySelectorAll('.graph-day[data-date]');
  days.forEach(day => {
    if (day.getAttribute('data-date') === date) {
      day.classList.add('selected');
    } else {
      day.classList.remove('selected');
    }
  });
  
  // Apply immediately (old behavior)
  applyDateFilter();
}

/**
 * Clear date filter
 */
function clearDateFilter() {
  selectedDates.clear();
  pendingSelectedDates.clear();
  searchToolbarFilters.dateStart = null;
  searchToolbarFilters.dateEnd = null;
  
  // Update UI
  const days = document.querySelectorAll('.graph-day[data-date]');
  days.forEach(day => {
    day.classList.remove('selected');
  });
  
  updateDatePillValue();
  applyCurrentFilters();
  saveSearchToolbarState();
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initContributionGraph);
} else {
  initContributionGraph();
}

// Add event listener for Apply button when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
  const dateApplyBtn = document.getElementById('date-apply');
  if (dateApplyBtn) {
    dateApplyBtn.addEventListener('click', applyDateFilter);
  }
});
