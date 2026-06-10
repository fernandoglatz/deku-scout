CREATE TABLE cookies (
    name   TEXT NOT NULL,
    value  TEXT NOT NULL,
    domain TEXT NOT NULL DEFAULT '',
    path   TEXT NOT NULL DEFAULT '/',
    locale TEXT NOT NULL DEFAULT 'br',
    PRIMARY KEY (name, domain, path, locale)
);
