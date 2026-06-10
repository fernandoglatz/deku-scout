# Mobile Responsiveness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make DekuScout's single-page UI work on mobile by adding a hamburger menu, full-width search, and a bottom-sheet price history popup.

**Architecture:** All changes are CSS + JS in `app/templates/index.html`. No backend changes, no new files. Each task targets one isolated concern; each can be verified in Chrome DevTools' mobile emulator.

**Tech Stack:** Vanilla JS (ES5 compatible, matching existing codebase), CSS media queries at `≤640px`, Chart.js (already loaded).

---

## How to run the app for manual testing

```bash
flask --app wsgi run --debug
```

Open http://localhost:5000. In Chrome: DevTools → Toggle device toolbar (Ctrl+Shift+M) → pick "iPhone SE" (375×667) or "Galaxy S8+" (360×740).

After each task, verify in the mobile emulator before committing.

---

## Task 1: Full-width search bar on mobile

**Files:**
- Modify: `app/templates/index.html` — inside the `@media (max-width: 640px)` block (line 181)

- [ ] **Step 1: Open the existing media query block**

In `app/templates/index.html`, find the existing media query near line 181:

```css
@media (max-width: 640px) {
  header, main { padding-left: 1rem; padding-right: 1rem; }
  .meta { display: none; }
}
```

- [ ] **Step 2: Add search box rule**

Replace the existing media query block with:

```css
@media (max-width: 640px) {
  header, main { padding-left: 1rem; padding-right: 1rem; }
  .meta { display: none; }
  .search-box { width: 100%; }
}
```

- [ ] **Step 3: Verify in mobile emulator**

Run the app (`flask --app wsgi run --debug`), open http://localhost:5000, switch to iPhone SE in DevTools. The search box should span the full toolbar width, with filter buttons wrapping onto the next line below it.

- [ ] **Step 4: Commit**

```bash
git add app/templates/index.html
git commit -m "style: full-width search box on mobile"
```

---

## Task 2: Hamburger menu for header controls

**Files:**
- Modify: `app/templates/index.html` — header HTML, CSS block, and main JS block

### 2a — Add CSS

- [ ] **Step 1: Add hamburger and mobile menu styles to the media query block**

Extend the `@media (max-width: 640px)` block (the one you modified in Task 1) to:

```css
@media (max-width: 640px) {
  header, main { padding-left: 1rem; padding-right: 1rem; }
  .meta { display: none; }
  .search-box { width: 100%; }

  /* hide all header controls on mobile */
  header .theme-btn,
  header .lang-select,
  header .user-badge,
  header #openModalBtn,
  header #rf { display: none; }

  /* show hamburger */
  #mobileMenuBtn { display: flex; }

  /* mobile dropdown panel */
  #mobileMenu {
    display: none;
    position: absolute;
    top: 100%;
    left: 0; right: 0;
    background: var(--surface);
    border-bottom: 1px solid var(--border);
    padding: 0.75rem 1rem;
    z-index: 19;
    flex-direction: column;
    gap: 0.65rem;
  }
  #mobileMenu.open { display: flex; }

  #mobileMenu .lang-select,
  #mobileMenu .user-badge,
  #mobileMenu .theme-btn,
  #mobileMenu #openModalBtn,
  #mobileMenu #rf { display: flex !important; }

  #mobileMenu .lang-select { width: 100%; }
  #mobileMenu .user-badge  { max-width: 100%; width: 100%; }

  #mobileMenuActions {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }
  #mobileMenuActions .btn { flex: 1; justify-content: center; }
}
```

Also add this rule **outside** the media query (so the button is hidden on desktop by default):

```css
#mobileMenuBtn { display: none; }
```

Place it after the `.theme-btn:hover` rule (~line 70).

- [ ] **Step 2: Verify no visible change on desktop**

Reload the page in a normal (non-mobile) viewport. Nothing should have changed.

### 2b — Add hamburger button to header HTML

- [ ] **Step 3: Add `#mobileMenuBtn` to the header**

In `app/templates/index.html`, find the `<header>` opening. Add the `#mobileMenuBtn` button as the **last child** of `<header>`, after the `<form id="rf">` closing tag:

```html
  <button class="theme-btn" id="mobileMenuBtn" aria-label="Menu" aria-expanded="false">&#9776;</button>
</header>
```

(The `&#9776;` is the ☰ hamburger character.)

Also add the `#mobileMenu` panel **immediately after** the closing `</header>` tag:

```html
</header>
<div id="mobileMenu" role="navigation" aria-label="Mobile menu">
  <!-- clones are inserted by JS -->
</div>
```

- [ ] **Step 4: Verify the hamburger button appears on mobile viewport**

In Chrome DevTools mobile view, you should now see the ☰ button on the right side of the header. Clicking it does nothing yet.

### 2c — Add toggle JS

- [ ] **Step 5: Add hamburger JS to the main script block**

In `app/templates/index.html`, find the main `<script>` block that contains the theme toggle code (the one with `themeBtn.addEventListener`). Add the following block **after** the theme toggle listener (after the `themeBtn.addEventListener` closure, before `function formatReleaseDate`):

```javascript
  // Mobile menu — populate with clones of header controls on first open
  var mobileMenuBtn = document.getElementById('mobileMenuBtn');
  var mobileMenu    = document.getElementById('mobileMenu');
  var mobileMenuReady = false;

  function buildMobileMenu() {
    if (mobileMenuReady) return;
    mobileMenuReady = true;

    // Clone lang select
    var langClone = document.getElementById('langSelect').cloneNode(true);
    langClone.id = 'langSelectMobile';
    langClone.addEventListener('change', function () {
      document.getElementById('langSelect').value = langClone.value;
      document.getElementById('langSelect').dispatchEvent(new Event('change'));
    });
    mobileMenu.appendChild(langClone);

    // Clone user badge (display only)
    var badge = document.querySelector('header .user-badge');
    if (badge) mobileMenu.appendChild(badge.cloneNode(true));

    // Actions row: theme + settings + refresh
    var actionsRow = document.createElement('div');
    actionsRow.id = 'mobileMenuActions';

    var themeClone = document.getElementById('themeToggle').cloneNode(true);
    themeClone.id = 'themeToggleMobile';
    themeClone.addEventListener('click', function () {
      document.getElementById('themeToggle').click();
      themeClone.textContent = document.getElementById('themeToggle').textContent;
    });
    actionsRow.appendChild(themeClone);

    var settingsBtn = document.getElementById('openModalBtn');
    if (settingsBtn) {
      var settingsClone = settingsBtn.cloneNode(true);
      settingsClone.addEventListener('click', function () {
        closeMobileMenu();
        settingsBtn.click();
      });
      actionsRow.appendChild(settingsClone);
    }

    var rfClone = document.getElementById('rf').cloneNode(true);
    rfClone.id = 'rfMobile';
    rfClone.addEventListener('submit', function () {
      document.getElementById('loading').classList.add('show');
      rfClone.querySelector('button').disabled = true;
    });
    actionsRow.appendChild(rfClone);

    mobileMenu.appendChild(actionsRow);
  }

  function closeMobileMenu() {
    mobileMenu.classList.remove('open');
    mobileMenuBtn.setAttribute('aria-expanded', 'false');
  }

  mobileMenuBtn.addEventListener('click', function (e) {
    e.stopPropagation();
    var isOpen = mobileMenu.classList.contains('open');
    if (!isOpen) {
      buildMobileMenu();
      mobileMenu.classList.add('open');
      mobileMenuBtn.setAttribute('aria-expanded', 'true');
    } else {
      closeMobileMenu();
    }
  });

  document.addEventListener('click', function (e) {
    if (mobileMenu.classList.contains('open') &&
        !mobileMenu.contains(e.target) &&
        e.target !== mobileMenuBtn) {
      closeMobileMenu();
    }
  });
```

- [ ] **Step 6: Verify hamburger menu opens and closes**

In mobile emulator:
- Tap ☰ → dropdown panel appears below header showing language select, email badge, theme button, settings button, refresh button.
- Tap ☰ again → panel closes.
- Tap anywhere outside → panel closes.
- Tap the theme button inside the menu → theme toggles (both in menu and header).
- Tap Refresh → page reloads with loading spinner.

- [ ] **Step 7: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: hamburger menu for header controls on mobile"
```

---

## Task 3: Price history bottom sheet on mobile

**Files:**
- Modify: `app/templates/index.html` — price-history JS block, CSS block

### 3a — Add bottom sheet CSS

- [ ] **Step 1: Add backdrop and bottom sheet styles**

Add the following CSS **outside** any media query (these styles are also needed by JS that checks `isTouchDevice`):

```css
#ph-backdrop {
  display: none;
  position: fixed; inset: 0;
  z-index: 498;
  background: rgba(0,0,0,.5);
}
#ph-backdrop.show { display: block; }
```

Place this after the `#ph-chart-wrap` rule (~line 180).

Then inside the `@media (max-width: 640px)` block, add:

```css
  #ph-popup {
    position: fixed !important;
    bottom: 0 !important; left: 0 !important; right: 0 !important;
    top: auto !important;
    width: 100% !important;
    max-width: 100% !important;
    border-radius: 12px 12px 0 0;
    z-index: 500;
    padding: 0 1rem 1.25rem;
    max-height: 60vh;
    overflow-y: auto;
  }
  .bs-handle {
    width: 36px; height: 4px;
    background: var(--border);
    border-radius: 2px;
    margin: 0.65rem auto 0.75rem;
  }
```

### 3b — Add backdrop element to HTML

- [ ] **Step 2: Add `#ph-backdrop` div before `#ph-popup`**

Find the `<div id="ph-popup"` line near the bottom of the file. Add the backdrop div immediately before it:

```html
<div id="ph-backdrop"></div>
<div id="ph-popup" style="display:none;position:fixed;z-index:500;">
```

- [ ] **Step 3: Verify no visual change on desktop**

Reload on desktop — no visible change. The popup still works on hover as before.

### 3c — Modify price-history JS for touch

- [ ] **Step 4: Replace the event-binding section of the price-history script**

In `app/templates/index.html`, find the price-history `<script>` block (the last one, containing `showPopup`, `hidePopup`, `positionPopup`). Find this section near the bottom of that script:

```javascript
  document.querySelectorAll('[data-ph-slug]').forEach(function (el) {
    el.classList.add('ph-trigger');
    el.addEventListener('mouseenter', function () { clearTimeout(hideTimer); showTimer = setTimeout(function () { showPopup(el); }, 280); });
    el.addEventListener('mouseleave', function () { clearTimeout(showTimer); hideTimer = setTimeout(hidePopup, 180); });
  });
  popup.addEventListener('mouseenter', function () { clearTimeout(hideTimer); });
  popup.addEventListener('mouseleave', function () { hideTimer = setTimeout(hidePopup, 180); });
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') hidePopup(); });
```

Replace it with:

```javascript
  var backdrop = document.getElementById('ph-backdrop');
  var isTouchDevice = ('ontouchstart' in window);

  function showBottomSheet(el) {
    showPopup(el);
    backdrop.classList.add('show');
  }

  function hideBottomSheet() {
    hidePopup();
    backdrop.classList.remove('show');
  }

  document.querySelectorAll('[data-ph-slug]').forEach(function (el) {
    el.classList.add('ph-trigger');
    if (isTouchDevice) {
      el.addEventListener('touchstart', function (e) {
        e.preventDefault();
        if (popup.style.display === 'block' && currentKey === el.dataset.phSlug + ':' + (el.dataset.phCurrency || 'br')) {
          hideBottomSheet();
        } else {
          showBottomSheet(el);
        }
      }, { passive: false });
    } else {
      el.addEventListener('mouseenter', function () { clearTimeout(hideTimer); showTimer = setTimeout(function () { showPopup(el); }, 280); });
      el.addEventListener('mouseleave', function () { clearTimeout(showTimer); hideTimer = setTimeout(hidePopup, 180); });
    }
  });

  if (!isTouchDevice) {
    popup.addEventListener('mouseenter', function () { clearTimeout(hideTimer); });
    popup.addEventListener('mouseleave', function () { hideTimer = setTimeout(hidePopup, 180); });
  }

  backdrop.addEventListener('click', hideBottomSheet);
  document.addEventListener('keydown', function (e) { if (e.key === 'Escape') hideBottomSheet(); });
```

- [ ] **Step 5: Add drag handle to popup HTML**

Find the `<div id="ph-popup"` HTML block:

```html
<div id="ph-popup" style="display:none;position:fixed;z-index:500;">
  <div id="ph-title"></div>
```

Add the drag handle as the first child inside the popup:

```html
<div id="ph-popup" style="display:none;position:fixed;z-index:500;">
  <div class="bs-handle"></div>
  <div id="ph-title"></div>
```

The handle is only visible on mobile (the `.bs-handle` CSS is only defined in the `@media (max-width: 640px)` block).

- [ ] **Step 6: Fix `positionPopup` to skip positioning in bottom-sheet mode**

Find the `positionPopup` function in the price-history script:

```javascript
  function positionPopup(el) {
    var rect = el.getBoundingClientRect();
    var pw = popup.offsetWidth || 380, ph = popup.offsetHeight;
    var left = Math.max(8, Math.min(window.innerWidth - pw - 8, rect.left + rect.width / 2 - pw / 2));
    var top = rect.top - ph - 8;
    if (top < 8) top = rect.bottom + 8;
    popup.style.left = left + 'px'; popup.style.top = top + 'px';
  }
```

Replace it with:

```javascript
  function positionPopup(el) {
    if (isTouchDevice) return;
    var rect = el.getBoundingClientRect();
    var pw = popup.offsetWidth || 380, ph = popup.offsetHeight;
    var left = Math.max(8, Math.min(window.innerWidth - pw - 8, rect.left + rect.width / 2 - pw / 2));
    var top = rect.top - ph - 8;
    if (top < 8) top = rect.bottom + 8;
    popup.style.left = left + 'px'; popup.style.top = top + 'px';
  }
```

- [ ] **Step 7: Verify bottom sheet on mobile emulator**

In Chrome DevTools mobile view (iPhone SE):
- Tap any price cell → bottom sheet slides up from bottom, chart loads.
- Tap backdrop (dark overlay) → sheet dismisses.
- Tap same price cell again → sheet dismisses.
- Press Escape → sheet dismisses.

On desktop (no touch emulation): hover still works exactly as before.

- [ ] **Step 8: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: price history bottom sheet on mobile (tap-to-show)"
```

---

## Final verification

- [ ] Run the full test suite to confirm no regressions:

```bash
python -m pytest tests/ -q
```

Expected: all 160 tests pass (no Python logic changed).

- [ ] Check `.gitignore` includes `.superpowers/`:

```bash
grep -q '.superpowers' .gitignore || echo '.superpowers/' >> .gitignore
```
