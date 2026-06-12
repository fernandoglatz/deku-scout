# Tip Banner Resize Update Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Update the tip banner message when the window crosses the 640px mobile/desktop breakpoint, but only while the tip is still visible.

**Architecture:** Add a debounced `resize` listener inside the existing tip banner JS block in `index.html`. Track the current breakpoint in a variable set at init time; on resize, swap the i18n key and text content only if the breakpoint changed and the tip has not been dismissed.

**Tech Stack:** Vanilla JS, existing `I18n.t()` helper, existing `tipDismissed` flag.

---

### Task 1: Update tip banner JS block

**Files:**
- Modify: `app/templates/index.html` (tip banner block ~lines 938–966)

- [ ] **Step 1: Locate the tip banner init block**

Open `app/templates/index.html` and find the block between the comments `// --- tip banner ---` and `// --- end tip banner ---` (around lines 938–966). The current init code is:

```js
if (tipEl) {
  var alreadySeen = false;
  try { alreadySeen = !!localStorage.getItem(TIP_KEY); } catch (e) {}
  if (!alreadySeen) {
    var tipKey = window.innerWidth <= 640 ? 'ph.tipTap' : 'ph.tipHover';
    tipText.dataset.i18n = tipKey;
    tipText.textContent = I18n.t(tipKey);
    tipEl.style.display = 'flex';
  } else {
    tipDismissed = true;
  }
  if (tipClose) tipClose.addEventListener('click', dismissTip);
}
// --- end tip banner ---
```

- [ ] **Step 2: Replace the tip banner init block**

Replace the entire block above with:

```js
var tipIsMobile = window.innerWidth <= 640;

if (tipEl) {
  var alreadySeen = false;
  try { alreadySeen = !!localStorage.getItem(TIP_KEY); } catch (e) {}
  if (!alreadySeen) {
    var tipKey = tipIsMobile ? 'ph.tipTap' : 'ph.tipHover';
    tipText.dataset.i18n = tipKey;
    tipText.textContent = I18n.t(tipKey);
    tipEl.style.display = 'flex';
  } else {
    tipDismissed = true;
  }
  if (tipClose) tipClose.addEventListener('click', dismissTip);
}

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
// --- end tip banner ---
```

- [ ] **Step 3: Manually verify in browser**

1. Open the app (clear `localStorage` key `dekuscout_ph_tip_seen` so the tip is not dismissed).
2. Load the page on a desktop width (> 640px) — confirm the desktop tip message appears.
3. Drag the browser window narrower than 640px — confirm the tip text switches to the mobile message.
4. Drag back wider — confirm it switches back to the desktop message.
5. Dismiss the tip (click ✕), then resize again — confirm the tip does NOT reappear.

- [ ] **Step 4: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: update tip banner message on window resize"
```
