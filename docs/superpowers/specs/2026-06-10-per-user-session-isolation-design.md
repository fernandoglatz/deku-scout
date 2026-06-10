# Per-User Session Isolation via Auth Proxy Header

**Date:** 2026-06-10
**Status:** Approved

## Summary

DekuScout will be deployed behind an auth proxy that injects an `X-Forwarded-User` header containing the user's email. When this header is present, each user gets a fully isolated SQLite database (config, games cache, cookies, price history). Icons remain globally shared. When the header is absent, the app falls back to the existing default `session.db` — preserving single-user/local-dev behavior unchanged.

## Architecture

### New module: `app/user.py`

Owns all identity logic. No Flask imports leak into callers that don't need them.

- `get_user_email() -> Optional[str]` — reads `X-Forwarded-User` from the current Flask request headers; strips whitespace; returns `None` if absent or blank.
- `resolve_db_path(email: str) -> str` — pure function; returns `data/users/<sha256(email)>/session.db`. Hash is `hashlib.sha256(email.encode()).hexdigest()` (full 64-char lowercase hex).
- `get_db_path() -> str` — reads the current request's `g.db_path`; safe to call outside a request context (returns `DB_FILE`).

### Flask integration: `app/__init__.py`

A `before_request` hook runs on every request:
1. Calls `get_user_email()`.
2. Computes the DB path (user-specific or default).
3. Stores it in `flask.g.db_path`.
4. If the path has not been seen before in this process, runs `run_migrations()` on it and records it in a module-level `_initialized_dbs: set[str]`.

The `_initialized_dbs` set prevents redundant migration checks on every request. Yoyo's runner is safe for concurrent first-requests on the same DB (SQLite locking handles it).

### Changes to `app/db.py`

`get_config(key)` and `set_config(key, value)` currently use the hardcoded `DB_FILE` constant. Both gain a `db_path` parameter with a default of `DB_FILE` for backwards compatibility. All call sites in `web.py` pass `get_db_path()` explicitly — consistent with how all other DB functions already work.

### Changes to `app/web.py`

Every direct reference to `DB_FILE` is replaced with `get_db_path()` from `app.user`. The `index()` route also reads `get_user_email()` and passes it to the template as `user_email`.

### Frontend: `app/templates/index.html`

When `user_email` is set, a small user badge is rendered in the header between the language selector and the settings button. Styled as a pill (border, muted color, `👤` icon), with `max-width` and `text-overflow: ellipsis` to handle long email addresses. Not rendered when `user_email` is `None`.

## Data Layout

```
data/
  session.db                        ← default (no header / local dev)
  users/
    <sha256(email-a)>/
      session.db                    ← user A's isolated DB
    <sha256(email-b)>/
      session.db                    ← user B's isolated DB
  icons/                            ← shared globally, unchanged
```

## Edge Cases

| Case | Behavior |
|---|---|
| Header absent or blank | Falls back to default `session.db` |
| Header with whitespace | Stripped; if empty after strip, treated as absent |
| Two simultaneous first requests for same user | Yoyo migration runner is concurrency-safe via SQLite locking; `_initialized_dbs` prevents repeat calls after init |
| Long email in header | Display truncated with ellipsis; DB path always uses hash |
| Special chars in email | Email used only for display; hash is always filesystem-safe |

## No New Migration Required

All user DBs use the same schema. Existing migrations V001–V004 are applied lazily on first access per user. No new migration file needed.

## Files Changed

| File | Change |
|---|---|
| `app/user.py` | **New** — identity helpers |
| `app/__init__.py` | Add `before_request` hook, `_initialized_dbs` set |
| `app/db.py` | Add `db_path` param to `get_config` / `set_config` |
| `app/web.py` | Replace `DB_FILE` with `get_db_path()`; pass `user_email` to template |
| `app/templates/index.html` | Add user badge in header |
