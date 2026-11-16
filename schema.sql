-- Database schema for Stocks Website.
-- Applied automatically on startup; every statement is safe to re-run.

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
    username TEXT NOT NULL,
    hash TEXT NOT NULL,
    cash NUMERIC NOT NULL DEFAULT 10000.00
);

CREATE UNIQUE INDEX IF NOT EXISTS username ON users (username);

-- One row per buy (positive shares) or sell (negative shares).
CREATE TABLE IF NOT EXISTS transactions (
    user_id INTEGER NOT NULL,
    user TEXT NOT NULL,
    name TEXT NOT NULL,
    symbol TEXT NOT NULL,
    shares INTEGER NOT NULL,
    price NUMERIC NOT NULL,
    datetime TEXT,
    FOREIGN KEY(user_id) REFERENCES users(id)
);

CREATE INDEX IF NOT EXISTS user_index ON transactions (user_id);
