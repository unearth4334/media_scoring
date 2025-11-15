# Mobile Performance Testing Guide

## Overview
This guide provides comprehensive testing procedures to diagnose and resolve mobile performance issues in the Media Scoring application. The performance diagnostics tool automatically tracks key metrics to identify bottlenecks.

## Quick Start - Running Tests

### Desktop Browser (for baseline)
1. Open http://10.0.78.66:7862 in Chrome DevTools
2. Open Console (F12)
3. Run: `perfTest()`
4. Wait 10 seconds for complete test
5. Review output and save results

### Mobile Device Testing
1. Connect mobile device to same network
2. Open http://10.0.78.66:7862 in mobile browser
3. Enable "Request Desktop Site" to access console
4. Run: `perfTest()`
5. Compare results with desktop baseline

## Performance Test Commands

### Full Diagnostic Test
```javascript
// Comprehensive 10-second test measuring:
// - Device capabilities (RAM, CPU cores, screen resolution)
// - Memory usage (before/after)
// - DOM complexity (element count, event listeners)
// - Scroll performance (FPS during scroll)
// - Network connection (4G, 3G, etc.)
// - Operation timings (API fetch, render, filter)
perfTest()
```

**Expected Output:**
```
[PERF] ===== STARTING FULL PERFORMANCE TEST =====
[PERF] Step 1: Measure initial memory
[PERF] Memory: {usedJSHeapSize: 45 MB, totalJSHeapSize: 67 MB, ...}
[PERF] Step 2: Measure DOM complexity
[PERF] DOM Complexity: {sidebarItems: 100, totalElements: 1247, ...}
[PERF] Step 3: Test scroll performance
[PERF] Scroll performance: 58.3 FPS
[PERF] Step 4: Measure FPS (2 second test)
[PERF] FPS: 60 (120 frames in 2000ms)
[PERF] Step 5: Measure memory after test
[PERF] Step 6: Generate report
[PERF] ===== TEST COMPLETE =====
[PERF] Summary: {deviceTier: 'high', issues: [], recommendations: [], health: 'good'}
```

### Individual Test Commands
```javascript
// Check device info and capabilities
window.perfDiag.metrics.device

// Measure current memory usage (Chrome only)
perfMemory()
// Output: {usedJSHeapSize: 45 MB, totalJSHeapSize: 67 MB, percentUsed: '32.1%'}

// Measure DOM complexity
perfDOM()
// Output: {sidebarItems: 100, totalElements: 1247, images: 102, videos: 1}

// Measure FPS over 2 seconds
perfFPS()
// Output: 60 FPS

// Generate full report
perfReport()
```

## Automatic Operation Tracking

The performance tool automatically tracks these operations:

### API Fetch (`api-fetch`)
**What it measures:** Time to fetch media files from server  
**Threshold:** 1000ms (1 second)  
**Logged when:** Every `loadVideos()` call  
**Metadata tracked:**
- `page`: Current page number
- `itemsLoaded`: Number of items in response
- `totalItems`: Total items in database
- `paginated`: true/false

**Example output:**
```
[PERF] api-fetch: 234.56ms
```

**Warning triggers:**
```
[PERF] Slow operation: api-fetch took 1523.45ms (threshold: 1000ms)
```

### Sidebar Rendering (`render-sidebar`)
**What it measures:** Time to build and inject HTML for sidebar items  
**Threshold:** 500ms  
**Logged when:** Every `renderSidebar()` call  
**Metadata tracked:**
- `totalItems`: Total videos array length
- `filteredItems`: Filtered videos count
- `thumbnailsEnabled`: Are thumbnails shown

**Example output:**
```
[PERF] render-sidebar: 145.23ms
```

**Performance indicators:**
- < 100ms: Excellent
- 100-300ms: Good
- 300-500ms: Fair (consider optimization)
- > 500ms: Poor (needs optimization)

### Filter Application (`apply-filter`)
**What it measures:** Time to filter videos array and update UI  
**Threshold:** 200ms  
**Logged when:** Every `applyFilter()` call  
**Metadata tracked:**
- `filterType`: 'none', 'rejected', 'unrated', or numeric score
- `resultCount`: Number of items after filter
- `totalCount`: Total items before filter

**Example output:**
```
[PERF] apply-filter: 12.34ms
```

### Long Tasks (automatic detection)
**What it measures:** JavaScript operations blocking main thread > 50ms  
**Threshold:** 50ms (browser standard)  
**Logged when:** Automatically by browser Performance Observer  
**Impact:** Causes UI freezing and poor responsiveness

**Example output:**
```
[PERF] Long task detected: 247.8ms
```

## Key Metrics to Investigate

### 1. Device Memory (RAM)
**Location:** `window.perfDiag.metrics.device.deviceMemory`  
**Values:**
- Low-end: ≤ 2 GB
- Mid-range: 3-4 GB
- High-end: ≥ 6 GB

**Impact on performance:**
- Low memory = frequent garbage collection
- Low memory = browser tab throttling
- Low memory = reduced cache size

**Recommendations for low memory:**
```javascript
// If deviceMemory <= 2 GB:
pageSize = 50;  // Reduce from 100
showThumbnails = false;  // Disable thumbnails
```

### 2. CPU Cores
**Location:** `window.perfDiag.metrics.device.hardwareConcurrency`  
**Values:**
- Low-end: 2 cores
- Mid-range: 4 cores
- High-end: 6+ cores

**Impact on performance:**
- Fewer cores = slower DOM operations
- Fewer cores = slower JavaScript execution
- Fewer cores = reduced parallel processing

### 3. Network Connection
**Location:** `window.perfDiag.metrics.device.connection`  
**Values:**
- `effectiveType`: '4g', '3g', '2g', 'slow-2g'
- `downlink`: Speed in Mbps
- `rtt`: Round-trip time in ms

**Impact on performance:**
- Slow connection = long API fetch times
- Slow connection = delayed thumbnail loads
- High RTT = perceived lag

**Recommendations for slow connection:**
```javascript
// If effectiveType === '3g' or '2g':
showThumbnails = false;
pageSize = 25;  // Smaller pages
```

### 4. DOM Complexity
**Location:** `perfDOM()`  
**Key metrics:**
- `sidebarItems`: Number of `.item` elements
- `totalElements`: Total DOM nodes
- `images`: Number of `<img>` tags

**Performance thresholds:**
- Excellent: < 100 sidebar items
- Good: 100-200 sidebar items
- Fair: 200-300 sidebar items
- Poor: > 300 sidebar items

**Why it matters:**
- More DOM nodes = slower rendering
- More DOM nodes = higher memory usage
- More event listeners = slower interaction

**Solution:** Virtual scrolling (Phase 2)

### 5. Memory Usage
**Location:** `perfMemory()`  
**Key metrics:**
- `usedJSHeapSize`: Current memory used (MB)
- `jsHeapSizeLimit`: Maximum memory available (MB)
- `percentUsed`: Percentage of limit

**Warning levels:**
- < 60%: Healthy
- 60-80%: Elevated (monitor)
- > 80%: Critical (may crash)

**Common causes of high memory:**
- Too many DOM nodes (100+ sidebar items)
- Large images not garbage collected
- Event listener leaks
- Large arrays (videos, filtered)

**Solutions:**
```javascript
// Clear unused data
videos = videos.slice(0, 100);  // Keep only current page
filtered = filtered.slice(0, 100);

// Force garbage collection (Chrome DevTools only)
// In DevTools Performance tab, click trash icon
```

### 6. FPS (Frames Per Second)
**Location:** `perfFPS()`  
**Target:** 60 FPS  
**Thresholds:**
- Excellent: 55-60 FPS
- Good: 45-55 FPS
- Fair: 30-45 FPS
- Poor: < 30 FPS

**What causes low FPS:**
- Layout thrashing (frequent DOM reads/writes)
- Heavy CSS animations
- Unoptimized images
- JavaScript blocking main thread

### 7. Scroll Performance
**Location:** Automatically tested in `perfTest()`  
**What it measures:** FPS while scrolling sidebar  
**Target:** 60 FPS

**Common scroll issues:**
- Rendering all thumbnails at once
- Heavy box shadows / filters
- Synchronous JavaScript during scroll
- Layout recalculations

## Common Performance Issues & Solutions

### Issue 1: High Initial Load Time (> 3 seconds)
**Symptoms:**
- `api-fetch` > 1000ms
- `render-sidebar` > 500ms
- Loading spinner visible for 3+ seconds

**Diagnosis:**
```javascript
// Run test and check these metrics
perfTest()
// Look for:
// - api-fetch duration
// - render-sidebar duration
// - DOM complexity (sidebarItems count)
```

**Root causes:**
1. **Server slow** (api-fetch > 1000ms)
   - Check network tab in DevTools
   - Verify database connection
   - Check server logs

2. **Rendering slow** (render-sidebar > 500ms)
   - Check DOM complexity: `perfDOM()`
   - Reduce page size if sidebarItems > 200
   - Disable thumbnails on mobile

3. **Memory constrained** (deviceMemory <= 2 GB)
   - Reduce page size to 50
   - Disable thumbnails
   - Clear unused data more aggressively

**Solutions:**
```javascript
// In app.js, adjust based on device tier
if (window.perfDiag.metrics.device.tier === 'low') {
  pageSize = 50;
  showThumbnails = false;
}

// Or manually reduce page size
pageSize = 50;
loadVideos(1, false);
```

### Issue 2: Janky Scrolling (< 30 FPS)
**Symptoms:**
- Scroll feels stuttery
- `perfFPS()` returns < 30
- Console shows layout shift warnings

**Diagnosis:**
```javascript
// Check FPS during scroll
window.perfDiag.testScrollPerformance()
// Should return > 50 FPS

// Check for long tasks
// These will appear automatically in console if detected
```

**Root causes:**
1. **Too many DOM nodes**
   - Check: `perfDOM().sidebarItems > 200`
   - Solution: Reduce page size or implement virtual scrolling

2. **Heavy CSS effects**
   - Check: Thumbnails with filters/shadows
   - Solution: Disable or simplify CSS on mobile

3. **Thumbnail loading during scroll**
   - Check: Network tab shows many thumbnail requests
   - Solution: Implement better lazy loading

**Solutions:**
```javascript
// Disable thumbnails on mobile
if (window.perfDiag.metrics.device.isMobile) {
  showThumbnails = false;
  renderSidebar();
}

// Reduce page size
pageSize = 50;
currentPage = 1;
loadVideos(1, false);

// Simplify CSS (add to style.css)
@media (max-width: 768px) {
  .thumbnail img {
    filter: none !important;
    box-shadow: none !important;
  }
}
```

### Issue 3: High Memory Usage (> 80%)
**Symptoms:**
- `perfMemory()` shows > 80% used
- Browser tab crashes
- "Page Unresponsive" warnings

**Diagnosis:**
```javascript
// Monitor memory over time
setInterval(() => {
  const mem = perfMemory();
  if (mem.percentUsed > 80) {
    console.error('HIGH MEMORY USAGE:', mem);
  }
}, 5000);
```

**Root causes:**
1. **Too many images loaded**
   - Check: `perfDOM().images > 100`
   - Solution: More aggressive lazy loading

2. **Large arrays not cleared**
   - Check: `videos.length` and `filtered.length`
   - Solution: Clear old pages when loading new ones

3. **Memory leaks**
   - Check: Memory steadily increasing over time
   - Solution: Remove event listeners properly

**Solutions:**
```javascript
// Clear old pages when loading new ones
if (append && videos.length > pageSize * 3) {
  // Keep only last 3 pages
  videos = videos.slice(-pageSize * 3);
}

// Remove unused images
document.querySelectorAll('img').forEach(img => {
  if (!img.complete || img.naturalHeight === 0) {
    img.remove();
  }
});

// Force garbage collection (Chrome DevTools)
// Performance tab > Collect garbage icon
```

### Issue 4: Slow Filter Application (> 200ms)
**Symptoms:**
- `apply-filter` > 200ms in console
- UI freezes when changing filters
- Rating buttons feel unresponsive

**Diagnosis:**
```javascript
// Check filter performance
window.perfDiag.startTimer('apply-filter');
applyFilter();
window.perfDiag.endTimer('apply-filter');
```

**Root causes:**
1. **Large array filtering** (videos.length > 1000)
2. **Synchronous DOM updates**
3. **Multiple filter/render cycles**

**Solutions:**
```javascript
// Use pagination to reduce array size
// Already implemented in Phase 1

// Debounce filter changes
let filterTimeout;
function debouncedFilter() {
  clearTimeout(filterTimeout);
  filterTimeout = setTimeout(() => {
    applyFilter();
    renderSidebar();
  }, 150);
}

// Use Web Workers for heavy filtering (future optimization)
```

## Mobile-Specific Testing

### iOS Safari
**Known issues:**
- No `performance.memory` API
- Aggressive memory management
- Different rendering engine (WebKit)

**Testing steps:**
1. Open Safari on iPhone/iPad
2. Enable Web Inspector: Settings > Safari > Advanced > Web Inspector
3. Connect to Mac and open Safari > Develop > [Your Device]
4. Run `perfTest()` in console

**Expected differences from desktop:**
- Lower `hardwareConcurrency` (2-6 cores)
- Lower `deviceMemory` (often not available)
- Lower FPS on older devices (30-45 FPS)

### Chrome Android
**Known issues:**
- Memory pressure on < 4GB RAM devices
- Throttling when battery saver enabled
- Background tab restrictions

**Testing steps:**
1. Open Chrome on Android device
2. Navigate to http://10.0.78.66:7862
3. Three-dot menu > Request desktop site
4. Open DevTools via chrome://inspect on desktop
5. Run `perfTest()` in remote console

**Expected differences from desktop:**
- Lower FPS (30-50 FPS typical)
- Higher memory usage percentage
- Slower render times (2-3x desktop)

### Samsung Internet
**Known issues:**
- Custom user agent
- Different performance characteristics
- Limited DevTools support

**Testing steps:**
1. Install Samsung Internet browser
2. Navigate to http://10.0.78.66:7862
3. Use USB debugging with Chrome DevTools
4. Run `perfTest()` in console

## Optimization Recommendations by Device Tier

### Low-End Devices (≤ 2GB RAM, ≤ 2 cores)
**Target:** 2-5 second initial load, 30+ FPS scroll

**Recommended settings:**
```javascript
pageSize = 25;
showThumbnails = false;
thumbnailHeight = 32;  // If enabled
// Disable animations
document.body.classList.add('reduce-motion');
```

**Expected results:**
- `api-fetch`: 300-800ms
- `render-sidebar`: 100-300ms
- `apply-filter`: 20-100ms
- FPS: 30-45

### Mid-Range Devices (3-4GB RAM, 4 cores)
**Target:** 1-3 second initial load, 45+ FPS scroll

**Recommended settings:**
```javascript
pageSize = 50;
showThumbnails = true;
thumbnailHeight = 48;
```

**Expected results:**
- `api-fetch`: 200-600ms
- `render-sidebar`: 80-200ms
- `apply-filter`: 10-50ms
- FPS: 45-55

### High-End Devices (≥ 6GB RAM, ≥ 6 cores)
**Target:** < 1 second initial load, 60 FPS scroll

**Recommended settings:**
```javascript
pageSize = 100;
showThumbnails = true;
thumbnailHeight = 64;
// Enable all features
```

**Expected results:**
- `api-fetch`: 100-400ms
- `render-sidebar`: 50-150ms
- `apply-filter`: 5-30ms
- FPS: 55-60

## Collecting Test Results

### Automated Report Export
```javascript
// Run full test and save results
async function collectTestData() {
  const report = await perfTest();
  
  // Copy to clipboard
  navigator.clipboard.writeText(JSON.stringify(report, null, 2));
  
  console.log('Test results copied to clipboard!');
  console.log('Paste into GitHub issue or Discord message');
  
  return report;
}

collectTestData();
```

### Manual Data Collection
For devices without DevTools access:

1. Run `perfTest()`
2. Take screenshots of console output
3. Note these key values:
   - Device tier (low/mid/high)
   - Memory percent used
   - FPS result
   - DOM complexity (sidebar items)
   - api-fetch duration
   - render-sidebar duration

### Reporting Template
```markdown
## Performance Test Results

**Device:** [iPhone 12 / Samsung Galaxy S21 / etc.]
**Browser:** [Safari 17 / Chrome Android 120 / etc.]
**Network:** [WiFi 4G / Mobile 3G / etc.]

**Device Metrics:**
- Memory: [2 GB / 4 GB / 6 GB]
- CPU Cores: [2 / 4 / 6]
- Screen: [390x844 / 1080x2400]
- Device Tier: [low / mid / high]

**Performance Results:**
- Initial Load Time: [X seconds]
- API Fetch: [X ms]
- Render Sidebar: [X ms]
- Apply Filter: [X ms]
- FPS: [X fps]
- Memory Used: [X%]
- DOM Items: [X sidebar items]

**Issues Identified:**
- [List any warnings or slow operations]

**Health Status:** [good / fair / poor]
```

## Next Steps After Testing

### If Performance is GOOD (< 2s load, 60 FPS)
✅ Current implementation is sufficient  
→ Proceed with feature development

### If Performance is FAIR (2-5s load, 45-60 FPS)
⚠️ Minor optimizations recommended  
→ Adjust page size based on device tier  
→ Disable thumbnails on mobile  
→ Implement Phase 2 (virtual scrolling)

### If Performance is POOR (> 5s load, < 45 FPS)
❌ Major optimizations required  
→ Immediately reduce page size to 25-50  
→ Disable all thumbnails  
→ Investigate server-side issues  
→ Implement Phase 2 (virtual scrolling)  
→ Consider Phase 3 (tile view optimization)

## Advanced Debugging

### Enable Verbose Logging
```javascript
// Enable detailed performance logging
window.perfDiag.logToConsole = true;

// Log all measurements
window.perfDiag.measurements.forEach(m => {
  console.log(`[${m.type}] ${m.duration}ms at ${new Date(m.timestamp).toISOString()}`);
});
```

### Monitor Real-Time Performance
```javascript
// Monitor performance every 5 seconds
setInterval(() => {
  const mem = perfMemory();
  const dom = perfDOM();
  console.log(`[MONITOR] Memory: ${mem.percentUsed}%, DOM Items: ${dom.sidebarItems}`);
}, 5000);
```

### Record Performance Timeline
```javascript
// Use Chrome DevTools Performance tab
// 1. Open DevTools > Performance
// 2. Click Record
// 3. Interact with app (scroll, filter, navigate)
// 4. Stop recording after 10 seconds
// 5. Analyze timeline for:
//    - Long tasks (yellow)
//    - Layout shifts (purple)
//    - Paint operations (green)
```

## Frequently Asked Questions

### Q: Why is my desktop fast but mobile slow?
**A:** Multiple factors:
1. **RAM:** Desktop has 16GB+, mobile has 2-4GB
2. **CPU:** Desktop has 8+ cores, mobile has 2-4 cores
3. **Network:** Desktop on gigabit ethernet, mobile on WiFi/cellular
4. **Browser:** Desktop browsers are more optimized
5. **Screen:** Mobile must render at higher pixel ratios (2x-3x)

### Q: Which metric is most important?
**A:** Depends on the issue:
- **Slow initial load:** Check `api-fetch` and `render-sidebar`
- **Janky scrolling:** Check FPS and DOM complexity
- **Crashes:** Check memory usage percentage
- **Unresponsive UI:** Check for long tasks

### Q: Should I test on real devices or simulators?
**A:** Always test on real devices for accurate results:
- Simulators don't accurately represent memory pressure
- Simulators run on desktop CPU/RAM
- Network conditions differ significantly
- Browser optimizations differ

### Q: How often should I run performance tests?
**A:** Test after these changes:
- Adding/modifying features
- Changing page size or pagination
- Updating CSS styling
- Upgrading dependencies
- Before each production deployment

### Q: Can I automate these tests?
**A:** Yes, for CI/CD integration:
```javascript
// In automated test suite
const report = await window.perfTest();
if (report.summary.health === 'poor') {
  throw new Error('Performance regression detected');
}
```

## Support & Feedback

If you discover performance issues not covered in this guide:

1. Run `perfTest()` and collect results
2. Use the reporting template above
3. Create GitHub issue with test results
4. Include device/browser information
5. Attach screenshots of console output

For urgent performance issues:
- Reduce page size immediately: `pageSize = 25`
- Disable thumbnails: `showThumbnails = false`
- Contact development team with test results
