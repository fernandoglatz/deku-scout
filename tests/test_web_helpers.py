import pytest


# ── _parse_price ──────────────────────────────────────────────────────────────

def test_parse_price_usd():
    from app.web import _parse_price
    assert _parse_price("$4.99") == 4.99


def test_parse_price_brl():
    from app.web import _parse_price
    assert _parse_price("R$ 50,00") == 50.0


def test_parse_price_brl_thousands():
    from app.web import _parse_price
    assert _parse_price("R$ 1.234,56") == pytest.approx(1234.56)


def test_parse_price_usd_thousands():
    from app.web import _parse_price
    assert _parse_price("$1,234.56") == pytest.approx(1234.56)


def test_parse_price_jpy():
    from app.web import _parse_price
    assert _parse_price("¥1,500") == 1500.0


def test_parse_price_integer_only():
    from app.web import _parse_price
    assert _parse_price("50") == 50.0


def test_parse_price_empty_string():
    from app.web import _parse_price
    assert _parse_price("") == 0.0


def test_parse_price_unavailable():
    from app.web import _parse_price
    assert _parse_price("Unavailable") == 0.0


def test_parse_price_multiple_dots():
    from app.web import _parse_price
    assert _parse_price("1.234.567") == 1234567.0


def test_parse_price_multiple_commas():
    from app.web import _parse_price
    assert _parse_price("1,234,567") == 1234567.0


def test_parse_price_strips_whitespace():
    from app.web import _parse_price
    assert _parse_price("  $9.99  ") == 9.99


def test_parse_price_clp_no_decimal():
    from app.web import _parse_price
    assert _parse_price("$10,000") == 10000.0


# ── _format_price ─────────────────────────────────────────────────────────────

def test_format_price_usd():
    from app.web import _format_price
    assert _format_price(4.99, "us") == "$4.99"


def test_format_price_brl():
    from app.web import _format_price
    assert _format_price(50.0, "br") == "R$ 50,00"


def test_format_price_brl_thousands():
    from app.web import _format_price
    assert _format_price(1234.56, "br") == "R$ 1.234,56"


def test_format_price_jpy_no_decimal():
    from app.web import _format_price
    assert _format_price(1500.0, "jp") == "¥1,500"


def test_format_price_clp_no_decimal():
    from app.web import _format_price
    assert _format_price(10000.0, "cl") == "$10,000"


def test_format_price_multi_char_symbol():
    from app.web import _format_price
    assert _format_price(9.99, "my") == "RM 9.99"


def test_format_price_chf():
    from app.web import _format_price
    assert _format_price(9.99, "ch") == "CHF 9.99"


def test_format_price_gbp():
    from app.web import _format_price
    assert _format_price(9.99, "gb") == "£9.99"


def test_format_price_eur():
    from app.web import _format_price
    assert _format_price(9.99, "de") == "€9.99"


# ── _get_selected_locales ─────────────────────────────────────────────────────

def test_get_selected_locales_default(monkeypatch):
    from app.web import _get_selected_locales
    monkeypatch.setattr("app.web.get_config", lambda _key, _db=None: None)
    assert _get_selected_locales() == ["br", "us"]


def test_get_selected_locales_configured(monkeypatch):
    from app.web import _get_selected_locales
    import json
    monkeypatch.setattr("app.web.get_config",
                        lambda key, _db=None: json.dumps(["br", "us", "jp"]) if key == "SELECTED_CURRENCIES" else None)
    assert _get_selected_locales() == ["br", "us", "jp"]


# ── _get_reference_locale ─────────────────────────────────────────────────────

def test_get_reference_locale_default(monkeypatch):
    from app.web import _get_reference_locale
    monkeypatch.setattr("app.web.get_config", lambda _key, _db=None: None)
    assert _get_reference_locale(["br", "us"]) == "br"


def test_get_reference_locale_configured(monkeypatch):
    from app.web import _get_reference_locale
    monkeypatch.setattr("app.web.get_config", lambda key, _db=None: "us" if key == "REFERENCE_CURRENCY" else None)
    assert _get_reference_locale(["br", "us"]) == "us"


def test_get_reference_locale_invalid_falls_back(monkeypatch):
    from app.web import _get_reference_locale
    monkeypatch.setattr("app.web.get_config", lambda key, _db=None: "jp" if key == "REFERENCE_CURRENCY" else None)
    # "jp" is not in selected → fall back to first
    assert _get_reference_locale(["br", "us"]) == "br"


# ── _compute_best_buy ─────────────────────────────────────────────────────────

def _make_game(br_price="R$ 50,00", us_price="$9.99", br_discount="", us_discount="",
               sale_ends=None):
    return {
        "prices": {
            "br": {"original": "R$ 100,00", "current": br_price, "discount": br_discount},
            "us": {"original": "$20.00",    "current": us_price,  "discount": us_discount},
        },
        "sale_ends": sale_ends or {},
        "sale_end": "",
    }


def test_compute_best_buy_single_locale():
    from app.web import _compute_best_buy
    games = [{"prices": {"br": {"current": "R$ 50", "discount": "-50%"}}, "sale_ends": {}}]
    _compute_best_buy(games, ["br"], "br")
    assert games[0]["best_buy"] == ""
    assert games[0]["best_buy_label"] == ""
    assert games[0]["has_discount"] is True


def test_compute_best_buy_has_discount_false():
    from app.web import _compute_best_buy
    games = [{"prices": {"br": {"current": "R$ 50", "discount": ""}}, "sale_ends": {}}]
    _compute_best_buy(games, ["br"], "br")
    assert games[0]["has_discount"] is False


def test_compute_best_buy_all_unavailable():
    from app.web import _compute_best_buy
    games = [{"prices": {"br": {"current": "Unavailable", "discount": ""}}, "sale_ends": {}}]
    _compute_best_buy(games, ["br"], "br")
    assert games[0]["all_unavailable"] is True


def test_compute_best_buy_not_all_unavailable_when_one_available():
    from app.web import _compute_best_buy
    games = [{"prices": {
        "br": {"current": "R$ 50", "discount": ""},
        "us": {"current": "Unavailable", "discount": ""},
    }, "sale_ends": {}}]
    _compute_best_buy(games, ["br", "us"], "br")
    assert games[0]["all_unavailable"] is False


def test_compute_best_buy_foreign_cheaper(monkeypatch):
    from app.web import _compute_best_buy
    import app.web as web_module
    monkeypatch.setattr(web_module, "fetch_rate", lambda _f, _t: 5.0)  # 1 USD = 5 BRL

    # US: $10 * 5 = R$ 50, cheaper than R$ 60
    games = [_make_game(br_price="R$ 60,00", us_price="$10.00")]
    _compute_best_buy(games, ["br", "us"], "br")

    assert games[0]["best_buy"] == "us"
    assert games[0]["best_buy_save"] != ""


def test_compute_best_buy_reference_cheaper(monkeypatch):
    from app.web import _compute_best_buy
    import app.web as web_module
    monkeypatch.setattr(web_module, "fetch_rate", lambda _f, _t: 10.0)  # 1 USD = 10 BRL

    # US: $10 * 10 = R$ 100, more than R$ 50
    games = [_make_game(br_price="R$ 50,00", us_price="$10.00")]
    _compute_best_buy(games, ["br", "us"], "br")

    assert games[0]["best_buy"] == "br"
    assert games[0]["best_buy_save"] != ""


def test_compute_best_buy_equal_prices(monkeypatch):
    from app.web import _compute_best_buy
    import app.web as web_module
    monkeypatch.setattr(web_module, "fetch_rate", lambda _f, _t: 1.0)

    games = [_make_game(br_price="R$ 50,00", us_price="$50.00")]
    _compute_best_buy(games, ["br", "us"], "br")

    assert games[0]["best_buy"] == "eq"
    assert games[0]["best_buy_save"] == ""


def test_compute_best_buy_foreign_unavailable_falls_back_to_reference(monkeypatch):
    from app.web import _compute_best_buy
    import app.web as web_module
    monkeypatch.setattr(web_module, "fetch_rate", lambda _f, _t: 5.0)

    games = [{"prices": {
        "br": {"current": "R$ 50", "discount": ""},
        "us": {"current": "Unavailable", "discount": ""},
    }, "sale_ends": {}}]
    _compute_best_buy(games, ["br", "us"], "br")

    assert games[0]["best_buy"] == "br"


def test_compute_best_buy_reference_unavailable_uses_foreign(monkeypatch):
    from app.web import _compute_best_buy
    import app.web as web_module
    monkeypatch.setattr(web_module, "fetch_rate", lambda _f, _t: 5.0)

    games = [{"prices": {
        "br": {"current": "Unavailable", "discount": ""},
        "us": {"current": "$10.00", "discount": ""},
    }, "sale_ends": {}}]
    _compute_best_buy(games, ["br", "us"], "br")

    assert games[0]["best_buy"] == "us"
    assert games[0]["best_buy_save"] == ""


def test_compute_best_buy_updates_sale_end_from_sale_ends():
    from app.web import _compute_best_buy
    games = [{"prices": {
        "br": {"current": "R$ 50", "discount": ""},
    }, "sale_ends": {"br": "2026-06-15T23:59:59Z"}, "sale_end": ""}]
    _compute_best_buy(games, ["br"], "br")
    assert games[0]["sale_end"] == "2026-06-15T23:59:59Z"


def test_compute_best_buy_sale_end_uses_best_buy_locale(monkeypatch):
    from app.web import _compute_best_buy
    import app.web as web_module
    monkeypatch.setattr(web_module, "fetch_rate", lambda _f, _t: 5.0)

    # US is cheaper, so sale_end should come from US sale_ends
    games = [{"prices": {
        "br": {"current": "R$ 100", "discount": ""},
        "us": {"current": "$10.00", "discount": ""},
    }, "sale_ends": {
        "br": "2026-06-10T23:59:59Z",
        "us": "2026-06-20T23:59:59Z",
    }, "sale_end": ""}]
    _compute_best_buy(games, ["br", "us"], "br")

    assert games[0]["best_buy"] == "us"
    assert games[0]["sale_end"] == "2026-06-20T23:59:59Z"


def test_compute_best_buy_sale_end_uses_reference_when_eq(monkeypatch):
    from app.web import _compute_best_buy
    import app.web as web_module
    monkeypatch.setattr(web_module, "fetch_rate", lambda _f, _t: 1.0)

    games = [{"prices": {
        "br": {"current": "R$ 50", "discount": ""},
        "us": {"current": "$50.00", "discount": ""},
    }, "sale_ends": {
        "br": "2026-06-10T23:59:59Z",
        "us": "2026-06-20T23:59:59Z",
    }, "sale_end": ""}]
    _compute_best_buy(games, ["br", "us"], "br")

    assert games[0]["best_buy"] == "eq"
    assert games[0]["sale_end"] == "2026-06-10T23:59:59Z"
