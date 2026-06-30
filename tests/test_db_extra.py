import pytest
import requests


# ── cookies ───────────────────────────────────────────────────────────────────

def test_save_and_load_cookies_round_trip(temp_db):
    from app.db import save_cookies, load_cookies

    jar = requests.cookies.RequestsCookieJar()
    jar.set("session", "abc123", domain="www.dekudeals.com", path="/")
    save_cookies(jar, temp_db, locale="br")

    rows = load_cookies(temp_db, locale="br")
    assert len(rows) == 1
    name, value, domain, path = rows[0]
    assert name == "session"
    assert value == "abc123"
    assert domain == "www.dekudeals.com"
    assert path == "/"


def test_load_cookies_returns_empty_when_no_table(temp_db):
    from app.db import load_cookies

    rows = load_cookies(temp_db, locale="br")
    assert rows == []


def test_save_cookies_locale_isolation(temp_db):
    from app.db import save_cookies, load_cookies

    jar_br = requests.cookies.RequestsCookieJar()
    jar_br.set("br_cookie", "br_val", domain="d.com", path="/")

    jar_us = requests.cookies.RequestsCookieJar()
    jar_us.set("us_cookie", "us_val", domain="d.com", path="/")

    save_cookies(jar_br, temp_db, locale="br")
    save_cookies(jar_us, temp_db, locale="us")

    br_rows = load_cookies(temp_db, locale="br")
    us_rows = load_cookies(temp_db, locale="us")

    assert any(r[0] == "br_cookie" for r in br_rows)
    assert not any(r[0] == "us_cookie" for r in br_rows)
    assert any(r[0] == "us_cookie" for r in us_rows)
    assert not any(r[0] == "br_cookie" for r in us_rows)


def test_save_cookies_replaces_existing(temp_db):
    from app.db import save_cookies, load_cookies

    jar1 = requests.cookies.RequestsCookieJar()
    jar1.set("token", "old", domain="d.com", path="/")
    save_cookies(jar1, temp_db, locale="br")

    jar2 = requests.cookies.RequestsCookieJar()
    jar2.set("token", "new", domain="d.com", path="/")
    save_cookies(jar2, temp_db, locale="br")

    rows = load_cookies(temp_db, locale="br")
    values = [r[1] for r in rows if r[0] == "token"]
    assert values == ["new"]


def test_save_cookies_empty_jar(temp_db):
    from app.db import save_cookies, load_cookies

    jar = requests.cookies.RequestsCookieJar()
    save_cookies(jar, temp_db, locale="br")

    rows = load_cookies(temp_db, locale="br")
    assert rows == []


# ── price history cache ───────────────────────────────────────────────────────

def test_save_and_get_price_history_cache(temp_db):
    from app.db import save_price_history_cache, get_cached_price_history

    data = {"headers": ["Date", "Price"], "data": [["2024-01-01", "4.99"]]}
    save_price_history_cache("game-slug", "br", data, temp_db)

    result = get_cached_price_history("game-slug", "br", temp_db)
    assert result == data


def test_get_price_history_cache_returns_none_when_empty(temp_db):
    from app.db import get_cached_price_history

    result = get_cached_price_history("nonexistent", "br", temp_db)
    assert result is None


def test_get_price_history_cache_expired(temp_db, monkeypatch):
    from app.db import save_price_history_cache, get_cached_price_history
    import app.db as db_module

    monkeypatch.setattr(db_module, "HISTORY_CACHE_TTL", -1)
    data = {"headers": [], "data": []}
    save_price_history_cache("game-slug", "br", data, temp_db)

    result = get_cached_price_history("game-slug", "br", temp_db)
    assert result is None


def test_price_history_cache_keyed_by_currency(temp_db):
    from app.db import save_price_history_cache, get_cached_price_history

    br_data = {"headers": ["Date", "BRL"], "data": []}
    us_data = {"headers": ["Date", "USD"], "data": []}
    save_price_history_cache("game", "br", br_data, temp_db)
    save_price_history_cache("game", "us", us_data, temp_db)

    assert get_cached_price_history("game", "br", temp_db) == br_data
    assert get_cached_price_history("game", "us", temp_db) == us_data


def test_price_history_cache_overwrite(temp_db):
    from app.db import save_price_history_cache, get_cached_price_history

    save_price_history_cache("g", "br", {"v": 1}, temp_db)
    save_price_history_cache("g", "br", {"v": 2}, temp_db)

    assert get_cached_price_history("g", "br", temp_db) == {"v": 2}


# ── games cache ───────────────────────────────────────────────────────────────

def test_clear_games_cache_empties_table(temp_db):
    from app.db import save_games_cache, load_games_cache, clear_games_cache

    games = [{"name": "Game", "slug": "game", "prices": {}, "release_date": "",
              "sale_end": "", "image_url": "", "icon_ext": "", "sale_ends": {}}]
    save_games_cache(games, temp_db)
    clear_games_cache(temp_db)

    result, ts, is_stale = load_games_cache(temp_db)
    assert result is None
    assert ts is None
    assert is_stale is False


def test_load_games_cache_expired_returns_stale(temp_db, monkeypatch):
    from app.db import save_games_cache, load_games_cache
    import app.db as db_module

    monkeypatch.setattr(db_module, "CACHE_TTL", -1)
    games = [{"name": "Game", "slug": "game", "prices": {}, "release_date": "",
              "sale_end": "", "image_url": "", "icon_ext": "", "sale_ends": {}}]
    ts = save_games_cache(games, temp_db)

    result, fetched_at, is_stale = load_games_cache(temp_db)
    assert result is not None
    assert abs(fetched_at - ts) < 1
    assert is_stale is True


def test_save_games_cache_preserves_sale_ends(temp_db):
    from app.db import save_games_cache, load_games_cache

    games = [{
        "name": "Game",
        "slug": "game",
        "prices": {"br": {"current": "R$ 50", "original": "R$ 100", "discount": "-50%"}},
        "release_date": "2024-01-01",
        "sale_end": "",
        "image_url": "",
        "icon_ext": "",
        "sale_ends": {"br": "2026-06-15T23:59:59Z"},
    }]
    save_games_cache(games, temp_db)
    loaded, _, _stale = load_games_cache(temp_db)

    assert loaded[0]["sale_ends"]["br"] == "2026-06-15T23:59:59Z"


def test_save_games_cache_multiple_games(temp_db):
    from app.db import save_games_cache, load_games_cache

    games = [
        {"name": f"Game {i}", "slug": f"game-{i}", "prices": {}, "release_date": "",
         "sale_end": "", "image_url": "", "icon_ext": "", "sale_ends": {}}
        for i in range(5)
    ]
    save_games_cache(games, temp_db)
    loaded, _, _stale = load_games_cache(temp_db)

    assert len(loaded) == 5
    assert loaded[0]["name"] == "Game 0"
    assert loaded[4]["name"] == "Game 4"


# ── games_cache platform flags ─────────────────────────────────────────────────

def test_games_cache_persists_platform_flags(temp_db):
    from app.db import save_games_cache, load_games_cache

    games = [
        {"name": "Switch 1 Game", "slug": "s1", "switch1": True, "switch2": False},
        {"name": "Switch 2 Game", "slug": "s2", "switch1": False, "switch2": True},
        {"name": "Both Game", "slug": "both", "switch1": True, "switch2": True},
        {"name": "Neither Game", "slug": "none"},
    ]
    save_games_cache(games, temp_db)

    loaded, _, _ = load_games_cache(temp_db)
    by_slug = {g["slug"]: g for g in loaded}
    assert by_slug["s1"]["switch1"] is True and by_slug["s1"]["switch2"] is False
    assert by_slug["s2"]["switch1"] is False and by_slug["s2"]["switch2"] is True
    assert by_slug["both"]["switch1"] is True and by_slug["both"]["switch2"] is True
    assert by_slug["none"]["switch1"] is False and by_slug["none"]["switch2"] is False
