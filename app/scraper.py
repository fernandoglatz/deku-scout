import logging
import os
import time

import requests
from bs4 import BeautifulSoup

from app.config import DB_FILE, HEADERS, ICONS_DIR, LOCALE_URL, WISHLIST_URL
from app.db import load_cookies, save_cookies, save_games_cache
from app.parsing import parse_release_date, parse_sale_end

log = logging.getLogger(__name__)


def _make_headers(user_agent: str = None, **extra) -> dict:
    h = {**HEADERS}
    if user_agent:
        h["User-Agent"] = user_agent
    h.update(extra)
    return h


def build_session(db_path: str, locale: str = "br") -> requests.Session:
    session = requests.Session()
    cookies = load_cookies(db_path, locale)
    log.info("build_session: loaded %d cookies for locale=%s", len(cookies), locale)
    for name, value, domain, path in cookies:
        session.cookies.set(name, value, domain=domain, path=path)
    return session


def set_locale(session: requests.Session, country: str, wishlist_url: str = None, user_agent: str = None) -> None:
    url = wishlist_url or WISHLIST_URL
    headers = _make_headers(
        user_agent,
        **{
            "Content-Type": "application/x-www-form-urlencoded",
            "Origin": "https://www.dekudeals.com",
            "Referer": url,
        },
    )
    log.info("set_locale: switching to country=%s", country)
    t0 = time.monotonic()
    resp = session.post(LOCALE_URL, data={"country": country}, headers=headers, timeout=30)
    resp.raise_for_status()
    log.info("set_locale: done (%.2fs, status=%d)", time.monotonic() - t0, resp.status_code)


def fetch_wishlist(session: requests.Session, wishlist_url: str = None, user_agent: str = None) -> str:
    url = wishlist_url or WISHLIST_URL
    log.info("fetch_wishlist: GET %s", url)
    t0 = time.monotonic()
    response = session.get(url + "?sort=release_date", headers=_make_headers(user_agent), timeout=30)
    response.raise_for_status()
    log.info("fetch_wishlist: done (%.2fs, %d bytes)", time.monotonic() - t0, len(response.content))
    return response.text


def extract_games(html: str) -> list[dict]:
    log.info("extract_games: parsing HTML (%d bytes)", len(html))
    soup = BeautifulSoup(html, "html.parser")

    view_list = soup.find(class_="view-list")
    if view_list is None:
        raise RuntimeError("Could not find .view-list on the page.")

    games = []
    for tag in view_list.find_all("a", class_="main-link", href=True):
        if not tag["href"].startswith("/items/"):
            continue
        name = tag.get_text(strip=True)
        if not name:
            continue

        # Walk up to the per-item container (div.col)
        container = tag.find_parent("div", class_="col")
        if container is None:
            continue

        original = container.find("s", class_="text-muted")
        current = container.find("strong")
        badge = container.find("span", class_="badge-danger")

        # Release date + sale end are in the no-class div inside the inner column
        inner = tag.find_parent("div", class_="d-flex flex-column flex-grow-1")
        date_div = None
        if inner:
            for child in inner.children:
                if hasattr(child, "get") and child.get("class") is None:
                    txt = child.get_text(" ", strip=True)
                    if txt:
                        date_div = txt
                        break

        release_date = ""
        sale_end = ""
        if date_div:
            if "Sale ends" in date_div:
                parts = date_div.split("Sale ends", 1)
                release_date = parse_release_date(parts[0].strip())
                sale_end = parse_sale_end(parts[1].strip())
            else:
                release_date = parse_release_date(date_div.strip())

        slug = tag["href"].removeprefix("/items/")

        img_tag = container.find("img")
        image_url = ""
        if img_tag:
            image_url = (
                img_tag.get("src")
                or img_tag.get("data-src")
                or img_tag.get("data-lazy-src")
                or ""
            )

        games.append(
            {
                "name": name,
                "slug": slug,
                "original": original.get_text(strip=True) if original else "",
                "current": current.get_text(strip=True) if current else "Unavailable",
                "discount": badge.get_text(strip=True) if badge else "",
                "release_date": release_date,
                "sale_end": sale_end,
                "image_url": image_url,
            }
        )

    log.info("extract_games: found %d games", len(games))
    return games


def merge_prices(games_by_locale: dict[str, list[dict]], reference_locale: str) -> list[dict]:
    """Merge prices from N locales into a unified game list keyed by game name."""
    by_name: dict[str, dict[str, dict]] = {}
    meta_by_name: dict[str, dict] = {}

    for locale, games in games_by_locale.items():
        for g in games:
            name = g["name"]
            if name not in by_name:
                by_name[name] = {}
            by_name[name][locale] = {
                "original": g["original"],
                "current": g["current"],
                "discount": g["discount"],
            }
            if name not in meta_by_name:
                meta_by_name[name] = {
                    "slug": g["slug"],
                    "release_date": g["release_date"],
                    "sale_ends": {},
                    "image_url": g.get("image_url", ""),
                }
            if locale == reference_locale:
                meta_by_name[name]["slug"] = g["slug"]
                meta_by_name[name]["release_date"] = g["release_date"]
                meta_by_name[name]["image_url"] = g.get("image_url", "")
            if g.get("sale_end"):
                meta_by_name[name]["sale_ends"][locale] = g["sale_end"]

    ref_names = [g["name"] for g in games_by_locale.get(reference_locale, [])]
    other_names = [n for n in by_name if n not in ref_names]

    result = []
    for name in ref_names + other_names:
        meta = meta_by_name[name]
        sale_ends = meta.get("sale_ends", {})
        result.append({
            "name": name,
            "slug": meta["slug"],
            "prices": by_name[name],
            "release_date": meta["release_date"],
            "sale_end": sale_ends.get(reference_locale, ""),
            "sale_ends": sale_ends,
            "image_url": meta["image_url"],
        })
    return result


def _icon_path(slug: str, ext: str = "jpg") -> str:
    """Return the local filesystem path for a game icon."""
    safe = slug.replace("/", "_")[:80]
    return os.path.join(ICONS_DIR, f"{safe}.{ext}")


def _content_type_to_ext(content_type: str) -> str:
    ct = content_type.lower()
    if "png" in ct:
        return "png"
    if "webp" in ct:
        return "webp"
    if "gif" in ct:
        return "gif"
    return "jpg"


def _existing_icon_ext(slug: str) -> str:
    """Return the extension of an already-downloaded icon, or empty string."""
    safe = slug.replace("/", "_")[:80]
    if not os.path.exists(ICONS_DIR):
        return ""
    for fname in os.listdir(ICONS_DIR):
        if fname.startswith(safe + "."):
            return os.path.splitext(fname)[1].lstrip(".")
    return ""


def download_icons(games: list[dict], user_agent: str = None) -> dict[str, str]:
    """Download missing game icons into ICONS_DIR. Returns slug→ext mapping."""
    os.makedirs(ICONS_DIR, exist_ok=True)
    result: dict[str, str] = {}
    to_download = [g for g in games if not _existing_icon_ext(g["slug"]) and g.get("image_url")]
    cached = len(games) - len(to_download)
    log.info("download_icons: %d cached, %d to download", cached, len(to_download))
    for g in games:
        slug = g["slug"]
        existing = _existing_icon_ext(slug)
        if existing:
            result[slug] = existing
            continue
        url = g.get("image_url", "")
        if not url:
            continue
        try:
            log.debug("download_icons: fetching icon for %s", slug)
            resp = requests.get(url, headers=_make_headers(user_agent), timeout=15)
            resp.raise_for_status()
            ext = _content_type_to_ext(resp.headers.get("content-type", ""))
            path = _icon_path(slug, ext)
            with open(path, "wb") as fh:
                fh.write(resp.content)
            result[slug] = ext
        except Exception as exc:
            log.warning("download_icons: failed for %s: %s", slug, exc)
    log.info("download_icons: finished (%d icons saved)", len(result))
    return result


def fetch_all_games(
    db_path: str = DB_FILE,
    wishlist_url: str = None,
    locales: list[str] = None,
    reference_locale: str = None,
    user_agent: str = None,
) -> tuple[list[dict], float]:
    url = wishlist_url or WISHLIST_URL
    if locales is None:
        locales = ["br", "us"]
    if reference_locale is None:
        reference_locale = locales[0]

    log.info("fetch_all_games: starting (locales=%s, reference=%s)", locales, reference_locale)
    t_start = time.monotonic()

    session = build_session(db_path, reference_locale)
    games_by_locale: dict[str, list[dict]] = {}

    for locale in locales:
        log.info("fetch_all_games: fetching locale=%s", locale)
        set_locale(session, locale, wishlist_url=url, user_agent=user_agent)
        games_by_locale[locale] = extract_games(fetch_wishlist(session, wishlist_url=url, user_agent=user_agent))
        save_cookies(session.cookies, db_path, locale=locale)

    log.info("fetch_all_games: restoring reference locale=%s", reference_locale)
    set_locale(session, reference_locale, wishlist_url=url, user_agent=user_agent)
    save_cookies(session.cookies, db_path, locale=reference_locale)

    games = merge_prices(games_by_locale, reference_locale=reference_locale)
    log.info("fetch_all_games: merged %d games, downloading icons", len(games))
    icon_exts = download_icons(games, user_agent=user_agent)
    for g in games:
        g["icon_ext"] = icon_exts.get(g["slug"], "")
    ts = save_games_cache(games, db_path)
    log.info("fetch_all_games: done in %.2fs", time.monotonic() - t_start)
    return games, ts
