# Price History Onboarding — Design Spec

**Date:** 2026-06-12
**Status:** Approved

## Problem

DekuScout already renders a price history chart popup when the user hovers (desktop) or taps (mobile) any price cell. The cells have `cursor: help` as a visual hint, but there is no explicit onboarding telling users this feature exists. New users routinely miss it.

## Solution

A one-time dismissible tip banner shown between the toolbar and the games table on first visit. It is removed once the user dismisses it explicitly or naturally discovers the feature by interacting with a price cell.

## Scope

- Pure frontend change: JS + CSS additions inside `app/templates/index.html`
- No backend changes, no new routes, no new files

## Visual Design

Slim bar (full width of the table area) sitting between the `.toolbar` div and `.table-wrap` div:

```
┌─────────────────────────────────────────────────────────────────────┐
│ 📈  Tip: hover any price to see its full price history chart.    [✕] │
└─────────────────────────────────────────────────────────────────────┘
```

Styling matches the existing dark/light theme variables:
- Background: `var(--surface)`
- Border: `1px solid var(--border)` with a `3px solid var(--accent)` left accent stripe
- Text: `var(--text-sub)`, muted ✕ button in `var(--text-muted)`
- Border-radius: 8px, padding: `.6rem 1rem`

## Behavior

### Visibility condition
The banner is only inserted into the DOM when the games table is rendered (wishlist configured + data present). It must not appear on the "Setup Wishlist" screen or the loading screen.

### Device-adaptive text
Reuses the existing `isTouchDevice` detection (`window.matchMedia('(pointer: coarse)').matches`):
- Desktop: "Tip: **hover** any price to see its full price history chart."
- Mobile: "Tip: **tap** any price to see its full price history chart."

### Dismiss triggers
Two ways to dismiss, both idempotent:

1. **✕ button click** — user explicitly closes it
2. **First price cell interaction** — the existing `mouseenter` (desktop) or `touchend` (mobile) handler on `[data-ph-slug]` elements calls the dismiss function before (or alongside) showing the popup. This fires only once.

### Persistence
- Key: `dekuscout_ph_tip_seen` in `localStorage`
- On page load: if key exists, banner is not rendered at all
- On dismiss: key is set and banner fades out (`opacity 0.2s ease`)

### Animation
- Appear: `slideDown` — `opacity 0 → 1` + `transform: translateY(-6px) → translateY(0)` over 250ms
- Dismiss: `fadeOut` — `opacity 1 → 0` over 200ms, then `display: none`

## Implementation location

All changes confined to `app/templates/index.html`:

1. **CSS block** (inside `<style>`): add `.ph-tip` styles + keyframe animations
2. **HTML block** (Jinja `{% if games %}` section): insert the `.ph-tip` div between `.toolbar` and `.table-wrap`
3. **JS block** (in the existing price-history `<script>` at the bottom): add tip dismissal logic and hook into existing `mouseenter`/`touchend` listeners

## Out of scope

- No i18n for the tip text (tip is English-only for now; localization can be added later if needed)
- No server-side tracking of onboarding completion
- No multi-step tour or spotlight overlay
