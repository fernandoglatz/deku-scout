import logging
import time

import requests

from app.config import COUNTRIES, RATE_TTL, SPREAD

log = logging.getLogger(__name__)
_rate_cache: dict = {}  # (from_locale, to_locale) -> {"rate": float, "ts": float}


def _locale_to_iso(locale: str) -> str:
    return COUNTRIES.get(locale, {}).get("iso", locale.upper())


def _fetch_rate(from_iso: str, to_iso: str) -> float:
    url = f"https://open.er-api.com/v6/latest/{from_iso}"
    log.info("_fetch_rate: GET %s → %s", from_iso, to_iso)
    t0 = time.monotonic()
    resp = requests.get(url, timeout=10)
    resp.raise_for_status()
    data = resp.json()
    if data.get("result") != "success":
        raise RuntimeError(f"Exchange rate API error: {data}")
    rate = float(data["rates"][to_iso])
    log.info("_fetch_rate: %s→%s = %.6f (%.2fs)", from_iso, to_iso, rate, time.monotonic() - t0)
    return rate


def fetch_rate(from_locale: str, to_locale: str) -> float:
    """Return how many units of to_locale currency equal 1 unit of from_locale currency."""
    if from_locale == to_locale:
        return 1.0

    from_iso = _locale_to_iso(from_locale)
    to_iso = _locale_to_iso(to_locale)

    if from_iso == to_iso:
        return 1.0

    cache_key = (from_locale, to_locale)
    cached = _rate_cache.get(cache_key)
    if cached and time.time() - cached["ts"] < RATE_TTL:
        return cached["rate"]

    try:
        rate = round(_fetch_rate(from_iso, to_iso) * SPREAD, 6)
        _rate_cache[cache_key] = {"rate": rate, "ts": time.time()}
        return rate
    except Exception as exc:
        log.warning("fetch_rate: failed to fetch %s→%s: %s", from_iso, to_iso, exc)
        return cached["rate"] if cached else 1.0


def fetch_exchange_rate() -> float:
    """Legacy: USD→BRL rate (used by unconfigured index page)."""
    return fetch_rate("us", "br")
