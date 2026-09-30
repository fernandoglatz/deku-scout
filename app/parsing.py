import re
from datetime import date, datetime, timedelta, timezone


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


def last_sale_start(history: dict, on_sale_now: bool = False, max_sale_days: int = 60) -> str:
    """Return the ISO date the most recent eShop sale started, or "" if none.

    `history` is DekuDeals' price_history_data: {"headers": [store, ...],
    "data": [[date, _, price_per_store...], ...]}. Only "Nintendo eShop" series
    are used (cheapest one per day when there are several, e.g. Switch/Switch 2).

    A sale starts when the price drops below the regular price and ends when it
    returns. A drop lasting longer than `max_sale_days` is a permanent price cut,
    not a sale. Histories can begin mid-sale: a short opening stretch that later
    rises counts as a sale, and `on_sale_now` (from the item page) covers one
    still running, where the regular price never appears.
    """
    headers = history.get("headers") or []
    cols = [i + 2 for i, h in enumerate(headers) if "eshop" in str(h).lower()]
    if not cols:
        return ""

    regular = last_price = None
    start = prev_start = run_start = first_day = ""
    in_sale = changed = False
    for row in history.get("data") or []:
        prices = [row[c] for c in cols if c < len(row) and row[c] is not None]
        if not prices:
            continue
        day, price = row[0], min(prices)
        first_day = first_day or day
        if price != last_price:
            # History that begins at a sale price and later rises: that first
            # stretch was a sale (unless it lasted long enough to be a price hike).
            if (not changed and last_price is not None and price > last_price
                    and (date.fromisoformat(day) - date.fromisoformat(first_day)).days <= max_sale_days):
                start = first_day
            changed = changed or last_price is not None
            run_start, last_price = day, price
        if regular is None or price >= regular:
            regular, in_sale = price, False
        elif not in_sale:
            in_sale, prev_start, start = True, start, day
        elif (date.fromisoformat(day) - date.fromisoformat(start)).days > max_sale_days:
            regular, in_sale, start = price, False, prev_start

    if on_sale_now and not in_sale:
        return run_start
    return start
