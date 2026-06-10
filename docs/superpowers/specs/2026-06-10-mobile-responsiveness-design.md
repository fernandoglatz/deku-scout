# Mobile Responsiveness Design

**Date:** 2026-06-10  
**Status:** Approved  

## Overview

Make DekuScout's single-page UI work well on mobile devices. Three areas require targeted changes: the header (too many controls for one row), the search bar (fixed width), and the price history popup (hover-only, oversized).

All changes are scoped to a `≤ 640px` media query — the breakpoint already exists in the codebase.

---

## 1. Header — Hamburger Menu

**Problem:** The header currently contains logo, meta info, theme toggle, language select, user badge, settings button, and refresh button. On narrow screens these overflow.

**Solution:** On mobile, collapse all controls except the logo into a hamburger (`☰`) dropdown.

- Logo (`h1`) stays visible at all times on the left.
- All secondary elements hidden on mobile: `.theme-btn`, `.lang-select`, `.user-badge`, `#openModalBtn`, `#rf` (refresh form).
- A new `☰` button (`#mobileMenuBtn`) appears on the right of the header.
- Tapping `☰` toggles a `#mobileMenu` panel that renders immediately below the header (not overlaid) containing all hidden controls in a single-column vertical layout.
- Menu closes when:
  - `☰` is tapped again
  - User taps anywhere outside the header/menu
  - A button inside the menu is activated (refresh, settings)

**Structure of `#mobileMenu`:**
```
[ Language select         ]
[ 👤 user@email.com badge ]
[ ☀️ Theme  |  ⚙ Settings  |  ↺ Refresh ]
```

---

## 2. Search Bar — Full Width on Mobile

**Problem:** `.search-box` has a fixed `width: 260px`, which wastes space on narrow screens and can cause overflow on very small ones.

**Solution:** On mobile, set `.search-box { width: 100%; }`. The toolbar already uses `flex-wrap: wrap`, so the search box takes its own row and filter buttons wrap below it naturally.

---

## 3. Price History — Bottom Sheet on Mobile

**Problem:** The `#ph-popup` is triggered on `mouseenter`/`mouseleave` (hover-only) and is `380px` wide — wider than many phones. Touch devices never trigger it.

**Solution:** On touch devices, replace the hover popup with a bottom sheet:

- Detect touch capability: `'ontouchstart' in window` (evaluated once at init).
- On **desktop** (no touch): existing hover behavior unchanged.
- On **mobile** (touch): 
  - `mouseenter`/`mouseleave` listeners are not attached.
  - `touchstart` on a `[data-ph-slug]` cell opens `#ph-popup` in bottom-sheet mode.
  - Bottom sheet styles (applied via a `.bottom-sheet-mode` class on `#ph-popup`):
    - `position: fixed; bottom: 0; left: 0; right: 0; width: 100%;`
    - `border-radius: 12px 12px 0 0;`
    - `max-height: 60vh; overflow-y: auto;`
    - A drag handle bar (`div.bs-handle`) prepended inside the popup.
  - Dismiss by: tapping the backdrop, tapping outside, or pressing Escape.
  - A semi-transparent `#ph-backdrop` div (`position:fixed; inset:0; z-index:499`) is shown behind the sheet when open.
  - The existing `positionPopup()` function is skipped in bottom-sheet mode.
  - Chart rendering (`renderChart`) is unchanged — same Chart.js call, just different container positioning.

---

## Architecture

All changes are CSS + small JS additions inside `app/templates/index.html`. No new files, no backend changes.

- CSS additions go into the existing `<style>` block, inside a new `@media (max-width: 640px)` section.
- JS additions go into the existing inline `<script>` blocks:
  - Hamburger toggle logic in the main script block (near theme toggle).
  - Touch vs. hover branching in the price-history script block.

---

## Error Handling

- If `#mobileMenuBtn` click listener fires and `#mobileMenu` doesn't exist in DOM, create it lazily.
- Bottom sheet: if chart fetch fails, error state is shown inside the sheet (same `#ph-error` element, already handled).

---

## Out of Scope

- Table column hiding on mobile (the `overflow-x: auto` scroll is acceptable for a data table).
- Swipe-down gesture to close bottom sheet (tap-outside is sufficient).
- Any backend changes.
