import json
import os
import sqlite3
import time
from typing import Optional

import requests

from app.config import CACHE_TTL, DB_FILE, HISTORY_CACHE_TTL
from app.parsing import parse_release_date, parse_sale_end
import re


def save_cookies(jar: requests.cookies.RequestsCookieJar, db_path: str, locale: str = "br") -> None:
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    with sqlite3.connect(db_path) as conn:
        # Migrate old schema if locale column is missing
        cols = {r[1] for r in conn.execute("PRAGMA table_info(cookies)")}
        if cols and ("domain" not in cols or "locale" not in cols):
            conn.execute("DROP TABLE cookies")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cookies (
                name   TEXT NOT NULL,
                value  TEXT NOT NULL,
                domain TEXT NOT NULL DEFAULT '',
                path   TEXT NOT NULL DEFAULT '/',
                locale TEXT NOT NULL DEFAULT 'br',
                PRIMARY KEY (name, domain, path, locale)
            )
            """
        )
        rows = [(c.name, c.value, c.domain or "", c.path or "/", locale) for c in jar]
        conn.executemany(
            "INSERT OR REPLACE INTO cookies (name, value, domain, path, locale) VALUES (?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()


def load_cookies(db_path: str, locale: str = "br") -> list[tuple]:
    try:
        with sqlite3.connect(db_path) as conn:
            return conn.execute(
                "SELECT name, value, domain, path FROM cookies WHERE locale=?",
                (locale,),
            ).fetchall()
    except sqlite3.OperationalError:
        return []


def clear_games_cache(db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS games_cache")
        conn.commit()


def save_games_cache(games: list[dict], db_path: str) -> float:
    ts = time.time()
    with sqlite3.connect(db_path) as conn:
        conn.execute("DROP TABLE IF EXISTS games_cache")
        conn.execute(
            """
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
            )
            """
        )
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


def load_games_cache(db_path: str) -> tuple[Optional[list[dict]], Optional[float]]:
    try:
        with sqlite3.connect(db_path) as conn:
            try:
                rows = conn.execute(
                    "SELECT name, slug, prices, release_date, sale_end, image_url, icon_ext, fetched_at, sale_ends"
                    " FROM games_cache ORDER BY id"
                ).fetchall()
                has_sale_ends = True
            except sqlite3.OperationalError:
                rows = conn.execute(
                    "SELECT name, slug, prices, release_date, sale_end, image_url, icon_ext, fetched_at"
                    " FROM games_cache ORDER BY id"
                ).fetchall()
                has_sale_ends = False
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
                    "sale_ends": _normalize_sale_ends(r[8]) if has_sale_ends else {},
                }
                for r in rows
            ],
            fetched_at,
        )
    except sqlite3.OperationalError:
        return None, None


def get_cached_price_history(slug: str, currency: str, db_path: str) -> Optional[dict]:
    try:
        with sqlite3.connect(db_path) as conn:
            row = conn.execute(
                "SELECT data, fetched_at FROM price_history_cache"
                " WHERE slug=? AND currency=?",
                (slug, currency),
            ).fetchone()
        if row and time.time() - row[1] < HISTORY_CACHE_TTL:
            return json.loads(row[0])
    except sqlite3.OperationalError:
        pass
    return None


def save_price_history_cache(slug: str, currency: str, data: dict, db_path: str) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS price_history_cache (
                slug       TEXT NOT NULL,
                currency   TEXT NOT NULL DEFAULT 'brl',
                data       TEXT NOT NULL,
                fetched_at REAL NOT NULL,
                PRIMARY KEY (slug, currency)
            )
        """
        )
        conn.execute(
            "INSERT OR REPLACE INTO price_history_cache"
            " (slug, currency, data, fetched_at) VALUES (?,?,?,?)",
            (slug, currency, json.dumps(data), time.time()),
        )
        conn.commit()


def init_config_table() -> None:
    """Create the config table if it doesn't exist."""
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS config (
                key TEXT PRIMARY KEY,
                value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.commit()


def get_config(key: str) -> Optional[str]:
    """Retrieve a config value from the database."""
    with sqlite3.connect(DB_FILE) as conn:
        cursor = conn.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
    return row[0] if row else None


def set_config(key: str, value: str) -> None:
    """Save or update a config value."""
    with sqlite3.connect(DB_FILE) as conn:
        conn.execute(
            """
            INSERT INTO config (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET value=?, updated_at=CURRENT_TIMESTAMP
            """,
            (key, value, value),
        )
        conn.commit()
