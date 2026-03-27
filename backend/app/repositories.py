from __future__ import annotations

import json
import math
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import settings
from .database import get_conn
from .database import record_batch_write_status
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
                WHERE source = ? AND COALESCE(seller_id, '') = ? AND status = 'open'
                """,
                (source, normalized),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT COUNT(*) AS c
                FROM listings_raw
                WHERE source = ? AND COALESCE(seller_id, '') = ? AND status = 'open' AND id != ?
                """,
                (source, normalized, exclude_row_id),
            ).fetchone()
    return int(row["c"]) if row else 0


def _save_features_with_conn(
    conn: sqlite3.Connection,
    ref_type: str,
    ref_id: int,
    feature: FeatureData,
    extracted_by: str,
) -> int:
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


def save_features(ref_type: str, ref_id: int, feature: FeatureData, extracted_by: str) -> int:
    with get_conn() as conn:
        return _save_features_with_conn(conn, ref_type, ref_id, feature, extracted_by)


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


def _save_valuation_with_conn(conn: sqlite3.Connection, result: ValuationOut) -> int:
    sql = """
    INSERT INTO valuation_records(
        listing_row_id, expected_sale_price, buy_limit, suggested_list_price,
        ci_low, ci_high, model_confidence, comparables_count, reasoning
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
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


def save_valuation(result: ValuationOut) -> int:
    with get_conn() as conn:
        return _save_valuation_with_conn(conn, result)


def get_latest_valuation_for_listing(listing_row_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT * FROM valuation_records WHERE listing_row_id = ? ORDER BY id DESC LIMIT 1",
            (listing_row_id,),
        )
        return cur.fetchone()


def _upsert_opportunity_with_conn(
    conn: sqlite3.Connection,
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
    conn.execute(
        sql,
        (listing_row_id, valuation_id, expected_profit, roi, score, status, note),
    )
    row = conn.execute(
        "SELECT id FROM opportunities WHERE listing_row_id = ?",
        (listing_row_id,),
    ).fetchone()
    return int(row["id"])


def upsert_opportunity(
    listing_row_id: int,
    valuation_id: int,
    expected_profit: float,
    roi: float,
    score: float,
    status: str,
    note: str = "",
) -> int:
    with get_conn() as conn:
        return _upsert_opportunity_with_conn(
            conn,
            listing_row_id,
            valuation_id,
            expected_profit,
            roi,
            score,
            status,
            note,
        )


def persist_scan_batch(batch_items: list[dict[str, Any]]) -> dict[str, int]:
    if not batch_items:
        return {"written": 0}

    started = time.perf_counter()
    try:
        with get_conn() as conn:
            conn.execute("BEGIN IMMEDIATE")
            for item in batch_items:
                feature = item.get("feature")
                extracted_by = str(item.get("extracted_by") or "")
                if isinstance(feature, FeatureData) and extracted_by:
                    _save_features_with_conn(
                        conn,
                        "listing",
                        int(item["listing_row_id"]),
                        feature,
                        extracted_by,
                    )

                valuation_id = _save_valuation_with_conn(
                    conn,
                    item["valuation"],
                )
                _upsert_opportunity_with_conn(
                    conn,
                    int(item["listing_row_id"]),
                    valuation_id,
                    float(item["expected_profit"]),
                    float(item["roi"]),
                    float(item["score"]),
                    str(item["status"]),
                    str(item.get("note") or ""),
                )
        record_batch_write_status(
            batch_size=len(batch_items),
            duration_ms=int((time.perf_counter() - started) * 1000),
        )
        return {"written": len(batch_items)}
    except Exception as exc:
        record_batch_write_status(
            batch_size=len(batch_items),
            duration_ms=int((time.perf_counter() - started) * 1000),
            error=str(exc),
        )
        raise


def list_opportunities(status: str | None = None, limit: int = 100) -> list[sqlite3.Row]:
    base_sql = """
    SELECT o.*, l.title, l.source, l.seller_id, l.list_price, v.expected_sale_price, v.suggested_list_price
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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_active_forward_validation_batch_with_conn(
    conn: sqlite3.Connection,
) -> sqlite3.Row | None:
    return conn.execute(
        """
        SELECT *
        FROM forward_validation_batches
        WHERE status = 'open'
        ORDER BY id DESC
        LIMIT 1
        """
    ).fetchone()


def _count_forward_validation_members_with_conn(
    conn: sqlite3.Connection,
    batch_id: int,
) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c
        FROM forward_validation_trades
        WHERE batch_id = ?
        """,
        (batch_id,),
    ).fetchone()
    return int(row["c"]) if row else 0


def _close_forward_validation_batch_with_conn(
    conn: sqlite3.Connection,
    batch_id: int,
) -> None:
    conn.execute(
        """
        UPDATE forward_validation_batches
        SET status = 'closed',
            closed_at = COALESCE(closed_at, ?)
        WHERE id = ?
        """,
        (_utc_now_iso(), batch_id),
    )


def _auto_enroll_trade_in_active_validation_with_conn(
    conn: sqlite3.Connection,
    trade_id: int,
    *,
    enrollment_note: str = "auto_enroll_on_approval",
) -> dict[str, Any] | None:
    batch = _get_active_forward_validation_batch_with_conn(conn)
    if not batch or not bool(batch["auto_enroll"]):
        return None

    batch_id = int(batch["id"])
    target_sample_size = max(1, int(batch["target_sample_size"]))
    existing = conn.execute(
        """
        SELECT id
        FROM forward_validation_trades
        WHERE trade_id = ?
        LIMIT 1
        """,
        (trade_id,),
    ).fetchone()
    if existing:
        return {
            "batch_id": batch_id,
            "trade_id": trade_id,
            "enrolled": False,
            "reason": "already_enrolled",
        }

    current_count = _count_forward_validation_members_with_conn(conn, batch_id)
    if current_count >= target_sample_size:
        _close_forward_validation_batch_with_conn(conn, batch_id)
        return {
            "batch_id": batch_id,
            "trade_id": trade_id,
            "enrolled": False,
            "reason": "batch_full",
        }

    conn.execute(
        """
        INSERT INTO forward_validation_trades(batch_id, trade_id, enrollment_note)
        VALUES (?, ?, ?)
        """,
        (batch_id, trade_id, enrollment_note),
    )
    enrolled_count = current_count + 1
    closed = enrolled_count >= target_sample_size
    if closed:
        _close_forward_validation_batch_with_conn(conn, batch_id)
    return {
        "batch_id": batch_id,
        "trade_id": trade_id,
        "enrolled": True,
        "enrolled_count": enrolled_count,
        "target_sample_size": target_sample_size,
        "closed": closed,
    }


def _serialize_forward_validation_batch_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": str(row["name"]),
        "target_sample_size": int(row["target_sample_size"]),
        "status": str(row["status"]),
        "auto_enroll": bool(row["auto_enroll"]),
        "note": str(row["note"] or ""),
        "created_at": row["created_at"],
        "closed_at": row["closed_at"],
        "enrolled_count": int(row["enrolled_count"] or 0),
        "sold_count": int(row["sold_count"] or 0),
    }


def create_forward_validation_batch(
    *,
    name: str,
    target_sample_size: int,
    note: str = "",
    auto_enroll: bool = True,
) -> dict[str, Any]:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ValueError("name is required")
    sample_size = max(1, min(500, int(target_sample_size)))
    with get_conn() as conn:
        active = _get_active_forward_validation_batch_with_conn(conn)
        if active:
            raise ValueError("an open forward validation batch already exists")
        cur = conn.execute(
            """
            INSERT INTO forward_validation_batches(
                name, target_sample_size, status, auto_enroll, note
            )
            VALUES (?, ?, 'open', ?, ?)
            """,
            (normalized_name, sample_size, 1 if auto_enroll else 0, str(note or "")),
        )
        batch_id = int(cur.lastrowid)
        row = conn.execute(
            """
            SELECT
                b.*,
                0 AS enrolled_count,
                0 AS sold_count
            FROM forward_validation_batches b
            WHERE b.id = ?
            """,
            (batch_id,),
        ).fetchone()
    return _serialize_forward_validation_batch_row(row)


def list_forward_validation_batches(limit: int = 20) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                b.*,
                COUNT(fvt.id) AS enrolled_count,
                COALESCE(SUM(CASE WHEN t.status = 'sold' THEN 1 ELSE 0 END), 0) AS sold_count
            FROM forward_validation_batches b
            LEFT JOIN forward_validation_trades fvt ON fvt.batch_id = b.id
            LEFT JOIN trades t ON t.id = fvt.trade_id
            GROUP BY b.id
            ORDER BY b.id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [_serialize_forward_validation_batch_row(row) for row in rows]


def close_forward_validation_batch(batch_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                b.*,
                COUNT(fvt.id) AS enrolled_count,
                COALESCE(SUM(CASE WHEN t.status = 'sold' THEN 1 ELSE 0 END), 0) AS sold_count
            FROM forward_validation_batches b
            LEFT JOIN forward_validation_trades fvt ON fvt.batch_id = b.id
            LEFT JOIN trades t ON t.id = fvt.trade_id
            WHERE b.id = ?
            GROUP BY b.id
            """,
            (batch_id,),
        ).fetchone()
        if not row:
            raise ValueError("forward validation batch not found")
        _close_forward_validation_batch_with_conn(conn, batch_id)
        refreshed = conn.execute(
            """
            SELECT
                b.*,
                COUNT(fvt.id) AS enrolled_count,
                COALESCE(SUM(CASE WHEN t.status = 'sold' THEN 1 ELSE 0 END), 0) AS sold_count
            FROM forward_validation_batches b
            LEFT JOIN forward_validation_trades fvt ON fvt.batch_id = b.id
            LEFT JOIN trades t ON t.id = fvt.trade_id
            WHERE b.id = ?
            GROUP BY b.id
            """,
            (batch_id,),
        ).fetchone()
    return _serialize_forward_validation_batch_row(refreshed)


_AUTOTRADE_TUNING_FIELDS: tuple[str, ...] = (
    "min_score",
    "min_roi",
    "max_risk_score",
    "require_risk_score",
)


def _normalize_autotrade_tuning_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    payload = dict(raw or {})
    return {
        "min_score": float(payload.get("min_score", 0.0) or 0.0),
        "min_roi": float(payload.get("min_roi", 0.0) or 0.0),
        "max_risk_score": float(payload.get("max_risk_score", 0.0) or 0.0),
        "require_risk_score": bool(payload.get("require_risk_score", False)),
    }


def _load_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return {}
    return payload if isinstance(payload, dict) else {}


def _load_json_array(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return raw
    text = str(raw or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except (TypeError, ValueError):
        return []
    return payload if isinstance(payload, list) else []


def _serialize_autotrade_tuning_event_row(row: sqlite3.Row) -> dict[str, Any]:
    previous_config = _normalize_autotrade_tuning_config(
        _load_json_object(row["previous_config_json"]),
    )
    next_config = _normalize_autotrade_tuning_config(
        _load_json_object(row["next_config_json"]),
    )
    delta = {
        key: (
            bool(next_config[key]) != bool(previous_config[key])
            if key == "require_risk_score"
            else round(float(next_config[key]) - float(previous_config[key]), 4)
        )
        for key in _AUTOTRADE_TUNING_FIELDS
    }
    return {
        "id": int(row["id"]),
        "source": str(row["source"] or ""),
        "applied_by": str(row["applied_by"] or ""),
        "note": str(row["note"] or ""),
        "previous_config": previous_config,
        "next_config": next_config,
        "delta": delta,
        "rollback_of_event_id": (
            int(row["rollback_of_event_id"])
            if row["rollback_of_event_id"] is not None
            else None
        ),
        "created_at": row["created_at"],
    }


def create_autotrade_tuning_event(
    *,
    source: str,
    applied_by: str,
    note: str,
    previous_config: dict[str, Any],
    next_config: dict[str, Any],
    rollback_of_event_id: int | None = None,
) -> dict[str, Any]:
    normalized_previous = _normalize_autotrade_tuning_config(previous_config)
    normalized_next = _normalize_autotrade_tuning_config(next_config)
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO autotrade_tuning_events(
                source,
                applied_by,
                note,
                previous_config_json,
                next_config_json,
                rollback_of_event_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(source or "").strip(),
                str(applied_by or "").strip(),
                str(note or "").strip(),
                json.dumps(normalized_previous, ensure_ascii=True),
                json.dumps(normalized_next, ensure_ascii=True),
                rollback_of_event_id,
            ),
        )
        row = conn.execute(
            "SELECT * FROM autotrade_tuning_events WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _serialize_autotrade_tuning_event_row(row)


def list_autotrade_tuning_events(limit: int = 30) -> list[dict[str, Any]]:
    capped_limit = max(1, min(200, int(limit)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM autotrade_tuning_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (capped_limit,),
        ).fetchall()
    return [_serialize_autotrade_tuning_event_row(row) for row in rows]


def get_autotrade_tuning_event(event_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM autotrade_tuning_events WHERE id = ? LIMIT 1",
            (event_id,),
        ).fetchone()
    if not row:
        return None
    return _serialize_autotrade_tuning_event_row(row)


def _serialize_autotrade_tuning_activity_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "decision_type": str(row["decision_type"] or ""),
        "trigger_source": str(row["trigger_source"] or ""),
        "actor": str(row["actor"] or ""),
        "summary": str(row["summary"] or ""),
        "details": _load_json_object(row["details_json"]),
        "related_event_id": (
            int(row["related_event_id"])
            if row["related_event_id"] is not None
            else None
        ),
        "created_at": row["created_at"],
    }


def create_autotrade_tuning_activity(
    *,
    decision_type: str,
    trigger_source: str,
    actor: str,
    summary: str,
    details: dict[str, Any] | None = None,
    related_event_id: int | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO autotrade_tuning_activity(
                decision_type,
                trigger_source,
                actor,
                summary,
                details_json,
                related_event_id
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(decision_type or "").strip(),
                str(trigger_source or "").strip(),
                str(actor or "").strip(),
                str(summary or "").strip(),
                json.dumps(details or {}, ensure_ascii=True),
                related_event_id,
            ),
        )
        row = conn.execute(
            "SELECT * FROM autotrade_tuning_activity WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _serialize_autotrade_tuning_activity_row(row)


def list_autotrade_tuning_activity(limit: int = 50) -> list[dict[str, Any]]:
    capped_limit = max(1, min(500, int(limit)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM autotrade_tuning_activity
            ORDER BY id DESC
            LIMIT ?
            """,
            (capped_limit,),
        ).fetchall()
    return [_serialize_autotrade_tuning_activity_row(row) for row in rows]


def get_autotrade_tuning_daily_report(hours: int = 24) -> dict[str, Any]:
    window_hours = max(1, min(24 * 30, int(hours)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM autotrade_tuning_activity
            WHERE created_at >= datetime('now', ?)
            ORDER BY id DESC
            """,
            (f"-{window_hours} hours",),
        ).fetchall()

    items = [_serialize_autotrade_tuning_activity_row(row) for row in rows]
    counts_by_type: dict[str, int] = {}
    blocked_reason_counts: dict[str, int] = {}
    for item in items:
        decision_type = item["decision_type"] or "unknown"
        counts_by_type[decision_type] = counts_by_type.get(decision_type, 0) + 1
        for reason in item.get("details", {}).get("guard_reasons", []) or []:
            reason_text = str(reason or "").strip()
            if not reason_text:
                continue
            blocked_reason_counts[reason_text] = blocked_reason_counts.get(reason_text, 0) + 1

    top_blocked_reasons = [
        {"reason": reason, "count": count}
        for reason, count in sorted(
            blocked_reason_counts.items(),
            key=lambda item: (-item[1], item[0]),
        )[:5]
    ]

    return {
        "hours": window_hours,
        "activity_count": len(items),
        "counts_by_type": counts_by_type,
        "latest_activity": items[0] if items else None,
        "top_blocked_reasons": top_blocked_reasons,
        "items": items[:10],
    }


def _serialize_seller_control_state_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "source": str(row["source"] or ""),
        "seller_id": str(row["seller_id"] or ""),
        "state": str(row["state"] or "normal"),
        "reason": str(row["reason"] or ""),
        "frozen_until": row["frozen_until"],
        "metadata": _load_json_object(row["metadata_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_seller_control_state(source: str, seller_id: str) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM seller_control_states
            WHERE source = ? AND seller_id = ?
            LIMIT 1
            """,
            (str(source or "").strip(), str(seller_id or "").strip()),
        ).fetchone()
    if not row:
        return None
    return _serialize_seller_control_state_row(row)


def list_seller_control_states(
    *,
    state: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    capped_limit = max(1, min(500, int(limit)))
    sql = "SELECT * FROM seller_control_states"
    params: list[Any] = []
    if state:
        sql += " WHERE state = ?"
        params.append(str(state or "").strip())
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(capped_limit)
    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [_serialize_seller_control_state_row(row) for row in rows]


def upsert_seller_control_state(
    *,
    source: str,
    seller_id: str,
    state: str,
    reason: str = "",
    frozen_until: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_source = str(source or "").strip()
    normalized_seller_id = str(seller_id or "").strip()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO seller_control_states(
                source, seller_id, state, reason, frozen_until, metadata_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(source, seller_id) DO UPDATE SET
                state=excluded.state,
                reason=excluded.reason,
                frozen_until=excluded.frozen_until,
                metadata_json=excluded.metadata_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                normalized_source,
                normalized_seller_id,
                str(state or "normal").strip(),
                str(reason or "").strip(),
                frozen_until,
                json.dumps(metadata or {}, ensure_ascii=True),
            ),
        )
        row = conn.execute(
            """
            SELECT *
            FROM seller_control_states
            WHERE source = ? AND seller_id = ?
            LIMIT 1
            """,
            (normalized_source, normalized_seller_id),
        ).fetchone()
    return _serialize_seller_control_state_row(row)


def create_seller_control_event(
    *,
    source: str,
    seller_id: str,
    event_type: str,
    reason: str,
    previous_state: dict[str, Any] | None,
    next_state: dict[str, Any] | None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO seller_control_events(
                source,
                seller_id,
                event_type,
                reason,
                previous_state_json,
                next_state_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(source or "").strip(),
                str(seller_id or "").strip(),
                str(event_type or "").strip(),
                str(reason or "").strip(),
                json.dumps(previous_state or {}, ensure_ascii=True),
                json.dumps(next_state or {}, ensure_ascii=True),
            ),
        )
        row = conn.execute(
            "SELECT * FROM seller_control_events WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return {
        "id": int(row["id"]),
        "source": str(row["source"] or ""),
        "seller_id": str(row["seller_id"] or ""),
        "event_type": str(row["event_type"] or ""),
        "reason": str(row["reason"] or ""),
        "previous_state": _load_json_object(row["previous_state_json"]),
        "next_state": _load_json_object(row["next_state_json"]),
        "created_at": row["created_at"],
    }


def _serialize_seller_control_event_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "source": str(row["source"] or ""),
        "seller_id": str(row["seller_id"] or ""),
        "event_type": str(row["event_type"] or ""),
        "reason": str(row["reason"] or ""),
        "previous_state": _load_json_object(row["previous_state_json"]),
        "next_state": _load_json_object(row["next_state_json"]),
        "created_at": row["created_at"],
    }


def list_seller_control_events(limit: int = 50) -> list[dict[str, Any]]:
    capped_limit = max(1, min(500, int(limit)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM seller_control_events
            ORDER BY id DESC
            LIMIT ?
            """,
            (capped_limit,),
        ).fetchall()
    return [_serialize_seller_control_event_row(row) for row in rows]


def list_seller_control_events_for_seller(
    *,
    source: str,
    seller_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    capped_limit = max(1, min(100, int(limit)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM seller_control_events
            WHERE source = ? AND seller_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (str(source or "").strip(), str(seller_id or "").strip(), capped_limit),
        ).fetchall()
    return [_serialize_seller_control_event_row(row) for row in rows]


def get_seller_control_daily_report(hours: int = 24) -> dict[str, Any]:
    window_hours = max(1, min(24 * 30, int(hours)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM seller_control_events
            WHERE created_at >= datetime('now', ?)
            ORDER BY id DESC
            """,
            (f"-{window_hours} hours",),
        ).fetchall()

    items = [_serialize_seller_control_event_row(row) for row in rows]
    counts_by_type: dict[str, int] = {}
    counts_by_seller: dict[str, int] = {}
    for item in items:
        event_type = str(item["event_type"] or "unknown")
        counts_by_type[event_type] = counts_by_type.get(event_type, 0) + 1
        seller_key = f"{item['source']}/{item['seller_id']}"
        counts_by_seller[seller_key] = counts_by_seller.get(seller_key, 0) + 1

    hottest_sellers = [
        {"seller": seller, "count": count}
        for seller, count in sorted(
            counts_by_seller.items(),
            key=lambda item: (-item[1], item[0]),
        )[:5]
    ]

    return {
        "hours": window_hours,
        "event_count": len(items),
        "counts_by_type": counts_by_type,
        "latest_event": items[0] if items else None,
        "hottest_sellers": hottest_sellers,
        "items": items[:10],
    }


def _serialize_seller_control_preset_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "name": str(row["name"] or ""),
        "base_preset": str(row["base_preset"] or "all"),
        "source_filter": str(row["source_filter"] or ""),
        "action": str(row["action"] or "observe"),
        "reason": str(row["reason"] or ""),
        "duration_hours": int(row["duration_hours"]) if row["duration_hours"] is not None else None,
        "last_applied_at": row["last_applied_at"],
        "last_applied_action": str(row["last_applied_action"] or ""),
        "last_applied_by": str(row["last_applied_by"] or ""),
        "last_matched_count": int(row["last_matched_count"] or 0),
        "last_processed_count": int(row["last_processed_count"] or 0),
        "last_matched_items": _load_json_array(row["last_matched_items_json"]),
        "created_by": str(row["created_by"] or ""),
        "updated_by": str(row["updated_by"] or ""),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _serialize_seller_control_preset_run_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "preset_id": int(row["preset_id"]),
        "action": str(row["action"] or ""),
        "actor": str(row["actor"] or ""),
        "reason": str(row["reason"] or ""),
        "duration_hours": int(row["duration_hours"]) if row["duration_hours"] is not None else None,
        "matched_count": int(row["matched_count"] or 0),
        "processed_count": int(row["processed_count"] or 0),
        "matched_items": _load_json_array(row["matched_items_json"]),
        "created_at": row["created_at"],
    }


def list_seller_control_preset_runs(*, preset_id: int, limit: int = 10) -> list[dict[str, Any]]:
    capped_limit = max(1, min(50, int(limit)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM seller_control_preset_runs
            WHERE preset_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (int(preset_id), capped_limit),
        ).fetchall()
    return [_serialize_seller_control_preset_run_row(row) for row in rows]


def get_seller_control_preset(preset_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM seller_control_presets
            WHERE id = ?
            LIMIT 1
            """,
            (int(preset_id),),
        ).fetchone()
    if not row:
        return None
    return _serialize_seller_control_preset_row(row)


def _build_seller_control_preset_stats(runs: list[dict[str, Any]]) -> dict[str, Any]:
    recent_runs = list(runs[:5])
    run_count = len(recent_runs)
    total_matched = sum(int(run.get("matched_count") or 0) for run in recent_runs)
    total_processed = sum(int(run.get("processed_count") or 0) for run in recent_runs)
    avg_matched = round(total_matched / run_count, 2) if run_count else 0.0
    avg_processed = round(total_processed / run_count, 2) if run_count else 0.0
    avg_processed_rate = round((total_processed / total_matched), 4) if total_matched > 0 else 0.0
    return {
        "run_count": run_count,
        "avg_matched_count": avg_matched,
        "avg_processed_count": avg_processed,
        "avg_processed_rate": avg_processed_rate,
    }


def _seller_control_preset_effectiveness_score(stats: dict[str, Any] | None) -> float:
    payload = dict(stats or {})
    run_count = max(0.0, float(payload.get("run_count") or 0.0))
    avg_processed = max(0.0, float(payload.get("avg_processed_count") or 0.0))
    avg_rate = max(0.0, min(1.0, float(payload.get("avg_processed_rate") or 0.0)))
    volume_factor = min(1.0, avg_processed / 5.0)
    confidence_factor = min(1.0, run_count / 5.0)
    return round((avg_rate * 0.6) + (volume_factor * 0.25) + (confidence_factor * 0.15), 4)


def list_seller_control_presets(limit: int = 50) -> list[dict[str, Any]]:
    capped_limit = max(1, min(200, int(limit)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM seller_control_presets
            ORDER BY updated_at DESC, id DESC
            LIMIT ?
            """,
            (capped_limit,),
        ).fetchall()
        presets = [_serialize_seller_control_preset_row(row) for row in rows]
        preset_ids = [preset["id"] for preset in presets]
        run_rows = conn.execute(
            f"""
            SELECT *
            FROM seller_control_preset_runs
            WHERE preset_id IN ({",".join("?" for _ in preset_ids)}) 
            ORDER BY id DESC
            """,
            tuple(preset_ids),
        ).fetchall() if preset_ids else []
    grouped_runs: dict[int, list[dict[str, Any]]] = {}
    for row in run_rows:
        item = _serialize_seller_control_preset_run_row(row)
        grouped_runs.setdefault(int(item["preset_id"]), []).append(item)
    for preset in presets:
        recent_runs = grouped_runs.get(int(preset["id"]), [])[:5]
        preset["recent_runs"] = recent_runs
        preset["recent_stats"] = _build_seller_control_preset_stats(recent_runs)
        preset["effectiveness_score"] = _seller_control_preset_effectiveness_score(preset["recent_stats"])
        preset["effectiveness_rank"] = None
    ranked = [
        preset for preset in presets
        if int((preset.get("recent_stats") or {}).get("run_count") or 0) > 0
    ]
    ranked.sort(
        key=lambda preset: (
            float(preset.get("effectiveness_score") or 0.0),
            float((preset.get("recent_stats") or {}).get("avg_processed_rate") or 0.0),
            float((preset.get("recent_stats") or {}).get("avg_processed_count") or 0.0),
            -int(preset.get("id") or 0),
        ),
        reverse=True,
    )
    for index, preset in enumerate(ranked, start=1):
        preset["effectiveness_rank"] = index
    return presets


def upsert_seller_control_preset(
    *,
    name: str,
    base_preset: str,
    source_filter: str = "",
    action: str,
    reason: str = "",
    duration_hours: int | None = None,
    actor: str = "operator",
) -> dict[str, Any]:
    normalized_name = str(name or "").strip()
    if not normalized_name:
        raise ValueError("name is required")
    normalized_base = str(base_preset or "all").strip() or "all"
    normalized_source = str(source_filter or "").strip()
    normalized_action = str(action or "observe").strip() or "observe"
    normalized_actor = str(actor or "operator").strip() or "operator"
    duration_value = max(1, int(duration_hours)) if duration_hours is not None else None
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO seller_control_presets(
                name,
                base_preset,
                source_filter,
                action,
                reason,
                duration_hours,
                created_by,
                updated_by
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                base_preset=excluded.base_preset,
                source_filter=excluded.source_filter,
                action=excluded.action,
                reason=excluded.reason,
                duration_hours=excluded.duration_hours,
                updated_by=excluded.updated_by,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                normalized_name,
                normalized_base,
                normalized_source,
                normalized_action,
                str(reason or "").strip(),
                duration_value,
                normalized_actor,
                normalized_actor,
            ),
        )
        row = conn.execute(
            """
            SELECT *
            FROM seller_control_presets
            WHERE name = ?
            LIMIT 1
            """,
            (normalized_name,),
        ).fetchone()
    return _serialize_seller_control_preset_row(row)


def delete_seller_control_preset(preset_id: int) -> dict[str, Any]:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM seller_control_presets
            WHERE id = ?
            LIMIT 1
            """,
            (int(preset_id),),
        ).fetchone()
        if not row:
            raise ValueError("seller control preset not found")
        conn.execute(
            "DELETE FROM seller_control_presets WHERE id = ?",
            (int(preset_id),),
        )
    return _serialize_seller_control_preset_row(row)


def record_seller_control_preset_run(
    *,
    preset_id: int,
    action: str,
    actor: str = "operator",
    matched_count: int = 0,
    processed_count: int = 0,
    matched_items: list[dict[str, Any]] | None = None,
    reason: str = "",
    duration_hours: int | None = None,
) -> dict[str, Any]:
    normalized_action = str(action or "").strip() or "observe"
    normalized_actor = str(actor or "operator").strip() or "operator"
    normalized_reason = str(reason or "").strip()
    duration_value = max(1, int(duration_hours)) if duration_hours is not None else None
    normalized_matched_items = [
        {
            "source": str((item or {}).get("source") or "").strip(),
            "seller_id": str((item or {}).get("seller_id") or "").strip(),
        }
        for item in list(matched_items or [])
        if str((item or {}).get("source") or "").strip()
        and str((item or {}).get("seller_id") or "").strip()
    ][:8]
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM seller_control_presets
            WHERE id = ?
            LIMIT 1
            """,
            (int(preset_id),),
        ).fetchone()
        if not row:
            raise ValueError("seller control preset not found")
        conn.execute(
            """
            INSERT INTO seller_control_preset_runs(
                preset_id,
                action,
                actor,
                reason,
                duration_hours,
                matched_count,
                processed_count,
                matched_items_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(preset_id),
                normalized_action,
                normalized_actor,
                normalized_reason,
                duration_value,
                max(0, int(matched_count)),
                max(0, int(processed_count)),
                json.dumps(normalized_matched_items, ensure_ascii=True),
            ),
        )
        conn.execute(
            """
            UPDATE seller_control_presets
            SET last_applied_at = CURRENT_TIMESTAMP,
                last_applied_action = ?,
                last_applied_by = ?,
                last_matched_count = ?,
                last_processed_count = ?,
                last_matched_items_json = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                normalized_action,
                normalized_actor,
                max(0, int(matched_count)),
                max(0, int(processed_count)),
                json.dumps(normalized_matched_items, ensure_ascii=True),
                int(preset_id),
            ),
        )
        updated = conn.execute(
            """
            SELECT *
            FROM seller_control_presets
            WHERE id = ?
            LIMIT 1
            """,
            (int(preset_id),),
        ).fetchone()
    return _serialize_seller_control_preset_row(updated)


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
        validation_enrollment = _auto_enroll_trade_in_active_validation_with_conn(
            conn,
            trade_id,
        )
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
            "forward_validation": validation_enrollment,
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
        _auto_enroll_trade_in_active_validation_with_conn(conn, int(cur.lastrowid))
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


def _parse_db_timestamp(raw_value: Any) -> datetime | None:
    text = str(raw_value or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return float(ordered[mid])
    return float((ordered[mid - 1] + ordered[mid]) / 2.0)


def _build_trade_performance_summary(
    rows: list[sqlite3.Row],
    *,
    target_sample_size: int = 0,
) -> dict[str, Any]:
    total_count = len(rows)
    active_count = 0
    sold_count = 0
    realized_gross_profit = 0.0
    realized_net_profit = 0.0
    profitable_sold_count = 0
    holding_days_values: list[float] = []
    realized_roi_values: list[float] = []

    for row in rows:
        status = str(row["status"] or "").strip().lower()
        if status in {"approved_for_buy", "listed_for_sale"}:
            active_count += 1
        if status != "sold" or row["sold_price"] is None:
            continue

        sold_count += 1
        approved_buy_price = float(row["approved_buy_price"] or 0.0)
        sold_price = float(row["sold_price"] or 0.0)
        gross_profit = sold_price - approved_buy_price
        net_profit = (
            sold_price
            - approved_buy_price
            - settings.default_shipping_cost
            - (settings.platform_fee_rate * sold_price)
        )
        realized_gross_profit += gross_profit
        realized_net_profit += net_profit
        if net_profit > 0:
            profitable_sold_count += 1
        if approved_buy_price > 0:
            realized_roi_values.append(net_profit / approved_buy_price)

        created_at = _parse_db_timestamp(row["created_at"])
        updated_at = _parse_db_timestamp(row["updated_at"])
        if created_at and updated_at:
            holding_days = max(0.0, (updated_at - created_at).total_seconds() / 86400.0)
            holding_days_values.append(holding_days)

    profit_hit_rate = (profitable_sold_count / sold_count) if sold_count else 0.0
    avg_holding_days = (
        sum(holding_days_values) / len(holding_days_values) if holding_days_values else 0.0
    )
    median_holding_days = _median(holding_days_values)
    avg_realized_roi = (
        sum(realized_roi_values) / len(realized_roi_values) if realized_roi_values else 0.0
    )
    progress = (total_count / target_sample_size) if target_sample_size > 0 else 0.0

    return {
        "total_count": total_count,
        "active_count": active_count,
        "sold_count": sold_count,
        "realized_gross_profit": round(realized_gross_profit, 2),
        "realized_net_profit": round(realized_net_profit, 2),
        "profitable_sold_count": profitable_sold_count,
        "profit_hit_rate": round(profit_hit_rate, 4),
        "avg_holding_days": round(avg_holding_days, 2),
        "median_holding_days": round(median_holding_days, 2),
        "avg_realized_roi": round(avg_realized_roi, 4),
        "target_sample_size": target_sample_size,
        "progress": round(progress, 4) if target_sample_size > 0 else 0.0,
    }


def _compute_trade_profit_components(row: sqlite3.Row) -> dict[str, Any] | None:
    status = str(row["status"] or "").strip().lower()
    if status != "sold" or row["sold_price"] is None:
        return None

    sold_at = _parse_db_timestamp(row["updated_at"])
    if sold_at is None:
        return None

    approved_buy_price = float(row["approved_buy_price"] or 0.0)
    sold_price = float(row["sold_price"] or 0.0)
    gross_profit = sold_price - approved_buy_price
    net_profit = (
        sold_price
        - approved_buy_price
        - settings.default_shipping_cost
        - (settings.platform_fee_rate * sold_price)
    )
    roi = (net_profit / approved_buy_price) if approved_buy_price > 0 else 0.0

    return {
        "sold_at": sold_at,
        "approved_buy_price": approved_buy_price,
        "sold_price": sold_price,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
        "roi": roi,
        "source": str(row["listing_source"] or "unknown").strip() or "unknown",
    }


def _build_realized_window_summary(
    rows: list[sqlite3.Row],
    *,
    since: datetime | None = None,
) -> dict[str, Any]:
    sold_count = 0
    realized_gross_profit = 0.0
    realized_net_profit = 0.0
    profitable_sold_count = 0
    realized_roi_values: list[float] = []

    for row in rows:
        details = _compute_trade_profit_components(row)
        if not details:
            continue
        sold_at = details["sold_at"]
        if since is not None and sold_at < since:
            continue

        sold_count += 1
        realized_gross_profit += float(details["gross_profit"])
        realized_net_profit += float(details["net_profit"])
        if float(details["net_profit"]) > 0:
            profitable_sold_count += 1
        if float(details["approved_buy_price"]) > 0:
            realized_roi_values.append(float(details["roi"]))

    profit_hit_rate = (profitable_sold_count / sold_count) if sold_count else 0.0
    avg_realized_roi = (
        sum(realized_roi_values) / len(realized_roi_values) if realized_roi_values else 0.0
    )

    return {
        "sold_count": sold_count,
        "realized_gross_profit": round(realized_gross_profit, 2),
        "realized_net_profit": round(realized_net_profit, 2),
        "profitable_sold_count": profitable_sold_count,
        "profit_hit_rate": round(profit_hit_rate, 4),
        "avg_realized_roi": round(avg_realized_roi, 4),
    }


def _build_inventory_exposure_summary(rows: list[sqlite3.Row]) -> dict[str, Any]:
    active_statuses = {"approved_for_buy", "listed_for_sale"}
    active_trade_count = 0
    listed_trade_count = 0
    approved_trade_count = 0
    deployed_capital = 0.0
    target_exit_value = 0.0

    for row in rows:
        status = str(row["status"] or "").strip().lower()
        if status not in active_statuses:
            continue
        active_trade_count += 1
        if status == "listed_for_sale":
            listed_trade_count += 1
        if status == "approved_for_buy":
            approved_trade_count += 1
        deployed_capital += float(row["approved_buy_price"] or 0.0)
        target_exit_value += float(row["target_sell_price"] or 0.0)

    return {
        "active_trade_count": active_trade_count,
        "listed_trade_count": listed_trade_count,
        "approved_trade_count": approved_trade_count,
        "deployed_capital": round(deployed_capital, 2),
        "target_exit_value": round(target_exit_value, 2),
        "expected_exit_spread": round(target_exit_value - deployed_capital, 2),
    }


def _build_source_profit_snapshot(
    rows: list[sqlite3.Row],
    *,
    since: datetime | None = None,
) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        details = _compute_trade_profit_components(row)
        if not details:
            continue
        sold_at = details["sold_at"]
        if since is not None and sold_at < since:
            continue

        source = str(details["source"] or "unknown")
        bucket = grouped.setdefault(
            source,
            {
                "source": source,
                "sold_count": 0,
                "profitable_sold_count": 0,
                "realized_net_profit": 0.0,
                "avg_realized_roi_values": [],
            },
        )
        bucket["sold_count"] += 1
        if float(details["net_profit"]) > 0:
            bucket["profitable_sold_count"] += 1
        bucket["realized_net_profit"] += float(details["net_profit"])
        bucket["avg_realized_roi_values"].append(float(details["roi"]))

    items: list[dict[str, Any]] = []
    for bucket in grouped.values():
        sold_count = int(bucket["sold_count"])
        profitable_sold_count = int(bucket["profitable_sold_count"])
        roi_values = list(bucket["avg_realized_roi_values"])
        realized_net_profit = round(float(bucket["realized_net_profit"]), 2)
        profit_hit_rate = round(
            (profitable_sold_count / sold_count) if sold_count else 0.0,
            4,
        )
        avg_realized_roi = round(
            (sum(roi_values) / len(roi_values)) if roi_values else 0.0,
            4,
        )
        strategy_mode = "hold"
        strategy_summary = "Insufficient edge to change source weighting."
        threshold_delta = {
            "min_score": 0.0,
            "min_roi": 0.0,
            "max_risk_score": 0.0,
        }
        intake_multiplier = 1.0

        if sold_count < 2:
            strategy_summary = "Need more sold trades before adapting this source."
        elif realized_net_profit < 0 or profit_hit_rate < 0.45 or avg_realized_roi < 0:
            strategy_mode = "tighten"
            strategy_summary = "Recent source quality is weak. Tighten entry thresholds."
            threshold_delta = {
                "min_score": 4.0,
                "min_roi": 0.02,
                "max_risk_score": -4.0,
            }
            intake_multiplier = 0.6
        elif realized_net_profit > 0 and profit_hit_rate >= 0.65 and avg_realized_roi >= 0.08:
            strategy_mode = "widen"
            strategy_summary = "Recent source quality is healthy. Widen the funnel slightly."
            threshold_delta = {
                "min_score": -2.0,
                "min_roi": -0.005,
                "max_risk_score": 2.0,
            }
            intake_multiplier = 1.15

        items.append(
            {
                "source": str(bucket["source"]),
                "sold_count": sold_count,
                "profitable_sold_count": profitable_sold_count,
                "realized_net_profit": realized_net_profit,
                "profit_hit_rate": profit_hit_rate,
                "avg_realized_roi": avg_realized_roi,
                "strategy_mode": strategy_mode,
                "strategy_summary": strategy_summary,
                "threshold_delta": threshold_delta,
                "intake_multiplier": intake_multiplier,
            }
        )

    ordered = sorted(
        items,
        key=lambda item: (
            float(item["realized_net_profit"]),
            int(item["sold_count"]),
            str(item["source"]),
        ),
        reverse=True,
    )
    weakest = (
        min(
            items,
            key=lambda item: (
                float(item["realized_net_profit"]),
                int(item["sold_count"]),
                str(item["source"]),
            ),
        )
        if items
        else None
    )

    return {
        "best": ordered[0] if ordered else None,
        "weakest": weakest,
        "items": ordered[:5],
    }


def _build_seller_profit_snapshot(
    rows: list[sqlite3.Row],
    *,
    since: datetime | None = None,
) -> dict[str, Any]:
    now_utc = datetime.now(timezone.utc)
    decay_days = max(1.0, float(settings.auto_approve_seller_reputation_decay_days))
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        details = _compute_trade_profit_components(row)
        if not details:
            continue
        sold_at = details["sold_at"]
        if since is not None and sold_at < since:
            continue

        seller_id = str(row["seller_id"] or "").strip()
        source = str(details["source"] or "unknown").strip() or "unknown"
        if not seller_id:
            continue
        seller_key = f"{source}::{seller_id}"
        bucket = grouped.setdefault(
            seller_key,
            {
                "source": source,
                "seller_id": seller_id,
                "seller_key": seller_key,
                "sold_count": 0,
                "profitable_sold_count": 0,
                "realized_net_profit": 0.0,
                "avg_realized_roi_values": [],
                "weighted_sold": 0.0,
                "weighted_profit_hits": 0.0,
                "weighted_net_profit": 0.0,
                "weighted_roi_sum": 0.0,
                "history": [],
                "trade_samples": [],
            },
        )
        age_days = max(0.0, (now_utc - sold_at).total_seconds() / 86400.0)
        weight = max(0.2, math.exp(-age_days / decay_days))
        bucket["sold_count"] += 1
        if float(details["net_profit"]) > 0:
            bucket["profitable_sold_count"] += 1
        bucket["realized_net_profit"] += float(details["net_profit"])
        bucket["avg_realized_roi_values"].append(float(details["roi"]))
        bucket["weighted_sold"] += weight
        bucket["weighted_profit_hits"] += weight if float(details["net_profit"]) > 0 else 0.0
        bucket["weighted_net_profit"] += float(details["net_profit"]) * weight
        bucket["weighted_roi_sum"] += float(details["roi"]) * weight
        bucket["history"].append((sold_at, float(details["net_profit"])))
        bucket["trade_samples"].append(
            (
                sold_at,
                {
                    "trade_id": int(row["id"]),
                    "title": str(row["listing_title"] or ""),
                    "sold_at": sold_at.isoformat(),
                    "approved_buy_price": round(float(details["approved_buy_price"]), 2),
                    "sold_price": round(float(details["sold_price"]), 2),
                    "net_profit": round(float(details["net_profit"]), 2),
                    "roi": round(float(details["roi"]), 4),
                },
            )
        )

    items: list[dict[str, Any]] = []
    for bucket in grouped.values():
        sold_count = int(bucket["sold_count"])
        profitable_sold_count = int(bucket["profitable_sold_count"])
        roi_values = list(bucket["avg_realized_roi_values"])
        realized_net_profit = round(float(bucket["realized_net_profit"]), 2)
        profit_hit_rate = round(
            (profitable_sold_count / sold_count) if sold_count else 0.0,
            4,
        )
        avg_realized_roi = round(
            (sum(roi_values) / len(roi_values)) if roi_values else 0.0,
            4,
        )
        weighted_sold = float(bucket["weighted_sold"] or 0.0)
        weighted_hit_rate = (
            float(bucket["weighted_profit_hits"]) / weighted_sold if weighted_sold > 0 else 0.0
        )
        weighted_avg_roi = (
            float(bucket["weighted_roi_sum"]) / weighted_sold if weighted_sold > 0 else 0.0
        )
        weighted_net_profit = float(bucket["weighted_net_profit"] or 0.0)
        history = sorted(
            list(bucket["history"]),
            key=lambda item: item[0],
            reverse=True,
        )
        recent_trades = [
            trade_payload
            for _, trade_payload in sorted(
                list(bucket["trade_samples"]),
                key=lambda item: item[0],
                reverse=True,
            )[:5]
        ]
        positive_streak = 0
        for _, net_profit in history:
            if net_profit > 0:
                positive_streak += 1
                continue
            break
        reputation_score = round(
            (weighted_hit_rate * 50.0)
            + (weighted_avg_roi * 100.0)
            + max(-40.0, min(40.0, weighted_net_profit / 5.0)),
            2,
        )
        seller_lane = "neutral"
        lane_summary = "Need more evidence before changing seller preference."
        threshold_delta = {
            "min_score": 0.0,
            "min_roi": 0.0,
            "max_risk_score": 0.0,
        }
        intake_multiplier = 1.0

        if sold_count < 2:
            lane_summary = "Need more sold trades before trusting this seller."
        elif reputation_score < -5 or weighted_net_profit < 0 or weighted_hit_rate < 0.4 or weighted_avg_roi < 0:
            seller_lane = "blacklist"
            lane_summary = "Seller is underperforming. Block new approvals for now."
            threshold_delta = {
                "min_score": 8.0,
                "min_roi": 0.05,
                "max_risk_score": -8.0,
            }
            intake_multiplier = 0.0
        elif reputation_score >= 18:
            seller_lane = "observe"
            lane_summary = "Seller is improving. Keep under observation before full restore."
            threshold_delta = {
                "min_score": 2.0,
                "min_roi": 0.01,
                "max_risk_score": -2.0,
            }
            intake_multiplier = 0.7
        if reputation_score >= 35 and weighted_net_profit > 0 and weighted_hit_rate >= 0.75 and weighted_avg_roi >= 0.1:
            seller_lane = "whitelist"
            lane_summary = "Seller is outperforming. Allow a modest priority boost."
            threshold_delta = {
                "min_score": -3.0,
                "min_roi": -0.01,
                "max_risk_score": 3.0,
            }
            intake_multiplier = 1.25

        items.append(
            {
                "source": str(bucket["source"]),
                "seller_id": str(bucket["seller_id"]),
                "seller_key": str(bucket["seller_key"]),
                "sold_count": sold_count,
                "profitable_sold_count": profitable_sold_count,
                "realized_net_profit": realized_net_profit,
                "profit_hit_rate": profit_hit_rate,
                "avg_realized_roi": avg_realized_roi,
                "weighted_hit_rate": round(weighted_hit_rate, 4),
                "weighted_avg_realized_roi": round(weighted_avg_roi, 4),
                "weighted_net_profit": round(weighted_net_profit, 2),
                "positive_streak": positive_streak,
                "reputation_score": reputation_score,
                "seller_lane": seller_lane,
                "lane_summary": lane_summary,
                "threshold_delta": threshold_delta,
                "intake_multiplier": intake_multiplier,
                "recent_trades": recent_trades,
            }
        )

    ordered = sorted(
        items,
        key=lambda item: (
            float(item["realized_net_profit"]),
            int(item["sold_count"]),
            str(item["seller_key"]),
        ),
        reverse=True,
    )
    weakest = (
        min(
            items,
            key=lambda item: (
                float(item["realized_net_profit"]),
                int(item["sold_count"]),
                str(item["seller_key"]),
            ),
        )
        if items
        else None
    )

    return {
        "best": ordered[0] if ordered else None,
        "weakest": weakest,
        "items": ordered[:8],
    }


def _enrich_seller_attribution_items(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for item in items:
        source = str(item.get("source") or "").strip()
        seller_id = str(item.get("seller_id") or "").strip()
        if not source or not seller_id:
            enriched.append(item)
            continue
        enriched.append(
            {
                **item,
                "current_control": get_seller_control_state(source, seller_id),
                "recent_control_events": list_seller_control_events_for_seller(
                    source=source,
                    seller_id=seller_id,
                    limit=5,
                ),
            }
        )
    return enriched


def _build_loss_streak_summary(rows: list[sqlite3.Row]) -> dict[str, Any]:
    sold_items: list[dict[str, Any]] = []
    for row in rows:
        details = _compute_trade_profit_components(row)
        if details:
            sold_items.append(details)
    sold_items.sort(key=lambda item: item["sold_at"], reverse=True)

    current_consecutive_losses = 0
    current_loss_total = 0.0
    latest_sold_at = sold_items[0]["sold_at"].isoformat() if sold_items else ""
    latest_source = sold_items[0]["source"] if sold_items else ""

    for item in sold_items:
        net_profit = float(item["net_profit"])
        if net_profit < 0:
            current_consecutive_losses += 1
            current_loss_total += net_profit
            continue
        break

    return {
        "current_consecutive_losses": current_consecutive_losses,
        "current_loss_total": round(current_loss_total, 2),
        "latest_sold_at": latest_sold_at,
        "latest_source": latest_source,
    }


def _build_seller_control_summary() -> dict[str, Any]:
    now = datetime.now(timezone.utc)
    items: list[dict[str, Any]] = []
    active_freeze_count = 0
    active_observe_count = 0
    for state in list_seller_control_states(state="frozen", limit=50):
        frozen_until = _parse_db_timestamp(state.get("frozen_until"))
        if frozen_until is not None and frozen_until <= now:
            continue
        active_freeze_count += 1
        items.append(state)
    for state in list_seller_control_states(state="observe", limit=50):
        observe_until = _parse_db_timestamp(state.get("frozen_until"))
        if observe_until is not None and observe_until <= now:
            continue
        active_observe_count += 1
        items.append(state)
    return {
        "active_freeze_count": active_freeze_count,
        "active_observe_count": active_observe_count,
        "items": items[:8],
    }


def _list_forward_validation_trade_rows_with_conn(
    conn: sqlite3.Connection,
    batch_id: int,
) -> list[sqlite3.Row]:
    return conn.execute(
        """
        SELECT
            t.id AS trade_id,
            t.status,
            t.approved_buy_price,
            t.target_sell_price,
            t.sold_price,
            t.created_at,
            t.updated_at,
            l.title,
            fvt.enrolled_at
        FROM forward_validation_trades fvt
        JOIN trades t ON t.id = fvt.trade_id
        JOIN opportunities o ON o.id = t.opportunity_id
        JOIN listings_raw l ON l.id = o.listing_row_id
        WHERE fvt.batch_id = ?
        ORDER BY fvt.id ASC
        """,
        (batch_id,),
    ).fetchall()


def get_trade_performance_report() -> dict[str, Any]:
    with get_conn() as conn:
        pending = conn.execute(
            "SELECT COUNT(*) AS c FROM opportunities WHERE status = 'pending_review'"
        ).fetchone()["c"]
        trade_rows = conn.execute(
            """
            SELECT
                t.id,
                t.status,
                t.approved_buy_price,
                t.target_sell_price,
                t.sold_price,
                t.created_at,
                t.updated_at,
                l.source AS listing_source,
                l.seller_id,
                l.title AS listing_title
            FROM trades t
            JOIN opportunities o ON o.id = t.opportunity_id
            JOIN listings_raw l ON l.id = o.listing_row_id
            ORDER BY t.id DESC
            """
        ).fetchall()
        overall = _build_trade_performance_summary(trade_rows)
        now_utc = datetime.now(timezone.utc)
        today_start = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        last_7d_start = now_utc - timedelta(days=7)
        today_summary = _build_realized_window_summary(trade_rows, since=today_start)
        last_7d_summary = _build_realized_window_summary(trade_rows, since=last_7d_start)
        inventory_summary = _build_inventory_exposure_summary(trade_rows)
        source_snapshot = _build_source_profit_snapshot(trade_rows, since=last_7d_start)
        seller_snapshot = _build_seller_profit_snapshot(trade_rows, since=last_7d_start)
        seller_snapshot_all_time = _build_seller_profit_snapshot(trade_rows)
        seller_attribution_all_time = _enrich_seller_attribution_items(
            list(seller_snapshot_all_time["items"] or [])
        )
        loss_streak = _build_loss_streak_summary(trade_rows)
        seller_control_summary = _build_seller_control_summary()

        try:
            batch_rows = conn.execute(
                """
                SELECT
                    b.*,
                    COUNT(fvt.id) AS enrolled_count,
                    COALESCE(SUM(CASE WHEN t.status = 'sold' THEN 1 ELSE 0 END), 0) AS sold_count
                FROM forward_validation_batches b
                LEFT JOIN forward_validation_trades fvt ON fvt.batch_id = b.id
                LEFT JOIN trades t ON t.id = fvt.trade_id
                GROUP BY b.id
                ORDER BY b.id DESC
                LIMIT 5
                """
            ).fetchall()
        except sqlite3.OperationalError as exc:
            if "forward_validation" not in str(exc):
                raise
            batch_rows = []

        recent_batches: list[dict[str, Any]] = []
        active_batch_payload: dict[str, Any] | None = None
        for batch_row in batch_rows:
            batch_id = int(batch_row["id"])
            member_rows = _list_forward_validation_trade_rows_with_conn(conn, batch_id)
            summary = _build_trade_performance_summary(
                member_rows,
                target_sample_size=int(batch_row["target_sample_size"] or 0),
            )
            payload = {
                **_serialize_forward_validation_batch_row(batch_row),
                **summary,
                "items": [
                    {
                        "trade_id": int(item["trade_id"]),
                        "title": str(item["title"] or ""),
                        "status": str(item["status"] or ""),
                        "approved_buy_price": float(item["approved_buy_price"] or 0.0),
                        "target_sell_price": float(item["target_sell_price"] or 0.0),
                        "sold_price": (
                            float(item["sold_price"]) if item["sold_price"] is not None else None
                        ),
                        "enrolled_at": item["enrolled_at"],
                    }
                    for item in member_rows
                ],
            }
            recent_batches.append(payload)
            if payload["status"] == "open" and active_batch_payload is None:
                active_batch_payload = payload

    return {
        "pending_review_count": int(pending),
        "active_trades_count": int(overall["active_count"]),
        "sold_count": int(overall["sold_count"]),
        "gross_profit": float(overall["realized_gross_profit"]),
        "realized_net_profit": float(overall["realized_net_profit"]),
        "profit_hit_rate": float(overall["profit_hit_rate"]),
        "avg_holding_days": float(overall["avg_holding_days"]),
        "median_holding_days": float(overall["median_holding_days"]),
        "avg_realized_roi": float(overall["avg_realized_roi"]),
        "total_trade_count": int(overall["total_count"]),
        "profitable_sold_count": int(overall["profitable_sold_count"]),
        "profit_cockpit": {
            "today": today_summary,
            "last_7d": last_7d_summary,
            "inventory": inventory_summary,
            "best_source_7d": source_snapshot["best"],
            "weakest_source_7d": source_snapshot["weakest"],
            "source_leaderboard_7d": source_snapshot["items"],
            "best_seller_7d": seller_snapshot["best"],
            "weakest_seller_7d": seller_snapshot["weakest"],
            "seller_leaderboard_7d": seller_snapshot["items"],
            "best_seller_all_time": seller_attribution_all_time[0] if seller_attribution_all_time else None,
            "seller_attribution_all_time": seller_attribution_all_time,
            "seller_controls": seller_control_summary,
            "loss_streak": loss_streak,
        },
        "forward_validation": {
            "active_batch": active_batch_payload,
            "recent_batches": recent_batches,
        },
    }


def get_dashboard_metrics() -> dict[str, Any]:
    return get_trade_performance_report()


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


def _parse_json_object(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {}
        try:
            parsed = json.loads(text)
        except Exception:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def get_execution_log_summary(limit: int = 24) -> dict[str, Any]:
    try:
        rows = list_execution_logs(limit=max(1, min(500, int(limit))))
    except sqlite3.OperationalError:
        return {
            "sample_size": 0,
            "success_count": 0,
            "failure_count": 0,
            "success_rate": 0.0,
            "failure_rate": 0.0,
            "business_ban_count": 0,
            "last_failure_at": "",
        }
    sample_size = len(rows)
    failure_count = 0
    business_ban_count = 0
    last_failure_at = ""

    for row in rows:
        success = bool(row["success"])
        if not success:
            failure_count += 1
            if not last_failure_at:
                last_failure_at = str(row["created_at"] or "")

        response_payload = _parse_json_object(row["response_json"])
        business_ban_code = str(response_payload.get("business_ban_code") or "").strip()
        error_text = " ".join(
            part
            for part in (
                str(row["error"] or "").strip(),
                str(response_payload.get("error") or "").strip(),
            )
            if part
        ).lower()
        if business_ban_code or "business ban" in error_text:
            business_ban_count += 1

    success_count = sample_size - failure_count
    success_rate = (success_count / sample_size) if sample_size else 0.0
    failure_rate = (failure_count / sample_size) if sample_size else 0.0
    return {
        "sample_size": sample_size,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_rate, 4),
        "failure_rate": round(failure_rate, 4),
        "business_ban_count": business_ban_count,
        "last_failure_at": last_failure_at,
    }


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
    SELECT e.*, t.status AS trade_status
    FROM execution_logs e
    JOIN trades t ON t.id = e.trade_id
    WHERE e.success = 0
      AND NOT EXISTS (
          SELECT 1
          FROM execution_logs newer
          WHERE newer.trade_id = e.trade_id
            AND newer.action = e.action
            AND newer.id > e.id
      )
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
