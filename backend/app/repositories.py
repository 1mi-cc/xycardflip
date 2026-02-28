from __future__ import annotations

import json
import sqlite3
from typing import Any

from .database import get_conn
from .schemas import FeatureData, ListingIn, SaleIn, ValuationOut


def _normalize_optional_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _load_existing_pairs(
    conn: sqlite3.Connection,
    table: str,
    id_column: str,
    pairs: set[tuple[str, str]],
) -> set[tuple[str, str]]:
    ids = sorted({id_value for _, id_value in pairs})
    if not ids:
        return set()

    placeholders = ",".join("?" for _ in ids)
    sql = f"SELECT source, {id_column} FROM {table} WHERE {id_column} IN ({placeholders})"
    rows = conn.execute(sql, tuple(ids)).fetchall()
    existing: set[tuple[str, str]] = set()
    for row in rows:
        source = str(row["source"])
        id_value_raw = row[id_column]
        if id_value_raw is None:
            continue
        id_value = str(id_value_raw)
        existing.add((source, id_value))
    return existing


def insert_sales(rows: list[SaleIn]) -> int:
    sql = """
    INSERT INTO sales_raw(source, item_id, title, description, sold_price, sold_at, raw_json)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    row_item_pairs = {
        (row.source, item_id)
        for row in rows
        for item_id in [_normalize_optional_id(row.item_id)]
        if item_id
    }

    values: list[tuple[Any, ...]] = []
    seen_in_batch: set[tuple[str, str]] = set()
    with get_conn() as conn:
        existing_pairs = _load_existing_pairs(conn, "sales_raw", "item_id", row_item_pairs)
        for row in rows:
            item_id = _normalize_optional_id(row.item_id)
            if item_id:
                key = (row.source, item_id)
                if key in existing_pairs or key in seen_in_batch:
                    continue
                seen_in_batch.add(key)

            values.append(
                (
                    row.source,
                    item_id,
                    row.title,
                    row.description,
                    row.sold_price,
                    row.sold_at.isoformat(),
                    json.dumps(row.raw, ensure_ascii=True),
                )
            )

        if not values:
            return 0
        conn.executemany(sql, values)
    return len(values)


def insert_listings(rows: list[ListingIn]) -> int:
    sql = """
    INSERT INTO listings_raw(source, listing_id, seller_id, title, description, list_price, listed_at, status, raw_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    row_listing_pairs = {
        (row.source, listing_id)
        for row in rows
        for listing_id in [_normalize_optional_id(row.listing_id)]
        if listing_id
    }

    values: list[tuple[Any, ...]] = []
    seen_in_batch: set[tuple[str, str]] = set()
    with get_conn() as conn:
        existing_pairs = _load_existing_pairs(
            conn,
            "listings_raw",
            "listing_id",
            row_listing_pairs,
        )
        for row in rows:
            listing_id = _normalize_optional_id(row.listing_id)
            seller_id = _normalize_optional_id(row.seller_id)
            if listing_id:
                key = (row.source, listing_id)
                if key in existing_pairs or key in seen_in_batch:
                    continue
                seen_in_batch.add(key)

            values.append(
                (
                    row.source,
                    listing_id,
                    seller_id,
                    row.title,
                    row.description,
                    row.list_price,
                    row.listed_at.isoformat(),
                    row.status,
                    json.dumps(row.raw, ensure_ascii=True),
                )
            )

        if not values:
            return 0
        conn.executemany(sql, values)
    return len(values)


def get_listing(row_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute("SELECT * FROM listings_raw WHERE id = ?", (row_id,))
        return cur.fetchone()


def get_open_listings(limit: int = 50) -> list[sqlite3.Row]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM listings_raw WHERE status = 'open' ORDER BY listed_at DESC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()


def get_seller_open_listing_count(source: str, seller_id: str | None, exclude_row_id: int | None = None) -> int:
    normalized = _normalize_optional_id(seller_id)
    if not normalized:
        return 0
    with get_conn() as conn:
        if exclude_row_id is None:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM listings_raw
                WHERE source = ? AND seller_id = ? AND status = 'open'
                """,
                (source, normalized),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM listings_raw
                WHERE source = ? AND seller_id = ? AND status = 'open' AND id != ?
                """,
                (source, normalized, exclude_row_id),
            ).fetchone()
    return int(row["c"]) if row else 0


def save_features(ref_type: str, ref_id: int, feature: FeatureData, extracted_by: str) -> int:
    sql = """
    INSERT INTO item_features(ref_type, ref_id, card_name, rarity, edition, card_condition, extras_json, confidence, extracted_by)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(ref_type, ref_id) DO UPDATE SET
        card_name=excluded.card_name,
        rarity=excluded.rarity,
        edition=excluded.edition,
        card_condition=excluded.card_condition,
        extras_json=excluded.extras_json,
        confidence=excluded.confidence,
        extracted_by=excluded.extracted_by,
        extracted_at=CURRENT_TIMESTAMP
    """
    with get_conn() as conn:
        conn.execute(
            sql,
            (
                ref_type,
                ref_id,
                feature.card_name,
                feature.rarity,
                feature.edition,
                feature.card_condition,
                json.dumps(feature.extras, ensure_ascii=True),
                feature.confidence,
                extracted_by,
            ),
        )
        row = conn.execute(
            "SELECT id FROM item_features WHERE ref_type = ? AND ref_id = ?",
            (ref_type, ref_id),
        ).fetchone()
    return int(row["id"])


def get_features(ref_type: str, ref_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM item_features WHERE ref_type = ? AND ref_id = ?",
            (ref_type, ref_id),
        )
        return cur.fetchone()


def get_recent_sales(features: FeatureData, limit: int = 80) -> list[sqlite3.Row]:
    sql = """
    SELECT s.sold_price, s.sold_at
    FROM sales_raw s
    LEFT JOIN item_features f ON f.ref_type = 'sale' AND f.ref_id = s.id
    WHERE
        (f.card_name = ? OR s.title LIKE ?)
        AND (? = 'unknown' OR f.rarity = ? OR f.rarity IS NULL)
        AND (? = 'unknown' OR f.edition = ? OR f.edition IS NULL)
    ORDER BY s.sold_at DESC
    LIMIT ?
    """
    with get_conn() as conn:
        cur = conn.execute(
            sql,
            (
                features.card_name,
                f"%{features.card_name}%",
                features.rarity,
                features.rarity,
                features.edition,
                features.edition,
                limit,
            ),
        )
        return cur.fetchall()


def save_valuation(result: ValuationOut) -> int:
    sql = """
    INSERT INTO valuation_records(
        listing_row_id, expected_sale_price, buy_limit, suggested_list_price,
        ci_low, ci_high, model_confidence, comparables_count, reasoning
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with get_conn() as conn:
        cur = conn.execute(
            sql,
            (
                result.listing_row_id,
                result.expected_sale_price,
                result.buy_limit,
                result.suggested_list_price,
                result.ci_low,
                result.ci_high,
                result.model_confidence,
                result.comparables_count,
                result.reasoning,
            ),
        )
        return int(cur.lastrowid)


def get_latest_valuation_for_listing(listing_row_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM valuation_records WHERE listing_row_id = ? ORDER BY id DESC LIMIT 1",
            (listing_row_id,),
        )
        return cur.fetchone()


def upsert_opportunity(
    listing_row_id: int,
    valuation_id: int,
    expected_profit: float,
    roi: float,
    score: float,
    status: str,
    note: str = "",
) -> int:
    sql = """
    INSERT INTO opportunities(
        listing_row_id,
        valuation_id,
        expected_profit,
        roi,
        score,
        status,
        review_note
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(listing_row_id) DO UPDATE SET
        valuation_id=excluded.valuation_id,
        expected_profit=excluded.expected_profit,
        roi=excluded.roi,
        score=excluded.score,
        status=excluded.status,
        review_note=excluded.review_note,
        reviewed_at=NULL
    """
    with get_conn() as conn:
        conn.execute(
            sql,
            (listing_row_id, valuation_id, expected_profit, roi, score, status, note),
        )
        row = conn.execute(
            "SELECT id FROM opportunities WHERE listing_row_id = ?",
            (listing_row_id,),
        ).fetchone()
    return int(row["id"])


def list_opportunities(status: str | None = None, limit: int = 100) -> list[sqlite3.Row]:
    base_sql = """
    SELECT o.*, l.title, l.list_price, v.expected_sale_price, v.suggested_list_price
    FROM opportunities o
    JOIN listings_raw l ON l.id = o.listing_row_id
    JOIN valuation_records v ON v.id = o.valuation_id
    """
    params: tuple[Any, ...]
    if status:
        sql = f"{base_sql} WHERE o.status = ? ORDER BY o.score DESC LIMIT ?"
        params = (status, limit)
    else:
        sql = f"{base_sql} ORDER BY o.score DESC LIMIT ?"
        params = (limit,)
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def update_opportunity_status(opportunity_id: int, status: str, note: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE opportunities
            SET status = ?, review_note = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, note, opportunity_id),
        )


def get_opportunity(opportunity_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT o.*, l.list_price, v.suggested_list_price
            FROM opportunities o
            JOIN listings_raw l ON l.id = o.listing_row_id
            JOIN valuation_records v ON v.id = o.valuation_id
            WHERE o.id = ?
            """,
            (opportunity_id,),
        )
        return cur.fetchone()


def create_trade(
    opportunity_id: int,
    approved_buy_price: float,
    target_sell_price: float,
    approved_by: str,
    note: str,
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO trades(opportunity_id, approved_buy_price, target_sell_price, approved_by, note)
            VALUES (?, ?, ?, ?, ?)
            """,
            (opportunity_id, approved_buy_price, target_sell_price, approved_by, note),
        )
        return int(cur.lastrowid)


def get_trade(trade_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT t.*, o.listing_row_id, l.title, l.list_price
            FROM trades t
            JOIN opportunities o ON o.id = t.opportunity_id
            JOIN listings_raw l ON l.id = o.listing_row_id
            WHERE t.id = ?
            """,
            (trade_id,),
        )
        return cur.fetchone()


def get_trade_pricing_context(trade_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT
                t.id AS trade_id,
                t.status,
                t.approved_buy_price,
                t.target_sell_price,
                t.created_at AS trade_created_at,
                t.updated_at AS trade_updated_at,
                o.id AS opportunity_id,
                l.id AS listing_row_id,
                l.title,
                l.source,
                l.seller_id,
                v.expected_sale_price,
                v.suggested_list_price,
                v.ci_low,
                v.ci_high
            FROM trades t
            JOIN opportunities o ON o.id = t.opportunity_id
            JOIN listings_raw l ON l.id = o.listing_row_id
            JOIN valuation_records v ON v.id = o.valuation_id
            WHERE t.id = ?
            """,
            (trade_id,),
        )
        return cur.fetchone()


def list_recent_sold_trade_prices_by_title_keyword(keyword: str, limit: int = 30) -> list[float]:
    normalized = keyword.strip()
    if not normalized:
        return []
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT t.sold_price
            FROM trades t
            JOIN opportunities o ON o.id = t.opportunity_id
            JOIN listings_raw l ON l.id = o.listing_row_id
            WHERE t.status = 'sold'
              AND t.sold_price IS NOT NULL
              AND l.title LIKE ?
            ORDER BY t.updated_at DESC
            LIMIT ?
            """,
            (f"%{normalized}%", limit),
        ).fetchall()
    return [float(r["sold_price"]) for r in rows if r["sold_price"] is not None]


def count_active_trades() -> int:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*) AS c
            FROM trades
            WHERE status IN ('approved_for_buy', 'listed_for_sale')
            """
        ).fetchone()
    return int(row["c"]) if row else 0


def list_open_trade_ids(limit: int = 100) -> list[int]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT id
            FROM trades
            WHERE status IN ('approved_for_buy', 'listed_for_sale')
            ORDER BY updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [int(r["id"]) for r in rows]


def list_trades(status: str | None = None, limit: int = 100) -> list[sqlite3.Row]:
    base_sql = """
    SELECT t.*, o.listing_row_id, l.title, l.list_price
    FROM trades t
    JOIN opportunities o ON o.id = t.opportunity_id
    JOIN listings_raw l ON l.id = o.listing_row_id
    """
    params: tuple[Any, ...]
    if status:
        sql = f"{base_sql} WHERE t.status = ? ORDER BY t.updated_at DESC LIMIT ?"
        params = (status, limit)
    else:
        sql = f"{base_sql} ORDER BY t.updated_at DESC LIMIT ?"
        params = (limit,)
    with get_conn() as conn:
        cur = conn.execute(sql, params)
        return cur.fetchall()


def update_trade_target_price(trade_id: int, target_sell_price: float, note: str = "") -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE trades
            SET target_sell_price = ?,
                note = CASE
                    WHEN ? = '' THEN note
                    WHEN note = '' THEN ?
                    ELSE note || '; ' || ?
                END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (target_sell_price, note, note, note, trade_id),
        )


def update_trade_listed(trade_id: int, listing_url: str, note: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE trades
            SET status = 'listed_for_sale',
                listing_url = ?,
                note = CASE WHEN note = '' THEN ? ELSE note || '; ' || ? END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (listing_url, note, note, trade_id),
        )


def update_trade_sold(trade_id: int, sold_price: float, note: str) -> None:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE trades
            SET status = 'sold',
                sold_price = ?,
                note = CASE WHEN note = '' THEN ? ELSE note || '; ' || ? END,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (sold_price, note, note, trade_id),
        )


def get_dashboard_metrics() -> dict[str, Any]:
    with get_conn() as conn:
        pending = conn.execute(
            "SELECT COUNT(*) AS c FROM opportunities WHERE status = 'pending_review'"
        ).fetchone()["c"]
        approved = conn.execute(
            "SELECT COUNT(*) AS c FROM trades WHERE status IN ('approved_for_buy', 'listed_for_sale')"
        ).fetchone()["c"]
        sold_row = conn.execute(
            """
            SELECT COUNT(*) AS c,
                   COALESCE(SUM(sold_price - approved_buy_price), 0) AS gross_profit
            FROM trades
            WHERE status = 'sold'
            """
        ).fetchone()
        return {
            "pending_review_count": pending,
            "active_trades_count": approved,
            "sold_count": sold_row["c"],
            "gross_profit": round(float(sold_row["gross_profit"]), 2),
        }
