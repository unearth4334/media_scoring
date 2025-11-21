# Filter Toolbar Test Plan

## Overview
This document outlines comprehensive test cases for verifying the media browser filter toolbar functionality, including state retention, UI behavior, and filter application.

## Test Environments
- **Browser**: Chrome, Firefox, Safari
- **Viewport**: Desktop (>768px), Mobile (<768px)
- **Database Mode**: Enabled (buffered) and Disabled (client-side)

## Test Cases

### 1. State Retention Tests

#### 1.1 Browser Refresh with Default Filters
**Preconditions:** Application freshly loaded with default filter values
**Steps:**
1. Load application
2. Verify all pills show default values (File Type: All, Rating: All, Date: All, NSFW: All)
3. Verify all pills are grey (no special styling)
4. Refresh browser (F5)
5. Verify pills still show default values
6. Verify pills still grey

**Expected Result:** All pills remain grey with default "All" values

---

#### 1.2 Browser Refresh with Applied Filters
**Preconditions:** Application loaded
**Steps:**
1. Set File Type filter to "JPG, PNG" only (uncheck MP4)
2. Click "Apply" button
3. Set Rating filter to "★3+"
4. Click "Apply" button
5. Verify pills show: File Type (JPG, PNG), Rating (★3+)
6. Verify pills are CYAN (applied state)
7. Click Refresh button (with filter icon)
8. Wait for content to load
9. Refresh browser (F5)
10. Verify pills still show: File Type (JPG, PNG), Rating (★3+)
11. Verify pills are still CYAN

**Expected Result:** Applied filters persist after browser refresh and pills remain cyan

---

#### 1.3 Browser Refresh with Modified but Unapplied Filters
**Preconditions:** Application loaded with some applied filters
**Steps:**
1. Apply Rating filter to "★2+"
2. Click Refresh button
3. Verify pill is CYAN
4. Change Rating filter to "★4+" (don't click Apply or Refresh)
5. Verify pill is GREEN (modified state)
6. Refresh browser (F5)
7. Verify pill shows "★2+" (last applied value)
8. Verify pill is CYAN (not green)

**Expected Result:** Unapplied modifications are lost on refresh; last applied state is restored

---

### 2. Pill Color State Tests

#### 2.1 Default State (Grey)
**Preconditions:** Application freshly loaded
**Steps:**
1. Load application
2. Verify File Type pill shows "All" and is GREY
3. Verify Rating pill shows "All" and is GREY
4. Verify Date pill shows "All" and is GREY
5. Verify NSFW pill shows "All" and is GREY

**Expected Result:** All pills with default values are grey (no border color)

---

#### 2.2 Applied State (Cyan)
**Preconditions:** Application loaded
**Steps:**
1. Set File Type to "JPG" only
2. Click "Apply" button
3. Click Refresh button
4. Verify File Type pill shows "JPG" and is CYAN (cyan border, cyan text)
5. Verify other pills remain GREY

**Expected Result:** Applied non-default filter is cyan, defaults remain grey

---

#### 2.3 Modified State (Green)
**Preconditions:** Application loaded
**Steps:**
1. Open Rating filter editor
2. Select "★3+"
3. Don't click Apply yet
4. Close editor (click outside or press ESC)
5. Verify Rating pill shows "★3+" and is GREEN (green border, green text)
6. Verify "Filters changed - Click to refresh" indicator is visible

**Expected Result:** Modified but unapplied filter is green

---

#### 2.4 Transition from Cyan to Green
**Preconditions:** Application with applied filters
**Steps:**
1. Apply Rating "★2+", click Refresh
2. Verify pill is CYAN
3. Open Rating editor, change to "★4+"
4. Close editor without applying
5. Verify pill is GREEN
6. Click Refresh button
7. Verify pill is now CYAN

**Expected Result:** Pill transitions from cyan→green→cyan correctly

---

#### 2.5 Transition from Green to Grey
**Preconditions:** Application with modified filter
**Steps:**
1. Set Rating to "★3+" (don't apply)
2. Verify pill is GREEN
3. Open Rating editor, select "All"
4. Click "Apply" button
5. Click Refresh button
6. Verify pill is GREY

**Expected Result:** Applying default value changes pill from green to grey

---

### 3. Individual Filter Tests

#### 3.1 File Type Filter
**Test Cases:**
- Apply filter: JPG only → verify only JPG files shown
- Apply filter: PNG only → verify only PNG files shown
- Apply filter: MP4 only → verify only MP4 files shown
- Apply filter: JPG + PNG → verify JPG and PNG shown, no MP4
- Apply filter: None selected → verify empty result set or all files
- Apply filter: All selected → verify all file types shown

---

#### 3.2 Rating Filter
**Test Cases:**
- Apply filter: Rejected → verify only score=-1 files shown
- Apply filter: Unrated → verify only score=0 files shown
- Apply filter: Unrated+ → verify score>=0 files shown
- Apply filter: ★1+ → verify score>=1 files shown
- Apply filter: ★2+ → verify score>=2 files shown
- Apply filter: ★3+ → verify score>=3 files shown
- Apply filter: ★4+ → verify score>=4 files shown
- Apply filter: ★5 → verify only score=5 files shown
- Apply filter: All → verify all files shown regardless of score

---

#### 3.3 Creation Date Filter
**Test Cases:**
- Apply filter: Select single date → verify only files from that date
- Apply filter: Select date range (week) → verify files within range
- Apply filter: Select date range (month) → verify files within range
- Clear filter → verify all dates shown
- Apply filter with no files on date → verify empty result

---

#### 3.4 NSFW Filter
**Test Cases:**
- Apply filter: All → verify all files shown (SFW + NSFW)
- Apply filter: SFW Only → verify only non-NSFW files shown
- Apply filter: NSFW Only → verify only NSFW-flagged files shown

---

### 4. Filter Intersection Tests

#### 4.1 File Type + Rating
**Steps:**
1. Apply File Type: JPG only
2. Apply Rating: ★3+
3. Click Refresh
4. Verify only JPG files with score>=3 shown

---

#### 4.2 File Type + Date
**Steps:**
1. Apply File Type: PNG only
2. Apply Date: Single day
3. Click Refresh
4. Verify only PNG files from that specific date shown

---

#### 4.3 Rating + Date
**Steps:**
1. Apply Rating: ★4+
2. Apply Date: Last week
3. Click Refresh
4. Verify only files with score>=4 from last week shown

---

#### 4.4 File Type + Rating + Date
**Steps:**
1. Apply File Type: JPG, PNG
2. Apply Rating: ★2+
3. Apply Date: Last month
4. Click Refresh
5. Verify only JPG/PNG files with score>=2 from last month shown

---

#### 4.5 All Filters Combined
**Steps:**
1. Apply File Type: JPG
2. Apply Rating: ★3+
3. Apply Date: Single day
4. Apply NSFW: SFW Only
5. Click Refresh
6. Verify only SFW JPG files with score>=3 from that date shown

---

### 5. Edge Cases

#### 5.1 Empty Result Sets
**Steps:**
1. Apply filters that result in no matching files
2. Verify empty state is shown
3. Verify no errors in console
4. Clear filters
5. Verify files reappear

---

#### 5.2 Rapid Filter Changes
**Steps:**
1. Rapidly change multiple filters
2. Click Refresh before all UI updates complete
3. Verify correct filters are applied
4. Verify no race conditions

---

#### 5.3 Filter with Sort
**Steps:**
1. Apply Rating: ★3+
2. Set Sort: Rating (Descending)
3. Click Refresh
4. Verify files are filtered AND sorted correctly

---

### 6. Non-Buffer Mode Tests

#### 6.1 Filters Without Database
**Preconditions:** Database disabled
**Steps:**
1. Apply File Type filter
2. Apply Rating filter
3. Verify filters work client-side
4. Verify pill colors still work correctly

---

### 7. Mobile-Specific Tests

#### 7.1 Touch Targets
**Steps:**
1. Open on mobile device (<768px)
2. Verify pills are at least 44px tall (Apple guideline)
3. Verify pills can be tapped easily
4. Verify editor popups work correctly

---

#### 7.2 Mobile Editor Behavior
**Steps:**
1. Open filter editor on mobile
2. Verify editor appears correctly
3. Apply filter
4. Verify pill updates correctly

---

## Manual Testing Checklist

Before marking Issue #3 as complete, verify:

- [ ] All individual filter types work correctly
- [ ] All filter combinations work correctly  
- [ ] Browser refresh retains applied filters
- [ ] Pill colors accurately reflect state (grey/cyan/green)
- [ ] Modified filters show green until refresh
- [ ] Applied filters show cyan
- [ ] Default filters show grey
- [ ] No console errors during filter operations
- [ ] Sort order works with filters
- [ ] Empty result sets handled gracefully
- [ ] Mobile view works correctly

## Automated Test Creation

For automated testing, consider adding:
- Unit tests for `isValueEqual()` function
- Unit tests for filter value comparison logic
- Integration tests for filter API endpoints
- E2E tests using Playwright/Selenium for UI interactions

## Known Limitations

1. Client-side filtering (non-buffer mode) may not support all filter combinations
2. Date filter relies on contribution graph data loading
3. File type filter limited to jpg, png, mp4 by default

## References

- Related Code Files:
  - `app/static/js/search-toolbar.js` - Filter UI logic
  - `app/static/js/app.js` - Buffer integration
  - `app/routers/search.py` - Filter API endpoints
  - `app/static/themes/*.css` - Pill styling
