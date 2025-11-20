# Filter Toolbar Implementation Changes

## Summary
Modified the filter toolbar implementation so that filter scope is only modified by the refresh button. Apply, Clear, and other filter actions now only update the UI state without triggering a search/filter operation.

## Changes Made

### 1. search-toolbar.js
- **Sort field select** (line 368-374): Removed `applyCurrentFilters()` call, now only updates state and UI
- **Sort direction buttons** (line 377-397): Removed `applyCurrentFilters()` calls from both asc and desc buttons
- **NSFW filter buttons** (line 433-465): Removed `applyCurrentFilters()` calls from all three buttons (All, SFW Only, NSFW Only)
- **applySearchToolbarFilter()** (line 479-536): Removed `applyCurrentFilters()` call on line 531
- **clearFilter()** (line 538-597): Removed `applyCurrentFilters()` call on line 593

### 2. contribution-graph.js
- **applyDateFilter()** (line 325-351): Removed `applyCurrentFilters()` call on line 342
- **clearDateFilter()** (line 395-410): Removed `applyCurrentFilters()` call on line 408

### 3. app.js (No changes needed)
- Refresh button already properly calls `applyCurrentFilters()` (line 1640-1653)

## Behavior Changes

### Before
- Clicking Apply/Clear buttons immediately triggered filtering
- Changing sort options immediately triggered filtering  
- Changing NSFW filter immediately triggered filtering
- Selecting dates and clicking Apply immediately triggered filtering
- Each action caused a separate backend API call (for database mode) or client-side filtering

### After
- Clicking Apply/Clear buttons only updates the filter state and UI indicators
- Changing sort options only updates the filter state and UI indicators
- Changing NSFW filter only updates the filter state and UI indicators
- Selecting dates and clicking Apply only updates the filter state and UI indicators
- User can make multiple filter adjustments without triggering searches
- Only clicking the Refresh button triggers the actual filtering operation
- This reduces wasted backend API calls and improves performance when users make multiple filter adjustments

## Manual Testing Steps

1. **Start the application**
   ```bash
   python run.py --dir ./media --port 7862
   ```

2. **Test filter state updates without search**
   - Open http://127.0.0.1:7862 in browser
   - Click on File Type pill, change selection, click Apply
   - Verify: Pill value updates but sidebar content does NOT change
   - Click on Rating pill, change rating, click Apply
   - Verify: Pill value updates but sidebar content does NOT change
   - Click on Sort pill (if visible), change sort order
   - Verify: Pill value updates but sidebar content does NOT change

3. **Test refresh button triggers filtering**
   - After making multiple filter changes above
   - Click the Refresh button (circular arrow icon)
   - Verify: Sidebar content now updates to reflect all filter changes

4. **Test Clear buttons**
   - Make filter changes (File Type, Rating, etc.)
   - Click Clear button in each editor
   - Verify: Pill value resets but sidebar content does NOT change
   - Click Refresh button
   - Verify: Sidebar now shows all content (filters cleared)

5. **Test NSFW filter**
   - Click NSFW pill
   - Toggle between All/SFW Only/NSFW Only
   - Verify: Pill value updates but sidebar content does NOT change
   - Click Refresh button
   - Verify: Sidebar updates to show filtered content

6. **Test date filter (if contribution graph is loaded)**
   - Click Date pill
   - Select one or more dates in the contribution graph
   - Click Apply
   - Verify: Pill value updates but sidebar content does NOT change
   - Click Refresh button
   - Verify: Sidebar updates to show content from selected dates

## Benefits

1. **Reduced Backend Load**: Multiple filter changes no longer cause multiple API calls
2. **Better UX**: Users can experiment with filter combinations before committing
3. **Performance**: Especially important for large datasets where filtering is expensive
4. **Consistency**: All filters now behave the same way (update state, then refresh)

## Backward Compatibility

- All filter state is still persisted to cookies
- Filter restoration on page reload still works
- The refresh button behavior is unchanged
- No breaking changes to the API

## Notes

- The refresh button behavior is already correct and was not modified
- Filter state persistence (saveSearchToolbarState) is still called to remember user preferences
- UI updates (updatePillValues) are still called to show current filter state
- This is a pure frontend change with no backend modifications required
