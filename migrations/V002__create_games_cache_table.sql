-- depends: V001__create_cookies_table

CREATE TABLE games_cache (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    name         TEXT    NOT NULL,
    slug         TEXT    NOT NULL DEFAULT '',
    prices       TEXT    NOT NULL DEFAULT '{}',
    release_date TEXT    NOT NULL DEFAULT '',
    sale_end     TEXT    NOT NULL DEFAULT '',
    image_url    TEXT    NOT NULL DEFAULT '',
    icon_ext     TEXT    NOT NULL DEFAULT '',
    fetched_at   REAL    NOT NULL,
    sale_ends    TEXT    NOT NULL DEFAULT '{}'
);
