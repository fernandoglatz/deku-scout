# Mobile Card View Design

**Date:** 2026-06-10  
**Status:** Approved  

## Overview

Replace the horizontally-scrolling table with a card list on mobile (≤640px). The table remains unchanged on desktop. Cards are rendered server-side in the same Jinja2 template alongside the table and are toggled via CSS.

---

## Layout

On mobile, the `.table-wrap` div is hidden and `#cardList` is shown. On desktop the reverse is true.

Each card contains:
- Game icon (same `/icons/<slug>` source, with emoji fallback)
- Game name as a link to dekudeals.com
- All selected price columns — original (strikethrough), current, discount badge
- Sale end date (formatted, same as table)
- On-sale highlight (green tint border/background)
- Unavailable state (40% opacity)

---

## Data / Attributes

Cards carry the same filter attributes as table rows so existing JS works:

```html
<div class="game-card"
     data-sale="1|0"
     data-unavail="1|0"
     data-bestbuy="{{ g.best_buy }}">
```

Price cells carry price-history attributes so the existing bottom-sheet tap works:

```html
<div class="card-price-cell"
     data-ph-slug="{{ g.slug }}"
     data-ph-currency="{{ locale }}">
```

---

## JS Changes

**`applyFilters()`** — extend to also show/hide `.game-card` elements using the same `data-sale`, `data-unavail`, `data-bestbuy` logic and the card's `data-name` attribute for search matching.

**`applyDates()`** — extend selectors to include `.card-sale-end[data-date]` for sale-end dates on cards.

**Price history** — the existing `document.querySelectorAll('[data-ph-slug]')` binding already covers card price cells as long as they have `data-ph-slug` and `data-ph-currency`. No extra JS needed.

**Sorting** — no sort UI on mobile. Cards render in the same DOM order as the table rows (shared Jinja2 loop order), so whatever sort the desktop had is reflected. Acceptable trade-off for mobile simplicity.

---

## Architecture

All changes in `app/templates/index.html` only. No backend changes.

- Jinja2 loop for cards added immediately after `.table-wrap` closing div
- CSS for cards added to the `<style>` block, card list hidden by default, shown inside `@media (max-width: 640px)`; table hidden inside same breakpoint
- JS additions are small extensions to `applyFilters()` and `applyDates()`

---

## Out of Scope

- Sort UI on mobile
- Pagination or virtual scroll
- Any backend changes
