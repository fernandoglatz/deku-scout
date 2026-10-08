-- depends: V006__create_performance_cache_table

CREATE TABLE switchplaza_cache (
    norm_name  TEXT    PRIMARY KEY,
    fps        INTEGER NOT NULL DEFAULT 0,
    label      TEXT    NOT NULL DEFAULT '',
    resolution TEXT    NOT NULL DEFAULT '',
    patch_type TEXT    NOT NULL DEFAULT '',
    docked     TEXT    NOT NULL DEFAULT '',
    handheld   TEXT    NOT NULL DEFAULT '',
    fetched_at REAL    NOT NULL
);
