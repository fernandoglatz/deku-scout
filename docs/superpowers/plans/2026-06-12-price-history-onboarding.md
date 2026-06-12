# Price History Onboarding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show a one-time dismissible tip banner telling users they can hover (desktop) or tap (mobile) any price cell to reveal its full price history chart.

**Architecture:** Pure frontend — all changes in a single Jinja2 template. The banner sits between the toolbar and the games table, only rendered when games are present. Dismiss state is persisted to `localStorage`. The JS lives inside the existing price-history IIFE so it shares the already-computed `isTouchDevice` value and can hook into the same `mouseenter`/`touchend` listeners.

**Tech Stack:** HTML/CSS/JS (vanilla), Jinja2, localStorage

---

## File Map

| File | Change |
|------|--------|
| `app/templates/index.html` | Add CSS, HTML, and JS for the tip banner |

No other files are touched.

---

### Task 1: Add CSS for the tip banner

**Files:**
- Modify: `app/templates/index.html` — inside the existing `<style>` block, before the closing `</style>` tag (currently line ~255)

- [ ] **Step 1: Add `.ph-tip` styles and keyframes**

Find the closing `</style>` tag and insert the following CSS just before it:

```css
    .ph-tip {
      display: flex; align-items: center; gap: .75rem;
      background: var(--surface); border: 1px solid var(--border);
      border-left: 3px solid var(--accent);
      border-radius: 8px; padding: .6rem 1rem;
      font-size: .82rem; color: var(--text-sub);
      margin-bottom: .75rem;
      animation: phTipIn .25s ease;
    }
    .ph-tip b { color: var(--text); }
    .ph-tip-close {
      margin-left: auto; background: none; border: none;
      color: var(--text-muted); cursor: pointer;
      font-size: .95rem; line-height: 1; padding: .1rem .35rem;
      border-radius: 3px; transition: color .15s;
    }
    .ph-tip-close:hover { color: var(--text); }
    @keyframes phTipIn {
      from { opacity: 0; transform: translateY(-6px); }
      to   { opacity: 1; transform: translateY(0); }
    }
    @keyframes phTipOut {
      from { opacity: 1; }
      to   { opacity: 0; }
    }
```

- [ ] **Step 2: Verify CSS was added in the right place**

Open `app/templates/index.html` and confirm the new CSS rules appear inside the `<style>` block and before `</style>`. No duplicate `@keyframes` names should exist in the file (search for `phTipIn`).

---

### Task 2: Add the banner HTML

**Files:**
- Modify: `app/templates/index.html` — inside the `{% if games %}` Jinja block, between the `.toolbar` div and the `.table-wrap` div

- [ ] **Step 1: Locate the insertion point**

In `app/templates/index.html`, find this exact line (currently ~line 317):
```html
  <div class="table-wrap">
```
The new HTML goes immediately before it, still inside `{% if games %}`.

- [ ] **Step 2: Insert the banner HTML**

Add the following block between `</div>` (end of `.toolbar`) and `<div class="table-wrap">`:

```html
  <div class="ph-tip" id="ph-tip" style="display:none;">
    <span>📈</span>
    <span id="ph-tip-text"></span>
    <button class="ph-tip-close" id="ph-tip-close" aria-label="Dismiss tip">✕</button>
  </div>
```

The `style="display:none;"` ensures the banner is invisible until JS initialises it — this prevents a flash if localStorage says it was already dismissed.

- [ ] **Step 3: Verify the HTML structure**

Confirm the final order inside `{% if games %}` is:
1. `.stats` div
2. `.toolbar` div
3. `#ph-tip` div  ← new
4. `.table-wrap` div

---

### Task 3: Add the JS dismissal logic

**Files:**
- Modify: `app/templates/index.html` — inside the existing price-history `<script>` block (the IIFE that starts with `(function () {` after the `chart.js` `<script>` tag, currently ~line 779)

The tip JS must live **inside** this IIFE because `isTouchDevice` is a local variable there.

- [ ] **Step 1: Locate the insertion point inside the IIFE**

Find this comment/code block inside the price-history IIFE (currently ~line 896):

```js
  document.querySelectorAll('[data-ph-slug]').forEach(function (el) {
    el.classList.add('ph-trigger');
```

The tip initialisation runs just **before** this `querySelectorAll` loop.

- [ ] **Step 2: Insert the tip initialisation block**

Add the following directly before the `document.querySelectorAll('[data-ph-slug]')` loop:

```js
  // --- tip banner ---
  var tipEl    = document.getElementById('ph-tip');
  var tipText  = document.getElementById('ph-tip-text');
  var tipClose = document.getElementById('ph-tip-close');
  var TIP_KEY  = 'dekuscout_ph_tip_seen';

  function dismissTip() {
    if (!tipEl || tipEl.style.display === 'none') return;
    tipEl.style.animation = 'phTipOut .2s ease forwards';
    setTimeout(function () { tipEl.style.display = 'none'; }, 200);
    try { localStorage.setItem(TIP_KEY, '1'); } catch (e) {}
  }

  if (tipEl) {
    var alreadySeen = false;
    try { alreadySeen = !!localStorage.getItem(TIP_KEY); } catch (e) {}
    if (!alreadySeen) {
      tipText.textContent = isTouchDevice
        ? 'Tip: tap any price to see its full price history chart.'
        : 'Tip: hover any price to see its full price history chart.';
      tipEl.style.display = 'flex';
    }
    if (tipClose) tipClose.addEventListener('click', dismissTip);
  }
  // --- end tip banner ---
```

- [ ] **Step 3: Hook dismiss into the existing price-cell listeners**

Still inside the `document.querySelectorAll('[data-ph-slug]').forEach` loop, the existing code branches on `isTouchDevice`. Add a single `dismissTip()` call at the top of each branch so the banner disappears on first real interaction:

Find the existing listener block:

```js
    if (isTouchDevice) {
      el.addEventListener('touchend', function (e) {
        e.preventDefault();
        if (popup.style.display === 'block' && currentKey === el.dataset.phSlug + ':' + (el.dataset.phCurrency || 'br')) {
          hideBottomSheet();
        } else {
          showBottomSheet(el);
        }
      });
    } else {
      el.addEventListener('mouseenter', function () { clearTimeout(hideTimer); showTimer = setTimeout(function () { showPopup(el); }, 280); });
      el.addEventListener('mouseleave', function () { clearTimeout(showTimer); hideTimer = setTimeout(hidePopup, 180); });
    }
```

Replace it with:

```js
    if (isTouchDevice) {
      el.addEventListener('touchend', function (e) {
        e.preventDefault();
        dismissTip();
        if (popup.style.display === 'block' && currentKey === el.dataset.phSlug + ':' + (el.dataset.phCurrency || 'br')) {
          hideBottomSheet();
        } else {
          showBottomSheet(el);
        }
      });
    } else {
      el.addEventListener('mouseenter', function () { dismissTip(); clearTimeout(hideTimer); showTimer = setTimeout(function () { showPopup(el); }, 280); });
      el.addEventListener('mouseleave', function () { clearTimeout(showTimer); hideTimer = setTimeout(hidePopup, 180); });
    }
```

- [ ] **Step 4: Verify `dismissTip` is defined before use**

Confirm in the file that the `// --- tip banner ---` block (which defines `dismissTip`) appears **before** the `querySelectorAll('[data-ph-slug]')` loop that calls it.

---

### Task 4: Manual verification and commit

- [ ] **Step 1: Start the app**

```bash
python -m flask --app wsgi run
```
or however the project is normally run (check `docker-compose.yaml` or `wsgi.py`).

- [ ] **Step 2: Verify first-visit behaviour**

1. Open the app in a browser with the games table visible.
2. Confirm the blue-accented tip banner appears above the table with the correct text ("hover" on desktop, "tap" on mobile).
3. Hover over any price cell — confirm the banner fades out and the price history popup appears as normal.
4. Reload the page — confirm the banner does **not** reappear (localStorage key set).

- [ ] **Step 3: Verify ✕ dismiss**

1. Delete `dekuscout_ph_tip_seen` from localStorage (DevTools → Application → Local Storage).
2. Reload — banner should reappear.
3. Click ✕ — banner fades out.
4. Reload — banner should not reappear.

- [ ] **Step 4: Verify no-games state**

Navigate to a fresh session with no wishlist configured. Confirm the tip banner is not visible (it only renders inside `{% if games %}`).

- [ ] **Step 5: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: add one-time tip banner for price history hover/tap discovery"
```
