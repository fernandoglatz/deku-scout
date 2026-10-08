import csv
import io
import json
import os
import re

import requests

from app.config import HEADERS, PERFORMANCE_SHEET_GID, PERFORMANCE_SHEET_ID, SWITCHPLAZA_API_URL

# Path to the pre-scraped handheld-performance.com data
_HANDED_DATA_PATH = os.path.join(os.path.dirname(__file__), "data", "handheld_performance.json")


def load_handheld_performance() -> dict:
    """Load pre-scraped performance data from handheld-performance.com.

    Returns {norm_name: {'fps', 'label', 'resolution', 'docked', 'handheld'}}
    or empty dict on error. 'docked'/'handheld' are human-readable per-mode
    summaries ("720p 60 FPS"), empty when the mode has no data.
    """
    if not os.path.exists(_HANDED_DATA_PATH):
        return {}
    with open(_HANDED_DATA_PATH) as f:
        data = json.load(f)
    result: dict = {}
    for game in data.get("games", []):
        title = game.get("title", "") or ""
        norm = normalize_name(title)
        if not norm:
            continue
        # Prefer handheld mode FPS; fall back to docked
        perf = game.get("performance") or []
        entry = None
        for p in perf:
            if p.get("mode") == "Handheld" and p.get("fps"):
                entry = p
                break
        else:
            # Fall back to first entry with FPS
            for p in perf:
                if p.get("fps"):
                    entry = p
                    break
        if not entry or entry.get("fps") is None:
            continue
        fps_val = entry["fps"]
        result[norm] = {
            "fps": fps_val,
            "label": f"{fps_val}fps",
            "resolution": normalize_resolution(entry.get("resolution")),
            "docked": _handheld_mode_summary(perf, "Docked"),
            "handheld": _handheld_mode_summary(perf, "Handheld"),
        }
    return result


def _handheld_mode_summary(perf: list, mode: str) -> str:
    """Join one mode's rows as "<resolution> <framerate>" ("720p 60 FPS / ...")."""
    parts = []
    for p in perf:
        if p.get("mode") != mode:
            continue
        text = f"{p.get('resolution') or ''} {p.get('framerate') or ''}".strip()
        if text:
            parts.append(text)
    return " / ".join(parts)


def refresh_handheld_performance() -> int:
    """Scrape handheld-performance.com and update the local data file.

    Returns the number of games saved, or 0 on error.
    """
    import re as _re
    import urllib.request as _urllib

    def fetch_page(slug):
        url = f"https://handheld-performance.com/games/{slug}"
        req = _urllib.Request(url, headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64)"})
        with _urllib.urlopen(req, timeout=10) as resp:
            return resp.read().decode("utf-8")

    def get_slugs():
        url = "https://handheld-performance.com/sitemap-0.xml"
        req = _urllib.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with _urllib.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8")
        return [_re.sub(r"<.*", "", m.group(1))
                for m in _re.finditer(r'/games/\K([^/"]+)', html)]

    def parse_game_page(html, slug):
        h1_match = _re.search(r'<h1[^>]*>(.*?)</h1>', html)
        title = _re.sub(r'<[^>]+>', '', h1_match.group(1)).strip() if h1_match else slug

        tbody_match = _re.search(r'<tbody[^>]*>(.*?)</tbody>', html, _re.DOTALL)
        if not tbody_match:
            return None

        rows = []
        for row in _re.findall(r'<tr(.*?)</tr>', tbody_match.group(1), _re.DOTALL):
            cells = _re.findall(r'<td[^>]*>(.*?)</td>', row, _re.DOTALL)
            if len(cells) >= 5:
                mode = _re.sub(r'<[^>]+>', '', cells[0]).strip()
                resolution = _re.sub(r'<[^>]+>', '', cells[2]).strip().replace("(*)", "").strip()
                framerate_str = _re.sub(r'<[^>]+>', '', cells[3]).strip()
                stability_text = _re.sub(r'<[^>]+>', '', cells[4]).strip()
                fps_match = _re.search(r'(\d+)\s*FPS', framerate_str)
                fps = int(fps_match.group(1)) if fps_match else None
                rows.append({
                    "mode": mode,
                    "resolution": resolution,
                    "framerate": framerate_str,
                    "fps": fps,
                    "stability": stability_text,
                })

        notes = []
        for m in _re.finditer(r'Notes.*?<\/span>\s*(.*?)</p>', html, _re.DOTALL):
            note = _re.sub(r'<[^>]+>', '', m.group(1)).strip()
            if note and len(note) > 5:
                notes.append(note)

        video_id = None
        video_match = _re.search(r'data-title="Game Footage"[^>]*style="background-image:url\(([^)]+)\)', html)
        if video_match:
            yt_match = _re.search(r'ytimg\.com/vi/([^/]+)', video_match.group(1))
            if yt_match:
                video_id = yt_match.group(1)

        return {
            "slug": slug,
            "title": title,
            "url": f"https://handheld-performance.com/games/{slug}",
            "performance": rows,
            "notes": notes,
            "video_id": video_id,
        }

    try:
        slugs = get_slugs()
        results = []
        import time as _time
        for slug in slugs:
            html = fetch_page(slug)
            game_data = parse_game_page(html, slug)
            if game_data and game_data["performance"]:
                results.append(game_data)
            _time.sleep(0.5)

        os.makedirs(os.path.dirname(_HANDED_DATA_PATH), exist_ok=True)
        output = {
            "source": "handheld-performance.com",
            "total_games": len(results),
            "games": results,
        }
        with open(_HANDED_DATA_PATH, "w") as f:
            json.dump(output, f, indent=2)
        return len(results)
    except Exception:
        import sys
        print(f"Error refreshing handheld performance data", file=sys.stderr)
        return 0

_TRADEMARK = str.maketrans("", "", "™®©")

# Common abbreviation/expansion pairs for fuzzy matching.
_ALIASES = {
    "re": ["resident evil"],
    "veronica": ["code veronique", "veronique"],
    "zelda": ["legend of zelda"],
    "mk": ["mortal kombat"],
    "ff": ["final fantasy"],
    "sok": ["kingdom hearts"],
    "ssbu": ["super smash bros ultimate"],
    "sm": ["super mario"],
}


def normalize_name(name: str) -> str:
    """Lowercase, drop trademark symbols and punctuation, collapse whitespace."""
    s = (name or "").lower().translate(_TRADEMARK)
    s = re.sub(r"[^\w\s]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _expand_name(name: str) -> set:
    """Return the normalized name plus all alias-expanded variants as a token set."""
    tokens = set(name.split())
    expanded = set(tokens)
    for abbr, expansions in _ALIASES.items():
        if abbr in tokens:
            # Add expansion tokens, remove abbreviation
            expanded.discard(abbr)
            for exp in expansions:
                expanded.update(exp.split())
    return expanded


def _numbers(name: str) -> set[str]:
    """Extract numeric tokens from a normalized name."""
    return {t for t in normalize_name(name).split() if t.isdigit()}


def fuzzy_match(query_name: str, candidates: dict) -> tuple[str, dict] | tuple[None, None]:
    """Best containment match for query_name among {key: value} candidates.

    Returns (best_key, best_value) or (None, None). A candidate is considered a
    match only if at least 60% of the expanded query tokens appear in the
    expanded candidate AND they share at least 2 significant tokens (tokens
    longer than 3 characters after stop-word removal). Candidates that have
    different numeric tokens are skipped to avoid matching "Game 3+4" with
    "Game 1+2".
    """
    STOP = {"the", "of", "and", "a", "an", "in", "on", "for", "with", "s"}

    norm = normalize_name(query_name)
    expanded_q = _expand_name(norm)
    q_nums = _numbers(norm)
    if not expanded_q:
        return None, None

    # Significant tokens (longer than 3 chars, minus stops)
    sig_q = {t for t in expanded_q if len(t) > 3 and t not in STOP}
    min_sig_common = min(2, max(len(sig_q) - 1, 0))

    best_score = 0.0
    best_key = None
    best_val = None

    for key, val in candidates.items():
        tokens = set(key.split())
        expanded_k = _expand_name(key)
        # How many query tokens are contained in the candidate?
        containment_raw = len(expanded_q & tokens) / max(len(expanded_q), 1)
        containment_exp = len(expanded_q & expanded_k) / max(len(expanded_q), 1)
        score = max(containment_raw, containment_exp)

        sig_k = {t for t in expanded_k if len(t) > 3 and t not in STOP}
        common_sig = len(sig_q & sig_k)

        # Skip if numbers differ (e.g. "Game 3+4" vs "Game 1+2")
        k_nums = _numbers(key)
        if q_nums and k_nums and q_nums != k_nums:
            continue

        if score >= 0.6 and common_sig >= min_sig_common and score > best_score:
            best_score = score
            best_key = key
            best_val = val

    return best_key, best_val


def extract_fps(text: str):
    """Return (sort_value, label) parsed from prose, or None if no number.

    'Capped 60FPS...' -> (60, '60fps'); 'Uncapped...' -> (999, 'Uncapped');
    'Unchanged / Not Noticeable', 'N/A', '' -> None.
    """
    if not text:
        return None
    low = text.strip().lower()
    if "uncapped" in low:
        return (999, "Uncapped")
    m = re.search(r"(\d+)\s*fps", low)
    if m:
        n = int(m.group(1))
        return (n, f"{n}fps")
    return None


def parse_performance_csv(text: str) -> dict:
    """Parse the gviz CSV into {norm_name: {'fps', 'label', 'patch_type'}}.

    Column layout (positional): 0=name, 3=patch type, 4=framerate (docked),
    7=framerate (handheld). Prefer docked fps, fall back to handheld. Rows with
    no name, an obvious header/news blob, or no numeric fps are skipped.
    """
    result: dict = {}
    reader = csv.reader(io.StringIO(text))
    for row in reader:
        if len(row) < 5:
            continue
        name = row[0].strip()
        if not name or "\n" in name or len(name) > 100:
            continue
        norm = normalize_name(name)
        if not norm:
            continue
        patch_type = row[3].strip() if len(row) > 3 else ""
        fps = extract_fps(row[4])
        if fps is None and len(row) > 7:
            fps = extract_fps(row[7])
        if fps is None:
            continue
        result[norm] = {"fps": fps[0], "label": fps[1], "patch_type": patch_type}
    return result


def _headers(user_agent: str = None) -> dict:
    h = dict(HEADERS)
    if user_agent:
        h["User-Agent"] = user_agent
    return h


def fetch_performance_sheet(sheet_id: str = None, gid: str = None,
                            user_agent: str = None, timeout: int = 20) -> dict:
    """Fetch the community sheet as CSV and parse it. Raises on network/HTTP error."""
    sheet_id = sheet_id or PERFORMANCE_SHEET_ID
    gid = gid if gid is not None else PERFORMANCE_SHEET_GID
    url = (f"https://docs.google.com/spreadsheets/d/{sheet_id}"
           f"/gviz/tq?tqx=out:csv&gid={gid}")
    resp = requests.get(url, headers=_headers(user_agent), timeout=timeout)
    resp.raise_for_status()
    return parse_performance_csv(resp.text)


_RESOLUTION_RE = re.compile(r"^\s*(<)?\s*(\d+)\s*([pk])", re.IGNORECASE)


def normalize_resolution(text: str) -> str:
    """Canonical short resolution: '1080P' -> '1080p', '4k' -> '4K', '<1080P' -> '<1080p'.

    Trailing qualifiers are dropped ('720p (D)' -> '720p', '1080p-1200p' -> '1080p').
    Returns '' for missing or unrecognised values ('Unknown', '60 FPS').
    """
    m = _RESOLUTION_RE.match(text or "")
    if not m:
        return ""
    below, number, unit = m.groups()
    return f"{below or ''}{number}{'K' if unit.lower() == 'k' else 'p'}"


_PROFILE_RES_RE = re.compile(r"<?\s*\d+\s*[pk]", re.IGNORECASE)
_PROFILE_FPS_RE = re.compile(r"\s*(\d+)\s*(?:fps)?\s*", re.IGNORECASE)


def parse_perf_profiles(text: str) -> list[dict]:
    """Parse a Switchplaza perf string into [{'resolution', 'fps', 'label'}].

    '1080P 60 FPS (Performance) / 4K 30 FPS' -> two profiles; '4K60' and
    '60 FPS' are accepted; a resolution-only profile gets fps=None.
    'TBA', 'N/A' and empty values yield [].
    """
    profiles = []
    for part in (text or "").split("/"):
        label_match = re.search(r"\(([^)]*)\)", part)
        label = label_match.group(1).strip() if label_match else ""
        core = re.sub(r"\(.*?\)", "", part).strip()

        res_match = _PROFILE_RES_RE.match(core)
        resolution = normalize_resolution(res_match.group(0)) if res_match else ""
        rest = core[res_match.end():] if res_match else core
        fps_match = _PROFILE_FPS_RE.fullmatch(rest) if rest else None
        if not resolution and not fps_match:
            continue
        profiles.append({
            "resolution": resolution,
            "fps": int(fps_match.group(1)) if fps_match else None,
            "label": label,
        })
    return profiles


def _perf_text(value) -> str:
    """The raw perf string when it holds at least one profile, else ''."""
    text = (value or "").strip()
    return text if parse_perf_profiles(text) else ""


def parse_switchplaza_games(games: list) -> dict:
    """Build {norm_name: {fps, label, resolution, patch_type, docked, handheld}}.

    The headline fps/resolution comes from the first docked profile with an
    fps, falling back to handheld (matching the sheet's docked preference).
    'docked'/'handheld' keep the full per-mode strings for the tooltip.
    Games with no fps are skipped.
    """
    result: dict = {}
    for game in games:
        norm = normalize_name(game.get("title"))
        if not norm:
            continue
        docked = _perf_text(game.get("docked_perf"))
        handheld = _perf_text(game.get("handheld_perf"))
        primary = next(
            (p for text in (docked, handheld) for p in parse_perf_profiles(text) if p["fps"]),
            None,
        )
        if primary is None:
            continue
        row = {
            "fps": primary["fps"],
            "label": f"{primary['fps']}fps",
            "resolution": primary["resolution"],
            "patch_type": (game.get("console_type") or "").strip(),
            "docked": docked,
            "handheld": handheld,
        }
        result[norm] = row
    return result


# Generic edition descriptors only: title-specific subtitles ("Tarnished
# Edition", "Devil Hunter Edition") are part of the name and must still match exactly.
_EDITION_SUFFIX = re.compile(
    r"\s+(?:gold|deluxe|digital deluxe|complete|definitive|ultimate|special|standard"
    r"|premium|limited|legendary|legacy|enhanced|collector s"
    r"|(?:\d+(?:st|nd|rd|th) )?anniversary|game of the year|goty"
    r"|nintendo switch 2)\s+edition$"
)
_SW2_EDITION_SUFFIX = re.compile(r"\s+nintendo switch 2 edition$")


def edition_key(norm_name: str) -> str:
    """Strip trailing generic edition suffixes from a normalized name.

    'resident evil 4 gold edition' -> 'resident evil 4';
    'braid anniversary edition nintendo switch 2 edition' -> 'braid'.
    A bare descriptor ('deluxe edition') is left as is.
    """
    key = norm_name or ""
    while True:
        stripped = _EDITION_SUFFIX.sub("", key)
        if stripped == key:
            return key
        key = stripped


def build_edition_index(rows: dict) -> dict:
    """Index {norm_name: row} by edition_key.

    On a collision the shortest (base) title wins, then alphabetical order,
    so the result does not depend on the order rows were loaded in.
    """
    index: dict = {}
    for norm_name in sorted(rows, key=lambda k: (len(k), k)):
        index.setdefault(edition_key(norm_name), rows[norm_name])
    return index


def edition_match(norm_name: str, index: dict):
    """Row whose title differs from norm_name only by edition suffixes, or None.

    A Switch 2 Edition title is never matched this way: the base entry it
    would fall back to describes the Switch 1 version's performance.
    """
    if not norm_name or _SW2_EDITION_SUFFIX.search(norm_name):
        return None
    return index.get(edition_key(norm_name))


_SWITCHPLAZA_MAX_PAGES = 20


def fetch_switchplaza(user_agent: str = None, timeout: int = 30, page_size: int = 5000) -> dict:
    """Fetch every game from the Switchplaza API and parse it. Raises on network/HTTP error.

    One request normally covers the whole catalogue; further pages are
    followed if the API reports more (capped as a runaway guard).
    """
    games: list = []
    page = 1
    while page <= _SWITCHPLAZA_MAX_PAGES:
        resp = requests.get(
            SWITCHPLAZA_API_URL,
            params={"page": page, "limit": page_size},
            headers=_headers(user_agent),
            timeout=timeout,
        )
        resp.raise_for_status()
        payload = resp.json()
        batch = payload.get("data") or []
        games.extend(batch)
        pages = (payload.get("pagination") or {}).get("pages") or 1
        if not batch or page >= pages:
            break
        page += 1
    return parse_switchplaza_games(games)
