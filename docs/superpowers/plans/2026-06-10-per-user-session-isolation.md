# Per-User Session Isolation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Isolate each user's SQLite database (config, cache, cookies) based on the `X-Forwarded-User` header injected by an upstream auth proxy, with a fallback to the default `session.db` when the header is absent.

**Architecture:** A new `app/user.py` module owns identity logic (`get_user_email`, `resolve_db_path`, `get_db_path`). A Flask `before_request` hook in `app/__init__.py` reads the header, computes the per-request DB path, stores it in `flask.g`, and lazily runs migrations for new user DBs. All DB call sites in `app/web.py` are updated to use `get_db_path()` instead of the hardcoded `DB_FILE` constant.

**Tech Stack:** Python 3.12, Flask, SQLite (via `sqlite3`), yoyo-migrations, pytest, hashlib (stdlib)

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `app/user.py` | **Create** | Identity helpers: `get_user_email`, `resolve_db_path`, `get_db_path` |
| `app/db.py` | **Modify** | Add optional `db_path` param to `get_config` / `set_config` |
| `app/__init__.py` | **Modify** | Add `_initialized_dbs` set and `before_request` hook |
| `app/web.py` | **Modify** | Replace all `DB_FILE` usages with `get_db_path()`; pass `user_email` to template |
| `app/templates/index.html` | **Modify** | Add `.user-badge` CSS + conditional badge in header |
| `tests/test_user.py` | **Create** | Unit tests for all functions in `app/user.py` |
| `tests/conftest.py` | **Modify** | `client` fixture patches both `config.DB_FILE` and `db.DB_FILE`; remove unused `temp_db_web` |

---

## Task 1: Create `app/user.py` with identity helpers

**Files:**
- Create: `app/user.py`
- Create: `tests/test_user.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_user.py`:

```python
import hashlib
import os

import pytest
from flask import Flask, g


def test_resolve_db_path_is_deterministic():
    from app.user import resolve_db_path
    assert resolve_db_path("user@example.com") == resolve_db_path("user@example.com")


def test_resolve_db_path_uses_sha256():
    from app.user import resolve_db_path
    email = "user@example.com"
    expected_hash = hashlib.sha256(email.encode()).hexdigest()
    path = resolve_db_path(email)
    assert expected_hash in path
    assert path.endswith("session.db")


def test_resolve_db_path_different_emails_differ():
    from app.user import resolve_db_path
    assert resolve_db_path("a@example.com") != resolve_db_path("b@example.com")


def test_resolve_db_path_is_under_data_dir(monkeypatch, tmp_path):
    import app.config as config_module
    monkeypatch.setattr(config_module, "DATA_DIR", str(tmp_path))
    from app.user import resolve_db_path
    path = resolve_db_path("user@example.com")
    assert path.startswith(os.path.join(str(tmp_path), "users"))


def test_get_user_email_returns_none_outside_request():
    from app.user import get_user_email
    assert get_user_email() is None


def test_get_user_email_returns_email_from_header():
    from app.user import get_user_email
    app = Flask(__name__)
    with app.test_request_context(headers={"X-Forwarded-User": "alice@example.com"}):
        assert get_user_email() == "alice@example.com"


def test_get_user_email_strips_whitespace():
    from app.user import get_user_email
    app = Flask(__name__)
    with app.test_request_context(headers={"X-Forwarded-User": "  alice@example.com  "}):
        assert get_user_email() == "alice@example.com"


def test_get_user_email_returns_none_when_header_absent():
    from app.user import get_user_email
    app = Flask(__name__)
    with app.test_request_context():
        assert get_user_email() is None


def test_get_user_email_returns_none_when_header_blank():
    from app.user import get_user_email
    app = Flask(__name__)
    with app.test_request_context(headers={"X-Forwarded-User": "   "}):
        assert get_user_email() is None


def test_get_db_path_outside_request_returns_default():
    from app.user import get_db_path
    from app.config import DB_FILE
    assert get_db_path() == DB_FILE


def test_get_db_path_returns_g_db_path_in_request():
    from app.user import get_db_path
    app = Flask(__name__)
    with app.test_request_context():
        g.db_path = "/tmp/custom.db"
        assert get_db_path() == "/tmp/custom.db"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_user.py -v
```

Expected: all fail with `ModuleNotFoundError: No module named 'app.user'`

- [ ] **Step 3: Create `app/user.py`**

```python
import hashlib
import os
from typing import Optional

from flask import g, has_request_context, request

from app import config


def get_user_email() -> Optional[str]:
    if not has_request_context():
        return None
    raw = request.headers.get("X-Forwarded-User", "")
    value = raw.strip()
    return value if value else None


def resolve_db_path(email: str) -> str:
    digest = hashlib.sha256(email.encode()).hexdigest()
    return os.path.join(config.DATA_DIR, "users", digest, "session.db")


def get_db_path() -> str:
    if has_request_context() and hasattr(g, "db_path"):
        return g.db_path
    return config.DB_FILE
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_user.py -v
```

Expected: all 11 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/user.py tests/test_user.py
git commit -m "feat: add app/user.py with per-request identity helpers"
```

---

## Task 2: Add `db_path` parameter to `get_config` / `set_config`

**Files:**
- Modify: `app/db.py` (lines 146–165)

- [ ] **Step 1: Run existing config tests to establish baseline**

```
pytest tests/test_db_config.py -v -k "test_set_and_get_config or test_get_nonexistent or test_update_config or test_multiple_config"
```

Expected: 4 tests PASS

- [ ] **Step 2: Update `get_config` and `set_config` in `app/db.py`**

Replace the two functions at the bottom of [app/db.py](app/db.py):

```python
def get_config(key: str, db_path: str = DB_FILE) -> Optional[str]:
    with sqlite3.connect(db_path) as conn:
        cursor = conn.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
    return row[0] if row else None


def set_config(key: str, value: str, db_path: str = DB_FILE) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=?, updated_at=CURRENT_TIMESTAMP
            """,
            (key, value, value),
        )
        conn.commit()
```

- [ ] **Step 3: Verify existing tests still pass**

```
pytest tests/test_db_config.py tests/test_db_extra.py -v
```

Expected: all tests PASS (default param preserves existing behavior)

- [ ] **Step 4: Commit**

```bash
git add app/db.py
git commit -m "refactor: add optional db_path param to get_config and set_config"
```

---

## Task 3: Add `before_request` hook to `app/__init__.py`

**Files:**
- Modify: `app/__init__.py`
- Modify: `tests/test_user.py` (add integration test)

- [ ] **Step 1: Write the failing integration test**

Append to `tests/test_user.py`:

```python
def test_before_request_sets_default_db_for_anonymous(client):
    response = client.get("/api/config")
    assert response.status_code == 200


def test_before_request_creates_user_db_on_first_request(client, monkeypatch, tmp_path):
    import app.config as config_module
    monkeypatch.setattr(config_module, "DATA_DIR", str(tmp_path))
    from app.user import resolve_db_path

    email = "alice@example.com"
    response = client.get("/api/config", headers={"X-Forwarded-User": email})
    assert response.status_code == 200

    expected_db = resolve_db_path(email)
    assert os.path.exists(expected_db)


def test_before_request_user_db_is_isolated_from_default(client, monkeypatch, tmp_path):
    import app.config as config_module
    monkeypatch.setattr(config_module, "DATA_DIR", str(tmp_path))
    from app.user import resolve_db_path
    from app.db import set_config, get_config

    email = "bob@example.com"
    client.post(
        "/api/config",
        json={"selected_currencies": ["jp"], "reference_currency": "jp"},
        headers={"X-Forwarded-User": email},
    )

    user_db = resolve_db_path(email)
    assert get_config("SELECTED_CURRENCIES", user_db) == '["jp"]'
    assert get_config("SELECTED_CURRENCIES") is None
```

- [ ] **Step 2: Run to verify they fail**

```
pytest tests/test_user.py::test_before_request_creates_user_db_on_first_request tests/test_user.py::test_before_request_user_db_is_isolated_from_default -v
```

Expected: FAIL — the `before_request` hook doesn't exist yet, so `g.db_path` is never set and `get_db_path()` falls back to `DB_FILE` for all requests.

- [ ] **Step 3: Update `app/__init__.py`**

Replace the full file content:

```python
import logging

from flask import Flask

from app import config
from app.migrations import run_migrations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

_initialized_dbs: set[str] = set()


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")

    run_migrations(config.DB_FILE)
    _initialized_dbs.add(config.DB_FILE)

    from app.user import get_user_email, resolve_db_path

    @app.before_request
    def _set_db_path():
        from flask import g
        email = get_user_email()
        db_path = resolve_db_path(email) if email else config.DB_FILE
        g.db_path = db_path
        if db_path not in _initialized_dbs:
            run_migrations(db_path)
            _initialized_dbs.add(db_path)

    from app.web import web_bp
    app.register_blueprint(web_bp)

    return app
```

- [ ] **Step 4: Run the new tests to verify they pass**

```
pytest tests/test_user.py -v
```

Expected: all 14 tests PASS

- [ ] **Step 5: Commit**

```bash
git add app/__init__.py tests/test_user.py
git commit -m "feat: add before_request hook for per-user DB path isolation"
```

---

## Task 4: Update `app/web.py` and `tests/conftest.py`

**Files:**
- Modify: `app/web.py`
- Modify: `tests/conftest.py`

- [ ] **Step 1: Update `tests/conftest.py`**

The `client` fixture must patch both `app.config.DB_FILE` and `app.db.DB_FILE` to the same temp path so that direct `get_config(key)` calls (using `db.DB_FILE` default) and web-route calls (using `get_db_path()` → `config.DB_FILE`) hit the same database. Also remove the unused `temp_db_web` fixture.

Replace the full content of `tests/conftest.py`:

```python
import os
import tempfile

import pytest

from app import create_app


@pytest.fixture
def client(monkeypatch, tmp_path):
    """Flask test client fixture."""
    import app.config as config_module
    import app.db as db_module

    db_path = str(tmp_path / "test_client.db")
    monkeypatch.setattr(config_module, "DB_FILE", db_path)
    monkeypatch.setattr(db_module, "DB_FILE", db_path)

    app = create_app()
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_db(monkeypatch):
    """Temporary database that patches app.db.DB_FILE."""
    import app.db as db_module
    from app.migrations import run_migrations

    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    monkeypatch.setattr(db_module, "DB_FILE", path)
    run_migrations(path)

    yield path

    if os.path.exists(path):
        os.remove(path)
```

- [ ] **Step 2: Verify all existing tests still pass before touching web.py**

```
pytest tests/ -v --ignore=tests/test_user.py
```

Expected: all pass

- [ ] **Step 3: Update imports in `app/web.py`**

Replace the import block at the top of [app/web.py](app/web.py). Remove `DB_FILE` from the `app.config` import and add `app.user` imports:

Old:
```python
from app.config import COUNTRIES, DB_FILE, HEADERS, ICONS_DIR
from app.db import (
    clear_games_cache,
    get_cached_price_history,
    get_config,
    load_games_cache,
    save_price_history_cache,
    set_config,
)
```

New:
```python
from app.config import COUNTRIES, HEADERS, ICONS_DIR
from app.db import (
    clear_games_cache,
    get_cached_price_history,
    get_config,
    load_games_cache,
    save_price_history_cache,
    set_config,
)
from app.user import get_db_path, get_user_email
```

- [ ] **Step 4: Update `_get_selected_locales` and `_get_reference_locale`**

Replace both helper functions in [app/web.py](app/web.py):

```python
def _get_selected_locales() -> list[str]:
    raw = get_config("SELECTED_CURRENCIES", get_db_path())
    return json.loads(raw) if raw else ["br", "us"]


def _get_reference_locale(selected_locales: list[str]) -> str:
    ref = get_config("REFERENCE_CURRENCY", get_db_path())
    return ref if ref and ref in selected_locales else selected_locales[0]
```

- [ ] **Step 5: Update the `index` route**

Replace the `index()` function in [app/web.py](app/web.py):

```python
@web_bp.route("/")
def index():
    db_path = get_db_path()
    user_email = get_user_email()
    wishlist_url = get_config("WISHLIST_URL", db_path)
    wishlist_configured = wishlist_url is not None
    selected_locales = _get_selected_locales()
    reference_locale = _get_reference_locale(selected_locales)
    exchange_rates: dict = {}

    if not wishlist_configured:
        return render_template(
            "index.html",
            wishlist_configured=False,
            wishlist_error=False,
            wishlist_error_message=None,
            games=None,
            on_sale=0,
            unavailable=0,
            last_updated="Never",
            total=0,
            selected_locales=selected_locales,
            reference_locale=reference_locale,
            countries=COUNTRIES,
            exchange_rates=exchange_rates,
            user_email=user_email,
        )

    games, fetched_at = load_games_cache(db_path)
    if games is None:
        log.info("index: cache miss — fetching live data (locales=%s)", selected_locales)
        try:
            games, fetched_at = fetch_all_games(
                db_path,
                wishlist_url=wishlist_url,
                locales=selected_locales,
                reference_locale=reference_locale,
            )
        except requests.exceptions.ConnectionError:
            return (
                "<h1>Offline</h1><p>Could not connect to dekudeals.com. "
                "Check your internet connection and <a href='/'>try again</a>.</p>",
                503,
            )
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return render_template(
                    "index.html",
                    wishlist_configured=True,
                    wishlist_error=True,
                    wishlist_error_message="Wishlist not found. Please update your configuration.",
                    games=None,
                    on_sale=0,
                    unavailable=0,
                    last_updated="Never",
                    total=0,
                    selected_locales=selected_locales,
                    reference_locale=reference_locale,
                    countries=COUNTRIES,
                    exchange_rates={},
                    user_email=user_email,
                )
            return (
                "<h1>Error</h1><p>Failed to fetch wishlist data. "
                "<a href='/'>Try again</a>.</p>",
                502,
            )
        except requests.exceptions.RequestException:
            return (
                "<h1>Error</h1><p>Failed to fetch wishlist data. "
                "<a href='/'>Try again</a>.</p>",
                502,
            )
    else:
        log.info("index: cache hit — %d games from cache", len(games))
        threading.Thread(target=download_icons, args=(games,), daemon=True).start()

    last_updated = (
        datetime.fromtimestamp(fetched_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if fetched_at
        else "Never"
    )

    for locale in selected_locales:
        if locale != reference_locale:
            exchange_rates[locale] = fetch_rate(locale, reference_locale)

    _compute_best_buy(games, selected_locales, reference_locale)

    on_sale = sum(1 for g in games if g.get("has_discount"))
    unavailable = sum(1 for g in games if g.get("all_unavailable"))

    return render_template(
        "index.html",
        wishlist_configured=True,
        wishlist_error=False,
        wishlist_error_message=None,
        games=games,
        last_updated=last_updated,
        total=len(games),
        on_sale=on_sale,
        unavailable=unavailable,
        selected_locales=selected_locales,
        reference_locale=reference_locale,
        countries=COUNTRIES,
        exchange_rates=exchange_rates,
        user_email=user_email,
    )
```

- [ ] **Step 6: Update `get_config_api` and `set_config_api`**

Replace both route functions in [app/web.py](app/web.py):

```python
@web_bp.route("/api/config", methods=["GET"])
def get_config_api():
    db_path = get_db_path()
    url = get_config("WISHLIST_URL", db_path)
    selected_locales = _get_selected_locales()
    reference_locale = _get_reference_locale(selected_locales)
    return jsonify({
        "wishlist_url": url,
        "configured": url is not None,
        "selected_currencies": selected_locales,
        "reference_currency": reference_locale,
    })


@web_bp.route("/api/config", methods=["POST"])
def set_config_api():
    db_path = get_db_path()
    data = request.get_json()
    has_currencies = data and ("selected_currencies" in data or "reference_currency" in data)
    has_input = data and "input" in data

    if not has_currencies and not has_input:
        return jsonify({"success": False, "error": "Missing 'input' field"}), 400

    if has_currencies:
        selected = data.get("selected_currencies")
        if selected is not None:
            if not isinstance(selected, list) or len(selected) == 0:
                return jsonify({"success": False, "error": "At least one currency must be selected"}), 400
            invalid = [c for c in selected if c not in COUNTRIES]
            if invalid:
                return jsonify({"success": False, "error": f"Invalid locale codes: {invalid}"}), 400
            set_config("SELECTED_CURRENCIES", json.dumps(selected), db_path)
            clear_games_cache(db_path)

        reference = data.get("reference_currency")
        if reference is not None:
            current_raw = get_config("SELECTED_CURRENCIES", db_path)
            current_selected = json.loads(current_raw) if current_raw else []
            if reference not in current_selected:
                return jsonify({"success": False, "error": "Reference currency must be one of the selected currencies"}), 400
            set_config("REFERENCE_CURRENCY", reference, db_path)

    if not has_input:
        return jsonify({"success": True}), 200

    url, parse_error = _parse_wishlist_input(data["input"])
    if parse_error:
        return jsonify({"success": False, "error": parse_error}), 400

    validation_error = _validate_wishlist_url(url)
    if validation_error:
        return jsonify({"success": False, "error": validation_error}), 400

    set_config("WISHLIST_URL", url, db_path)
    return jsonify({"success": True, "wishlist_url": url}), 200
```

- [ ] **Step 7: Update `refresh`, `serve_icon`, and `price_history_api`**

Replace all three route functions in [app/web.py](app/web.py):

```python
@web_bp.route("/refresh", methods=["POST"])
def refresh():
    db_path = get_db_path()
    wishlist_url = get_config("WISHLIST_URL", db_path)
    selected_locales = _get_selected_locales()
    reference_locale = _get_reference_locale(selected_locales)
    fetch_all_games(
        db_path,
        wishlist_url=wishlist_url,
        locales=selected_locales,
        reference_locale=reference_locale,
    )
    return redirect(url_for("web.index"))


@web_bp.route("/icons/<path:slug>")
def serve_icon(slug: str):
    safe_slug = slug.replace("/", "_")[:80]
    _IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    base, ext = os.path.splitext(safe_slug)
    search_base = base if ext.lower() in _IMAGE_EXTS else safe_slug
    icon_found = None
    for fname in os.listdir(ICONS_DIR) if os.path.exists(ICONS_DIR) else []:
        if fname.startswith(search_base + "."):
            icon_found = os.path.join(ICONS_DIR, fname)
            break

    if not icon_found:
        try:
            import sqlite3 as _sqlite3
            with _sqlite3.connect(get_db_path()) as conn:
                row = conn.execute(
                    "SELECT image_url FROM games_cache WHERE slug = ?", (slug,)
                ).fetchone()
            if row and row[0]:
                resp = requests.get(row[0], headers=HEADERS, timeout=15)
                resp.raise_for_status()
                os.makedirs(ICONS_DIR, exist_ok=True)
                ext = _content_type_to_ext(resp.headers.get("content-type", ""))
                icon_found = _icon_path(slug, ext)
                with open(icon_found, "wb") as fh:
                    fh.write(resp.content)
        except Exception:
            pass

    if not icon_found or not os.path.exists(icon_found):
        return "", 404

    try:
        ext = os.path.splitext(icon_found)[1].lower()
        mimetype_map = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
        mimetype = mimetype_map.get(ext, "image/jpeg")
        return send_file(icon_found, mimetype=mimetype)
    except (FileNotFoundError, OSError):
        return "", 404


@web_bp.route("/price-history/<path:slug>")
def price_history_api(slug: str):
    db_path = get_db_path()
    currency = request.args.get("currency", "br").lower()
    locale = currency
    cached = get_cached_price_history(slug, currency, db_path)
    if cached is not None:
        return jsonify(cached)
    try:
        from app.scraper import build_session, set_locale

        sess = build_session(db_path, locale)
        set_locale(sess, locale)
        resp = sess.get(
            f"https://www.dekudeals.com/items/{slug}",
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        script_tag = soup.find("script", id="price_history_data")
        if not script_tag or not script_tag.string:
            return jsonify({"headers": [], "data": []})
        data = json.loads(script_tag.string)
        save_price_history_cache(slug, currency, data, db_path)
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
```

Note: `serve_icon` uses `import sqlite3 as _sqlite3` to avoid shadowing the module-level `sqlite3` import. Alternatively, since `sqlite3` is already imported at the top of `web.py`, just use `sqlite3.connect(get_db_path())` directly.

- [ ] **Step 8: Run the full test suite**

```
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 9: Commit**

```bash
git add app/web.py tests/conftest.py
git commit -m "feat: route all DB operations through per-user db_path in web.py"
```

---

## Task 5: Add user badge to `app/templates/index.html`

**Files:**
- Modify: `app/templates/index.html`

- [ ] **Step 1: Add `.user-badge` CSS**

Find the `.theme-btn:hover` rule (around line 70) and insert the badge style immediately after it:

```css
    .user-badge {
      background: var(--surface); color: var(--text-muted);
      border: 1px solid var(--border);
      padding: 0.45rem 0.7rem; border-radius: 6px;
      font-size: 0.75rem; white-space: nowrap;
      max-width: 200px; overflow: hidden; text-overflow: ellipsis;
      display: inline-flex; align-items: center; gap: 0.3rem;
      cursor: default;
    }
```

- [ ] **Step 2: Add user badge in the header**

Find the header section (around line 194) where the theme button appears:

```html
  <button class="theme-btn" id="themeToggle" title="Toggle light/dark theme">&#9790;</button>
  <select class="lang-select" id="langSelect" ...>
```

Insert the badge between the language select and the settings/setup button:

```html
  <button class="theme-btn" id="themeToggle" title="Toggle light/dark theme">&#9790;</button>
  <select class="lang-select" id="langSelect" title="Language / Idioma">
    <option value="en">🇺🇸 English</option>
    <option value="pt">🇧🇷 Português</option>
    <option value="es">🇪🇸 Español</option>
    <option value="ja">🇯🇵 日本語</option>
  </select>
  {% if user_email %}
  <span class="user-badge" title="{{ user_email }}">&#128100; {{ user_email }}</span>
  {% endif %}
  {% if not wishlist_configured %}
  <button class="btn" id="openModalBtn" type="button" data-i18n="btn.setupWishlist">Setup Wishlist</button>
  {% else %}
  <button class="theme-btn" id="openModalBtn" type="button" title="Change settings">&#9881;</button>
  {% endif %}
```

- [ ] **Step 3: Run tests to verify no regressions**

```
pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/templates/index.html
git commit -m "feat: show authenticated user email badge in page header"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| `X-Forwarded-User` header → per-user DB | Tasks 1, 3 |
| Hash: `sha256(email)`, full hex | Task 1 |
| DB path: `data/users/<hash>/session.db` | Task 1 |
| No header → fallback to default `session.db` | Task 3 |
| Lazy migration for new user DBs | Task 3 |
| `_initialized_dbs` to skip repeat migrations | Task 3 |
| `get_config`/`set_config` accept `db_path` | Task 2 |
| All web routes use `get_db_path()` | Task 4 |
| Icons remain globally shared | Task 4 (ICONS_DIR unchanged) |
| User email shown in header | Task 5 |
| `user_email=None` → badge not rendered | Task 5 |

**Placeholder scan:** No TBDs. All steps include complete code.

**Type consistency:**
- `resolve_db_path(email: str) -> str` — used in Task 1, Task 3 hook, Task 3 tests ✓
- `get_user_email() -> Optional[str]` — used in Task 1, Task 3 hook, Task 4 `index()` ✓
- `get_db_path() -> str` — used in Task 1, Tasks 4 all routes ✓
- `get_config(key, db_path=DB_FILE)` — used in Task 2, Task 4 all call sites ✓
- `set_config(key, value, db_path=DB_FILE)` — used in Task 2, Task 4 all call sites ✓
