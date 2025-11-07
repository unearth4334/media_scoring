/**
 * Centralized SVG icon library for the Video & Image Scorer application
 * 
 * This file contains all SVG icon functions used throughout the app.
 * Icons are designed to work with CSS custom properties for theming.
 */

/**
 * Reject button icon - circular X
 * @param {boolean} selected - Whether the reject state is active
 * @returns {string} SVG markup
 */
function svgReject(selected) {
  const circleFill = selected ? "var(--reject-fill-selected)" : "var(--reject-fill-unselected)";
  const xColor = selected ? "var(--reject-x-selected)" : "var(--reject-x-unselected)";
  const r = 16, cx = 20, cy = 20;
  return `
<svg width="40" height="40" viewBox="0 0 40 40">
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="${circleFill}" stroke="var(--reject-stroke-color)" stroke-width="2" />
  <line x1="${cx-10}" y1="${cy-10}" x2="${cx+10}" y2="${cy+10}" stroke="${xColor}" stroke-width="4" stroke-linecap="round" />
  <line x1="${cx-10}" y1="${cy+10}" x2="${cx+10}" y2="${cy-10}" stroke="${xColor}" stroke-width="4" stroke-linecap="round" />
</svg>`;
}

/**
 * Star rating icon
 * @param {boolean} filled - Whether the star should be filled/selected
 * @returns {string} SVG markup
 */
function svgStar(filled) {
  const fill = filled ? "var(--star-fill-selected)" : "var(--star-fill-unselected)";
  return `
<svg width="40" height="40" viewBox="0 0 40 40">
  <polygon points="20,4 24,16 36,16 26,24 30,36 20,28 10,36 14,24 4,16 16,16"
    fill="${fill}" stroke="var(--star-stroke-color)" stroke-width="2"/>
</svg>`;
}

/**
 * Clear button icon - vertical pipe
 * @param {boolean} selected - Whether the clear state is active
 * @returns {string} SVG markup
 */
function svgClear(selected) {
  const lineColor = selected ? "var(--star-fill-selected)" : "var(--star-stroke-color)";
  return `
<svg width="20" height="40" viewBox="0 0 20 40">
  <line x1="10" y1="8" x2="10" y2="32" stroke="${lineColor}" stroke-width="6" stroke-linecap="round"/>
</svg>`;
}

/**
 * Maximize media icon - expand corners
 * @returns {string} SVG markup
 */
function svgMaximize() {
  return `
<svg width="24" height="24" viewBox="0 0 24 24" fill="none">
  <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;
}

/**
 * Minimize media icon - contract corners
 * @returns {string} SVG markup
 */
function svgMinimize() {
  return `
<svg width="24" height="24" viewBox="0 0 24 24" fill="none">
  <path d="M4 14h6m0 0v6m0-6l-7 7m17-11h-6m0 0V4m0 6l7-7" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;
}

/**
 * Thumbnail icon - list view with thumbnails and text (single icon for checkbox toggle)
 * Shows squares on the left (thumbnails) and horizontal lines on the right (text)
 * @returns {string} SVG markup
 */
function svgThumbnail() {
  return `
<svg width="16" height="16" viewBox="0 0 24 24" fill="none">
  <rect x="3" y="3" width="5" height="5" stroke="currentColor" stroke-width="2" fill="currentColor" opacity="0.3"/>
  <line x1="11" y1="4.5" x2="21" y2="4.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="11" y1="7.5" x2="18" y2="7.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
  <rect x="3" y="11" width="5" height="5" stroke="currentColor" stroke-width="2" fill="currentColor" opacity="0.3"/>
  <line x1="11" y1="12.5" x2="21" y2="12.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
  <line x1="11" y1="15.5" x2="18" y2="15.5" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
</svg>`;
}

/**
 * Download icon - downward arrow with line
 * @returns {string} SVG markup
 */
function svgDownload() {
  return `
<svg width="24" height="24" viewBox="0 0 24 24" fill="none">
  <path d="M12 3v12m0 0l-5-5m5 5l5-5M5 19h14" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;
}

/**
 * Export/ZIP folder icon
 * @returns {string} SVG markup
 */
function svgExport() {
  return `
<svg width="16" height="12" viewBox="0 0 24 24" fill="none" style="margin-right: 2px;">
  <path d="M16 22H8C6.9 22 6 21.1 6 20V4C6 2.9 6.9 2 8 2H14L18 6V20C18 21.1 17.1 22 16 22Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M14 2V6H18" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M10 12H14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M10 16H14" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
</svg>`;
}

/**
 * Directory up arrow icon
 * @returns {string} SVG markup
 */
function svgDirectoryUp() {
  return `
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M18 15l-6-6-6 6"/>
</svg>`;
}

/**
 * Folder/directory browse icon
 * @returns {string} SVG markup
 */
function svgDirectoryBrowse() {
  return `
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"/>
</svg>`;
}

/**
 * Triangle dropdown icon
 * @returns {string} SVG markup
 */
function svgDropdownTriangle() {
  return `
<svg width="12" height="8" viewBox="0 0 12 8" fill="white">
  <path d="M6 8L0 0h12z"/>
</svg>`;
}

/**
 * Refresh/reload icon
 * @returns {string} SVG markup
 */
function svgRefresh() {
  return `
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/>
  <path d="M21 3v5h-5"/>
  <path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/>
  <path d="M3 21v-5h5"/>
</svg>`;
}

/**
 * Clipboard/copy icon
 * @returns {string} SVG markup
 */
function svgClipboard() {
  return `
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
</svg>`;
}

/**
 * Close/X icon - simple X for closing panels
 * @returns {string} SVG markup
 */
function svgClose() {
  return `
<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <line x1="18" y1="6" x2="6" y2="18" stroke-linecap="round"/>
  <line x1="6" y1="6" x2="18" y2="18" stroke-linecap="round"/>
</svg>`;
}

/**
 * Hamburger menu icon - three horizontal lines
 * @returns {string} SVG markup
 */
function svgMenu() {
  return `
<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
  <line x1="3" y1="6" x2="21" y2="6" stroke-linecap="round"/>
  <line x1="3" y1="12" x2="21" y2="12" stroke-linecap="round"/>
  <line x1="3" y1="18" x2="21" y2="18" stroke-linecap="round"/>
</svg>`;
}

/**
 * Mobile reject icon - red X in red circle
 * @returns {string} SVG markup
 */
function svgMobileReject() {
  const r = 14, cx = 16, cy = 16;
  return `
<svg width="32" height="32" viewBox="0 0 32 32">
  <circle cx="${cx}" cy="${cy}" r="${r}" fill="#f44336" stroke="#f44336" stroke-width="2" />
  <line x1="${cx-7}" y1="${cy-7}" x2="${cx+7}" y2="${cy+7}" stroke="#ffffff" stroke-width="3" stroke-linecap="round" />
  <line x1="${cx-7}" y1="${cy+7}" x2="${cx+7}" y2="${cy-7}" stroke="#ffffff" stroke-width="3" stroke-linecap="round" />
</svg>`;
}

/**
 * Mobile star icon - empty star outline
 * @returns {string} SVG markup
 */
function svgMobileStarEmpty() {
  return `
<svg width="32" height="32" viewBox="0 0 32 32">
  <polygon points="16,3 19,12 28,12 21,18 24,28 16,22 8,28 11,18 4,12 13,12"
    fill="none" stroke="#00bcd4" stroke-width="2"/>
</svg>`;
}

/**
 * Mobile star icon - filled star with number
 * @param {number} score - The score number to display (1-5)
 * @returns {string} SVG markup
 */
function svgMobileStarFilled(score) {
  return `
<svg width="32" height="32" viewBox="0 0 32 32">
  <polygon points="16,3 19,12 28,12 21,18 24,28 16,22 8,28 11,18 4,12 13,12"
    fill="#00bcd4" stroke="#00bcd4" stroke-width="2"/>
  <text x="16" y="19" text-anchor="middle" font-size="14" font-weight="700" fill="rgba(24, 24, 24, 0.95)">${score}</text>
</svg>`;
}

/**
 * Magnifying glass icon for zoom functionality
 * @returns {string} SVG markup
 */
function svgMagnifyingGlass() {
  return `
<svg width="24" height="24" viewBox="0 0 24 24" fill="none">
  <circle cx="11" cy="11" r="6" stroke="currentColor" stroke-width="2"/>
  <path d="M15 15l5 5" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
  <path d="M11 8v6M8 11h6" stroke="currentColor" stroke-width="1.5" stroke-linecap="round"/>
</svg>`;
}

/**
 * Fit to pane icon (equals sign in a frame)
 * @returns {string} SVG markup
 */
function svgFitToPane() {
  return `
<svg width="24" height="24" viewBox="0 0 24 24" fill="none">
  <rect x="3" y="3" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" rx="2"/>
  <path d="M8 9h8M8 15h8" stroke="currentColor" stroke-width="2" stroke-linecap="round"/>
</svg>`;
}
