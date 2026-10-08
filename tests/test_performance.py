from app.performance import normalize_name, extract_fps, parse_performance_csv


def test_normalize_strips_trademark_and_punctuation():
    assert normalize_name("The Legend of Zelda™: Tears of the Kingdom") == \
        "the legend of zelda tears of the kingdom"


def test_normalize_collapses_whitespace_and_case():
    assert normalize_name("  ARMS   ") == "arms"


def test_extract_fps_capped():
    assert extract_fps("Capped 60FPS, increased consistency") == (60, "60fps")
    assert extract_fps("Capped 30FPS, increased consistency") == (30, "30fps")


def test_extract_fps_uncapped():
    assert extract_fps("Uncapped, increased framerate") == (999, "Uncapped")


def test_extract_fps_none_cases():
    assert extract_fps("Unchanged / Not Noticeable") is None
    assert extract_fps("N/A") is None
    assert extract_fps("") is None


def test_parse_csv_extracts_games_and_prefers_docked():
    csv_text = (
        '"[NEWS] big merged\nheader blob","x","y","z","stuff"\n'
        '"ARMS","Nintendo","5.5.1","Free Update","Capped 60FPS, increased consistency",'
        '"Unchanged","Improved","Capped 60FPS","Unchanged"\n'
        '"Among Us","Innersloth","2025","Unpatched","N/A","N/A","N/A","N/A","N/A"\n'
        '"Handheld Only Game","Pub","1.0","Unpatched","N/A","N/A","N/A","Capped 30FPS","x"\n'
    )
    result = parse_performance_csv(csv_text)
    assert result["arms"] == {"fps": 60, "label": "60fps", "patch_type": "Free Update"}
    # Among Us has no numeric fps in docked or handheld -> excluded
    assert "among us" not in result
    # Falls back to handheld when docked is N/A
    assert result["handheld only game"]["fps"] == 30


def test_fetch_performance_sheet_parses_response(monkeypatch):
    import app.performance as perf

    class FakeResp:
        text = ('"name","pub","ver","patch","fps"\n'
                '"ARMS","Nintendo","5.5.1","Free Update","Capped 60FPS"\n')
        def raise_for_status(self):
            pass

    captured = {}

    def fake_get(url, headers=None, timeout=None):
        captured["url"] = url
        return FakeResp()

    monkeypatch.setattr(perf.requests, "get", fake_get)
    result = perf.fetch_performance_sheet(sheet_id="SID", gid="7")
    assert result["arms"]["fps"] == 60
    assert "SID" in captured["url"] and "gid=7" in captured["url"]
    assert "out:csv" in captured["url"]


# ---------------------------------------------------------------------------
# Resolution / Switchplaza
# ---------------------------------------------------------------------------

from app.performance import (
    normalize_resolution,
    parse_perf_profiles,
    parse_switchplaza_games,
)


def test_normalize_resolution_variants():
    assert normalize_resolution("1080P") == "1080p"
    assert normalize_resolution("4K") == "4K"
    assert normalize_resolution("4k") == "4K"
    assert normalize_resolution("<1080P") == "<1080p"
    assert normalize_resolution("720p (D)") == "720p"
    assert normalize_resolution("1080p-1200p") == "1080p"
    assert normalize_resolution("Unknown") == ""
    assert normalize_resolution("") == ""
    assert normalize_resolution(None) == ""


def test_parse_perf_profiles_resolution_and_fps():
    assert parse_perf_profiles("1080P 60 FPS") == [
        {"resolution": "1080p", "fps": 60, "label": ""}]


def test_parse_perf_profiles_multiple_with_labels():
    assert parse_perf_profiles("1080P 60 FPS (Performance) / 4K 30 FPS (Quality)") == [
        {"resolution": "1080p", "fps": 60, "label": "Performance"},
        {"resolution": "4K", "fps": 30, "label": "Quality"},
    ]


def test_parse_perf_profiles_fps_only_and_compact_forms():
    assert parse_perf_profiles("60 FPS") == [{"resolution": "", "fps": 60, "label": ""}]
    assert parse_perf_profiles("4K60") == [{"resolution": "4K", "fps": 60, "label": ""}]
    assert parse_perf_profiles("1080P 60FPS") == [{"resolution": "1080p", "fps": 60, "label": ""}]
    assert parse_perf_profiles("<1080P 30 FPS") == [{"resolution": "<1080p", "fps": 30, "label": ""}]


def test_parse_perf_profiles_resolution_only_has_no_fps():
    assert parse_perf_profiles("1080P") == [{"resolution": "1080p", "fps": None, "label": ""}]


def test_parse_perf_profiles_empty_values():
    assert parse_perf_profiles("TBA") == []
    assert parse_perf_profiles("N/A") == []
    assert parse_perf_profiles("") == []
    assert parse_perf_profiles(None) == []


def _sp_game(title, handheld="TBA", docked="TBA", console_type="Switch 2"):
    return {"title": title, "handheld_perf": handheld, "docked_perf": docked,
            "console_type": console_type}


def test_parse_switchplaza_prefers_docked_first_profile():
    result = parse_switchplaza_games([
        _sp_game("Twofold", "1080P 60 FPS", "1440P 60 FPS / 4K 30 FPS"),
    ])
    assert result["twofold"] == {
        "fps": 60, "label": "60fps", "resolution": "1440p",
        "patch_type": "Switch 2",
        "docked": "1440P 60 FPS / 4K 30 FPS", "handheld": "1080P 60 FPS",
    }


def test_parse_switchplaza_falls_back_to_handheld():
    result = parse_switchplaza_games([_sp_game("Dogpile", "120 FPS", "TBA")])
    assert result["dogpile"]["fps"] == 120
    assert result["dogpile"]["resolution"] == ""
    assert result["dogpile"]["docked"] == ""
    assert result["dogpile"]["handheld"] == "120 FPS"


def test_parse_switchplaza_skips_profiles_without_fps():
    # Docked lists only a resolution; handheld carries the fps.
    result = parse_switchplaza_games([_sp_game("G", "720P 30 FPS", "1080P")])
    assert result["g"]["fps"] == 30 and result["g"]["resolution"] == "720p"


def test_parse_switchplaza_skips_games_without_fps():
    result = parse_switchplaza_games([
        _sp_game("No Data"),
        _sp_game("Res Only", "1080P", "N/A"),
        _sp_game("", "60 FPS", "60 FPS"),
        {"title": "Null Perf", "handheld_perf": None, "docked_perf": None},
    ])
    assert result == {}


def test_parse_switchplaza_stores_titles_as_listed():
    # Edition variants are resolved at lookup time (edition_key), not stored as aliases.
    result = parse_switchplaza_games([
        _sp_game("FOUNTAINS - Nintendo Switch™ 2 Edition", "120 FPS", "120 FPS",
                 "Switch 2 Edition"),
    ])
    assert set(result) == {"fountains nintendo switch 2 edition"}
    assert result["fountains nintendo switch 2 edition"]["patch_type"] == "Switch 2 Edition"


# ---------------------------------------------------------------------------
# Edition-insensitive matching
# ---------------------------------------------------------------------------

from app.performance import build_edition_index, edition_key, edition_match


def test_edition_key_strips_generic_edition_descriptors():
    assert edition_key("resident evil 4 gold edition") == "resident evil 4"
    assert edition_key("moving out 2 deluxe edition") == "moving out 2"
    assert edition_key("mortal shell complete edition") == "mortal shell"
    assert edition_key("cyberpunk 2077 ultimate edition") == "cyberpunk 2077"
    assert edition_key("braid anniversary edition") == "braid"
    assert edition_key("tomba special edition") == "tomba"
    assert edition_key("shadow of mordor game of the year edition") == "shadow of mordor"


def test_edition_key_multi_word_descriptors():
    assert edition_key("game digital deluxe edition") == "game"
    assert edition_key("game 25th anniversary edition") == "game"
    assert edition_key("game collector s edition") == "game"


def test_edition_key_strips_stacked_suffixes():
    assert edition_key("braid anniversary edition nintendo switch 2 edition") == "braid"


def test_edition_key_keeps_unknown_descriptors():
    # Title-specific subtitles are part of the name, not generic edition words.
    assert edition_key("elden ring tarnished edition") == "elden ring tarnished edition"
    assert edition_key("devil may cry 5 devil hunter edition") == "devil may cry 5 devil hunter edition"


def test_edition_key_only_strips_a_trailing_suffix():
    name = "toy story 3 complete edition double pack"
    assert edition_key(name) == name


def test_edition_key_never_empties_a_name():
    assert edition_key("deluxe edition") == "deluxe edition"
    assert edition_key("") == ""


def test_build_edition_index_prefers_base_entry():
    rows = {
        "game nintendo switch 2 edition": {"fps": 60},
        "game": {"fps": 30},
        "game deluxe edition": {"fps": 40},
    }
    assert build_edition_index(rows) == {"game": {"fps": 30}}


def test_build_edition_index_is_order_independent():
    a = {"game gold edition": {"fps": 1}, "game deluxe edition": {"fps": 2}}
    b = dict(reversed(list(a.items())))
    assert build_edition_index(a) == build_edition_index(b)


def test_edition_match_both_directions_and_across_editions():
    index = build_edition_index({
        "resident evil 4 gold edition": {"fps": 60},
        "mortal shell": {"fps": 30},
        "grid legends deluxe edition": {"fps": 60},
    })
    assert edition_match("resident evil 4", index) == {"fps": 60}
    assert edition_match("mortal shell complete edition", index) == {"fps": 30}
    assert edition_match("grid legends gold edition", index) == {"fps": 60}


def test_edition_match_no_match_returns_none():
    index = build_edition_index({"resident evil 4 gold edition": {"fps": 60}})
    assert edition_match("resident evil 5", index) is None
    assert edition_match("", index) is None


def test_edition_match_switch2_edition_query_never_takes_base_game_data():
    # The base entry describes the Switch 1 version, not the Switch 2 Edition.
    index = build_edition_index({"fountains": {"fps": 30}})
    assert edition_match("fountains nintendo switch 2 edition", index) is None


def test_edition_match_base_query_finds_switch2_edition():
    index = build_edition_index({"fountains nintendo switch 2 edition": {"fps": 120}})
    assert edition_match("fountains", index) == {"fps": 120}


def test_fetch_switchplaza_parses_response(monkeypatch):
    import app.performance as perf

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [_sp_game("TOEM 2", "60 FPS", "1080P 60 FPS")],
                    "pagination": {"page": 1, "limit": 5000, "total": 1, "pages": 1}}

    captured = {}

    def fake_get(url, params=None, headers=None, timeout=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return FakeResp()

    monkeypatch.setattr(perf.requests, "get", fake_get)
    result = perf.fetch_switchplaza(user_agent="UA/1")
    assert result["toem 2"]["resolution"] == "1080p"
    assert captured["url"].startswith("https://switchplaza.net/api/games")
    assert captured["params"]["limit"] >= 5000
    assert captured["headers"]["User-Agent"] == "UA/1"


def test_fetch_switchplaza_follows_pagination(monkeypatch):
    import app.performance as perf

    pages = {
        1: [_sp_game("A", "30 FPS", "30 FPS")],
        2: [_sp_game("B", "60 FPS", "60 FPS")],
    }
    requested = []

    class FakeResp:
        def __init__(self, page):
            self.page = page

        def raise_for_status(self):
            pass

        def json(self):
            return {"data": pages[self.page],
                    "pagination": {"page": self.page, "pages": 2}}

    def fake_get(url, params=None, headers=None, timeout=None):
        requested.append(params["page"])
        return FakeResp(params["page"])

    monkeypatch.setattr(perf.requests, "get", fake_get)
    result = perf.fetch_switchplaza()
    assert requested == [1, 2]
    assert set(result) == {"a", "b"}


def test_fetch_switchplaza_propagates_http_error(monkeypatch):
    import pytest
    import requests as _requests
    import app.performance as perf

    class FakeResp:
        def raise_for_status(self):
            raise _requests.HTTPError("503")

    monkeypatch.setattr(perf.requests, "get", lambda *a, **k: FakeResp())
    with pytest.raises(_requests.HTTPError):
        perf.fetch_switchplaza()


def test_load_handheld_performance_includes_resolution(monkeypatch, tmp_path):
    import json as _json
    import app.performance as perf

    path = tmp_path / "handheld.json"
    path.write_text(_json.dumps({"games": [{
        "title": "Mortal Kombat 11",
        "performance": [
            {"mode": "Docked", "resolution": "720p", "framerate": "60 FPS", "fps": 60},
            {"mode": "Handheld", "resolution": "480p (D)", "framerate": "60 FPS", "fps": 60},
        ],
    }]}))
    monkeypatch.setattr(perf, "_HANDED_DATA_PATH", str(path))
    result = perf.load_handheld_performance()
    assert result["mortal kombat 11"] == {
        "fps": 60, "label": "60fps", "resolution": "480p",
        "docked": "720p 60 FPS", "handheld": "480p (D) 60 FPS",
    }
