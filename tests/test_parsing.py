import re
from datetime import datetime, timedelta, timezone

import pytest

from app.parsing import parse_release_date, parse_sale_end


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
