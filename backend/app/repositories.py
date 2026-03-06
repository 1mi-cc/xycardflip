from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone
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


def _normalize_text_key(raw: str | None) -> str:
    text = str(raw or "").strip().lower()
    return " ".join(text.split())


def _normalize_price_key(raw: float | int | str | None) -> float:
    try:
        return round(float(raw or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _listing_fingerprint(
    *,
    source: str,
    seller_id: str | None,
    title: str | None,
    list_price: float | int | str | None,
) -> tuple[str, str, str, float]:
    return (
        str(source or "").strip(),
        _normalize_optional_id(seller_id) or "",
        _normalize_text_key(title),
        _normalize_price_key(list_price),
    )


def _load_existing_listing_fingerprints(
    conn: sqlite3.Connection,
    fingerprints: set[tuple[str, str, str, float]],
) -> set[tuple[str, str, str, float]]:
    if not fingerprints:
        return set()

    # Keep dedupe window bounded so historical listings do not suppress recent legitimate relists.
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
    rows = conn.execute(
        """
        SELECT source, seller_id, title, list_price
        FROM listings_raw
        WHERE status = 'open' AND listed_at >= ?
        ORDER BY id DESC
        LIMIT 5000
        """,
        (cutoff,),
    ).fetchall()
    existing: set[tuple[str, str, str, float]] = set()
    for row in rows:
        fp = _listing_fingerprint(
            source=str(row["source"] or ""),
            seller_id=row["seller_id"],
            title=row["title"],
            list_price=row["list_price"],
        )
        if fp in fingerprints:
            existing.add(fp)
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
    row_fingerprints = {
        _listing_fingerprint(
            source=row.source,
            seller_id=_normalize_optional_id(row.seller_id),
            title=row.title,
            list_price=row.list_price,
        )
        for row in rows
        if not _normalize_optional_id(row.listing_id)
    }

    values: list[tuple[Any, ...]] = []
    seen_in_batch: set[tuple[str, str]] = set()
    seen_fingerprints_in_batch: set[tuple[str, str, str, float]] = set()
    with get_conn() as conn:
        existing_pairs = _load_existing_pairs(
            conn,
            "listings_raw",
            "listing_id",
            row_listing_pairs,
        )
        existing_fingerprints = _load_existing_listing_fingerprints(conn, row_fingerprints)
        for row in rows:
            listing_id = _normalize_optional_id(row.listing_id)
            seller_id = _normalize_optional_id(row.seller_id)
            if listing_id:
                key = (row.source, listing_id)
                if key in existing_pairs or key in seen_in_batch:
                    continue
                seen_in_batch.add(key)
            else:
                fp = _listing_fingerprint(
                    source=row.source,
                    seller_id=seller_id,
                    title=row.title,
                    list_price=row.list_price,
                )
                if fp in existing_fingerprints or fp in seen_fingerprints_in_batch:
                    continue
                seen_fingerprints_in_batch.add(fp)

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


def get_listing_by_source_listing_id(source: str, listing_id: str) -> sqlite3.Row | None:
    normalized_id = _normalize_optional_id(listing_id)
    if not normalized_id:
        return None
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT *
            FROM listings_raw
            WHERE source = ? AND listing_id = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (str(source), normalized_id),
        )
        return cur.fetchone()


def upsert_listing(row: ListingIn) -> tuple[int | None, bool]:
    listing_id = _normalize_optional_id(row.listing_id)
    seller_id = _normalize_optional_id(row.seller_id)
    if listing_id:
        existing = get_listing_by_source_listing_id(row.source, listing_id)
        if existing:
            return int(existing["id"]), False
    else:
        fp = _listing_fingerprint(
            source=row.source,
            seller_id=seller_id,
            title=row.title,
            list_price=row.list_price,
        )
        with get_conn() as conn:
            existing = _load_existing_listing_fingerprints(conn, {fp})
            if fp in existing:
                candidates = conn.execute(
                    """
                    SELECT id, title
                    FROM listings_raw
                    WHERE source = ? AND COALESCE(seller_id, '') = ? AND ROUND(list_price, 2) = ?
                      AND status = 'open'
                    ORDER BY id DESC
                    LIMIT 200
                    """,
                    (fp[0], fp[1], fp[3]),
                ).fetchall()
                for item in candidates:
                    if _normalize_text_key(item["title"]) == fp[2]:
                        return int(item["id"]), False

    sql = """
    INSERT INTO listings_raw(source, listing_id, seller_id, title, description, list_price, listed_at, status, raw_json)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    with get_conn() as conn:
        cur = conn.execute(
            sql,
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
            ),
        )
        return int(cur.lastrowid), True


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


def get_opportunity_status_map_by_listing_rows(
    listing_row_ids: list[int],
) -> dict[int, str]:
    if not listing_row_ids:
        return {}
    normalized = sorted({int(row_id) for row_id in listing_row_ids if int(row_id) > 0})
    if not normalized:
        return {}
    placeholders = ",".join("?" for _ in normalized)
    sql = f"""
    SELECT listing_row_id, status
    FROM opportunities
    WHERE listing_row_id IN ({placeholders})
    """
    with get_conn() as conn:
        rows = conn.execute(sql, tuple(normalized)).fetchall()
    return {
        int(row["listing_row_id"]): str(row["status"] or "")
        for row in rows
    }


def has_frozen_opportunity_for_listing_fingerprint(
    *,
    source: str,
    seller_id: str | None,
    title: str,
    list_price: float,
    exclude_listing_row_id: int | None = None,
) -> bool:
    normalized_title = _normalize_text_key(title)
    normalized_seller = _normalize_optional_id(seller_id) or ""
    normalized_price = _normalize_price_key(list_price)
    sql = """
    SELECT l.id, l.title, o.status
    FROM listings_raw l
    JOIN opportunities o ON o.listing_row_id = l.id
    WHERE l.source = ?
      AND COALESCE(l.seller_id, '') = ?
      AND ROUND(l.list_price, 2) = ?
      AND l.status = 'open'
      AND o.status IN ('rejected', 'approved_for_buy')
    """
    params: list[Any] = [str(source or "").strip(), normalized_seller, normalized_price]
    if exclude_listing_row_id is not None:
        sql += " AND l.id != ?"
        params.append(int(exclude_listing_row_id))
    sql += " ORDER BY l.id DESC LIMIT 200"
    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    for row in rows:
        if _normalize_text_key(row["title"]) == normalized_title:
            return True
    return False


def has_reject_history_for_listing_signature(
    *,
    source: str,
    seller_id: str | None,
    title: str,
    exclude_listing_row_id: int | None = None,
) -> bool:
    normalized_title = _normalize_text_key(title)
    normalized_seller = _normalize_optional_id(seller_id) or ""

    sql = """
    SELECT l.id, l.title
    FROM opportunities o
    JOIN listings_raw l ON l.id = o.listing_row_id
    WHERE l.source = ?
      AND COALESCE(l.seller_id, '') = ?
      AND o.status = 'rejected'
      AND l.status = 'open'
    """
    params: list[Any] = [str(source or "").strip(), normalized_seller]
    if exclude_listing_row_id is not None:
        sql += " AND l.id != ?"
        params.append(int(exclude_listing_row_id))
    sql += " ORDER BY l.id DESC LIMIT 200"

    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        for row in rows:
            if _normalize_text_key(row["title"]) == normalized_title:
                return True

        # Secondary guard: if a row was rejected and later status drifted, keep blocking by reject logs.
        log_sql = """
        SELECT l.id, l.title
        FROM opportunity_reject_logs r
        JOIN listings_raw l ON l.id = r.listing_row_id
        WHERE l.source = ?
          AND COALESCE(l.seller_id, '') = ?
        """
        log_params: list[Any] = [str(source or "").strip(), normalized_seller]
        if exclude_listing_row_id is not None:
            log_sql += " AND l.id != ?"
            log_params.append(int(exclude_listing_row_id))
        log_sql += " ORDER BY r.id DESC LIMIT 200"

        log_rows = conn.execute(log_sql, tuple(log_params)).fetchall()
        for row in log_rows:
            if _normalize_text_key(row["title"]) == normalized_title:
                return True

    return False


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


def create_opportunity_reject_log(
    opportunity_id: int,
    *,
    note: str = "",
    reject_mode: str = "manual",
) -> int | None:
    with get_conn() as conn:
        context_row = conn.execute(
            """
            SELECT
                o.id AS opportunity_id,
                o.listing_row_id,
                o.valuation_id,
                o.status AS opportunity_status,
                o.expected_profit,
                o.roi,
                o.score,
                o.review_note,
                o.created_at AS opportunity_created_at,
                o.reviewed_at AS opportunity_reviewed_at,
                l.source,
                l.listing_id,
                l.seller_id,
                l.title,
                l.description,
                l.list_price,
                l.listed_at,
                l.status AS listing_status,
                v.expected_sale_price,
                v.buy_limit,
                v.suggested_list_price,
                v.ci_low,
                v.ci_high,
                v.model_confidence,
                v.comparables_count,
                v.reasoning AS valuation_reasoning,
                v.created_at AS valuation_created_at
            FROM opportunities o
            JOIN listings_raw l ON l.id = o.listing_row_id
            LEFT JOIN valuation_records v ON v.id = o.valuation_id
            WHERE o.id = ?
            """,
            (opportunity_id,),
        ).fetchone()
        if not context_row:
            return None

        snapshot = {
            "opportunity": {
                "id": int(context_row["opportunity_id"]),
                "status": str(context_row["opportunity_status"] or ""),
                "expected_profit": float(context_row["expected_profit"] or 0.0),
                "roi": float(context_row["roi"] or 0.0),
                "score": float(context_row["score"] or 0.0),
                "review_note": str(context_row["review_note"] or ""),
                "created_at": context_row["opportunity_created_at"],
                "reviewed_at": context_row["opportunity_reviewed_at"],
            },
            "listing": {
                "row_id": int(context_row["listing_row_id"]),
                "source": str(context_row["source"] or ""),
                "listing_id": context_row["listing_id"],
                "seller_id": context_row["seller_id"],
                "title": str(context_row["title"] or ""),
                "description": str(context_row["description"] or ""),
                "list_price": float(context_row["list_price"] or 0.0),
                "listed_at": context_row["listed_at"],
                "status": str(context_row["listing_status"] or ""),
            },
            "valuation": {
                "id": context_row["valuation_id"],
                "expected_sale_price": float(context_row["expected_sale_price"] or 0.0),
                "buy_limit": float(context_row["buy_limit"] or 0.0),
                "suggested_list_price": float(context_row["suggested_list_price"] or 0.0),
                "ci_low": float(context_row["ci_low"] or 0.0),
                "ci_high": float(context_row["ci_high"] or 0.0),
                "model_confidence": float(context_row["model_confidence"] or 0.0),
                "comparables_count": int(context_row["comparables_count"] or 0),
                "reasoning": str(context_row["valuation_reasoning"] or ""),
                "created_at": context_row["valuation_created_at"],
            },
        }

        cur = conn.execute(
            """
            INSERT INTO opportunity_reject_logs(
                opportunity_id, listing_row_id, reject_mode, note, snapshot_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(context_row["opportunity_id"]),
                int(context_row["listing_row_id"]),
                str(reject_mode or "manual"),
                str(note or ""),
                json.dumps(snapshot, ensure_ascii=True),
            ),
        )
        return int(cur.lastrowid)


def list_opportunity_reject_logs(
    *,
    opportunity_id: int | None = None,
    limit: int = 200,
) -> list[sqlite3.Row]:
    sql = """
    SELECT
        r.*,
        l.title,
        l.list_price,
        o.status AS current_status
    FROM opportunity_reject_logs r
    LEFT JOIN listings_raw l ON l.id = r.listing_row_id
    LEFT JOIN opportunities o ON o.id = r.opportunity_id
    """
    params: list[Any] = []
    if opportunity_id is not None:
        sql += " WHERE r.opportunity_id = ?"
        params.append(opportunity_id)
    sql += " ORDER BY r.id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()


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


def get_opportunity_by_listing_row_id(listing_row_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT o.*, l.list_price, v.suggested_list_price
            FROM opportunities o
            JOIN listings_raw l ON l.id = o.listing_row_id
            JOIN valuation_records v ON v.id = o.valuation_id
            WHERE o.listing_row_id = ?
            """,
            (listing_row_id,),
        )
        return cur.fetchone()


def _get_trade_by_opportunity_id_with_conn(
    conn: sqlite3.Connection, opportunity_id: int
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT t.*, o.listing_row_id, l.title, l.list_price
        FROM trades t
        JOIN opportunities o ON o.id = t.opportunity_id
        JOIN listings_raw l ON l.id = o.listing_row_id
        WHERE t.opportunity_id = ?
        ORDER BY t.id DESC
        LIMIT 1
        """,
        (opportunity_id,),
    ).fetchone()


def get_trade_by_opportunity_id(opportunity_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        return _get_trade_by_opportunity_id_with_conn(conn, opportunity_id)


def approve_opportunity_idempotent(
    *,
    opportunity_id: int,
    approved_buy_price: float,
    approved_by: str,
    note: str,
) -> dict[str, Any]:
    with get_conn() as conn:
        conn.execute("BEGIN IMMEDIATE")
        opp = conn.execute(
            """
            SELECT o.*, l.list_price, v.suggested_list_price
            FROM opportunities o
            JOIN listings_raw l ON l.id = o.listing_row_id
            JOIN valuation_records v ON v.id = o.valuation_id
            WHERE o.id = ?
            """,
            (opportunity_id,),
        ).fetchone()
        if not opp:
            raise ValueError("Opportunity not found")

        target_sell_price = float(opp["suggested_list_price"])
        opportunity_status = str(opp["status"] or "")
        existing_trade = _get_trade_by_opportunity_id_with_conn(conn, opportunity_id)
        if existing_trade:
            existing_trade_id = int(existing_trade["id"])
            return {
                "trade_id": existing_trade_id,
                "existing_trade_id": existing_trade_id,
                "created": False,
                "idempotent": True,
                "status": str(existing_trade["status"] or "approved_for_buy"),
                "opportunity_status": opportunity_status,
                "target_sell_price": target_sell_price,
                "approved_buy_price": float(existing_trade["approved_buy_price"]),
            }

        if opportunity_status != "pending_review":
            return {
                "trade_id": None,
                "existing_trade_id": None,
                "created": False,
                "idempotent": False,
                "status": opportunity_status,
                "opportunity_status": opportunity_status,
                "reason": "opportunity_not_pending_review",
                "message": "Opportunity is not pending review",
                "target_sell_price": target_sell_price,
                "approved_buy_price": float(approved_buy_price),
            }

        try:
            cur = conn.execute(
                """
                INSERT INTO trades(
                    opportunity_id,
                    approved_buy_price,
                    target_sell_price,
                    approved_by,
                    note
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    opportunity_id,
                    approved_buy_price,
                    target_sell_price,
                    approved_by,
                    note,
                ),
            )
        except sqlite3.IntegrityError:
            existing_trade = _get_trade_by_opportunity_id_with_conn(conn, opportunity_id)
            if existing_trade:
                existing_trade_id = int(existing_trade["id"])
                return {
                    "trade_id": existing_trade_id,
                    "existing_trade_id": existing_trade_id,
                    "created": False,
                    "idempotent": True,
                    "status": str(existing_trade["status"] or "approved_for_buy"),
                    "opportunity_status": opportunity_status,
                    "target_sell_price": target_sell_price,
                    "approved_buy_price": float(existing_trade["approved_buy_price"]),
                }
            raise

        trade_id = int(cur.lastrowid)
        conn.execute(
            """
            UPDATE opportunities
            SET status = ?, review_note = ?, reviewed_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            ("approved_for_buy", note, opportunity_id),
        )
        return {
            "trade_id": trade_id,
            "existing_trade_id": None,
            "created": True,
            "idempotent": False,
            "status": "approved_for_buy",
            "opportunity_status": "approved_for_buy",
            "target_sell_price": target_sell_price,
            "approved_buy_price": float(approved_buy_price),
        }


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


def create_execution_log(
    *,
    trade_id: int,
    action: str,
    provider: str,
    dry_run: bool,
    request_payload: dict[str, Any] | None = None,
    response_payload: dict[str, Any] | None = None,
    success: bool,
    error: str = "",
) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO execution_logs(
                trade_id, action, provider, dry_run, request_json, response_json, success, error
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trade_id,
                action,
                provider,
                1 if dry_run else 0,
                json.dumps(request_payload or {}, ensure_ascii=True),
                json.dumps(response_payload or {}, ensure_ascii=True),
                1 if success else 0,
                error,
            ),
        )
    return int(cur.lastrowid)


def list_execution_logs(
    *,
    trade_id: int | None = None,
    action: str | None = None,
    provider: str | None = None,
    dry_run: bool | None = None,
    success: bool | None = None,
    limit: int = 100,
) -> list[sqlite3.Row]:
    base_sql = """
    SELECT e.*, t.status AS trade_status, t.approved_buy_price, t.target_sell_price
    FROM execution_logs e
    JOIN trades t ON t.id = e.trade_id
    """
    params: list[Any] = []
    where: list[str] = []
    if trade_id is not None:
        where.append("e.trade_id = ?")
        params.append(trade_id)
    if action:
        where.append("e.action = ?")
        params.append(action)
    if provider:
        where.append("e.provider = ?")
        params.append(provider)
    if dry_run is not None:
        where.append("e.dry_run = ?")
        params.append(1 if dry_run else 0)
    if success is not None:
        where.append("e.success = ?")
        params.append(1 if success else 0)
    sql = base_sql
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY e.id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()


def get_latest_execution_log(
    *,
    trade_id: int,
    action: str,
    success_only: bool = False,
) -> sqlite3.Row | None:
    sql = """
    SELECT *
    FROM execution_logs
    WHERE trade_id = ? AND action = ?
    """
    params: list[Any] = [trade_id, action]
    if success_only:
        sql += " AND success = 1"
    sql += " ORDER BY id DESC LIMIT 1"
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchone()


def list_latest_failed_execution_candidates(
    *,
    action: str | None = None,
    limit: int = 20,
) -> list[sqlite3.Row]:
    sql = """
    WITH latest AS (
        SELECT trade_id, action, MAX(id) AS max_id
        FROM execution_logs
        GROUP BY trade_id, action
    )
    SELECT e.*, t.status AS trade_status
    FROM execution_logs e
    JOIN latest l ON l.max_id = e.id
    JOIN trades t ON t.id = e.trade_id
    WHERE e.success = 0
    """
    params: list[Any] = []
    if action:
        sql += " AND e.action = ?"
        params.append(action)
    sql += " ORDER BY e.id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        return cur.fetchall()
