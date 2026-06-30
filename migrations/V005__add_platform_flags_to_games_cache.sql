-- depends: V002__create_games_cache_table

ALTER TABLE games_cache ADD COLUMN switch1 INTEGER NOT NULL DEFAULT 0;
ALTER TABLE games_cache ADD COLUMN switch2 INTEGER NOT NULL DEFAULT 0;
