import re
from datetime import datetime, timedelta, timezone

import pytest

from app.parsing import last_sale_start, parse_release_date, parse_sale_end


# ── parse_release_date ─────────────────────────────────────────────────────────

def test_parse_release_date_full_long_month():
    assert parse_release_date("October 1, 2026") == "2026-10-01"


def test_parse_release_date_full_short_month():
    assert parse_release_date("Oct 1, 2026") == "2026-10-01"


def test_parse_release_date_year_only():
    assert parse_release_date("2026") == "2026"


def test_parse_release_date_year_only_far_future():
    assert parse_release_date("2035") == "2035"


def test_parse_release_date_no_year_long_month():
    result = parse_release_date("October 1")
    now = datetime.now(timezone.utc)
    assert result == f"{now.year}-10-01"


def test_parse_release_date_no_year_short_month():
    result = parse_release_date("Oct 1")
    now = datetime.now(timezone.utc)
    assert result == f"{now.year}-10-01"


def test_parse_release_date_january():
    assert parse_release_date("January 15, 2025") == "2025-01-15"


def test_parse_release_date_december():
    assert parse_release_date("December 31, 2024") == "2024-12-31"


def test_parse_release_date_strips_whitespace():
    assert parse_release_date("  October 1, 2026  ") == "2026-10-01"


def test_parse_release_date_empty_string():
    assert parse_release_date("") == ""


def test_parse_release_date_unparseable_returns_original():
    assert parse_release_date("some garbage text") == "some garbage text"


def test_parse_release_date_already_iso_passthrough():
    # ISO strings aren't in the strptime formats so they fall back to raw
    result = parse_release_date("2026-10-01")
    assert result == "2026-10-01"


# ── parse_sale_end ─────────────────────────────────────────────────────────────

def _parse_iso(s: str) -> datetime:
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def test_parse_sale_end_hours():
    before = datetime.now(timezone.utc)
    result = parse_sale_end("in 27 hours")
    parsed = _parse_iso(result)
    diff = (parsed - before).total_seconds()
    assert abs(diff - 27 * 3600) < 5


def test_parse_sale_end_minutes():
    before = datetime.now(timezone.utc)
    result = parse_sale_end("in 3 minutes")
    parsed = _parse_iso(result)
    diff = (parsed - before).total_seconds()
    assert abs(diff - 3 * 60) < 5


def test_parse_sale_end_days():
    before = datetime.now(timezone.utc)
    result = parse_sale_end("in 2 days")
    parsed = _parse_iso(result)
    diff = (parsed - before).total_seconds()
    assert abs(diff - 2 * 86400) < 5


def test_parse_sale_end_plural_hours():
    result = parse_sale_end("in 1 hour")
    assert result.endswith("Z")


def test_parse_sale_end_full_date_with_year():
    assert parse_sale_end("June 12, 2026") == "2026-06-12T23:59:59Z"


def test_parse_sale_end_short_month_with_year():
    assert parse_sale_end("Jun 12, 2026") == "2026-06-12T23:59:59Z"


def test_parse_sale_end_month_day_no_year_format():
    result = parse_sale_end("June 30")
    assert re.match(r"\d{4}-06-30T23:59:59Z", result)


def test_parse_sale_end_case_insensitive():
    before = datetime.now(timezone.utc)
    result = parse_sale_end("In 1 Hour")
    parsed = _parse_iso(result)
    diff = (parsed - before).total_seconds()
    assert abs(diff - 3600) < 5


def test_parse_sale_end_empty_string():
    assert parse_sale_end("") == ""


def test_parse_sale_end_unparseable_returns_empty():
    assert parse_sale_end("some garbage text") == ""


def test_parse_sale_end_result_is_iso_format():
    result = parse_sale_end("in 5 hours")
    assert re.match(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", result)


# ── last_sale_start ───────────────────────────────────────────────────────────

def _history(prices, headers=("Nintendo eShop",), start_day=1):
    """Build a DekuDeals-shaped price history: one row per day, one price per header."""
    rows = []
    for i, p in enumerate(prices):
        vals = list(p) if isinstance(p, tuple) else [p]
        rows.append([f"2026-01-{start_day + i:02d}", None] + vals)
    return {"headers": list(headers), "data": rows}


def test_last_sale_start_finds_most_recent_sale():
    h = _history([20, 20, 10, 10, 20, 20, 15, 15, 20])
    assert last_sale_start(h) == "2026-01-07"


def test_last_sale_start_current_sale():
    h = _history([20, 20, 10, 10], )
    assert last_sale_start(h, on_sale_now=True) == "2026-01-03"


def test_last_sale_start_deeper_discount_keeps_sale_start():
    h = _history([20, 15, 10, 10, 20])
    assert last_sale_start(h) == "2026-01-02"


def test_last_sale_start_never_on_sale():
    assert last_sale_start(_history([20, 20, 20])) == ""


def test_last_sale_start_price_increase_is_not_a_sale():
    assert last_sale_start(_history([20, 20, 25, 25])) == ""


def test_last_sale_start_permanent_price_cut_is_not_a_sale():
    # sale on day 2, then a permanent cut on day 5 lasting longer than max_sale_days
    h = _history([20, 10, 20, 20] + [12] * 20)
    assert last_sale_start(h, max_sale_days=10) == "2026-01-02"


def test_last_sale_start_history_begins_mid_sale():
    # launched on sale: no regular price in history, but the page says it's discounted
    h = _history([15, 15, 15])
    assert last_sale_start(h, on_sale_now=True) == "2026-01-01"


def test_last_sale_start_uses_only_eshop_series():
    h = _history([(9, 20), (9, 20), (9, 10), (9, 20)],
                 headers=("Walmart (physical)", "Nintendo eShop (digital)"))
    assert last_sale_start(h) == "2026-01-03"


def test_last_sale_start_multiple_eshop_series_uses_cheapest():
    h = _history([(20, None), (20, 20), (20, 10), (20, 20)],
                 headers=("Nintendo eShop (Switch)", "Nintendo eShop (Switch 2)"))
    assert last_sale_start(h) == "2026-01-03"


def test_last_sale_start_empty_or_malformed():
    assert last_sale_start({}) == ""
    assert last_sale_start({"headers": ["Amazon"], "data": [["2026-01-01", None, 5]]}) == ""
