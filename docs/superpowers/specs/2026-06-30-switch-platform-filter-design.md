# Switch 1 / Switch 2 platform filter

**Date:** 2026-06-30

## Goal

Let users filter the game list by Nintendo console: **Switch 1** and/or **Switch 2**.
The platform is not present on the wishlist page — it only appears on each game's
item detail page, inside `ul.details` under a `Platforms:` line.

## Data source

Each item page contains:

```html
<ul class="details list-group list-group-flush">
  ...
  <li class="list-group-item"><strong>Platforms:</strong>
      <a href="?platform=all">Nintendo Switch, PlayStation 5, ...</a></li>
</ul>
```

- Switch 1 game → list contains the exact token `Nintendo Switch`
- Switch 2 game → list contains the exact token `Nintendo Switch 2`
- A game may list **both**.

The app already downloads every available game's item page in
`_fetch_eshop_prices` ([app/scraper.py](../../../app/scraper.py)). Platform parsing
reuses that response — **no additional HTTP requests**.

## Design

### 1. Parsing (`app/scraper.py`)

New helper `_parse_platforms(html) -> dict` returning `{"switch1": bool, "switch2": bool}`:

1. Find `ul.details`.
2. Find the direct-child `li.list-group-item` whose `<strong>` text starts with `Platforms`.
3. Split the remaining text on commas, strip each token.
4. `switch1 = "Nintendo Switch" in tokens`, `switch2 = "Nintendo Switch 2" in tokens`.

Exact-token matching (not a substring search over the whole `.details` text) avoids a
false positive from the release-date line, which also contains the word "Switch".

In the `_fetch_eshop_prices` loop, set `game["switch1"]` / `game["switch2"]` from the
already-fetched HTML.

**Both-platform games** get both flags, so they match either filter.

**Known limitation:** `_fetch_eshop_prices` only fetches item pages for *available*
games. Unavailable games therefore stay `switch1=switch2=False` and won't appear under
either Switch filter. Accepted to avoid extra requests.

### 2. Persistence (`app/db.py` + migration `V005`)

Migration `V005__add_platform_flags_to_games_cache.sql` adds:

```sql
ALTER TABLE games_cache ADD COLUMN switch1 INTEGER NOT NULL DEFAULT 0;
ALTER TABLE games_cache ADD COLUMN switch2 INTEGER NOT NULL DEFAULT 0;
```

`save_games_cache` writes the flags as `0`/`1`; `load_games_cache` reads them back as
Python booleans on each game dict.

### 3. Frontend (`app/templates/index.html`)

- Each row gets `data-switch1` / `data-switch2` (`'1'`/`'0'`).
- Two filter buttons `data-filter="switch1"` / `data-filter="switch2"` after "Available".
  The existing generic button handler covers toggle + active-state + persistence.
- `applyFilters` gains two checks, **ANDed** with the other active filters (consistent
  with current behavior):
  ```js
  if (f === 'switch1' && tr.dataset.switch1 !== '1') matchFilter = false;
  if (f === 'switch2' && tr.dataset.switch2 !== '1') matchFilter = false;
  ```
- i18n keys `filter.switch1` / `filter.switch2` added to all four locale files
  (en, pt, es, ja).

## Testing

- Unit tests for `_parse_platforms`: Switch 1 only, Switch 2 only, both, neither,
  missing `Platforms:` line.
- DB round-trip test confirming the two flag columns persist and load.
