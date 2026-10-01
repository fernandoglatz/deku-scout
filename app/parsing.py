import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional


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


def last_price_event(history: dict, on_sale_now: Optional[bool] = None, max_sale_days: int = 60) -> str:
    """Return the ISO date of the most recent eShop price event, or "".

    Events: a sale that ended (its last day on sale), a permanent price drop or
    a price increase (the day the new price started). A sale still running at
    the end of the history is not an event.

    `history` is DekuDeals' price_history_data: {"headers": [store, ...],
    "data": [[date, _, price_per_store...], ...]}. Only "Nintendo eShop" series
    are used (cheapest one per day when there are several, e.g. Switch/Switch 2).

    A drop below the regular price is a sale until it lasts longer than
    `max_sale_days`, then it's a permanent price drop. `on_sale_now` (the item
    page's discount flag) settles a recent drop early: False means the lower
    price is the new regular price. Histories can begin mid-sale (launch
    discounts): a short opening stretch that later rises counts as a sale.
    """
    headers = history.get("headers") or []
    cols = [i + 2 for i, h in enumerate(headers) if "eshop" in str(h).lower()]
    if not cols:
        return ""

    # Collapse days into runs of the same price: [first_day, last_day, price].
    runs: list[list] = []
    for row in history.get("data") or []:
        prices = [row[c] for c in cols if c < len(row) and row[c] is not None]
        if not prices:
            continue
        day, price = row[0], min(prices)
        if runs and runs[-1][2] == price:
            runs[-1][1] = day
        else:
            runs.append([day, day, price])

    def days(a: str, b: str) -> int:
        return (date.fromisoformat(b) - date.fromisoformat(a)).days

    event = ""
    regular = None
    sale_start = sale_end = ""
    for i, (first, last, price) in enumerate(runs):
        if i == 0:
            nxt = runs[1] if len(runs) > 1 else None
            if nxt and nxt[2] > price and days(first, nxt[0]) <= max_sale_days:
                event = last  # history began mid-sale; the next run seeds regular
            else:
                regular = price
            continue
        if regular is None:
            regular = price
            continue
        if price >= regular:
            if sale_start:
                event = sale_end
            if price > regular:
                event = first  # price increase
            regular, sale_start = price, ""
        else:
            sale_start = sale_start or first
            sale_end = last
            if days(sale_start, last) > max_sale_days:  # permanent price drop
                event, regular, sale_start = first, price, ""
    if sale_start and on_sale_now is False:
        event = runs[-1][0]  # below regular with no discount: a price drop
    return event
