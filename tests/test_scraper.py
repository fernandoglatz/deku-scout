import os
import pytest


# ── _content_type_to_ext ──────────────────────────────────────────────────────

def test_content_type_png():
    from app.scraper import _content_type_to_ext
    assert _content_type_to_ext("image/png") == "png"


def test_content_type_webp():
    from app.scraper import _content_type_to_ext
    assert _content_type_to_ext("image/webp") == "webp"


def test_content_type_gif():
    from app.scraper import _content_type_to_ext
    assert _content_type_to_ext("image/gif") == "gif"


def test_content_type_jpeg_returns_jpg():
    from app.scraper import _content_type_to_ext
    assert _content_type_to_ext("image/jpeg") == "jpg"


def test_content_type_unknown_defaults_to_jpg():
    from app.scraper import _content_type_to_ext
    assert _content_type_to_ext("application/octet-stream") == "jpg"


def test_content_type_case_insensitive():
    from app.scraper import _content_type_to_ext
    assert _content_type_to_ext("IMAGE/PNG") == "png"


# ── _icon_path ────────────────────────────────────────────────────────────────

def test_icon_path_basic():
    from app.scraper import _icon_path
    from app.config import ICONS_DIR
    result = _icon_path("some-slug", "jpg")
    assert result == os.path.join(ICONS_DIR, "some-slug.jpg")


def test_icon_path_replaces_slash_with_underscore():
    from app.scraper import _icon_path
    from app.config import ICONS_DIR
    result = _icon_path("some/slug", "png")
    assert result == os.path.join(ICONS_DIR, "some_slug.png")


def test_icon_path_truncates_long_slug():
    from app.scraper import _icon_path
    long_slug = "a" * 100
    result = _icon_path(long_slug, "jpg")
    basename = os.path.basename(result)
    assert basename == "a" * 80 + ".jpg"


# ── _existing_icon_ext ────────────────────────────────────────────────────────

def test_existing_icon_ext_not_found(tmp_path, monkeypatch):
    from app.scraper import _existing_icon_ext
    import app.scraper as scraper_module
    monkeypatch.setattr(scraper_module, "ICONS_DIR", str(tmp_path))
    assert _existing_icon_ext("some-game") == ""


def test_existing_icon_ext_found_jpg(tmp_path, monkeypatch):
    from app.scraper import _existing_icon_ext
    import app.scraper as scraper_module
    monkeypatch.setattr(scraper_module, "ICONS_DIR", str(tmp_path))
    (tmp_path / "some-game.jpg").write_bytes(b"")
    assert _existing_icon_ext("some-game") == "jpg"


def test_existing_icon_ext_found_png(tmp_path, monkeypatch):
    from app.scraper import _existing_icon_ext
    import app.scraper as scraper_module
    monkeypatch.setattr(scraper_module, "ICONS_DIR", str(tmp_path))
    (tmp_path / "other-game.png").write_bytes(b"")
    assert _existing_icon_ext("other-game") == "png"


def test_existing_icon_ext_no_icons_dir(monkeypatch):
    from app.scraper import _existing_icon_ext
    import app.scraper as scraper_module
    monkeypatch.setattr(scraper_module, "ICONS_DIR", "/nonexistent/path/icons")
    assert _existing_icon_ext("game") == ""


# ── extract_games ──────────────────────────────────────────────────────────────

_BASE_HTML = """
<html><body>
<div class="view-list">
  <div class="col">
    <div class="d-flex flex-column flex-grow-1">
      <a class="main-link" href="/items/game-slug">Game Title</a>
      <div>October 1, 2026</div>
    </div>
    <img src="https://cdn.example.com/cover.jpg">
    <s class="text-muted">$9.99</s>
    <strong>$4.99</strong>
    <span class="badge-danger">-50%</span>
  </div>
</div>
</body></html>
"""


def test_extract_games_basic_fields():
    from app.scraper import extract_games
    games = extract_games(_BASE_HTML)
    assert len(games) == 1
    g = games[0]
    assert g["name"] == "Game Title"
    assert g["slug"] == "game-slug"
    assert g["original"] == "$9.99"
    assert g["current"] == "$4.99"
    assert g["discount"] == "-50%"
    assert g["image_url"] == "https://cdn.example.com/cover.jpg"
    assert g["release_date"] == "2026-10-01"


def test_extract_games_no_view_list_raises():
    from app.scraper import extract_games
    with pytest.raises(RuntimeError, match=r"\.view-list"):
        extract_games("<html><body><div>Nothing here</div></body></html>")


def test_extract_games_empty_list():
    from app.scraper import extract_games
    html = "<html><body><div class='view-list'></div></body></html>"
    assert extract_games(html) == []


def test_extract_games_unavailable_price():
    from app.scraper import extract_games
    html = """
    <html><body>
    <div class="view-list">
      <div class="col">
        <div class="d-flex flex-column flex-grow-1">
          <a class="main-link" href="/items/no-price">No Price Game</a>
        </div>
      </div>
    </div>
    </body></html>
    """
    games = extract_games(html)
    assert len(games) == 1
    assert games[0]["current"] == "Unavailable"
    assert games[0]["discount"] == ""
    assert games[0]["original"] == ""


def test_extract_games_skips_non_items_href():
    from app.scraper import extract_games
    html = """
    <html><body>
    <div class="view-list">
      <div class="col">
        <div class="d-flex flex-column flex-grow-1">
          <a class="main-link" href="/other/link">Skip Me</a>
        </div>
      </div>
    </div>
    </body></html>
    """
    assert extract_games(html) == []


def test_extract_games_with_sale_end():
    from app.scraper import extract_games
    html = """
    <html><body>
    <div class="view-list">
      <div class="col">
        <div class="d-flex flex-column flex-grow-1">
          <a class="main-link" href="/items/sale-game">Sale Game</a>
          <div>October 1, 2026 Sale ends in 2 days</div>
        </div>
        <strong>$4.99</strong>
      </div>
    </div>
    </body></html>
    """
    games = extract_games(html)
    assert len(games) == 1
    assert games[0]["release_date"] == "2026-10-01"
    assert games[0]["sale_end"]  # non-empty since "in 2 days" is relative to now


def test_extract_games_multiple_items():
    from app.scraper import extract_games
    html = """
    <html><body>
    <div class="view-list">
      <div class="col">
        <div class="d-flex flex-column flex-grow-1">
          <a class="main-link" href="/items/game-a">Game A</a>
        </div>
        <strong>$1.99</strong>
      </div>
      <div class="col">
        <div class="d-flex flex-column flex-grow-1">
          <a class="main-link" href="/items/game-b">Game B</a>
        </div>
        <strong>$2.99</strong>
      </div>
    </div>
    </body></html>
    """
    games = extract_games(html)
    assert len(games) == 2
    assert games[0]["slug"] == "game-a"
    assert games[1]["slug"] == "game-b"


def test_extract_games_image_data_src_fallback():
    from app.scraper import extract_games
    html = """
    <html><body>
    <div class="view-list">
      <div class="col">
        <div class="d-flex flex-column flex-grow-1">
          <a class="main-link" href="/items/lazy-img">Lazy Game</a>
        </div>
        <img data-src="https://cdn.example.com/lazy.jpg">
        <strong>$4.99</strong>
      </div>
    </div>
    </body></html>
    """
    games = extract_games(html)
    assert games[0]["image_url"] == "https://cdn.example.com/lazy.jpg"


# ── merge_prices (extended) ───────────────────────────────────────────────────

def test_merge_prices_sale_ends_per_locale():
    from app.scraper import merge_prices
    br_games = [{"name": "Game A", "slug": "game-a", "original": "R$ 100", "current": "R$ 50",
                 "discount": "-50%", "release_date": "2024-01-01",
                 "sale_end": "2026-06-15T23:59:59Z", "image_url": ""}]
    us_games = [{"name": "Game A", "slug": "game-a", "original": "$9.99", "current": "$4.99",
                 "discount": "-50%", "release_date": "2024-01-01",
                 "sale_end": "2026-06-16T23:59:59Z", "image_url": ""}]
    result = merge_prices({"br": br_games, "us": us_games}, reference_locale="br")

    assert result[0]["sale_ends"]["br"] == "2026-06-15T23:59:59Z"
    assert result[0]["sale_ends"]["us"] == "2026-06-16T23:59:59Z"
    assert result[0]["sale_end"] == "2026-06-15T23:59:59Z"  # reference locale


def test_merge_prices_reference_locale_slug_wins():
    from app.scraper import merge_prices
    br_games = [{"name": "Game", "slug": "game-br", "original": "R$ 100", "current": "R$ 50",
                 "discount": "", "release_date": "2024-01-01", "sale_end": "", "image_url": "img-br"}]
    us_games = [{"name": "Game", "slug": "game-us", "original": "$9", "current": "$4",
                 "discount": "", "release_date": "2024-01-01", "sale_end": "", "image_url": "img-us"}]
    result = merge_prices({"br": br_games, "us": us_games}, reference_locale="br")

    assert result[0]["slug"] == "game-br"
    assert result[0]["image_url"] == "img-br"


def test_merge_prices_preserves_order_reference_first():
    from app.scraper import merge_prices
    br_games = [
        {"name": "B", "slug": "b", "original": "", "current": "", "discount": "",
         "release_date": "", "sale_end": "", "image_url": ""},
        {"name": "A", "slug": "a", "original": "", "current": "", "discount": "",
         "release_date": "", "sale_end": "", "image_url": ""},
    ]
    result = merge_prices({"br": br_games}, reference_locale="br")
    assert result[0]["name"] == "B"
    assert result[1]["name"] == "A"


def test_merge_prices_game_only_in_non_reference():
    from app.scraper import merge_prices
    br_games = []
    us_games = [{"name": "US Only", "slug": "us-only", "original": "$9", "current": "$4",
                 "discount": "", "release_date": "", "sale_end": "", "image_url": ""}]
    result = merge_prices({"br": br_games, "us": us_games}, reference_locale="br")

    assert len(result) == 1
    assert result[0]["name"] == "US Only"
    assert "us" in result[0]["prices"]
    assert "br" not in result[0]["prices"]
