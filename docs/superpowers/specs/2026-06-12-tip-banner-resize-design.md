# Tip Banner Resize Update

**Date:** 2026-06-12

## Problem

The tip banner message (`ph.tipHover` for desktop, `ph.tipTap` for mobile) is determined once at page load based on `window.innerWidth`. If the user resizes the window across the 640px breakpoint while the tip is still visible, the message stays stale.

## Goal

Update the tip text in place when the window crosses the mobile/desktop breakpoint, but only if the tip is still visible (not dismissed).

## Design

### Breakpoint

Same threshold already used: `window.innerWidth <= 640` → mobile (`ph.tipTap`), otherwise desktop (`ph.tipHover`).

### Init change

Track the current breakpoint at init time:

```js
var tipIsMobile = window.innerWidth <= 640;
```

This replaces the inline `window.innerWidth <= 640` expression used to pick the initial `tipKey`, so there is no duplication.

### Resize listener

A debounced `resize` listener is added after the tip banner setup block:

```js
var tipResizeTimer;
window.addEventListener('resize', function () {
  clearTimeout(tipResizeTimer);
  tipResizeTimer = setTimeout(function () {
    if (tipDismissed) return;
    var nowMobile = window.innerWidth <= 640;
    if (nowMobile === tipIsMobile) return;
    tipIsMobile = nowMobile;
    var tipKey = tipIsMobile ? 'ph.tipTap' : 'ph.tipHover';
    tipText.dataset.i18n = tipKey;
    tipText.textContent = I18n.t(tipKey);
  }, 150);
});
```

### What does NOT change

- No re-show if tip was dismissed.
- No change to `localStorage` on resize.
- No animation on text swap.
- Breakpoint value (640px) unchanged.

## Files affected

- `app/templates/index.html` — tip banner JS block (~lines 938–966)
