"""Configuration settings for DekuScout."""
import os

_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DATA_DIR = os.path.abspath(os.environ.get("DATA_DIR", os.path.join(_PROJECT_ROOT, "data")))

WISHLIST_URL = os.environ.get(
    "WISHLIST_URL",
    "https://www.dekudeals.com/wishlist/x8kxhn96yf"
)
LOCALE_URL = "https://www.dekudeals.com/locale"

DB_FILE = os.path.abspath(os.path.join(DATA_DIR, "session.db"))
ICONS_DIR = os.path.abspath(os.path.join(DATA_DIR, "icons"))

CACHE_TTL = 30 * 60
HISTORY_CACHE_TTL = 6 * 60 * 60

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

SPREAD = 1.035
RATE_TTL = 60 * 60

# All DekuDeals-supported locales: locale_code -> {name, symbol, iso}
# NOTE: verify "gb" vs "uk" for United Kingdom against the live DekuDeals form.
COUNTRIES: dict[str, dict] = {
    "ar": {"name": "Argentina",      "symbol": "$",   "iso": "ARS"},
    "au": {"name": "Australia",      "symbol": "$",   "iso": "AUD"},
    "at": {"name": "Austria",        "symbol": "€",   "iso": "EUR"},
    "be": {"name": "Belgium",        "symbol": "€",   "iso": "EUR"},
    "br": {"name": "Brazil",         "symbol": "R$",  "iso": "BRL"},
    "bg": {"name": "Bulgaria",       "symbol": "€",   "iso": "EUR"},
    "ca": {"name": "Canada",         "symbol": "$",   "iso": "CAD"},
    "cl": {"name": "Chile",          "symbol": "$",   "iso": "CLP"},
    "co": {"name": "Colombia",       "symbol": "$",   "iso": "COP"},
    "hr": {"name": "Croatia",        "symbol": "€",   "iso": "EUR"},
    "cy": {"name": "Cyprus",         "symbol": "€",   "iso": "EUR"},
    "cz": {"name": "Czech Republic", "symbol": "Kč",  "iso": "CZK"},
    "dk": {"name": "Denmark",        "symbol": "kr.", "iso": "DKK"},
    "ee": {"name": "Estonia",        "symbol": "€",   "iso": "EUR"},
    "fi": {"name": "Finland",        "symbol": "€",   "iso": "EUR"},
    "fr": {"name": "France",         "symbol": "€",   "iso": "EUR"},
    "de": {"name": "Germany",        "symbol": "€",   "iso": "EUR"},
    "gr": {"name": "Greece",         "symbol": "€",   "iso": "EUR"},
    "hu": {"name": "Hungary",        "symbol": "€",   "iso": "EUR"},
    "ie": {"name": "Ireland",        "symbol": "€",   "iso": "EUR"},
    "it": {"name": "Italy",          "symbol": "€",   "iso": "EUR"},
    "jp": {"name": "Japan",          "symbol": "¥",   "iso": "JPY"},
    "lv": {"name": "Latvia",         "symbol": "€",   "iso": "EUR"},
    "lt": {"name": "Lithuania",      "symbol": "€",   "iso": "EUR"},
    "lu": {"name": "Luxembourg",     "symbol": "€",   "iso": "EUR"},
    "my": {"name": "Malaysia",       "symbol": "RM",  "iso": "MYR"},
    "mt": {"name": "Malta",          "symbol": "€",   "iso": "EUR"},
    "mx": {"name": "Mexico",         "symbol": "$",   "iso": "MXN"},
    "nl": {"name": "Netherlands",    "symbol": "€",   "iso": "EUR"},
    "nz": {"name": "New Zealand",    "symbol": "$",   "iso": "NZD"},
    "no": {"name": "Norway",         "symbol": "kr",  "iso": "NOK"},
    "pe": {"name": "Peru",           "symbol": "S/",  "iso": "PEN"},
    "pl": {"name": "Poland",         "symbol": "zł",  "iso": "PLN"},
    "pt": {"name": "Portugal",       "symbol": "€",   "iso": "EUR"},
    "ro": {"name": "Romania",        "symbol": "€",   "iso": "EUR"},
    "sg": {"name": "Singapore",      "symbol": "$",   "iso": "SGD"},
    "sk": {"name": "Slovakia",       "symbol": "€",   "iso": "EUR"},
    "si": {"name": "Slovenia",       "symbol": "€",   "iso": "EUR"},
    "za": {"name": "South Africa",   "symbol": "R",   "iso": "ZAR"},
    "es": {"name": "Spain",          "symbol": "€",   "iso": "EUR"},
    "se": {"name": "Sweden",         "symbol": "kr",  "iso": "SEK"},
    "ch": {"name": "Switzerland",    "symbol": "CHF", "iso": "CHF"},
    "th": {"name": "Thailand",       "symbol": "฿",   "iso": "THB"},
    "gb": {"name": "United Kingdom", "symbol": "£",   "iso": "GBP"},
    "us": {"name": "United States",  "symbol": "$",   "iso": "USD"},
}

# Currencies whose prices have no decimal places
NO_DECIMAL_ISOS = {"JPY", "CLP", "COP"}
