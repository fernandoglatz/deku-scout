-- depends: V002__create_games_cache_table

CREATE TABLE price_history_cache (
    slug       TEXT NOT NULL,
    currency   TEXT NOT NULL DEFAULT 'brl',
    data       TEXT NOT NULL,
    fetched_at REAL NOT NULL,
    PRIMARY KEY (slug, currency)
);

-- @rollback
DROP TABLE price_history_cache;
