# Quick Performance Testing Guide

## 🚀 Quick Start (2 minutes)

### On Your Mobile Device
1. Open http://10.0.78.66:7862 in your mobile browser
2. Wait for page to load completely
3. Open browser console:
   - **iOS Safari:** Connect device to Mac → Safari > Develop > [Your Device]
   - **Chrome Android:** Enable USB debugging → chrome://inspect on desktop
   - **Samsung Internet:** Use remote debugging via Chrome DevTools
4. Run this command in console:
   ```javascript
   perfTest()
   ```
5. Wait 10 seconds for test to complete
6. Take screenshot of results or copy output

## 📊 What the Test Measures

The `perfTest()` command automatically checks:
- ✅ Device RAM (2GB = low-end, 4GB = mid-range, 6GB+ = high-end)
- ✅ CPU cores (2 = low-end, 4 = mid-range, 6+ = high-end)
- ✅ Memory usage percentage (>80% = critical)
- ✅ Number of DOM elements (>200 = too many)
- ✅ Scroll FPS (target: 60 FPS)
- ✅ Network speed (4G, 3G, etc.)
- ✅ Operation timings (API fetch, rendering, filtering)

## 🎯 Quick Commands

Run these in browser console:

```javascript
// Full diagnostic test (10 seconds)
perfTest()

// Quick checks (instant)
perfMemory()  // Check RAM usage
perfDOM()     // Count DOM elements
perfFPS()     // Measure framerate (2 seconds)
perfReport()  // Generate report with recommendations
```

## 🔍 Understanding Results

### Good Performance ✅
```
[PERF] Device tier: high
[PERF] Memory: 35.2% used
[PERF] DOM: 100 sidebar items
[PERF] FPS: 60
[PERF] api-fetch: 234ms
[PERF] render-sidebar: 145ms
[PERF] Health: good
```
**Action:** None needed!

### Fair Performance ⚠️
```
[PERF] Device tier: mid
[PERF] Memory: 68.5% used
[PERF] DOM: 100 sidebar items
[PERF] FPS: 48
[PERF] api-fetch: 456ms
[PERF] render-sidebar: 289ms
[PERF] Health: fair
[PERF] Recommendations:
  - Reduce page size to 50 items
  - Consider disabling thumbnails
```
**Action:** Follow recommendations in console output

### Poor Performance ❌
```
[PERF] Device tier: low
[PERF] Memory: 87.3% used (HIGH!)
[PERF] DOM: 100 sidebar items
[PERF] FPS: 28 (LOW!)
[PERF] api-fetch: 1234ms (SLOW!)
[PERF] render-sidebar: 678ms (SLOW!)
[PERF] Health: poor
[PERF] Issues:
  - High memory usage: 87.3%
  - Low FPS: 28 fps
  - 3 slow operations detected
[PERF] Recommendations:
  - Reduce page size to 25 items
  - Disable thumbnails on mobile
  - Implement virtual scrolling
```
**Action:** Apply immediate fixes below

## 🛠️ Immediate Fixes for Poor Performance

### Fix 1: Reduce Page Size
Open browser console and run:
```javascript
pageSize = 25;  // Reduce from 100 to 25
currentPage = 1;
loadVideos(1, false);
```
**Result:** 75% fewer DOM elements, faster rendering

### Fix 2: Disable Thumbnails
```javascript
showThumbnails = false;
renderSidebar();
```
**Result:** No image loading, faster scroll

### Fix 3: Clear Memory
```javascript
// Refresh page to clear memory
location.reload();
```

### Fix 4: Check Network Speed
```javascript
window.perfDiag.metrics.device.connection
// If effectiveType is '3g' or '2g', network is the bottleneck
```

## 📱 Device-Specific Recommendations

### iPhone/iPad (iOS Safari)
**If slow:**
1. Close other browser tabs
2. Disable Safari extensions
3. Ensure iOS is updated
4. Try Safari private mode

**Typical performance:**
- iPhone 12+: Good (60 FPS)
- iPhone 8-11: Fair (45-55 FPS)
- iPhone 7 or older: Poor (30-45 FPS)

### Android (Chrome/Samsung Internet)
**If slow:**
1. Disable battery saver mode
2. Close background apps
3. Clear browser cache: Settings > Apps > Chrome > Storage > Clear cache
4. Reduce screen resolution if device allows

**Typical performance:**
- Flagship (S21+, Pixel 6+): Good (55-60 FPS)
- Mid-range (A52, Pixel 4a): Fair (45-55 FPS)
- Budget (< $300): Poor (30-45 FPS)

## 🐛 Common Issues & Solutions

### Issue: "perfTest is not defined"
**Cause:** Performance diagnostics script not loaded  
**Solution:**
```javascript
// Check if script is loaded
console.log(typeof window.perfDiag);
// Should print 'object', not 'undefined'

// If undefined, reload page
location.reload();
```

### Issue: Memory usage keeps climbing
**Cause:** Memory leak or too many images loaded  
**Solution:**
```javascript
// Check memory trend
perfMemory();  // Run 3 times, 5 seconds apart
// If percentUsed increases each time, leak suspected

// Clear and reload
location.reload();
```

### Issue: Scroll is very janky (< 30 FPS)
**Cause:** Too many DOM elements or heavy CSS  
**Solution:**
```javascript
// Check DOM complexity
perfDOM();
// If sidebarItems > 200, reduce page size

pageSize = 25;
loadVideos(1, false);
```

### Issue: Initial load takes > 10 seconds
**Cause:** Slow network or server issue  
**Solution:**
```javascript
// Check network speed
window.perfDiag.metrics.device.connection.effectiveType;
// If '3g' or '2g', network is slow

// Check API timing
// Look for: [PERF] api-fetch: XXXXms
// If > 2000ms, server or network issue
```

## 📋 Sharing Results

### Copy Full Report
```javascript
// Run test and copy to clipboard
perfTest().then(report => {
  navigator.clipboard.writeText(JSON.stringify(report, null, 2));
  console.log('✅ Report copied to clipboard! Paste into GitHub issue.');
});
```

### Quick Summary
Share these key values:
1. **Device:** [iPhone 12 / Galaxy S21 / etc.]
2. **Device Tier:** [From perfTest output: low/mid/high]
3. **Memory Used:** [From perfTest output: X%]
4. **FPS:** [From perfTest output: X fps]
5. **Load Time:** [Seconds from page load to fully visible]
6. **Health Status:** [From perfTest output: good/fair/poor]

## 🔬 Advanced Testing

### Test During Real Usage
```javascript
// Monitor performance while using app
setInterval(() => {
  const mem = perfMemory();
  const dom = perfDOM();
  console.log(`Memory: ${mem.percentUsed}%, DOM: ${dom.sidebarItems} items`);
}, 10000);  // Every 10 seconds
```

### Compare Before/After Changes
```javascript
// Before optimization
const before = await perfTest();
console.log('BEFORE:', before.summary);

// Apply fix (e.g., reduce page size)
pageSize = 50;
loadVideos(1, false);

// Wait 5 seconds, then test again
setTimeout(async () => {
  const after = await perfTest();
  console.log('AFTER:', after.summary);
  
  // Compare
  console.log('FPS improvement:', after.fps - before.fps);
}, 5000);
```

### Test Network Impact
```javascript
// Test with different page sizes
async function testPageSizes() {
  const results = {};
  
  for (const size of [25, 50, 100]) {
    console.log(`Testing with pageSize=${size}`);
    pageSize = size;
    
    window.perfDiag.startTimer(`load-${size}`);
    await loadVideos(1, false);
    const duration = window.perfDiag.endTimer(`load-${size}`);
    
    results[size] = duration;
    await new Promise(r => setTimeout(r, 2000));  // Wait 2s between tests
  }
  
  console.log('Results:', results);
  return results;
}

testPageSizes();
```

## 📖 Full Documentation

For comprehensive testing procedures, see:
`docs/MOBILE_PERFORMANCE_TESTING.md`

For optimization implementation details, see:
`docs/PERFORMANCE_OPTIMIZATION_PLAN.md`

## 💡 Pro Tips

1. **Test on WiFi first:** Eliminates network as variable
2. **Close other apps:** Frees up RAM for testing
3. **Test in private/incognito mode:** Disables extensions that could interfere
4. **Test at different times:** Server load may vary
5. **Compare with desktop:** Helps isolate client-side vs server-side issues

## 🎬 Next Steps Based on Results

### If Health = Good
✅ No action needed  
→ Continue using app normally

### If Health = Fair
⚠️ Minor tweaks recommended  
→ Apply Fix 1 (reduce page size)  
→ Consider disabling thumbnails on mobile

### If Health = Poor
❌ Immediate action required  
→ Apply Fix 1 + Fix 2 + Fix 3  
→ Report results to development team  
→ Consider using desktop until mobile is optimized

## 🆘 Getting Help

If performance issues persist after trying fixes:

1. Run `perfTest()` and save output
2. Take screenshots of console warnings
3. Note your device model and browser
4. Create GitHub issue with template from MOBILE_PERFORMANCE_TESTING.md
5. Include all diagnostic output

**The diagnostics tool automatically identifies the root cause** - look for:
- `[PERF] HIGH MEMORY USAGE` → Memory constrained
- `[PERF] LOW FPS` → Rendering bottleneck
- `[PERF] Slow operation` → Specific function is slow
- `[PERF] Long task detected` → JavaScript blocking UI
