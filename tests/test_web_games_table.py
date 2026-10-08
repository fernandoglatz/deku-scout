import json

import app.config as config_module
from app.db import save_games_cache, set_config


def _setup_games(db_path):
    set_config("WISHLIST_URL", "https://www.dekudeals.com/wishlist/test", db_path)
    set_config("SELECTED_CURRENCIES", json.dumps(["br"]), db_path)
    games = [
        {"name": "S1 Only", "slug": "s1", "switch1": True, "switch2": False, "prices": {}},
        {"name": "S2 Only", "slug": "s2", "switch1": False, "switch2": True, "prices": {}},
        {"name": "Both", "slug": "both", "switch1": True, "switch2": True, "prices": {}},
        {"name": "Neither", "slug": "none", "switch1": False, "switch2": False, "prices": {}},
    ]
    save_games_cache(games, db_path)


def test_games_table_no_filter_returns_all(client):
    _setup_games(config_module.DB_FILE)
    html = client.get("/api/games-table").get_data(as_text=True)
    for slug in ("s1", "s2", "both", "none"):
        assert f"/items/{slug}" in html


def test_games_table_switch1_filter(client):
    _setup_games(config_module.DB_FILE)
    html = client.get("/api/games-table?platform=switch1").get_data(as_text=True)
    assert "/items/s1" in html
    assert "/items/both" in html
    assert "/items/s2" not in html
    assert "/items/none" not in html


def test_games_table_switch2_filter(client):
    _setup_games(config_module.DB_FILE)
    html = client.get("/api/games-table?platform=switch2").get_data(as_text=True)
    assert "/items/s2" in html
    assert "/items/both" in html
    assert "/items/s1" not in html
    assert "/items/none" not in html


def test_games_table_both_filters_intersection(client):
    _setup_games(config_module.DB_FILE)
    html = client.get("/api/games-table?platform=switch1,switch2").get_data(as_text=True)
    assert "/items/both" in html
    assert "/items/s1" not in html
    assert "/items/s2" not in html
    assert "/items/none" not in html


def test_games_table_ignores_unknown_platform(client):
    _setup_games(config_module.DB_FILE)
    html = client.get("/api/games-table?platform=bogus").get_data(as_text=True)
    for slug in ("s1", "s2", "both", "none"):
        assert f"/items/{slug}" in html


def test_games_table_no_cache_returns_empty(client):
    set_config("WISHLIST_URL", "https://www.dekudeals.com/wishlist/test", config_module.DB_FILE)
    set_config("SELECTED_CURRENCIES", json.dumps(["br"]), config_module.DB_FILE)
    resp = client.get("/api/games-table")
    assert resp.status_code == 200
    assert "/items/" not in resp.get_data(as_text=True)


def _setup_mixed(db_path):
    set_config("WISHLIST_URL", "https://www.dekudeals.com/wishlist/test", db_path)
    set_config("SELECTED_CURRENCIES", json.dumps(["br"]), db_path)
    games = [
        {"name": "Discounted", "slug": "disc",
         "prices": {"br": {"current": "R$ 10", "original": "R$ 20", "discount": "-50%"}}},
        {"name": "Full Price", "slug": "full",
         "prices": {"br": {"current": "R$ 30"}}},
        {"name": "Gone", "slug": "gone",
         "prices": {"br": {"current": "Unavailable"}}},
    ]
    save_games_cache(games, db_path)


def test_games_table_sale_filter(client):
    _setup_mixed(config_module.DB_FILE)
    html = client.get("/api/games-table?sale=1").get_data(as_text=True)
    assert "/items/disc" in html
    assert "/items/full" not in html
    assert "/items/gone" not in html


def test_games_table_available_filter(client):
    _setup_mixed(config_module.DB_FILE)
    html = client.get("/api/games-table?available=1").get_data(as_text=True)
    assert "/items/disc" in html
    assert "/items/full" in html
    assert "/items/gone" not in html


def test_games_table_search_filter(client):
    _setup_mixed(config_module.DB_FILE)
    html = client.get("/api/games-table?q=full").get_data(as_text=True)
    assert "/items/full" in html
    assert "/items/disc" not in html
    assert "/items/gone" not in html


def test_games_table_combined_filters_are_anded(client):
    _setup_mixed(config_module.DB_FILE)
    # available AND search "disc" -> only the discounted game
    html = client.get("/api/games-table?available=1&q=disc").get_data(as_text=True)
    assert "/items/disc" in html
    assert "/items/full" not in html
    assert "/items/gone" not in html


def test_games_table_bestbuy_filter(client, monkeypatch):
    import app.web as web_module

    monkeypatch.setattr(web_module, "fetch_rate", lambda locale, ref: 1.0)
    set_config("WISHLIST_URL", "https://www.dekudeals.com/wishlist/test", config_module.DB_FILE)
    set_config("SELECTED_CURRENCIES", json.dumps(["br", "us"]), config_module.DB_FILE)
    save_games_cache([
        {"name": "Cheaper US", "slug": "us-win",
         "prices": {"br": {"current": "R$ 50"}, "us": {"current": "$ 10"}}},
        {"name": "Cheaper BR", "slug": "br-win",
         "prices": {"br": {"current": "R$ 5"}, "us": {"current": "$ 40"}}},
    ], config_module.DB_FILE)

    html = client.get("/api/games-table?bestbuy=us").get_data(as_text=True)
    assert "/items/us-win" in html
    assert "/items/br-win" not in html


def test_annotate_performance_base_and_sw2(temp_db):
    from app.db import save_performance_cache
    from app.web import _annotate_performance

    save_performance_cache({
        "arms": {"fps": 60, "label": "60fps", "patch_type": "Free Update"},
        "plain game": {"fps": 30, "label": "30fps", "patch_type": "Unpatched"},
    }, temp_db)

    games = [
        {"name": "ARMS", "switch2": False},          # SW2 via patch_type
        {"name": "Plain Game", "switch2": False},    # base fps, no SW2
        {"name": "Sw2 Flagged", "switch2": True},    # not in sheet -> empty
    ]
    _annotate_performance(games, temp_db)

    assert games[0]["perf_label"] == "60fps" and games[0]["perf_sw2"] is True
    assert games[0]["perf_sort"] == 60
    assert games[1]["perf_label"] == "30fps" and games[1]["perf_sw2"] is False
    assert games[2]["perf_label"] == "" and games[2]["perf_sort"] == 0
    assert games[2]["perf_sw2"] is False


def test_annotate_performance_sw2_flag_from_dekudeals(temp_db):
    from app.db import save_performance_cache
    from app.web import _annotate_performance

    save_performance_cache(
        {"g": {"fps": 30, "label": "30fps", "patch_type": "Unpatched"}}, temp_db)
    games = [{"name": "G", "switch2": True}]  # DekuDeals says SW2 version exists
    _annotate_performance(games, temp_db)
    assert games[0]["perf_sw2"] is True


def test_games_table_last_sale_column_uses_reference_locale(client):
    set_config("WISHLIST_URL", "https://www.dekudeals.com/wishlist/test", config_module.DB_FILE)
    set_config("SELECTED_CURRENCIES", json.dumps(["br"]), config_module.DB_FILE)
    save_games_cache([
        {"name": "Had Sale", "slug": "had", "prices": {"br": {"current": "R$ 30", "last_sale_end": "2026-06-25"}}},
        {"name": "Never", "slug": "never", "prices": {"br": {"current": "R$ 30"}}},
    ], config_module.DB_FILE)
    html = client.get("/api/games-table").get_data(as_text=True)
    assert 'class="last-sale"' in html
    assert 'data-date="2026-06-25"' in html


def _sp(fps, resolution="", patch_type="Switch 2", docked="", handheld=""):
    return {"fps": fps, "label": f"{fps}fps", "resolution": resolution,
            "patch_type": patch_type, "docked": docked, "handheld": handheld}


def test_annotate_performance_switchplaza_resolution_and_detail(temp_db, monkeypatch):
    import app.performance as perf
    from app.db import save_switchplaza_cache
    from app.web import _annotate_performance

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    save_switchplaza_cache({"twofold": _sp(60, "1440p", "Switch 2 Edition",
                                           "1440P 60 FPS", "1080P 60 FPS")}, temp_db)
    games = [{"name": "Twofold", "switch2": False}]
    _annotate_performance(games, temp_db)
    g = games[0]
    assert g["perf_label"] == "60fps" and g["perf_sort"] == 60
    assert g["perf_res"] == "1440p"
    assert g["perf_docked"] == "1440P 60 FPS" and g["perf_handheld"] == "1080P 60 FPS"
    assert g["perf_sw2"] is True


def test_annotate_performance_switchplaza_native_switch1_not_sw2(temp_db, monkeypatch):
    import app.performance as perf
    from app.db import save_switchplaza_cache
    from app.web import _annotate_performance

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    save_switchplaza_cache({"old game": _sp(30, "720p", "Switch 1")}, temp_db)
    games = [{"name": "Old Game", "switch2": False}]
    _annotate_performance(games, temp_db)
    assert games[0]["perf_sw2"] is False


def test_annotate_performance_switchplaza_beats_sheet_on_exact_match(temp_db, monkeypatch):
    import app.performance as perf
    from app.db import save_performance_cache, save_switchplaza_cache
    from app.web import _annotate_performance

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    save_performance_cache({"arms": {"fps": 30, "label": "30fps", "patch_type": "Unpatched"}}, temp_db)
    save_switchplaza_cache({"arms": _sp(60, "1080p")}, temp_db)
    games = [{"name": "ARMS", "switch2": False}]
    _annotate_performance(games, temp_db)
    assert games[0]["perf_label"] == "60fps" and games[0]["perf_res"] == "1080p"


def test_annotate_performance_exact_sheet_beats_fuzzy_switchplaza(temp_db, monkeypatch):
    import app.performance as perf
    from app.db import save_performance_cache, save_switchplaza_cache
    from app.web import _annotate_performance

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    save_performance_cache({"super game": {"fps": 30, "label": "30fps", "patch_type": ""}}, temp_db)
    save_switchplaza_cache({"super game deluxe": _sp(60, "4K")}, temp_db)
    games = [{"name": "Super Game", "switch2": False}]
    _annotate_performance(games, temp_db)
    assert games[0]["perf_label"] == "30fps"
    assert games[0]["perf_res"] == ""
    assert games[0]["perf_docked"] == "" and games[0]["perf_handheld"] == ""


def test_annotate_performance_switchplaza_never_fuzzy_matches(temp_db, monkeypatch):
    # Regression: fuzzy matching over the Switchplaza catalogue paired
    # "RESIDENT EVIL 3" with "Resident Evil Generation Pack", showing the wrong game's data.
    import app.performance as perf
    from app.db import save_switchplaza_cache
    from app.web import _annotate_performance

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    save_switchplaza_cache({
        "resident evil generation pack": _sp(60, "4K"),
        "super game deluxe": _sp(60, "4K"),
    }, temp_db)
    games = [{"name": "RESIDENT EVIL 3", "switch2": False},
             {"name": "Super Game", "switch2": False}]
    _annotate_performance(games, temp_db)
    assert [g["perf_label"] for g in games] == ["", ""]
    assert [g["perf_res"] for g in games] == ["", ""]


def test_annotate_performance_fuzzy_sheet_still_used_without_switchplaza_match(temp_db, monkeypatch):
    import app.performance as perf
    from app.db import save_performance_cache, save_switchplaza_cache
    from app.web import _annotate_performance

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    save_switchplaza_cache({"super game deluxe": _sp(60, "4K")}, temp_db)
    save_performance_cache({"super game deluxe": {"fps": 30, "label": "30fps", "patch_type": ""}}, temp_db)
    games = [{"name": "Super Game", "switch2": False}]
    _annotate_performance(games, temp_db)
    assert games[0]["perf_label"] == "30fps" and games[0]["perf_res"] == ""


def test_annotate_performance_switchplaza_edition_match(temp_db, monkeypatch):
    import app.performance as perf
    from app.db import save_switchplaza_cache
    from app.web import _annotate_performance

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    save_switchplaza_cache({"resident evil 4 gold edition": _sp(60, "4K")}, temp_db)
    games = [{"name": "Resident Evil 4", "switch2": False}]
    _annotate_performance(games, temp_db)
    assert games[0]["perf_label"] == "60fps" and games[0]["perf_res"] == "4K"


def test_annotate_performance_switch2_edition_title_matches_switchplaza_base(temp_db, monkeypatch):
    # Covers the old "<name> - Nintendo Switch 2 Edition" alias: a wishlist base
    # title still finds Switchplaza's Switch 2 Edition entry.
    import app.performance as perf
    from app.db import save_switchplaza_cache
    from app.web import _annotate_performance

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    save_switchplaza_cache({"twofold nintendo switch 2 edition": _sp(60, "1080p", "Switch 2 Edition")}, temp_db)
    games = [{"name": "Twofold", "switch2": False}]
    _annotate_performance(games, temp_db)
    assert games[0]["perf_res"] == "1080p" and games[0]["perf_sw2"] is True


def test_annotate_performance_switchplaza_edition_match_beats_exact_sheet(temp_db, monkeypatch):
    # Regression: "No Man's Sky" lost its Switch 2 Edition resolution to the
    # sheet's exact "Uncapped" row (the Switch 1 version on Switch 2 hardware).
    import app.performance as perf
    from app.db import save_performance_cache, save_switchplaza_cache
    from app.web import _annotate_performance

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    save_performance_cache({"no man s sky": {"fps": 999, "label": "Uncapped", "patch_type": ""}}, temp_db)
    save_switchplaza_cache({"no man s sky nintendo switch 2 edition":
                            _sp(30, "1440p", "Switch 2 Edition")}, temp_db)
    games = [{"name": "No Man's Sky", "switch2": False}]
    _annotate_performance(games, temp_db)
    assert games[0]["perf_label"] == "30fps" and games[0]["perf_res"] == "1440p"


def test_annotate_performance_switchplaza_edition_match_beats_fuzzy_sheet(temp_db, monkeypatch):
    import app.performance as perf
    from app.db import save_performance_cache, save_switchplaza_cache
    from app.web import _annotate_performance

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    save_performance_cache({"mortal shell complete": {"fps": 30, "label": "30fps", "patch_type": ""}}, temp_db)
    save_switchplaza_cache({"mortal shell": _sp(60, "1080p")}, temp_db)
    games = [{"name": "Mortal Shell: Complete Edition", "switch2": False}]
    _annotate_performance(games, temp_db)
    assert games[0]["perf_label"] == "60fps" and games[0]["perf_res"] == "1080p"


def test_annotate_performance_no_match_clears_resolution(temp_db, monkeypatch):
    import app.performance as perf
    from app.web import _annotate_performance

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    games = [{"name": "Unknown Game", "switch2": False}]
    _annotate_performance(games, temp_db)
    assert games[0]["perf_res"] == ""
    assert games[0]["perf_docked"] == "" and games[0]["perf_handheld"] == ""


def test_games_table_renders_resolution_and_mode_detail(client, monkeypatch):
    import app.performance as perf
    from app.db import save_switchplaza_cache

    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", "/nonexistent.json")
    db = config_module.DB_FILE
    set_config("WISHLIST_URL", "https://www.dekudeals.com/wishlist/test", db)
    set_config("SELECTED_CURRENCIES", json.dumps(["br"]), db)
    save_games_cache([
        {"name": "Twofold", "slug": "twofold", "switch1": False, "switch2": True, "prices": {}},
        {"name": "No Perf", "slug": "noperf", "switch1": True, "switch2": False, "prices": {}},
    ], db)
    save_switchplaza_cache({"twofold": _sp(60, "1440p", "Switch 2",
                                           "1440P 60 FPS / 4K 30 FPS", "1080P 60 FPS")}, db)
    html = client.get("/api/games-table").get_data(as_text=True)
    assert '<span class="perf-res">1440p</span>' in html
    assert 'data-perf-docked="1440P 60 FPS / 4K 30 FPS"' in html
    assert 'data-perf-handheld="1080P 60 FPS"' in html
    # Games without data render no resolution or detail attributes
    assert html.count('class="perf-res"') == 1
    assert html.count("data-perf-docked=") == 1
