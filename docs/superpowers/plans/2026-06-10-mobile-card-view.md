# Mobile Card View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the horizontal-scrolling table with a card list on mobile (≤640px), keeping the table on desktop.

**Architecture:** All changes in `app/templates/index.html`. Add card CSS (hidden by default, shown on mobile), a Jinja2 card loop after `.table-wrap`, and small extensions to `applyFilters()` and `applyDates()` so search/filter/date-formatting work on both table rows and cards.

**Tech Stack:** Jinja2, vanilla CSS, vanilla JS (ES5 compatible).

---

## How to run the app for manual testing

```bash
flask --app wsgi run --debug
```

Open http://localhost:5000. In Chrome DevTools: Toggle device toolbar (Ctrl+Shift+M) → iPhone SE (375×667).

---

## Task 1: Card CSS

**Files:**
- Modify: `app/templates/index.html` — `<style>` block and `@media (max-width: 640px)` block

- [ ] **Step 1: Add card base styles outside any media query**

In the `<style>` block, find the `.table-wrap` rule. Add the following **after** the last rule before `@media` (i.e., after `#ph-chart-wrap` and the backdrop rules, but before the `@media` block):

```css
#cardList { display: none; }
.game-card {
  background: var(--surface); border: 1px solid var(--border);
  border-radius: 8px; padding: .65rem .85rem;
  display: flex; gap: .75rem; align-items: flex-start;
}
.game-card.on-sale { background: var(--sale-row); border-color: rgba(16,185,129,.2); }
.game-card.unavailable { opacity: .4; }
.card-icon {
  width: 44px; height: 44px; object-fit: cover;
  border-radius: 6px; flex-shrink: 0; background: var(--border);
}
.card-icon-ph {
  width: 44px; height: 44px; border-radius: 6px;
  background: var(--border); flex-shrink: 0;
  display: inline-flex; align-items: center; justify-content: center; font-size: 1.3rem;
}
.card-body { flex: 1; min-width: 0; }
.card-name { margin-bottom: .3rem; }
.card-name a { color: var(--text); font-weight: 600; font-size: .88rem; text-decoration: none; }
.card-name a:hover { color: var(--accent); }
.card-prices { display: flex; flex-direction: column; gap: .2rem; }
.card-price-cell {
  display: flex; align-items: baseline; gap: .3rem;
  flex-wrap: wrap; font-size: .8rem; cursor: help;
}
.card-price-label { color: var(--text-muted); font-size: .72rem; font-weight: 600; min-width: 2.5rem; }
.card-price-orig { color: var(--orig-color); text-decoration: line-through; font-size: .75rem; font-variant-numeric: tabular-nums; }
.card-price-cur { font-weight: 600; font-variant-numeric: tabular-nums; }
.card-price-unavail { color: var(--text-muted); font-size: .78rem; }
.card-sale-end { color: var(--yellow); font-size: .75rem; margin-top: .3rem; }
```

- [ ] **Step 2: Add mobile overrides inside `@media (max-width: 640px)`**

Inside the existing `@media (max-width: 640px)` block, add at the end:

```css
  .table-wrap { display: none; }
  #cardList { display: flex; flex-direction: column; gap: .5rem; }
```

- [ ] **Step 3: Verify no visible change on desktop**

On desktop viewport, the table should look exactly as before.

- [ ] **Step 4: Commit**

```bash
git add app/templates/index.html
git commit -m "style: add card list CSS for mobile game view"
```

---

## Task 2: Card HTML (Jinja2 template)

**Files:**
- Modify: `app/templates/index.html` — after the closing `</div>` of `.table-wrap`

- [ ] **Step 1: Add `#cardList` after `.table-wrap`**

Find the closing `</div>` of the `.table-wrap` block (the line that closes `<div class="table-wrap">`). Add the following immediately after it, before the `{% elif wishlist_configured %}` line:

```html
  <div id="cardList">
    {% for g in games %}
    {% set is_on_sale = g.has_discount %}
    {% set is_unavail = g.all_unavailable %}
    <div class="game-card {{ 'on-sale' if is_on_sale else ('unavailable' if is_unavail else '') }}"
         data-sale="{{ '1' if is_on_sale else '0' }}"
         data-unavail="{{ '1' if is_unavail else '0' }}"
         data-bestbuy="{{ g.best_buy }}"
         data-name="{{ g.name | lower }}">
      <img class="card-icon" src="/icons/{{ g.slug }}{% if g.icon_ext %}.{{ g.icon_ext }}{% endif %}"
           onerror="this.replaceWith(Object.assign(document.createElement('span'),{className:'card-icon-ph',textContent:'🎮'}))"
           alt="" loading="lazy">
      <div class="card-body">
        <div class="card-name">
          <a href="https://www.dekudeals.com/items/{{ g.slug }}" target="_blank" rel="noopener">{{ g.name }}</a>
        </div>
        <div class="card-prices">
          {% for locale in selected_locales %}
          {% set p = g.prices.get(locale, {}) %}
          {%- set cur = p.get('current', '') if p else '' -%}
          <div class="card-price-cell" data-ph-slug="{{ g.slug }}" data-ph-currency="{{ locale }}">
            <span class="card-price-label">{{ countries[locale].symbol }} {{ locale.upper() }}</span>
            {%- if p and p.get('original') -%}
            <span class="card-price-orig">{{ p.original }}</span>
            {%- endif -%}
            {%- if not cur or cur == 'Unavailable' -%}
            <span class="card-price-unavail" data-i18n="cell.unavailable">Unavailable</span>
            {%- else -%}
            <span class="card-price-cur">{{ cur }}</span>
            {%- endif -%}
            {%- if p and p.get('discount') -%}
            <span class="disc">{{ p.discount }}</span>
            {%- endif -%}
          </div>
          {% endfor %}
        </div>
        <div class="card-sale-end" data-date="{{ g.sale_end }}"></div>
      </div>
    </div>
    {% endfor %}
  </div>
```

- [ ] **Step 2: Verify HTML renders on mobile**

In Chrome DevTools mobile view (iPhone SE), you should see the card list. Each game should show icon, name, prices, and (for on-sale items) a sale end placeholder (dates are added by JS in Task 3).

- [ ] **Step 3: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: add mobile card list HTML to game template"
```

---

## Task 3: JS — extend applyFilters and applyDates

**Files:**
- Modify: `app/templates/index.html` — main `<script>` block

- [ ] **Step 1: Extend `applyFilters()` to also filter cards**

Find the `applyFilters` function:

```javascript
  function applyFilters() {
    var q = searchEl.value.trim().toLowerCase();
    tbl.querySelector('tbody').querySelectorAll('tr').forEach(function (tr) {
      var matchSearch = !q || tr.cells[2].textContent.toLowerCase().includes(q);
      var matchFilter = true;
      if (activeFilters.size > 0) {
        activeFilters.forEach(function (f) {
          if (f === 'sale'      && tr.dataset.sale !== '1')    matchFilter = false;
          if (f === 'available' && tr.dataset.unavail === '1') matchFilter = false;
          if (f.startsWith('bb-') && tr.dataset.bestbuy !== f.slice(3)) matchFilter = false;
        });
      }
      tr.style.display = matchSearch && matchFilter ? '' : 'none';
    });
  }
```

Replace it with:

```javascript
  function applyFilters() {
    var q = searchEl.value.trim().toLowerCase();
    function matchesFilters(el) {
      if (activeFilters.size === 0) return true;
      var ok = true;
      activeFilters.forEach(function (f) {
        if (f === 'sale'      && el.dataset.sale !== '1')    ok = false;
        if (f === 'available' && el.dataset.unavail === '1') ok = false;
        if (f.startsWith('bb-') && el.dataset.bestbuy !== f.slice(3)) ok = false;
      });
      return ok;
    }
    tbl.querySelector('tbody').querySelectorAll('tr').forEach(function (tr) {
      var matchSearch = !q || tr.cells[2].textContent.toLowerCase().includes(q);
      tr.style.display = matchSearch && matchesFilters(tr) ? '' : 'none';
    });
    document.querySelectorAll('#cardList .game-card').forEach(function (card) {
      var matchSearch = !q || card.dataset.name.includes(q);
      card.style.display = matchSearch && matchesFilters(card) ? '' : 'none';
    });
  }
```

- [ ] **Step 2: Extend `applyDates()` to format card sale-end dates**

Find the `applyDates` function:

```javascript
  function applyDates() {
    var locale = I18n.localeString();
    document.querySelectorAll('td.sale-end[data-date]').forEach(function (td) {
      td.textContent = formatSaleEnd(td.dataset.date, locale);
    });
    document.querySelectorAll('td.rel-date[data-date]').forEach(function (td) {
      td.textContent = formatReleaseDate(td.dataset.date, locale);
    });
  }
```

Replace it with:

```javascript
  function applyDates() {
    var locale = I18n.localeString();
    document.querySelectorAll('td.sale-end[data-date]').forEach(function (td) {
      td.textContent = formatSaleEnd(td.dataset.date, locale);
    });
    document.querySelectorAll('td.rel-date[data-date]').forEach(function (td) {
      td.textContent = formatReleaseDate(td.dataset.date, locale);
    });
    document.querySelectorAll('.card-sale-end[data-date]').forEach(function (el) {
      el.textContent = formatSaleEnd(el.dataset.date, locale);
    });
  }
```

- [ ] **Step 3: Verify filters and search work on mobile**

In Chrome DevTools mobile view:
- Type in the search box → cards matching the query remain visible, others hide
- Tap "On Sale" filter → only on-sale cards shown
- Tap "Available" filter → unavailable cards hidden
- Tap "All" → all cards shown
- Sale end dates should appear on sale cards (formatted, e.g. "12h" or "Jun 15")

- [ ] **Step 4: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: wire search/filter/dates to mobile card list"
```

---

## Final verification

- [ ] Run tests:

```bash
python -m pytest tests/ -q
```

Expected: 160 tests pass.
