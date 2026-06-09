import re
from datetime import datetime, timedelta, timezone


def parse_release_date(raw: str) -> str:
    """Convert DekuDeals release-date text to an ISO-8601 date string (YYYY-MM-DD)
    or a plain year string ("2026").

    Handles:
      "October 1, 2026" / "Oct 1, 2026"  → "2026-10-01"
      "2026" / "2027"                    → "2026" (year-only, kept as-is)
    Returns "" on parse failure.
    """
    raw = raw.strip()
    if re.fullmatch(r"\d{4}", raw):
        return raw  # year-only: keep as-is for display
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d", "%b %d"):
        try:
            d = datetime.strptime(raw, fmt)
            if "%Y" not in fmt:
                now = datetime.now(timezone.utc)
                d = d.replace(year=now.year)
            return d.strftime("%Y-%m-%d")
        except ValueError:
            continue
    return raw  # fall back to original string if unparseable


def parse_sale_end(raw: str) -> str:
    """Convert DekuDeals sale-end text to an ISO-8601 UTC string.

    Handles:
      "in 27 hours" / "in 3 minutes" / "in 2 days"  → now + offset
      "June 12" / "Jun 12" / "June 12, 2026"        → midnight UTC
    Returns "" on parse failure.
    """
    raw = raw.strip()
    m = re.match(r"in\s+(\d+)\s+(hour|minute|day)s?", raw, re.IGNORECASE)
    if m:
        amount, unit = int(m.group(1)), m.group(2).lower()
        delta = {
            "hour": timedelta(hours=amount),
            "minute": timedelta(minutes=amount),
            "day": timedelta(days=amount),
        }[unit]
        return (datetime.now(timezone.utc) + delta).strftime("%Y-%m-%dT%H:%M:%SZ")
    now = datetime.now(timezone.utc)
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%B %d", "%b %d"):
        try:
            d = datetime.strptime(raw, fmt)
            if "%Y" not in fmt:
                d = d.replace(year=now.year)
                if d.date() < now.date():
                    d = d.replace(year=now.year + 1)
            return d.strftime("%Y-%m-%dT23:59:59Z")
        except ValueError:
            continue
    return ""
