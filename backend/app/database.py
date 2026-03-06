from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

from .config import settings


_data_integrity_status: dict[str, object] = {
    "checked_at": "",
    "ok": True,
    "message": "not checked",
    "trade_opportunity_unique_index": False,
    "has_duplicate_trade_opportunities": False,
    "duplicate_trade_opportunity_count": 0,
    "duplicate_trade_opportunity_ids": [],
}


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


def _trade_unique_index_exists(conn: sqlite3.Connection) -> bool:
    rows = conn.execute("PRAGMA index_list('trades')").fetchall()
    for row in rows:
        if str(row["name"]) == "ux_trades_opportunity_id":
            return True
    return False


def _snapshot_data_integrity(conn: sqlite3.Connection) -> dict[str, object]:
    duplicate_rows = conn.execute(
        """
        SELECT opportunity_id, COUNT(*) AS trade_count
        FROM trades
        GROUP BY opportunity_id
        HAVING COUNT(*) > 1
        ORDER BY trade_count DESC, opportunity_id DESC
        LIMIT 20
        """
    ).fetchall()
    duplicate_items = [
        {
            "opportunity_id": int(row["opportunity_id"]),
            "trade_count": int(row["trade_count"]),
        }
        for row in duplicate_rows
    ]
    return {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "trade_opportunity_unique_index": _trade_unique_index_exists(conn),
        "has_duplicate_trade_opportunities": bool(duplicate_items),
        "duplicate_trade_opportunity_count": len(duplicate_items),
        "duplicate_trade_opportunity_ids": duplicate_items,
    }


def _set_data_integrity_status(payload: dict[str, object]) -> None:
    global _data_integrity_status
    _data_integrity_status = {**payload}


def get_data_integrity_status() -> dict[str, object]:
    return {**_data_integrity_status}


def _ensure_trade_uniqueness(conn: sqlite3.Connection) -> dict[str, object]:
    snapshot = _snapshot_data_integrity(conn)
    if snapshot["has_duplicate_trade_opportunities"]:
        snapshot["ok"] = False
        snapshot["message"] = "发现重复 trade，已跳过唯一索引创建"
        _set_data_integrity_status(snapshot)
        return snapshot

    if not snapshot["trade_opportunity_unique_index"]:
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS ux_trades_opportunity_id
            ON trades(opportunity_id)
            """
        )
        snapshot = _snapshot_data_integrity(conn)

    snapshot["ok"] = bool(snapshot["trade_opportunity_unique_index"])
    snapshot["message"] = (
        "trade opportunity 唯一索引已就绪"
        if snapshot["ok"]
        else "trade opportunity 唯一索引创建失败"
    )
    _set_data_integrity_status(snapshot)
    return snapshot


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

    CREATE TABLE IF NOT EXISTS execution_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_id INTEGER NOT NULL,
        action TEXT NOT NULL,
        provider TEXT NOT NULL,
        dry_run INTEGER NOT NULL DEFAULT 1,
        request_json TEXT NOT NULL DEFAULT '{}',
        response_json TEXT NOT NULL DEFAULT '{}',
        success INTEGER NOT NULL DEFAULT 0,
        error TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(trade_id) REFERENCES trades(id)
    );

    CREATE TABLE IF NOT EXISTS opportunity_reject_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        opportunity_id INTEGER NOT NULL,
        listing_row_id INTEGER NOT NULL,
        reject_mode TEXT NOT NULL DEFAULT 'manual',
        note TEXT NOT NULL DEFAULT '',
        snapshot_json TEXT NOT NULL DEFAULT '{}',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(opportunity_id) REFERENCES opportunities(id),
        FOREIGN KEY(listing_row_id) REFERENCES listings_raw(id)
    );

    CREATE INDEX IF NOT EXISTS idx_sales_title ON sales_raw(title);
    CREATE INDEX IF NOT EXISTS idx_listings_status ON listings_raw(status);
    CREATE INDEX IF NOT EXISTS idx_opp_status ON opportunities(status);
    CREATE INDEX IF NOT EXISTS idx_execution_logs_trade_id ON execution_logs(trade_id);
    CREATE INDEX IF NOT EXISTS idx_execution_logs_action_created ON execution_logs(action, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_opp_reject_logs_opp_id ON opportunity_reject_logs(opportunity_id);
    CREATE INDEX IF NOT EXISTS idx_opp_reject_logs_created ON opportunity_reject_logs(created_at DESC);
    """
    with get_conn() as conn:
        conn.executescript(ddl)
        _ensure_trade_uniqueness(conn)
