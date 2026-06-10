import sqlite3
import pytest

from app.db import get_config, set_config


def test_migrations_create_config_table(temp_db):
    """Config table exists after migrations run (via temp_db fixture)."""
    with sqlite3.connect(temp_db) as conn:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='config'"
        )
        assert cursor.fetchone() is not None


def test_set_and_get_config(temp_db):
    """Test setting and retrieving config values."""
    # Set a config value
    set_config("test_key", "test_value")

    # Get the config value
    result = get_config("test_key")

    assert result == "test_value", f"Expected 'test_value', got {result}"


def test_get_nonexistent_config(temp_db):
    """Test getting a config value that doesn't exist."""
    # Get a non-existent config value
    result = get_config("nonexistent_key")

    assert result is None, f"Expected None, got {result}"


def test_update_config(temp_db):
    """Test updating an existing config value."""
    # Set initial value
    set_config("update_key", "initial_value")
    result1 = get_config("update_key")
    assert result1 == "initial_value"

    # Update the value
    set_config("update_key", "updated_value")
    result2 = get_config("update_key")

    assert result2 == "updated_value", f"Expected 'updated_value', got {result2}"


def test_multiple_config_values(temp_db):
    """Test storing and retrieving multiple config values."""
    # Set multiple values
    set_config("key1", "value1")
    set_config("key2", "value2")
    set_config("key3", "value3")

    # Retrieve and verify each value
    assert get_config("key1") == "value1"
    assert get_config("key2") == "value2"
    assert get_config("key3") == "value3"


def test_get_config_endpoint(client, monkeypatch):
    """Test GET /api/config endpoint."""
    import app.config as config_module

    # Test when no WISHLIST_URL is configured
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.get_json()
    assert "wishlist_url" in data
    assert "configured" in data
    assert data["wishlist_url"] is None
    assert data["configured"] is False

    # Set a WISHLIST_URL and test again (write to client's DB)
    set_config("WISHLIST_URL", "https://example.com/wishlist", config_module.DB_FILE)
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.get_json()
    assert data["wishlist_url"] == "https://example.com/wishlist"
    assert data["configured"] is True


# Tests for _parse_wishlist_input helper function
def test_parse_wishlist_input_valid_code():
    """Test parsing a valid wishlist code."""
    from app.web import _parse_wishlist_input

    url, error = _parse_wishlist_input("x8kxhn96yf")
    assert error is None
    assert url == "https://www.dekudeals.com/wishlist/x8kxhn96yf"


def test_parse_wishlist_input_valid_code_with_hyphens():
    """Test parsing a valid wishlist code with hyphens."""
    from app.web import _parse_wishlist_input

    url, error = _parse_wishlist_input("x8kx-hn96-yf")
    assert error is None
    assert url == "https://www.dekudeals.com/wishlist/x8kx-hn96-yf"


def test_parse_wishlist_input_valid_code_with_underscores():
    """Test parsing a valid wishlist code with underscores."""
    from app.web import _parse_wishlist_input

    url, error = _parse_wishlist_input("x8kx_hn96_yf")
    assert error is None
    assert url == "https://www.dekudeals.com/wishlist/x8kx_hn96_yf"


def test_parse_wishlist_input_valid_https_url():
    """Test parsing a valid HTTPS URL."""
    from app.web import _parse_wishlist_input

    test_url = "https://www.dekudeals.com/wishlist/x8kxhn96yf"
    url, error = _parse_wishlist_input(test_url)
    assert error is None
    assert url == test_url


def test_parse_wishlist_input_valid_http_url():
    """Test parsing a valid HTTP URL."""
    from app.web import _parse_wishlist_input

    test_url = "http://www.dekudeals.com/wishlist/x8kxhn96yf"
    url, error = _parse_wishlist_input(test_url)
    assert error is None
    assert url == test_url


def test_parse_wishlist_input_invalid_format():
    """Test parsing an invalid input format."""
    from app.web import _parse_wishlist_input

    url, error = _parse_wishlist_input("!!!invalid!!!")
    assert url is None
    assert error == "Please enter a valid wishlist code or full URL"


def test_parse_wishlist_input_invalid_special_chars():
    """Test parsing input with invalid special characters."""
    from app.web import _parse_wishlist_input

    url, error = _parse_wishlist_input("x8kx@hn96#yf")
    assert url is None
    assert error == "Please enter a valid wishlist code or full URL"


def test_parse_wishlist_input_whitespace_stripped():
    """Test that whitespace is properly stripped."""
    from app.web import _parse_wishlist_input

    url, error = _parse_wishlist_input("  x8kxhn96yf  ")
    assert error is None
    assert url == "https://www.dekudeals.com/wishlist/x8kxhn96yf"


def test_parse_wishlist_input_empty_string():
    """Test parsing an empty string."""
    from app.web import _parse_wishlist_input

    url, error = _parse_wishlist_input("")
    assert url is None
    assert error == "Please enter a valid wishlist code or full URL"


# Tests for _validate_wishlist_url helper function
def test_validate_wishlist_url_success(monkeypatch):
    """Test validating a URL that returns 200."""
    from app.web import _validate_wishlist_url
    import requests

    def mock_get(*args, **kwargs):
        class MockResponse:
            status_code = 200
        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)

    error = _validate_wishlist_url("https://www.dekudeals.com/wishlist/x8kxhn96yf")
    assert error is None


def test_validate_wishlist_url_404(monkeypatch):
    """Test validating a URL that returns 404."""
    from app.web import _validate_wishlist_url
    import requests

    def mock_get(*args, **kwargs):
        class MockResponse:
            status_code = 404
        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)

    error = _validate_wishlist_url("https://www.dekudeals.com/wishlist/invalid")
    assert error == "Wishlist not found (404). Please check the code or URL."


def test_validate_wishlist_url_server_error(monkeypatch):
    """Test validating a URL that returns 500."""
    from app.web import _validate_wishlist_url
    import requests

    def mock_get(*args, **kwargs):
        class MockResponse:
            status_code = 500
        return MockResponse()

    monkeypatch.setattr(requests, "get", mock_get)

    error = _validate_wishlist_url("https://www.dekudeals.com/wishlist/x8kxhn96yf")
    assert error == "Server error (HTTP 500). Try again later."


def test_validate_wishlist_url_timeout(monkeypatch):
    """Test validating a URL that times out."""
    from app.web import _validate_wishlist_url
    import requests

    def mock_get(*args, **kwargs):
        raise requests.Timeout()

    monkeypatch.setattr(requests, "get", mock_get)

    error = _validate_wishlist_url("https://www.dekudeals.com/wishlist/x8kxhn96yf")
    assert error == "Request timed out. Check your internet connection."


def test_validate_wishlist_url_connection_error(monkeypatch):
    """Test validating a URL with a connection error."""
    from app.web import _validate_wishlist_url
    import requests

    def mock_get(*args, **kwargs):
        raise requests.ConnectionError()

    monkeypatch.setattr(requests, "get", mock_get)

    error = _validate_wishlist_url("https://www.dekudeals.com/wishlist/x8kxhn96yf")
    assert error == "Connection error. Check your internet connection."


def test_validate_wishlist_url_generic_error(monkeypatch):
    """Test validating a URL with a generic exception."""
    from app.web import _validate_wishlist_url
    import requests

    def mock_get(*args, **kwargs):
        raise ValueError("Some unexpected error")

    monkeypatch.setattr(requests, "get", mock_get)

    error = _validate_wishlist_url("https://www.dekudeals.com/wishlist/x8kxhn96yf")
    assert error.startswith("Error validating URL:")


# Tests for POST /api/config endpoint
def test_post_config_endpoint_missing_input(client, temp_db):
    """Test POST /api/config with missing input field."""
    response = client.post("/api/config", json={})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Missing 'input' field" in data["error"]


def test_post_config_endpoint_invalid_input(client, temp_db):
    """Test POST /api/config with invalid input format."""
    response = client.post("/api/config", json={"input": "!!!invalid!!!"})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Please enter a valid wishlist code or full URL" in data["error"]


def test_post_config_endpoint_valid_code_success(client, monkeypatch):
    """Test POST /api/config with valid code and successful validation."""
    import app.config as config_module

    def mock_get(*args, **kwargs):
        class MockResponse:
            status_code = 200
        return MockResponse()

    import requests
    monkeypatch.setattr(requests, "get", mock_get)

    response = client.post("/api/config", json={"input": "x8kxhn96yf"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["wishlist_url"] == "https://www.dekudeals.com/wishlist/x8kxhn96yf"

    # Verify it was saved to the client's database
    saved_url = get_config("WISHLIST_URL", config_module.DB_FILE)
    assert saved_url == "https://www.dekudeals.com/wishlist/x8kxhn96yf"


def test_post_config_endpoint_valid_url_success(client, monkeypatch):
    """Test POST /api/config with valid URL and successful validation."""
    import app.config as config_module

    def mock_get(*args, **kwargs):
        class MockResponse:
            status_code = 200
        return MockResponse()

    import requests
    monkeypatch.setattr(requests, "get", mock_get)

    test_url = "https://www.dekudeals.com/wishlist/custom"
    response = client.post("/api/config", json={"input": test_url})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["wishlist_url"] == test_url

    # Verify it was saved to the client's database
    saved_url = get_config("WISHLIST_URL", config_module.DB_FILE)
    assert saved_url == test_url


def test_post_config_endpoint_url_not_found(client, monkeypatch):
    """Test POST /api/config when the URL returns 404."""
    def mock_get(*args, **kwargs):
        class MockResponse:
            status_code = 404
        return MockResponse()

    import requests
    monkeypatch.setattr(requests, "get", mock_get)

    response = client.post("/api/config", json={"input": "x8kxhn96yf"})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Wishlist not found (404)" in data["error"]

    # Verify config was NOT saved
    saved_url = get_config("WISHLIST_URL")
    assert saved_url is None


def test_post_config_endpoint_timeout(client, monkeypatch):
    """Test POST /api/config when the request times out."""
    def mock_get(*args, **kwargs):
        raise requests.Timeout()

    import requests
    monkeypatch.setattr(requests, "get", mock_get)

    response = client.post("/api/config", json={"input": "x8kxhn96yf"})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Request timed out" in data["error"]

    # Verify config was NOT saved
    saved_url = get_config("WISHLIST_URL")
    assert saved_url is None


def test_post_config_endpoint_connection_error(client, monkeypatch):
    """Test POST /api/config when there's a connection error."""
    def mock_get(*args, **kwargs):
        raise requests.ConnectionError()

    import requests
    monkeypatch.setattr(requests, "get", mock_get)

    response = client.post("/api/config", json={"input": "x8kxhn96yf"})
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False
    assert "Connection error" in data["error"]

    # Verify config was NOT saved
    saved_url = get_config("WISHLIST_URL")
    assert saved_url is None


def test_post_config_endpoint_updates_existing_config(client, monkeypatch):
    """Test that POST /api/config updates an existing config value."""
    import app.config as config_module

    def mock_get(*args, **kwargs):
        class MockResponse:
            status_code = 200
        return MockResponse()

    import requests
    monkeypatch.setattr(requests, "get", mock_get)

    # Set initial config in client's database
    set_config("WISHLIST_URL", "https://www.dekudeals.com/wishlist/old", config_module.DB_FILE)

    # Update with new config
    response = client.post("/api/config", json={"input": "x8kxhn96yf"})
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert data["wishlist_url"] == "https://www.dekudeals.com/wishlist/x8kxhn96yf"

    # Verify it was updated in the client's database
    saved_url = get_config("WISHLIST_URL", config_module.DB_FILE)
    assert saved_url == "https://www.dekudeals.com/wishlist/x8kxhn96yf"


# ── exchange rate tests ───────────────────────────────────────────────────────

def test_fetch_rate_same_locale():
    from app.exchange import fetch_rate
    assert fetch_rate("br", "br") == 1.0


def test_fetch_rate_uses_cache(monkeypatch):
    import app.exchange as ex
    import time
    ex._rate_cache[("us", "jp")] = {"rate": 150.0, "ts": time.time()}
    result = ex.fetch_rate("us", "jp")
    assert result == 150.0


def test_fetch_rate_fallback_on_error(monkeypatch):
    import app.exchange as ex
    import time
    ex._rate_cache[("ca", "br")] = {"rate": 3.9, "ts": 0.0}
    import requests
    monkeypatch.setattr(requests, "get", lambda *a, **k: (_ for _ in ()).throw(Exception("err")))
    result = ex.fetch_rate("ca", "br")
    assert result == 3.9


# ── games_cache schema tests ──────────────────────────────────────────────────

def test_save_and_load_games_cache_new_schema(temp_db):
    from app.db import save_games_cache, load_games_cache
    games = [
        {
            "name": "Test Game",
            "slug": "test-game",
            "prices": {
                "br": {"original": "R$ 100,00", "current": "R$ 50,00", "discount": "-50%"},
                "us": {"original": "$9.99",     "current": "$4.99",    "discount": "-50%"},
            },
            "release_date": "2024-01-15",
            "sale_end": "2024-02-01",
            "image_url": "https://example.com/img.jpg",
        }
    ]
    ts = save_games_cache(games, temp_db)
    loaded, fetched_at = load_games_cache(temp_db)
    assert loaded is not None
    assert len(loaded) == 1
    g = loaded[0]
    assert g["name"] == "Test Game"
    assert g["slug"] == "test-game"
    assert g["prices"]["br"]["current"] == "R$ 50,00"
    assert g["prices"]["us"]["discount"] == "-50%"
    assert g["release_date"] == "2024-01-15"
    assert abs(fetched_at - ts) < 1


def test_load_games_cache_returns_none_when_empty(temp_db):
    from app.db import load_games_cache
    result, ts = load_games_cache(temp_db)
    assert result is None
    assert ts is None


# ── scraper merge_prices tests ────────────────────────────────────────────────

def test_merge_prices_two_locales():
    from app.scraper import merge_prices
    br_games = [
        {"name": "Game A", "slug": "game-a", "original": "R$ 100", "current": "R$ 50",
         "discount": "-50%", "release_date": "2024-01-01", "sale_end": "", "image_url": ""},
    ]
    us_games = [
        {"name": "Game A", "slug": "game-a", "original": "$9.99", "current": "$4.99",
         "discount": "-50%", "release_date": "2024-01-01", "sale_end": "", "image_url": ""},
    ]
    result = merge_prices({"br": br_games, "us": us_games}, reference_locale="br")
    assert len(result) == 1
    g = result[0]
    assert g["name"] == "Game A"
    assert g["prices"]["br"]["current"] == "R$ 50"
    assert g["prices"]["us"]["current"] == "$4.99"


def test_merge_prices_missing_in_one_locale():
    from app.scraper import merge_prices
    br_games = [
        {"name": "BR Only", "slug": "br-only", "original": "R$ 80", "current": "R$ 80",
         "discount": "", "release_date": "", "sale_end": "", "image_url": ""},
    ]
    us_games = []
    result = merge_prices({"br": br_games, "us": us_games}, reference_locale="br")
    assert len(result) == 1
    assert result[0]["prices"]["br"]["current"] == "R$ 80"
    assert "us" not in result[0]["prices"]


# ── currency config endpoint tests ───────────────────────────────────────────

def test_get_config_returns_currencies(client):
    import app.config as config_module
    from app.db import set_config
    set_config("SELECTED_CURRENCIES", '["br","us"]', config_module.DB_FILE)
    set_config("REFERENCE_CURRENCY", "br", config_module.DB_FILE)
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.get_json()
    assert data["selected_currencies"] == ["br", "us"]
    assert data["reference_currency"] == "br"


def test_post_config_saves_currencies(client, monkeypatch):
    import json as _json
    import app.config as config_module
    from app.db import get_config
    response = client.post("/api/config", json={
        "selected_currencies": ["br", "us", "jp"],
        "reference_currency": "br",
    })
    assert response.status_code == 200
    data = response.get_json()
    assert data["success"] is True
    assert _json.loads(get_config("SELECTED_CURRENCIES", config_module.DB_FILE)) == ["br", "us", "jp"]
    assert get_config("REFERENCE_CURRENCY", config_module.DB_FILE) == "br"


def test_post_config_rejects_invalid_locale(client, temp_db):
    response = client.post("/api/config", json={
        "selected_currencies": ["br", "xx"],
        "reference_currency": "br",
    })
    assert response.status_code == 400
    data = response.get_json()
    assert data["success"] is False


def test_post_config_rejects_reference_not_in_selected(client, temp_db):
    # First save valid currencies
    client.post("/api/config", json={"selected_currencies": ["br", "us"], "reference_currency": "br"})
    # Then try to set reference to something not selected
    response = client.post("/api/config", json={
        "selected_currencies": ["br", "us"],
        "reference_currency": "jp",
    })
    assert response.status_code == 400
