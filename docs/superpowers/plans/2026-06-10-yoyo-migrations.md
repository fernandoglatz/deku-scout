# yoyo-migrations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace inline schema management in `db.py` with versioned SQL migration files using yoyo-migrations, applied automatically at app startup.

**Architecture:** A new `app/migrations.py` module owns the yoyo runner. Four SQL files in `migrations/` define the schema. `db.py` becomes pure query functions. `create_app()` calls `run_migrations(DB_FILE)` once at boot; yoyo's internal tracking table ensures idempotency.

**Tech Stack:** Python 3.10, SQLite (via `sqlite3`), yoyo-migrations ≥ 8.2, Flask, pytest

---

### Task 1: Add yoyo-migrations dependency

**Files:**
- Modify: `requirements.txt`

- [ ] **Step 1: Add yoyo-migrations to requirements.txt**

Open `requirements.txt` and add the line after `requests`:

```
yoyo-migrations>=8.2
```

Full file should read:
```
beautifulsoup4>=4.12
Flask>=3.0
gunicorn>=22.0
requests>=2.32
yoyo-migrations>=8.2

# dev / test
pytest>=8.0
```

- [ ] **Step 2: Install the dependency**

```bash
pip install yoyo-migrations
```

Expected: package installs without errors.

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "feat: add yoyo-migrations dependency"
```

---

### Task 2: Create SQL migration files

**Files:**
- Create: `migrations/V001__create_cookies_table.sql`
- Create: `migrations/V002__create_games_cache_table.sql`
- Create: `migrations/V003__create_price_history_cache_table.sql`
- Create: `migrations/V004__create_config_table.sql`

- [ ] **Step 1: Create migrations/ directory and V001**

Create `migrations/V001__create_cookies_table.sql`:

```sql
CREATE TABLE cookies (
    name   TEXT NOT NULL,
    value  TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT '',
    path   TEXT NOT NULL DEFAULT '/',
    locale TEXT NOT NULL DEFAULT 'br',
    PRIMARY KEY (name, domain, path, locale)
);

-- @rollback
DROP TABLE cookies;
```

- [ ] **Step 2: Create V002**

Create `migrations/V002__create_games_cache_table.sql`:

```sql
-- depends: V001__create_cookies_table

CREATE TABLE games_cache (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    slug         TEXT    NOT NULL DEFAULT '',
    prices       TEXT    NOT NULL DEFAULT '{}',
    release_date TEXT    NOT NULL DEFAULT '',
    sale_end     TEXT    NOT NULL DEFAULT '',
    image_url    TEXT    NOT NULL DEFAULT '',
    icon_ext     TEXT    NOT NULL DEFAULT '',
    fetched_at   REAL    NOT NULL,
    sale_ends    TEXT    NOT NULL DEFAULT '{}'
);

-- @rollback
DROP TABLE games_cache;
```

- [ ] **Step 3: Create V003**

Create `migrations/V003__create_price_history_cache_table.sql`:

```sql
-- depends: V002__create_games_cache_table

CREATE TABLE price_history_cache (
    slug       TEXT NOT NULL,
    currency   TEXT NOT NULL DEFAULT 'brl',
    data       TEXT NOT NULL,
    fetched_at REAL NOT NULL,
    PRIMARY KEY (slug, currency)
);

-- @rollback
DROP TABLE price_history_cache;
```

- [ ] **Step 4: Create V004**

Create `migrations/V004__create_config_table.sql`:

```sql
-- depends: V003__create_price_history_cache_table

CREATE TABLE config (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- @rollback
DROP TABLE config;
```

- [ ] **Step 5: Commit**

```bash
git add migrations/
git commit -m "feat: add SQL migration files V001-V004"
```

---

### Task 3: Implement app/migrations.py (TDD)

**Files:**
- Create: `tests/test_migrations.py`
- Create: `app/migrations.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_migrations.py`:

```python
import sqlite3


def test_run_migrations_creates_all_tables(tmp_path):
    from app.migrations import run_migrations

    db_path = str(tmp_path / "test.db")
    run_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '_yoyo%'"
            )
        }
    assert tables == {"cookies", "games_cache", "price_history_cache", "config"}


def test_run_migrations_idempotent(tmp_path):
    from app.migrations import run_migrations

    db_path = str(tmp_path / "test.db")
    run_migrations(db_path)
    run_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '_yoyo%'"
            )
        }
    assert tables == {"cookies", "games_cache", "price_history_cache", "config"}


def test_run_migrations_creates_data_directory(tmp_path):
    from app.migrations import run_migrations

    db_path = str(tmp_path / "nested" / "dir" / "test.db")
    run_migrations(db_path)

    with sqlite3.connect(db_path) as conn:
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '_yoyo%'"
        )}
    assert "config" in tables
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_migrations.py -v
```

Expected: 3 errors — `ModuleNotFoundError: No module named 'app.migrations'`

- [ ] **Step 3: Implement app/migrations.py**

Create `app/migrations.py`:

```python
import os

from yoyo import get_backend, read_migrations

_MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")


def run_migrations(db_path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(db_path)), exist_ok=True)
    backend = get_backend(f"sqlite:///{db_path}")
    migrations = read_migrations(_MIGRATIONS_DIR)
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_migrations.py -v
```

Expected: 3 passed

- [ ] **Step 5: Commit**

```bash
git add tests/test_migrations.py app/migrations.py
git commit -m "feat: implement app/migrations.py with yoyo runner"
```

---

### Task 4: Update test fixtures to run migrations

**Files:**
- Modify: `tests/conftest.py`

- [ ] **Step 1: Update temp_db and temp_db_web fixtures**

Replace the full contents of `tests/conftest.py` with:

```python
import os
import tempfile

import pytest

from app import create_app


@pytest.fixture
def client():
    """Flask test client fixture."""
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


@pytest.fixture
def temp_db_web(monkeypatch, tmp_path):
    """Temporary database that patches both app.db.DB_FILE and app.web.DB_FILE."""
    import app.db as db_module
    import app.web as web_module
    from app.migrations import run_migrations

    db_path = str(tmp_path / "test_web.db")
    monkeypatch.setattr(db_module, "DB_FILE", db_path)
    monkeypatch.setattr(web_module, "DB_FILE", db_path)
    run_migrations(db_path)

    yield db_path
```

- [ ] **Step 2: Run the full test suite**

```bash
pytest -v
```

Expected: most tests pass. Tests in `test_db_config.py` that call `init_config_table()` may still pass because the function still exists in `db.py`; the table now already exists from the fixture so those calls are no-ops. Note any failures.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: update fixtures to run migrations before tests"
```

---

### Task 5: Wire run_migrations into create_app()

**Files:**
- Modify: `app/__init__.py`

- [ ] **Step 1: Replace init_config_table with run_migrations**

Replace the full contents of `app/__init__.py` with:

```python
import logging

from flask import Flask

from app.config import DB_FILE
from app.migrations import run_migrations

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def create_app():
    app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")

    run_migrations(DB_FILE)

    from app.web import web_bp
    app.register_blueprint(web_bp)

    return app
```

- [ ] **Step 2: Run the full test suite**

```bash
pytest -v
```

Expected: all tests that passed before still pass.

- [ ] **Step 3: Commit**

```bash
git add app/__init__.py
git commit -m "feat: run migrations at app startup"
```

---

### Task 6: Clean up db.py — save_cookies

**Files:**
- Modify: `app/db.py`

- [ ] **Step 1: Remove schema management from save_cookies**

In `app/db.py`, replace the `save_cookies` function:

```python
def save_cookies(jar: RequestsCookieJar, db_path: str, locale: str = "br") -> None:
    with sqlite3.connect(db_path) as conn:
        rows = [(c.name, c.value, c.domain or "", c.path or "/", locale) for c in jar]
        conn.executemany(
            "INSERT OR REPLACE INTO cookies (name, value, domain, path, locale) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
```

Also remove the `import os` line at the top of `db.py` (it will no longer be used after all cleanup is done — hold off removing it until Task 9 to avoid a broken intermediate state).

- [ ] **Step 2: Run cookie-related tests**

```bash
pytest tests/test_db_extra.py -v -k "cookie"
```

Expected: all cookie tests pass.

- [ ] **Step 3: Commit**

```bash
git add app/db.py
git commit -m "refactor: remove inline schema from save_cookies"
```

---

### Task 7: Clean up db.py — games_cache functions

**Files:**
- Modify: `app/db.py`

- [ ] **Step 1: Replace save_games_cache — use DELETE instead of DROP+CREATE**

Replace the `save_games_cache` function in `app/db.py`:

```python
def save_games_cache(games: list[dict], db_path: str) -> float:
    ts = time.time()
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM games_cache")
        conn.executemany(
            "INSERT INTO games_cache"
            " (name, slug, prices, release_date, sale_end, image_url, icon_ext, fetched_at, sale_ends)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            [
                (
                    g["name"],
                    g["slug"],
                    json.dumps(g.get("prices", {})),
                    g.get("release_date", ""),
                    g.get("sale_end", ""),
                    g.get("image_url", ""),
                    g.get("icon_ext", ""),
                    ts,
                    json.dumps(g.get("sale_ends", {})),
                )
                for g in games
            ],
        )
        conn.commit()
    return ts
```

- [ ] **Step 2: Replace clear_games_cache — use DELETE instead of DROP**

Replace the `clear_games_cache` function in `app/db.py`:

```python
def clear_games_cache(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("DELETE FROM games_cache")
        conn.commit()
```

- [ ] **Step 3: Run games cache tests**

```bash
pytest tests/test_db_extra.py -v -k "games"
```

Expected: all games cache tests pass.

- [ ] **Step 4: Commit**

```bash
git add app/db.py
git commit -m "refactor: replace DROP+CREATE in games_cache with DELETE"
```

---

### Task 8: Clean up db.py — save_price_history_cache

**Files:**
- Modify: `app/db.py`

- [ ] **Step 1: Remove CREATE TABLE from save_price_history_cache**

Replace `save_price_history_cache` in `app/db.py`:

```python
def save_price_history_cache(slug: str, currency: str, data: dict, db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO price_history_cache"
            " (slug, currency, data, fetched_at) VALUES (?,?,?,?)",
            (slug, currency, json.dumps(data), time.time()),
        )
        conn.commit()
```

- [ ] **Step 2: Run price history tests**

```bash
pytest tests/test_db_extra.py -v -k "price_history"
```

Expected: all price history cache tests pass.

- [ ] **Step 3: Commit**

```bash
git add app/db.py
git commit -m "refactor: remove inline schema from save_price_history_cache"
```

---

### Task 9: Clean up db.py — load_games_cache, init_config_table, and os import

**Files:**
- Modify: `app/db.py`
- Modify: `tests/test_db_config.py`

- [ ] **Step 1: Simplify load_games_cache — remove sale_ends fallback**

Replace `load_games_cache` in `app/db.py`:

```python
def load_games_cache(db_path: str) -> tuple[Optional[list[dict]], Optional[float]]:
    try:
        with sqlite3.connect(db_path) as conn:
            rows = conn.execute(
                "SELECT name, slug, prices, release_date, sale_end, image_url, icon_ext, fetched_at, sale_ends"
                " FROM games_cache ORDER BY id"
            ).fetchall()
        if not rows:
            return None, None
        fetched_at = rows[0][7]
        if time.time() - fetched_at > CACHE_TTL:
            return None, fetched_at

        def _normalize_sale_end(val: str) -> str:
            if not val:
                return val
            if val.startswith("Sale ends "):
                return parse_sale_end(val[len("Sale ends "):].strip())
            return val

        def _normalize_release_date(val: str) -> str:
            if not val:
                return val
            if re.fullmatch(r"\d{4}(-\d{2}-\d{2})?", val):
                return val
            return parse_release_date(val)

        def _normalize_sale_ends(raw: str) -> dict:
            try:
                data = json.loads(raw) if raw else {}
                return {k: _normalize_sale_end(v) for k, v in data.items()}
            except (json.JSONDecodeError, AttributeError):
                return {}

        return (
            [
                {
                    "name": r[0],
                    "slug": r[1],
                    "prices": json.loads(r[2]) if r[2] else {},
                    "release_date": _normalize_release_date(r[3]),
                    "sale_end": _normalize_sale_end(r[4]),
                    "image_url": r[5],
                    "icon_ext": r[6],
                    "sale_ends": _normalize_sale_ends(r[8]),
                }
                for r in rows
            ],
            fetched_at,
        )
    except sqlite3.OperationalError:
        return None, None
```

- [ ] **Step 2: Delete init_config_table and remove os import**

In `app/db.py`:

1. Delete the entire `init_config_table` function (lines that define `def init_config_table() -> None:` through `conn.commit()`).

2. Remove `import os` from the top of the file.

The imports at the top of `app/db.py` should now be:

```python
import json
import sqlite3
import time
from typing import Optional

from requests.cookies import RequestsCookieJar

from app.config import CACHE_TTL, DB_FILE, HISTORY_CACHE_TTL
from app.parsing import parse_release_date, parse_sale_end
import re
```

- [ ] **Step 3: Update test_db_config.py — remove init_config_table calls**

In `tests/test_db_config.py`, make these changes:

1. Replace the import line:
   ```python
   # Old:
   from app.db import init_config_table, get_config, set_config
   # New:
   from app.db import get_config, set_config
   ```

2. Replace `test_init_config_table` with a test that verifies migrations create the config table:
   ```python
   def test_migrations_create_config_table(temp_db):
       """Config table exists after migrations run (via temp_db fixture)."""
       import sqlite3
       with sqlite3.connect(temp_db) as conn:
           cursor = conn.execute(
               "SELECT name FROM sqlite_master WHERE type='table' AND name='config'"
           )
           assert cursor.fetchone() is not None
   ```

3. Remove every `init_config_table()` call in the file. The table already exists because `temp_db` fixture runs `run_migrations()`. Search for all occurrences of `init_config_table()` and delete them (there are approximately 20 occurrences). Do NOT remove `set_config` or `get_config` calls — only `init_config_table()`.

4. Also remove the top-level `import app.db as db_module` line if it is no longer used (check — if no other reference to `db_module` exists in the file, remove it).

- [ ] **Step 4: Run the full test suite**

```bash
pytest -v
```

Expected: all tests pass. Zero failures.

- [ ] **Step 5: Commit**

```bash
git add app/db.py tests/test_db_config.py
git commit -m "refactor: remove all inline schema management from db.py"
```

---

### Task 10: Final verification

- [ ] **Step 1: Run full test suite one more time**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 2: Verify migration files are discovered correctly**

```bash
python -c "
from yoyo import read_migrations
import os
mdir = os.path.join(os.getcwd(), 'migrations')
migrations = list(read_migrations(mdir))
for m in migrations:
    print(m.id)
"
```

Expected output (order matters):
```
V001__create_cookies_table
V002__create_games_cache_table
V003__create_price_history_cache_table
V004__create_config_table
```

- [ ] **Step 3: Verify app starts and applies migrations to a fresh database**

```bash
DATA_DIR=/tmp/dekuscout_test python -c "
from app import create_app
app = create_app()
print('App started OK')
import sqlite3, os
db = '/tmp/dekuscout_test/session.db'
with sqlite3.connect(db) as conn:
    tables = [r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE '_yoyo%'\")]
    print('Tables:', sorted(tables))
"
```

Expected:
```
App started OK
Tables: ['config', 'cookies', 'games_cache', 'price_history_cache']
```

- [ ] **Step 4: Clean up temp database**

```bash
rm -rf /tmp/dekuscout_test
```
