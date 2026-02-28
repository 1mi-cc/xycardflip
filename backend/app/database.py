from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import Iterator

from .config import settings


def _connect() -> sqlite3.Connection:
    settings.ensure_paths()
    conn = sqlite3.connect(settings.sqlite_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@contextmanager
def get_conn() -> Iterator[sqlite3.Connection]:
    conn = _connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    ddl = """
    CREATE TABLE IF NOT EXISTS sales_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        item_id TEXT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        sold_price REAL NOT NULL,
        sold_at TEXT NOT NULL,
        raw_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS listings_raw (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        source TEXT NOT NULL,
        listing_id TEXT,
        seller_id TEXT,
        title TEXT NOT NULL,
        description TEXT DEFAULT '',
        list_price REAL NOT NULL,
        listed_at TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'open',
        raw_json TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );

    CREATE TABLE IF NOT EXISTS item_features (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        ref_type TEXT NOT NULL,
        ref_id INTEGER NOT NULL,
        card_name TEXT NOT NULL,
        rarity TEXT NOT NULL DEFAULT 'unknown',
        edition TEXT NOT NULL DEFAULT 'unknown',
        card_condition TEXT NOT NULL DEFAULT 'unknown',
        extras_json TEXT NOT NULL DEFAULT '{}',
        confidence REAL NOT NULL DEFAULT 0.5,
        extracted_by TEXT NOT NULL,
        extracted_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(ref_type, ref_id)
    );

    CREATE TABLE IF NOT EXISTS valuation_records (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_row_id INTEGER NOT NULL,
        expected_sale_price REAL NOT NULL,
        buy_limit REAL NOT NULL,
        suggested_list_price REAL NOT NULL,
        ci_low REAL NOT NULL,
        ci_high REAL NOT NULL,
        model_confidence REAL NOT NULL,
        comparables_count INTEGER NOT NULL,
        reasoning TEXT NOT NULL,
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(listing_row_id) REFERENCES listings_raw(id)
    );

    CREATE TABLE IF NOT EXISTS opportunities (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        listing_row_id INTEGER NOT NULL UNIQUE,
        valuation_id INTEGER NOT NULL,
        expected_profit REAL NOT NULL,
        roi REAL NOT NULL,
        score REAL NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending_review',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        reviewed_at TEXT,
        review_note TEXT DEFAULT '',
        FOREIGN KEY(listing_row_id) REFERENCES listings_raw(id),
        FOREIGN KEY(valuation_id) REFERENCES valuation_records(id)
    );

    CREATE TABLE IF NOT EXISTS trades (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        opportunity_id INTEGER NOT NULL,
        status TEXT NOT NULL DEFAULT 'approved_for_buy',
        approved_buy_price REAL NOT NULL,
        target_sell_price REAL NOT NULL,
        approved_by TEXT NOT NULL,
        listing_url TEXT DEFAULT '',
        sold_price REAL,
        note TEXT DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id)
    );

    CREATE INDEX IF NOT EXISTS idx_sales_title ON sales_raw(title);
    CREATE INDEX IF NOT EXISTS idx_listings_status ON listings_raw(status);
    CREATE INDEX IF NOT EXISTS idx_opp_status ON opportunities(status);
    """
    with get_conn() as conn:
        conn.executescript(ddl)

