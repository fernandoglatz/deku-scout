# Database Migrations with yoyo-migrations

**Date:** 2026-06-10  
**Status:** Approved

## Goal

Replace inline schema management in `db.py` with versioned SQL migration files using yoyo-migrations. The database is created from scratch via migrations — no defensive `CREATE TABLE IF NOT EXISTS` hacks or column-check workarounds.

## Approach

Option B: separate `app/migrations.py` module as the migration runner. `db.py` becomes query functions only; schema lifecycle lives exclusively in `migrations/`.

## File & Folder Structure

```
migrations/
  V001__create_cookies_table.sql
  V002__create_games_cache_table.sql
  V003__create_price_history_cache_table.sql
  V004__create_config_table.sql
app/
  migrations.py   — yoyo runner (new)
  db.py           — query functions only (schema removed)
  __init__.py     — calls run_migrations() at startup
requirements.txt  — add yoyo-migrations
```

## Migration Files

Flyway-style naming (`VXXX__description.sql`). Each file contains a plain `CREATE TABLE` (no `IF NOT EXISTS`) and a `-- @rollback` block.

Tables to create (schemas match current `db.py`):

- **V001** — `cookies` (name, value, domain, path, locale; PK on all five)
- **V002** — `games_cache` (id, name, slug, prices, release_date, sale_end, image_url, icon_ext, fetched_at, sale_ends)
- **V003** — `price_history_cache` (slug, currency, data, fetched_at; PK on slug+currency)
- **V004** — `config` (key, value, created_at, updated_at; PK on key)

yoyo tracks applied migrations in its own `_yoyo_migration` table and skips already-applied files on subsequent startups.

## app/migrations.py

```python
import os
from yoyo import get_backend, read_migrations

_MIGRATIONS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "migrations")

def run_migrations(db_path: str) -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    backend = get_backend(f"sqlite:///{db_path}")
    migrations = read_migrations(_MIGRATIONS_DIR)
    with backend.lock():
        backend.apply_migrations(backend.to_apply(migrations))
```

## create_app() Wiring

`app/__init__.py` calls `run_migrations(DB_FILE)` at startup instead of the old `init_config_table()`. Migrations apply automatically on every boot; yoyo is idempotent so already-applied migrations are skipped.

## db.py Cleanup

Remove all schema management from `db.py`:

- `init_config_table()` — deleted entirely
- `save_cookies` — remove column-check hack and `CREATE TABLE IF NOT EXISTS`
- `save_games_cache` — change `DROP TABLE + CREATE TABLE` to `DELETE FROM games_cache` then INSERT (same cache-replacement behavior, no inline schema)
- `clear_games_cache` — change `DROP TABLE IF EXISTS games_cache` to `DELETE FROM games_cache`
- `save_price_history_cache` — remove `CREATE TABLE IF NOT EXISTS`
- `load_games_cache` — remove the try/except fallback for missing `sale_ends` column; column is guaranteed by V002

## Testing

Existing `temp_db` and `temp_db_web` fixtures in `conftest.py` patch `DB_FILE`. They will need to call `run_migrations(path)` on the temp path before tests run, so the schema exists. The fixtures should be updated to call the migration runner after creating the temp file.

## Dependencies

Add to `requirements.txt`:
```
yoyo-migrations>=8.2
```
