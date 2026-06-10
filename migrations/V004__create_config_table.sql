-- depends: V003__create_price_history_cache_table

CREATE TABLE config (
    key        TEXT PRIMARY KEY,
    value      TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
