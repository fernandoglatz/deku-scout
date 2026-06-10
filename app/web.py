import json
import logging
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Optional, Tuple
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup
from flask import Blueprint, jsonify, redirect, render_template, request, send_file, url_for

log = logging.getLogger(__name__)

from app.config import COUNTRIES, HEADERS, ICONS_DIR
from app.user import get_db_path, get_user_email
from app.db import (
    clear_games_cache,
    get_cached_price_history,
    get_config,
    load_games_cache,
    save_price_history_cache,
    set_config,
)
from app.exchange import fetch_rate
from app.scraper import _content_type_to_ext, _icon_path, download_icons, fetch_all_games

web_bp = Blueprint("web", __name__)


def _parse_price(s: str) -> float:
    """Parse a price string from any locale format to float."""
    clean = re.sub(r'[^\d,.]', '', s.strip())
    if not clean:
        return 0.0
    dot_count = clean.count('.')
    comma_count = clean.count(',')
    if dot_count == 0 and comma_count == 0:
        return float(clean) if clean else 0.0
    if dot_count > 1:
        clean = clean.replace('.', '')
        if comma_count == 1:
            clean = clean.replace(',', '.')
    elif comma_count > 1:
        clean = clean.replace(',', '')
    elif dot_count == 1 and comma_count == 1:
        if clean.rfind(',') > clean.rfind('.'):
            clean = clean.replace('.', '').replace(',', '.')
        else:
            clean = clean.replace(',', '')
    elif comma_count == 1:
        parts = clean.split(',')
        if len(parts[1]) <= 2:
            clean = clean.replace(',', '.')
        else:
            clean = clean.replace(',', '')
    try:
        return float(clean)
    except ValueError:
        return 0.0


def _format_price(value: float, locale: str) -> str:
    """Format a float as a price string in the given locale's currency style."""
    info = COUNTRIES.get(locale, {})
    symbol = info.get("symbol", "")
    iso = info.get("iso", "")
    if iso in ("JPY", "CLP", "COP"):
        amount = f"{int(round(value)):,}"
        return f"{symbol}{amount}" if len(symbol) == 1 else f"{symbol} {amount}"
    if locale == "br":
        formatted = f"{value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"{symbol} {formatted}"
    if len(symbol) > 1:
        return f"{symbol} {value:,.2f}"
    return f"{symbol}{value:,.2f}"


def _parse_wishlist_input(input_str: str) -> Tuple[Optional[str], Optional[str]]:
    input_str = input_str.strip()
    if not input_str:
        return (None, "Please enter a valid wishlist code or full URL")
    if input_str.startswith("http://") or input_str.startswith("https://"):
        parsed = urlparse(input_str)
        clean = urlunparse(parsed._replace(query="", fragment=""))
        return (clean, None)
    if re.fullmatch(r"[a-zA-Z0-9_-]+", input_str):
        return (f"https://www.dekudeals.com/wishlist/{input_str}", None)
    return (None, "Please enter a valid wishlist code or full URL")


def _validate_wishlist_url(url: str) -> Optional[str]:
    try:
        response = requests.get(url, headers=HEADERS, timeout=5)
        if response.status_code == 404:
            return "Wishlist not found (404). Please check the code or URL."
        elif response.status_code != 200:
            return f"Server error (HTTP {response.status_code}). Try again later."
        return None
    except requests.Timeout:
        return "Request timed out. Check your internet connection."
    except requests.ConnectionError:
        return "Connection error. Check your internet connection."
    except Exception as e:
        return f"Error validating URL: {str(e)}"


def _get_selected_locales() -> list[str]:
    raw = get_config("SELECTED_CURRENCIES", get_db_path())
    return json.loads(raw) if raw else ["br", "us"]


def _get_reference_locale(selected_locales: list[str]) -> str:
    ref = get_config("REFERENCE_CURRENCY", get_db_path())
    return ref if ref and ref in selected_locales else selected_locales[0]


def _compute_best_buy(games: list[dict], selected_locales: list[str], reference_locale: str) -> None:
    """Annotate each game dict with best_buy, best_buy_label, best_buy_save, has_discount, all_unavailable."""
    rates = {
        locale: fetch_rate(locale, reference_locale)
        for locale in selected_locales
        if locale != reference_locale
    }

    for g in games:
        prices = g.get("prices", {})
        selected_prices = {k: v for k, v in prices.items() if k in selected_locales}

        g["has_discount"] = any(p.get("discount") for p in selected_prices.values())
        g["all_unavailable"] = bool(selected_prices) and all(
            not p.get("current") or p.get("current") == "Unavailable"
            for p in selected_prices.values()
        )

        if len(selected_locales) < 2:
            g["best_buy"] = ""
            g["best_buy_label"] = ""
            g["best_buy_save"] = ""
            continue

        ref_str = prices.get(reference_locale, {}).get("current", "")
        ref_val = _parse_price(ref_str) if ref_str and ref_str != "Unavailable" else 0.0

        best_locale = None
        best_in_ref: Optional[float] = None

        for locale in selected_locales:
            if locale == reference_locale:
                continue
            cur_str = prices.get(locale, {}).get("current", "")
            if not cur_str or cur_str == "Unavailable":
                continue
            cur_val = _parse_price(cur_str)
            if cur_val <= 0:
                continue
            price_in_ref = cur_val * rates.get(locale, 1.0)
            if best_in_ref is None or price_in_ref < best_in_ref:
                best_in_ref = price_in_ref
                best_locale = locale

        if best_locale is None or best_in_ref is None:
            if ref_val > 0:
                g["best_buy"] = reference_locale
                g["best_buy_label"] = _format_price(ref_val, reference_locale)
                g["best_buy_save"] = ""
            else:
                g["best_buy"] = ""
                g["best_buy_label"] = ""
                g["best_buy_save"] = ""
            continue

        label = _format_price(best_in_ref, reference_locale)

        if ref_val <= 0:
            g["best_buy"] = best_locale
            g["best_buy_label"] = label
            g["best_buy_save"] = ""
            continue

        diff = ref_val - best_in_ref
        if diff > 0.005:
            g["best_buy"] = best_locale
            g["best_buy_label"] = label
            g["best_buy_save"] = _format_price(diff, reference_locale)
        elif diff < -0.005:
            g["best_buy"] = reference_locale
            g["best_buy_label"] = label
            g["best_buy_save"] = _format_price(-diff, reference_locale)
        else:
            g["best_buy"] = "eq"
            g["best_buy_label"] = label
            g["best_buy_save"] = ""

    for g in games:
        sale_ends = g.get("sale_ends", {})
        if not sale_ends:
            continue
        effective = g.get("best_buy", "")
        if effective in ("", "eq"):
            effective = reference_locale
        g["sale_end"] = sale_ends.get(effective, g.get("sale_end", ""))


@web_bp.route("/")
def index():
    db_path = get_db_path()
    user_email = get_user_email()
    wishlist_url = get_config("WISHLIST_URL", db_path)
    wishlist_configured = wishlist_url is not None
    selected_locales = _get_selected_locales()
    reference_locale = _get_reference_locale(selected_locales)
    exchange_rates: dict = {}

    if not wishlist_configured:
        return render_template(
            "index.html",
            wishlist_configured=False,
            wishlist_error=False,
            wishlist_error_message=None,
            games=None,
            on_sale=0,
            unavailable=0,
            last_updated="Never",
            total=0,
            selected_locales=selected_locales,
            reference_locale=reference_locale,
            countries=COUNTRIES,
            exchange_rates=exchange_rates,
            user_email=user_email,
        )

    games, fetched_at = load_games_cache(db_path)
    if games is None:
        log.info("index: cache miss — fetching live data (locales=%s)", selected_locales)
        try:
            games, fetched_at = fetch_all_games(
                db_path,
                wishlist_url=wishlist_url,
                locales=selected_locales,
                reference_locale=reference_locale,
            )
        except requests.exceptions.ConnectionError:
            return (
                "<h1>Offline</h1><p>Could not connect to dekudeals.com. "
                "Check your internet connection and <a href='/'>try again</a>.</p>",
                503,
            )
        except requests.exceptions.HTTPError as e:
            if e.response is not None and e.response.status_code == 404:
                return render_template(
                    "index.html",
                    wishlist_configured=True,
                    wishlist_error=True,
                    wishlist_error_message="Wishlist not found. Please update your configuration.",
                    games=None,
                    on_sale=0,
                    unavailable=0,
                    last_updated="Never",
                    total=0,
                    selected_locales=selected_locales,
                    reference_locale=reference_locale,
                    countries=COUNTRIES,
                    exchange_rates={},
                    user_email=user_email,
                )
            return (
                "<h1>Error</h1><p>Failed to fetch wishlist data. "
                "<a href='/'>Try again</a>.</p>",
                502,
            )
        except requests.exceptions.RequestException:
            return (
                "<h1>Error</h1><p>Failed to fetch wishlist data. "
                "<a href='/'>Try again</a>.</p>",
                502,
            )
    else:
        log.info("index: cache hit — %d games from cache", len(games))
        threading.Thread(target=download_icons, args=(games,), daemon=True).start()

    last_updated = (
        datetime.fromtimestamp(fetched_at, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        if fetched_at
        else "Never"
    )

    for locale in selected_locales:
        if locale != reference_locale:
            exchange_rates[locale] = fetch_rate(locale, reference_locale)

    _compute_best_buy(games, selected_locales, reference_locale)

    on_sale = sum(1 for g in games if g.get("has_discount"))
    unavailable = sum(1 for g in games if g.get("all_unavailable"))

    return render_template(
        "index.html",
        wishlist_configured=True,
        wishlist_error=False,
        wishlist_error_message=None,
        games=games,
        last_updated=last_updated,
        total=len(games),
        on_sale=on_sale,
        unavailable=unavailable,
        selected_locales=selected_locales,
        reference_locale=reference_locale,
        countries=COUNTRIES,
        exchange_rates=exchange_rates,
        user_email=user_email,
    )


@web_bp.route("/api/config", methods=["GET"])
def get_config_api():
    db_path = get_db_path()
    url = get_config("WISHLIST_URL", db_path)
    selected_locales = _get_selected_locales()
    reference_locale = _get_reference_locale(selected_locales)
    return jsonify({
        "wishlist_url": url,
        "configured": url is not None,
        "selected_currencies": selected_locales,
        "reference_currency": reference_locale,
    })


@web_bp.route("/api/config", methods=["POST"])
def set_config_api():
    db_path = get_db_path()
    data = request.get_json()
    has_currencies = data and ("selected_currencies" in data or "reference_currency" in data)
    has_input = data and "input" in data

    if not has_currencies and not has_input:
        return jsonify({"success": False, "error": "Missing 'input' field"}), 400

    if has_currencies:
        selected = data.get("selected_currencies")
        if selected is not None:
            if not isinstance(selected, list) or len(selected) == 0:
                return jsonify({"success": False, "error": "At least one currency must be selected"}), 400
            invalid = [c for c in selected if c not in COUNTRIES]
            if invalid:
                return jsonify({"success": False, "error": f"Invalid locale codes: {invalid}"}), 400
            set_config("SELECTED_CURRENCIES", json.dumps(selected), db_path)
            clear_games_cache(db_path)

        reference = data.get("reference_currency")
        if reference is not None:
            current_raw = get_config("SELECTED_CURRENCIES", db_path)
            current_selected = json.loads(current_raw) if current_raw else []
            if reference not in current_selected:
                return jsonify({"success": False, "error": "Reference currency must be one of the selected currencies"}), 400
            set_config("REFERENCE_CURRENCY", reference, db_path)

    if not has_input:
        return jsonify({"success": True}), 200

    url, parse_error = _parse_wishlist_input(data["input"])
    if parse_error:
        return jsonify({"success": False, "error": parse_error}), 400

    validation_error = _validate_wishlist_url(url)
    if validation_error:
        return jsonify({"success": False, "error": validation_error}), 400

    set_config("WISHLIST_URL", url, db_path)
    return jsonify({"success": True, "wishlist_url": url}), 200


@web_bp.route("/refresh", methods=["POST"])
def refresh():
    db_path = get_db_path()
    wishlist_url = get_config("WISHLIST_URL", db_path)
    selected_locales = _get_selected_locales()
    reference_locale = _get_reference_locale(selected_locales)
    fetch_all_games(
        db_path,
        wishlist_url=wishlist_url,
        locales=selected_locales,
        reference_locale=reference_locale,
    )
    return redirect(url_for("web.index"))


@web_bp.route("/icons/<path:slug>")
def serve_icon(slug: str):
    safe_slug = slug.replace("/", "_")[:80]
    # Strip image extension from slug so URLs like /icons/game.jpg work correctly
    _IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
    base, ext = os.path.splitext(safe_slug)
    search_base = base if ext.lower() in _IMAGE_EXTS else safe_slug
    icon_found = None
    for fname in os.listdir(ICONS_DIR) if os.path.exists(ICONS_DIR) else []:
        if fname.startswith(search_base + "."):
            icon_found = os.path.join(ICONS_DIR, fname)
            break

    if not icon_found:
        try:
            with sqlite3.connect(get_db_path()) as conn:
                row = conn.execute(
                    "SELECT image_url FROM games_cache WHERE slug = ?", (slug,)
                ).fetchone()
            if row and row[0]:
                resp = requests.get(row[0], headers=HEADERS, timeout=15)
                resp.raise_for_status()
                os.makedirs(ICONS_DIR, exist_ok=True)
                ext = _content_type_to_ext(resp.headers.get("content-type", ""))
                icon_found = _icon_path(slug, ext)
                with open(icon_found, "wb") as fh:
                    fh.write(resp.content)
        except Exception:
            pass

    if not icon_found or not os.path.exists(icon_found):
        return "", 404

    try:
        ext = os.path.splitext(icon_found)[1].lower()
        mimetype_map = {".png": "image/png", ".webp": "image/webp", ".gif": "image/gif"}
        mimetype = mimetype_map.get(ext, "image/jpeg")
        return send_file(icon_found, mimetype=mimetype)
    except (FileNotFoundError, OSError):
        return "", 404


@web_bp.route("/price-history/<path:slug>")
def price_history_api(slug: str):
    db_path = get_db_path()
    currency = request.args.get("currency", "br").lower()
    locale = currency
    cached = get_cached_price_history(slug, currency, db_path)
    if cached is not None:
        return jsonify(cached)
    try:
        from app.scraper import build_session, set_locale

        sess = build_session(db_path, locale)
        set_locale(sess, locale)
        resp = sess.get(
            f"https://www.dekudeals.com/items/{slug}",
            headers=HEADERS,
            timeout=30,
        )
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        script_tag = soup.find("script", id="price_history_data")
        if not script_tag or not script_tag.string:
            return jsonify({"headers": [], "data": []})
        data = json.loads(script_tag.string)
        save_price_history_cache(slug, currency, data, db_path)
        return jsonify(data)
    except Exception as exc:
        return jsonify({"error": str(exc)}), 500
