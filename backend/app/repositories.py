from __future__ import annotations

import hashlib
import json
import math
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from typing import Any

from .config import settings
from .database import get_conn
from .database import record_batch_write_status
from .schemas import FeatureData, ListingIn, MarketplaceOfferIn, SaleIn, ValuationOut
from .services.listing_normalizer import ListingNormalization
from .services.listing_normalizer import TRADABLE_ITEM_TYPES
from .services.listing_normalizer import normalize_listing
from .services.marketplace_normalizer import explain_marketplace_match
from .services.marketplace_normalizer import normalize_marketplace_canonical_key


def _normalize_optional_id(raw: str | None) -> str | None:
    if raw is None:
        return None
    value = str(raw).strip()
    return value or None


def _parse_event_timestamp(raw: str | None) -> datetime:
    text = str(raw or "").strip()
    if not text:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    normalized = text.replace("Z", "+00:00")
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


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


def _normalize_marketplace_platform(raw: str | None) -> str:
    text = _normalize_text_key(raw)
    if text in {"xianyu_monitor", "market_monitor", "goofish"}:
        return "xianyu"
    return text


def _normalize_price_key(raw: float | int | str | None) -> float:
    try:
        return round(float(raw or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _normalize_listing_record(
    *,
    title: str,
    description: str,
) -> ListingNormalization:
    return normalize_listing(title=title, description=description)


def _listing_fingerprint(
    *,
    source: str,
    seller_id: str | None,
    title: str | None,
    list_price: float | int | str | None,
    normalized_key: str | None = None,
) -> tuple[str, str, str, float]:
    normalized_text = str(normalized_key or "").strip()
    return (
        str(source or "").strip(),
        _normalize_optional_id(seller_id) or "",
        normalized_text or _normalize_text_key(title),
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
        SELECT source, seller_id, title, list_price, normalized_key
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
            normalized_key=row["normalized_key"],
        )
        if fp in fingerprints:
            existing.add(fp)
    return existing


def _listing_normalization_payload(
    *,
    title: str,
    description: str,
) -> dict[str, Any]:
    normalized = _normalize_listing_record(title=title, description=description)
    return {
        "normalized_title": normalized.normalized_title,
        "normalized_key": normalized.normalized_key,
        "item_type": normalized.item_type,
        "noise_flags_json": json.dumps(normalized.noise_flags, ensure_ascii=True),
        "normalization_confidence": normalized.normalization_confidence,
        "normalization_blocked": 1 if normalized.normalization_blocked else 0,
        "normalization_reason": normalized.normalization_reason,
        "normalization_version": normalized.normalization_version,
    }


def _normalize_listing_row_if_needed(conn: sqlite3.Connection, row_id: int) -> None:
    row = conn.execute(
        """
        SELECT id, title, description, normalization_version
        FROM listings_raw
        WHERE id = ?
        LIMIT 1
        """,
        (row_id,),
    ).fetchone()
    if not row or str(row["normalization_version"] or "").strip():
        return

    normalization = _listing_normalization_payload(
        title=str(row["title"] or ""),
        description=str(row["description"] or ""),
    )
    conn.execute(
        """
        UPDATE listings_raw
        SET normalized_title = ?,
            normalized_key = ?,
            item_type = ?,
            noise_flags_json = ?,
            normalization_confidence = ?,
            normalization_blocked = ?,
            normalization_reason = ?,
            normalization_version = ?
        WHERE id = ?
        """,
        (
            normalization["normalized_title"],
            normalization["normalized_key"],
            normalization["item_type"],
            normalization["noise_flags_json"],
            normalization["normalization_confidence"],
            normalization["normalization_blocked"],
            normalization["normalization_reason"],
            normalization["normalization_version"],
            row_id,
        ),
    )


def _ensure_listing_normalization_for_rows(rows: list[sqlite3.Row]) -> None:
    stale_ids = [
        int(row["id"])
        for row in rows
        if not str(row["normalization_version"] or "").strip()
    ]
    if not stale_ids:
        return
    with get_conn() as conn:
        for row_id in stale_ids:
            _normalize_listing_row_if_needed(conn, row_id)


def _backfill_sale_normalization(row_ids: list[int]) -> None:
    normalized_ids = sorted({int(row_id) for row_id in row_ids if int(row_id) > 0})
    if not normalized_ids:
        return
    placeholders = ",".join("?" for _ in normalized_ids)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, title, description FROM sales_raw WHERE id IN ({placeholders})",
            tuple(normalized_ids),
        ).fetchall()
        for row in rows:
            normalization = _listing_normalization_payload(
                title=str(row["title"] or ""),
                description=str(row["description"] or ""),
            )
            conn.execute(
                """
                UPDATE sales_raw
                SET normalized_title = ?,
                    normalized_key = ?,
                    item_type = ?,
                    noise_flags_json = ?,
                    normalization_confidence = ?,
                    normalization_blocked = ?,
                    normalization_reason = ?,
                    normalization_version = ?
                WHERE id = ?
                """,
                (
                    normalization["normalized_title"],
                    normalization["normalized_key"],
                    normalization["item_type"],
                    normalization["noise_flags_json"],
                    normalization["normalization_confidence"],
                    normalization["normalization_blocked"],
                    normalization["normalization_reason"],
                    normalization["normalization_version"],
                    int(row["id"]),
                ),
            )


def insert_sales(rows: list[SaleIn]) -> int:
    sql = """
    INSERT INTO sales_raw(
        source, item_id, title, description, sold_price, sold_at,
        normalized_title, normalized_key, item_type, noise_flags_json,
        normalization_confidence, normalization_blocked, normalization_reason, normalization_version,
        raw_json
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            normalization = _listing_normalization_payload(
                title=row.title,
                description=row.description,
            )
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
                    normalization["normalized_title"],
                    normalization["normalized_key"],
                    normalization["item_type"],
                    normalization["noise_flags_json"],
                    normalization["normalization_confidence"],
                    normalization["normalization_blocked"],
                    normalization["normalization_reason"],
                    normalization["normalization_version"],
                    json.dumps(row.raw, ensure_ascii=True),
                )
            )

        if not values:
            return 0
        conn.executemany(sql, values)
    return len(values)


def insert_listings(rows: list[ListingIn]) -> int:
    sql = """
    INSERT INTO listings_raw(
        source, listing_id, seller_id, title, description, list_price, listed_at, status,
        normalized_title, normalized_key, item_type, noise_flags_json, normalization_confidence,
        normalization_blocked, normalization_reason, normalization_version, raw_json
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
            normalized_key=_listing_normalization_payload(
                title=row.title,
                description=row.description,
            )["normalized_key"],
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
            normalization = _listing_normalization_payload(
                title=row.title,
                description=row.description,
            )
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
                    normalized_key=normalization["normalized_key"],
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
                    normalization["normalized_title"],
                    normalization["normalized_key"],
                    normalization["item_type"],
                    normalization["noise_flags_json"],
                    normalization["normalization_confidence"],
                    normalization["normalization_blocked"],
                    normalization["normalization_reason"],
                    normalization["normalization_version"],
                    json.dumps(row.raw, ensure_ascii=True),
                )
            )

        if not values:
            return 0
        conn.executemany(sql, values)
    return len(values)


def _normalize_marketplace_canonical_key(raw_key: str | None, title: str) -> str:
    explicit = normalize_marketplace_canonical_key(raw_key=raw_key, title=title)
    if explicit:
        return explicit[:160]
    return normalize_marketplace_canonical_key(title=title)[:160]


def insert_marketplace_offers(rows: list[MarketplaceOfferIn]) -> int:
    sql = """
    INSERT INTO marketplace_offers(
        platform, offer_id, seller_id, title, canonical_key, item_type,
        list_price, shipping_cost, fee_rate, currency, listed_at, status, listing_url, raw_json
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(platform, offer_id) DO UPDATE SET
        seller_id=excluded.seller_id,
        title=excluded.title,
        canonical_key=excluded.canonical_key,
        item_type=excluded.item_type,
        list_price=excluded.list_price,
        shipping_cost=excluded.shipping_cost,
        fee_rate=excluded.fee_rate,
        currency=excluded.currency,
        listed_at=excluded.listed_at,
        status=excluded.status,
        listing_url=excluded.listing_url,
        raw_json=excluded.raw_json,
        updated_at=CURRENT_TIMESTAMP
    """
    values: list[tuple[Any, ...]] = []
    for row in rows:
        platform = _normalize_marketplace_platform(row.platform)
        if not platform:
            continue
        offer_id = _normalize_optional_id(row.offer_id)
        if not offer_id:
            offer_id = f"{platform}:{_normalize_marketplace_canonical_key(row.canonical_key, row.title)}:{_normalize_price_key(row.list_price)}"
        values.append(
            (
                platform,
                offer_id,
                _normalize_optional_id(row.seller_id),
                row.title.strip(),
                _normalize_marketplace_canonical_key(row.canonical_key, row.title),
                _normalize_text_key(row.item_type) or "generic",
                float(row.list_price),
                float(row.shipping_cost),
                float(row.fee_rate),
                str(row.currency or "CNY").strip().upper() or "CNY",
                row.listed_at.isoformat(),
                str(row.status or "open").strip() or "open",
                str(row.listing_url or "").strip(),
                json.dumps(row.raw, ensure_ascii=True),
            )
        )
    if not values:
        return 0
    with get_conn() as conn:
        conn.executemany(sql, values)
    return len(values)


def list_marketplace_offers(
    *,
    platform: str | None = None,
    status: str | None = None,
    limit: int = 100,
) -> list[sqlite3.Row]:
    sql = """
    SELECT *
    FROM marketplace_offers
    """
    where: list[str] = []
    params: list[Any] = []
    if platform:
        where.append("platform = ?")
        params.append(_normalize_marketplace_platform(platform))
    if status:
        where.append("status = ?")
        params.append(str(status).strip())
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += " ORDER BY listed_at DESC, id DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        return conn.execute(sql, tuple(params)).fetchall()


def backfill_marketplace_offers_from_listings(
    *,
    sources: tuple[str, ...] = ("xianyu_monitor",),
    limit: int = 500,
    listing_hours: int = 24 * 30,
) -> int:
    source_values = [str(item or "").strip() for item in sources if str(item or "").strip()]
    if not source_values:
        return 0
    listed_after = (datetime.now(timezone.utc) - timedelta(hours=max(1, int(listing_hours)))).isoformat()
    placeholders = ",".join("?" for _ in source_values)
    sql = f"""
    SELECT source, listing_id, seller_id, title, normalized_key, item_type, list_price, listed_at, status, raw_json
    FROM listings_raw
    WHERE status = 'open'
      AND COALESCE(source, '') IN ({placeholders})
      AND listed_at >= ?
    ORDER BY listed_at DESC
    LIMIT ?
    """
    params: list[Any] = [*source_values, listed_after, max(1, int(limit))]
    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    payload = [
        MarketplaceOfferIn(
            platform=_normalize_marketplace_platform(row["source"]),
            offer_id=_normalize_optional_id(row["listing_id"]),
            seller_id=_normalize_optional_id(row["seller_id"]),
            title=str(row["title"] or "").strip(),
            canonical_key=str(row["normalized_key"] or "").strip(),
            item_type=str(row["item_type"] or "generic").strip() or "generic",
            list_price=float(row["list_price"] or 0.0),
            shipping_cost=0.0,
            fee_rate=0.0,
            currency="CNY",
            listed_at=_parse_event_timestamp(str(row["listed_at"] or "")).astimezone(timezone.utc),
            status="open",
            listing_url="",
            raw=_parse_json_object(row["raw_json"]),
        )
        for row in rows
    ]
    return insert_marketplace_offers(payload)


def get_marketplace_provider_status(
    *,
    listing_hours: int = 24 * 30,
    providers: tuple[str, ...] = ("xianyu", "taobao", "jd", "pinduoduo"),
) -> list[dict[str, Any]]:
    normalized_providers = [_normalize_marketplace_platform(item) for item in providers if str(item or "").strip()]
    listed_after = (datetime.now(timezone.utc) - timedelta(hours=max(1, int(listing_hours)))).isoformat()
    with get_conn() as conn:
        offer_rows = conn.execute(
            """
            SELECT platform, COUNT(*) AS c, MAX(listed_at) AS latest_listed_at
            FROM marketplace_offers
            WHERE status = 'open' AND listed_at >= ?
            GROUP BY platform
            """,
            (listed_after,),
        ).fetchall()
        legacy_rows = conn.execute(
            """
            SELECT source, COUNT(*) AS c, MAX(listed_at) AS latest_listed_at
            FROM listings_raw
            WHERE status = 'open'
              AND COALESCE(source, '') != 'simulation_seed'
              AND listed_at >= ?
            GROUP BY source
            """,
            (listed_after,),
        ).fetchall()
    offer_map = {
        str(row["platform"] or "").strip().lower(): {
            "offer_count": int(row["c"] or 0),
            "latest_offer_at": str(row["latest_listed_at"] or ""),
        }
        for row in offer_rows
    }
    legacy_map: dict[str, dict[str, Any]] = {}
    for row in legacy_rows:
        provider = _normalize_marketplace_platform(row["source"])
        bucket = legacy_map.setdefault(
            provider,
            {"legacy_open_listing_count": 0, "latest_legacy_at": ""},
        )
        bucket["legacy_open_listing_count"] += int(row["c"] or 0)
        bucket["latest_legacy_at"] = max(
            str(bucket["latest_legacy_at"] or ""),
            str(row["latest_listed_at"] or ""),
        )
    items: list[dict[str, Any]] = []
    for provider in normalized_providers:
        offer_info = offer_map.get(provider, {})
        legacy_info = legacy_map.get(provider, {})
        items.append(
            {
                "provider": provider,
                "offer_count": int(offer_info.get("offer_count") or 0),
                "latest_offer_at": str(offer_info.get("latest_offer_at") or ""),
                "legacy_open_listing_count": int(legacy_info.get("legacy_open_listing_count") or 0),
                "latest_legacy_at": str(legacy_info.get("latest_legacy_at") or ""),
                "backfill_ready": int(legacy_info.get("legacy_open_listing_count") or 0) > 0,
            }
        )
    return items


def create_marketplace_shadow_run(
    *,
    trigger_source: str,
    status: str,
    candidate_count: int,
    accepted_count: int,
    blocked_count: int,
    error_count: int,
    config: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO marketplace_shadow_runs(
                trigger_source,
                status,
                candidate_count,
                accepted_count,
                blocked_count,
                error_count,
                config_json,
                summary_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(trigger_source or "").strip() or "operator",
                str(status or "").strip() or "completed",
                max(0, int(candidate_count)),
                max(0, int(accepted_count)),
                max(0, int(blocked_count)),
                max(0, int(error_count)),
                json.dumps(config or {}, ensure_ascii=True),
                json.dumps(summary or {}, ensure_ascii=True),
            ),
        )
        row = conn.execute(
            "SELECT * FROM marketplace_shadow_runs WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _serialize_marketplace_shadow_run(row)


def update_marketplace_shadow_run(
    run_id: int,
    *,
    status: str,
    candidate_count: int,
    accepted_count: int,
    blocked_count: int,
    error_count: int,
    config: dict[str, Any] | None = None,
    summary: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        conn.execute(
            """
            UPDATE marketplace_shadow_runs
            SET status = ?,
                candidate_count = ?,
                accepted_count = ?,
                blocked_count = ?,
                error_count = ?,
                config_json = ?,
                summary_json = ?
            WHERE id = ?
            """,
            (
                str(status or "").strip() or "completed",
                max(0, int(candidate_count)),
                max(0, int(accepted_count)),
                max(0, int(blocked_count)),
                max(0, int(error_count)),
                json.dumps(config or {}, ensure_ascii=True),
                json.dumps(summary or {}, ensure_ascii=True),
                int(run_id),
            ),
        )
        row = conn.execute(
            "SELECT * FROM marketplace_shadow_runs WHERE id = ?",
            (int(run_id),),
        ).fetchone()
    return _serialize_marketplace_shadow_run(row)


def create_marketplace_shadow_intent(
    *,
    run_id: int | None,
    intent_key: str,
    arbitrage_key: str,
    reference_title: str,
    buy_platform: str,
    sell_platform: str,
    buy_listing_id: str,
    sell_listing_id: str,
    platform_count: int,
    listing_count: int,
    estimated_net_profit: float,
    estimated_roi: float,
    confidence_score: float,
    decision_status: str,
    blocked_reason: str = "",
    snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO marketplace_shadow_intents(
                run_id,
                intent_key,
                arbitrage_key,
                reference_title,
                buy_platform,
                sell_platform,
                buy_listing_id,
                sell_listing_id,
                platform_count,
                listing_count,
                estimated_net_profit,
                estimated_roi,
                confidence_score,
                decision_status,
                blocked_reason,
                snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                int(run_id) if run_id is not None else None,
                str(intent_key or "").strip(),
                str(arbitrage_key or "").strip(),
                str(reference_title or "").strip(),
                str(buy_platform or "").strip(),
                str(sell_platform or "").strip(),
                str(buy_listing_id or "").strip(),
                str(sell_listing_id or "").strip(),
                max(0, int(platform_count)),
                max(0, int(listing_count)),
                float(estimated_net_profit or 0.0),
                float(estimated_roi or 0.0),
                float(confidence_score or 0.0),
                str(decision_status or "").strip() or "blocked",
                str(blocked_reason or "").strip(),
                json.dumps(snapshot or {}, ensure_ascii=True),
            ),
        )
        row = conn.execute(
            "SELECT * FROM marketplace_shadow_intents WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _serialize_marketplace_shadow_intent(row)


def list_marketplace_shadow_runs(limit: int = 50) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM marketplace_shadow_runs
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
    return [_serialize_marketplace_shadow_run(row) for row in rows]


def list_marketplace_shadow_intents(
    *,
    limit: int = 100,
    decision_status: str | None = None,
) -> list[dict[str, Any]]:
    sql = """
    SELECT *
    FROM marketplace_shadow_intents
    """
    params: list[Any] = []
    if decision_status:
        sql += " WHERE decision_status = ?"
        params.append(str(decision_status).strip())
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(max(1, int(limit)))
    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [_serialize_marketplace_shadow_intent(row) for row in rows]


def get_recent_marketplace_shadow_accept(
    *,
    intent_key: str,
    cooldown_minutes: int,
) -> dict[str, Any] | None:
    normalized_key = str(intent_key or "").strip()
    if not normalized_key:
        return None
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, int(cooldown_minutes)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM marketplace_shadow_intents
            WHERE intent_key = ?
              AND decision_status = 'accepted'
            ORDER BY id DESC
            LIMIT 20
            """,
            (normalized_key,),
        ).fetchall()
    for row in rows:
        if _parse_matching_sample_time(row["created_at"]) >= cutoff:
            return _serialize_marketplace_shadow_intent(row)
    return None


def get_marketplace_shadow_status() -> dict[str, Any]:
    runs = list_marketplace_shadow_runs(limit=1)
    intents = list_marketplace_shadow_intents(limit=20)
    accepted_recent = sum(1 for item in intents if str(item.get("decision_status") or "") == "accepted")
    blocked_recent = sum(1 for item in intents if str(item.get("decision_status") or "") == "blocked")
    return {
        "last_run": runs[0] if runs else {},
        "recent_intent_count": len(intents),
        "recent_accepted_count": accepted_recent,
        "recent_blocked_count": blocked_recent,
    }


def _serialize_marketplace_shadow_run(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "id": int(row["id"]),
        "trigger_source": str(row["trigger_source"] or ""),
        "status": str(row["status"] or ""),
        "candidate_count": int(row["candidate_count"] or 0),
        "accepted_count": int(row["accepted_count"] or 0),
        "blocked_count": int(row["blocked_count"] or 0),
        "error_count": int(row["error_count"] or 0),
        "config": _parse_json_object(row["config_json"]),
        "summary": _parse_json_object(row["summary_json"]),
        "created_at": str(row["created_at"] or ""),
    }


def _serialize_marketplace_shadow_intent(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    return {
        "id": int(row["id"]),
        "run_id": int(row["run_id"]) if row["run_id"] is not None else None,
        "intent_key": str(row["intent_key"] or ""),
        "arbitrage_key": str(row["arbitrage_key"] or ""),
        "reference_title": str(row["reference_title"] or ""),
        "buy_platform": str(row["buy_platform"] or ""),
        "sell_platform": str(row["sell_platform"] or ""),
        "buy_listing_id": str(row["buy_listing_id"] or ""),
        "sell_listing_id": str(row["sell_listing_id"] or ""),
        "platform_count": int(row["platform_count"] or 0),
        "listing_count": int(row["listing_count"] or 0),
        "estimated_net_profit": float(row["estimated_net_profit"] or 0.0),
        "estimated_roi": float(row["estimated_roi"] or 0.0),
        "confidence_score": float(row["confidence_score"] or 0.0),
        "decision_status": str(row["decision_status"] or ""),
        "blocked_reason": str(row["blocked_reason"] or ""),
        "snapshot": _parse_json_object(row["snapshot_json"]),
        "created_at": str(row["created_at"] or ""),
    }


def create_matching_lab_sample(
    *,
    left_title: str,
    right_title: str,
    left_key: str = "",
    right_key: str = "",
    expected_verdict: str = "",
    note: str = "",
    result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO matching_lab_samples(
                left_title, right_title, left_key, right_key, expected_verdict, note, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(left_title or "").strip(),
                str(right_title or "").strip(),
                str(left_key or "").strip(),
                str(right_key or "").strip(),
                str(expected_verdict or "").strip(),
                str(note or "").strip(),
                json.dumps(result or {}, ensure_ascii=True),
            ),
        )
        row = conn.execute(
            "SELECT * FROM matching_lab_samples WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _serialize_matching_lab_sample_row(row) if row else {}


def _serialize_matching_lab_sample_row(row: sqlite3.Row | None) -> dict[str, Any]:
    if row is None:
        return {}
    try:
        result_json = json.loads(str(row["result_json"] or "{}"))
    except json.JSONDecodeError:
        result_json = {}
    return {
        "id": int(row["id"]),
        "left_title": str(row["left_title"] or ""),
        "right_title": str(row["right_title"] or ""),
        "left_key": str(row["left_key"] or ""),
        "right_key": str(row["right_key"] or ""),
        "expected_verdict": str(row["expected_verdict"] or ""),
        "note": str(row["note"] or ""),
        "result": result_json,
        "created_at": str(row["created_at"] or ""),
    }


def list_matching_lab_samples(limit: int = 100) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM matching_lab_samples
            ORDER BY id DESC
            LIMIT ?
            """,
            (max(1, int(limit)),),
        ).fetchall()
    return [_serialize_matching_lab_sample_row(row) for row in rows]


def _parse_matching_sample_time(raw: Any) -> datetime:
    text = str(raw or "").strip()
    if not text:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    normalized = text.replace("Z", "+00:00")
    if " " in normalized and "T" not in normalized:
        normalized = normalized.replace(" ", "T", 1)
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def build_matching_lab_report(
    *,
    days: int = 30,
    limit: int = 2000,
    accuracy_threshold: float = 0.8,
    min_scored_samples: int = 10,
) -> dict[str, Any]:
    rows = list_matching_lab_samples(limit=max(1, int(limit)))
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, int(days)))
    recent_rows = [
        row
        for row in rows
        if _parse_matching_sample_time(row.get("created_at")) >= cutoff
    ]

    verdict_counts = {"same_group": 0, "close_match": 0, "different_group": 0}
    expected_counts = {"same_group": 0, "close_match": 0, "different_group": 0}
    scored_rows: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []

    for row in recent_rows:
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        actual_verdict = str(result.get("verdict") or "").strip()
        expected_verdict = str(row.get("expected_verdict") or "").strip()
        if actual_verdict in verdict_counts:
            verdict_counts[actual_verdict] += 1
        if expected_verdict in expected_counts:
            expected_counts[expected_verdict] += 1
            scored_rows.append(row)
            if actual_verdict != expected_verdict:
                mismatches.append(
                    {
                        "id": row["id"],
                        "left_title": row["left_title"],
                        "right_title": row["right_title"],
                        "expected_verdict": expected_verdict,
                        "actual_verdict": actual_verdict,
                        "note": row.get("note") or "",
                        "created_at": row["created_at"],
                    }
                )

    scored_count = len(scored_rows)
    mismatch_count = len(mismatches)
    correct_count = max(0, scored_count - mismatch_count)
    accuracy = (correct_count / scored_count) if scored_count > 0 else 0.0
    gate_ready = scored_count >= max(1, int(min_scored_samples))
    gate_passed = gate_ready and accuracy >= float(accuracy_threshold)

    distribution = [
        {
            "verdict": key,
            "count": int(value),
            "ratio": round((value / max(1, len(recent_rows))), 4),
        }
        for key, value in verdict_counts.items()
    ]
    expected_distribution = [
        {
            "verdict": key,
            "count": int(value),
            "ratio": round((value / max(1, scored_count)), 4) if scored_count else 0.0,
        }
        for key, value in expected_counts.items()
    ]
    mismatches.sort(key=lambda item: item["created_at"], reverse=True)
    return {
        "window_days": int(days),
        "sample_limit": int(limit),
        "summary": {
            "total_samples": len(recent_rows),
            "scored_samples": scored_count,
            "correct_samples": correct_count,
            "mismatch_samples": mismatch_count,
            "accuracy": round(accuracy, 4),
        },
        "gate": {
            "accuracy_threshold": float(accuracy_threshold),
            "min_scored_samples": int(min_scored_samples),
            "ready": gate_ready,
            "passed": gate_passed,
        },
        "actual_distribution": distribution,
        "expected_distribution": expected_distribution,
        "mismatches": mismatches[:20],
    }


def _build_matching_sample_signature(
    *,
    left_title: str,
    right_title: str,
    left_key: str = "",
    right_key: str = "",
    pair_signature: str = "",
    semantic_signature: str = "",
) -> str:
    explicit_pair = str(pair_signature or "").strip()
    if explicit_pair:
        return explicit_pair

    explicit_semantic = str(semantic_signature or "").strip()
    if explicit_semantic:
        return explicit_semantic

    left_canonical = normalize_marketplace_canonical_key(raw_key=left_key, title=left_title)
    right_canonical = normalize_marketplace_canonical_key(raw_key=right_key, title=right_title)
    parts = sorted(
        [
            f"{left_canonical}|{_normalize_text_key(left_title)}",
            f"{right_canonical}|{_normalize_text_key(right_title)}",
        ]
    )
    digest = hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()
    return f"titlepair:{digest}"


def _collect_existing_matching_sample_signatures(limit: int = 5000) -> set[str]:
    signatures: set[str] = set()
    for row in list_matching_lab_samples(limit=max(1, int(limit))):
        result = row.get("result") if isinstance(row.get("result"), dict) else {}
        for key in ("pair_signature", "semantic_signature"):
            value = str(result.get(key) or "").strip()
            if value:
                signatures.add(value)
        signatures.add(
            _build_matching_sample_signature(
                left_title=str(row.get("left_title") or ""),
                right_title=str(row.get("right_title") or ""),
                left_key=str(row.get("left_key") or ""),
                right_key=str(row.get("right_key") or ""),
                pair_signature=str(result.get("pair_signature") or ""),
                semantic_signature=str(result.get("semantic_signature") or ""),
            )
        )
    return signatures


def _serialize_review_offer(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "platform": str(row["platform"] or "").strip(),
        "offer_id": str(row["offer_id"] or "").strip(),
        "seller_id": str(row["seller_id"] or "").strip(),
        "title": str(row["title"] or "").strip(),
        "canonical_key": str(row["canonical_key"] or "").strip(),
        "item_type": str(row["item_type"] or "").strip(),
        "list_price": float(row["list_price"] or 0.0),
        "shipping_cost": float(row["shipping_cost"] or 0.0),
        "fee_rate": float(row["fee_rate"] or 0.0),
        "currency": str(row["currency"] or "CNY").strip().upper() or "CNY",
        "listed_at": str(row["listed_at"] or ""),
        "listing_url": str(row["listing_url"] or "").strip(),
    }


def _matching_review_pair_signature(left: dict[str, Any], right: dict[str, Any]) -> str:
    parts = sorted(
        [
            f"{left['platform']}:{left['offer_id']}",
            f"{right['platform']}:{right['offer_id']}",
        ]
    )
    return "offerpair:" + "||".join(parts)


def _matching_review_semantic_signature(
    left: dict[str, Any],
    right: dict[str, Any],
    comparison: dict[str, Any],
) -> str:
    left_key = str(comparison.get("left_canonical_key") or left.get("canonical_key") or "").strip()
    right_key = str(comparison.get("right_canonical_key") or right.get("canonical_key") or "").strip()
    parts = sorted(
        [
            f"{left['platform']}:{left_key or _normalize_text_key(left['title'])}",
            f"{right['platform']}:{right_key or _normalize_text_key(right['title'])}",
        ]
    )
    digest = hashlib.sha1("||".join(parts).encode("utf-8")).hexdigest()
    return f"semantic:{digest}"


def _matching_review_price_gap_ratio(left_price: float, right_price: float) -> float:
    high = max(float(left_price or 0.0), float(right_price or 0.0), 1.0)
    low = min(float(left_price or 0.0), float(right_price or 0.0))
    return round((high - low) / high, 4)


def _matching_review_price_band(price_gap_ratio: float) -> str:
    if price_gap_ratio <= 0.15:
        return "tight"
    if price_gap_ratio <= 0.35:
        return "medium"
    return "wide"


def _matching_review_priority(
    *,
    comparison: dict[str, Any],
    left: dict[str, Any],
    right: dict[str, Any],
) -> float:
    overlap_ratio = float(comparison.get("token_overlap_ratio") or 0.0)
    overlap_tokens = comparison.get("overlap_tokens") or []
    verdict = str(comparison.get("verdict") or "").strip()
    price_gap_ratio = _matching_review_price_gap_ratio(left["list_price"], right["list_price"])
    price_band = _matching_review_price_band(price_gap_ratio)

    verdict_bonus = {
        "close_match": 0.22,
        "same_group": 0.14,
        "different_group": 0.04,
    }.get(verdict, 0.0)
    price_bonus = {
        "tight": 0.16,
        "medium": 0.08,
        "wide": 0.0,
    }[price_band]
    cross_platform_bonus = 0.12 if "xianyu" in {left["platform"], right["platform"]} else 0.06
    overlap_bonus = min(len(overlap_tokens), 4) * 0.03
    return round(overlap_ratio + verdict_bonus + price_bonus + cross_platform_bonus + overlap_bonus, 4)


def _build_matching_review_queue_items(
    *,
    listing_hours: int = 24 * 30,
    candidate_pool: int = 300,
    min_token_overlap: float = 0.35,
) -> list[dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=max(1, int(listing_hours)))
    rows = list_marketplace_offers(status="open", limit=max(20, min(1000, int(candidate_pool))))
    offers = [
        _serialize_review_offer(row)
        for row in rows
        if _parse_matching_sample_time(row["listed_at"]) >= cutoff
    ]
    existing_signatures = _collect_existing_matching_sample_signatures(
        limit=max(1000, min(10000, int(candidate_pool) * 10))
    )

    candidate_map: dict[str, dict[str, Any]] = {}
    for index, left in enumerate(offers):
        for right in offers[index + 1 :]:
            if left["platform"] == right["platform"]:
                continue

            comparison = explain_marketplace_match(
                left_title=left["title"],
                right_title=right["title"],
                left_key=left["canonical_key"],
                right_key=right["canonical_key"],
            )
            overlap_ratio = float(comparison.get("token_overlap_ratio") or 0.0)
            overlap_tokens = list(comparison.get("overlap_tokens") or [])
            if not bool(comparison.get("exact_match")) and overlap_ratio < float(min_token_overlap) and len(overlap_tokens) < 2:
                continue

            pair_signature = _matching_review_pair_signature(left, right)
            semantic_signature = _matching_review_semantic_signature(left, right, comparison)
            fallback_signature = _build_matching_sample_signature(
                left_title=left["title"],
                right_title=right["title"],
                left_key=left["canonical_key"],
                right_key=right["canonical_key"],
            )
            if (
                pair_signature in existing_signatures
                or semantic_signature in existing_signatures
                or fallback_signature in existing_signatures
            ):
                continue

            price_gap_ratio = _matching_review_price_gap_ratio(left["list_price"], right["list_price"])
            price_band = _matching_review_price_band(price_gap_ratio)
            priority_score = _matching_review_priority(comparison=comparison, left=left, right=right)
            review_id = hashlib.sha1(pair_signature.encode("utf-8")).hexdigest()[:16]
            item = {
                "review_id": review_id,
                "pair_signature": pair_signature,
                "semantic_signature": semantic_signature,
                "priority_score": priority_score,
                "predicted_verdict": str(comparison.get("verdict") or "").strip(),
                "reason": str(comparison.get("reason") or "").strip(),
                "token_overlap_ratio": overlap_ratio,
                "overlap_tokens": overlap_tokens,
                "left_only_tokens": list(comparison.get("left_only_tokens") or []),
                "right_only_tokens": list(comparison.get("right_only_tokens") or []),
                "exact_match": bool(comparison.get("exact_match")),
                "price_gap_ratio": price_gap_ratio,
                "price_band": price_band,
                "platforms": sorted({left["platform"], right["platform"]}),
                "left": left,
                "right": right,
                "comparison": comparison,
            }
            current = candidate_map.get(semantic_signature)
            if current is None or float(item["priority_score"]) > float(current["priority_score"]):
                candidate_map[semantic_signature] = item

    items = sorted(
        candidate_map.values(),
        key=lambda item: (
            -float(item["priority_score"]),
            str(item["predicted_verdict"]) != "close_match",
            float(item["price_gap_ratio"]),
            str(item["left"]["listed_at"]),
            str(item["right"]["listed_at"]),
        ),
    )
    return items


def build_matching_review_queue(
    *,
    limit: int = 20,
    listing_hours: int = 24 * 30,
    candidate_pool: int = 300,
    min_token_overlap: float = 0.35,
) -> dict[str, Any]:
    items = _build_matching_review_queue_items(
        listing_hours=listing_hours,
        candidate_pool=candidate_pool,
        min_token_overlap=min_token_overlap,
    )[: max(1, int(limit))]
    return {
        "items": items,
        "count": len(items),
        "listing_hours": int(listing_hours),
        "candidate_pool": int(candidate_pool),
        "min_token_overlap": float(min_token_overlap),
    }


def label_matching_review_queue_item(
    *,
    review_id: str,
    expected_verdict: str,
    note: str = "",
    listing_hours: int = 24 * 30,
    candidate_pool: int = 300,
    min_token_overlap: float = 0.35,
) -> dict[str, Any]:
    review_key = str(review_id or "").strip()
    if not review_key:
        raise KeyError("review_id is required")

    items = _build_matching_review_queue_items(
        listing_hours=listing_hours,
        candidate_pool=candidate_pool,
        min_token_overlap=min_token_overlap,
    )
    match = next((item for item in items if str(item["review_id"]) == review_key), None)
    if match is None:
        raise KeyError(review_key)

    result_payload = dict(match["comparison"])
    result_payload.update(
        {
            "review_id": match["review_id"],
            "pair_signature": match["pair_signature"],
            "semantic_signature": match["semantic_signature"],
            "price_gap_ratio": match["price_gap_ratio"],
            "price_band": match["price_band"],
            "platforms": match["platforms"],
            "priority_score": match["priority_score"],
            "left_offer": match["left"],
            "right_offer": match["right"],
        }
    )
    sample = create_matching_lab_sample(
        left_title=str(match["left"]["title"] or ""),
        right_title=str(match["right"]["title"] or ""),
        left_key=str(match["left"]["canonical_key"] or ""),
        right_key=str(match["right"]["canonical_key"] or ""),
        expected_verdict=str(expected_verdict or "").strip(),
        note=str(note or "").strip(),
        result=result_payload,
    )
    return {
        "review_id": match["review_id"],
        "sample": sample,
    }


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
    normalization = _listing_normalization_payload(
        title=row.title,
        description=row.description,
    )
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
            normalized_key=normalization["normalized_key"],
        )
        with get_conn() as conn:
            existing = _load_existing_listing_fingerprints(conn, {fp})
            if fp in existing:
                candidates = conn.execute(
                    """
                    SELECT id, title, normalized_key
                    FROM listings_raw
                    WHERE source = ? AND COALESCE(seller_id, '') = ? AND ROUND(list_price, 2) = ?
                      AND status = 'open'
                    ORDER BY id DESC
                    LIMIT 200
                    """,
                    (fp[0], fp[1], fp[3]),
                ).fetchall()
                for item in candidates:
                    existing_key = str(item["normalized_key"] or "").strip() or _normalize_text_key(item["title"])
                    if existing_key == fp[2]:
                        return int(item["id"]), False

    sql = """
    INSERT INTO listings_raw(
        source, listing_id, seller_id, title, description, list_price, listed_at, status,
        normalized_title, normalized_key, item_type, noise_flags_json, normalization_confidence,
        normalization_blocked, normalization_reason, normalization_version, raw_json
    )
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                normalization["normalized_title"],
                normalization["normalized_key"],
                normalization["item_type"],
                normalization["noise_flags_json"],
                normalization["normalization_confidence"],
                normalization["normalization_blocked"],
                normalization["normalization_reason"],
                normalization["normalization_version"],
                json.dumps(row.raw, ensure_ascii=True),
            ),
        )
        return int(cur.lastrowid), True


def get_listing(row_id: int) -> sqlite3.Row | None:
    with get_conn() as conn:
        _normalize_listing_row_if_needed(conn, row_id)
        cur = conn.execute("SELECT * FROM listings_raw WHERE id = ?", (row_id,))
        return cur.fetchone()


def _backfill_listing_normalization(row_ids: list[int]) -> None:
    normalized_ids = sorted({int(row_id) for row_id in row_ids if int(row_id) > 0})
    if not normalized_ids:
        return
    placeholders = ",".join("?" for _ in normalized_ids)
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT id, title, description FROM listings_raw WHERE id IN ({placeholders})",
            tuple(normalized_ids),
        ).fetchall()
        for row in rows:
            normalization = _listing_normalization_payload(
                title=str(row["title"] or ""),
                description=str(row["description"] or ""),
            )
            conn.execute(
                """
                UPDATE listings_raw
                SET normalized_title = ?,
                    normalized_key = ?,
                    item_type = ?,
                    noise_flags_json = ?,
                    normalization_confidence = ?,
                    normalization_blocked = ?,
                    normalization_reason = ?,
                    normalization_version = ?
                WHERE id = ?
                """,
                (
                    normalization["normalized_title"],
                    normalization["normalized_key"],
                    normalization["item_type"],
                    normalization["noise_flags_json"],
                    normalization["normalization_confidence"],
                    normalization["normalization_blocked"],
                    normalization["normalization_reason"],
                    normalization["normalization_version"],
                    int(row["id"]),
                ),
            )


def get_open_listings(
    limit: int = 50,
    *,
    include_noise_filtered: bool = False,
    include_simulation: bool = False,
) -> list[sqlite3.Row]:
    sql = "SELECT * FROM listings_raw WHERE status = 'open'"
    params: list[Any] = []
    if not include_simulation:
        sql += " AND COALESCE(source, '') != ?"
        params.append("simulation_seed")
    sql += " ORDER BY listed_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
        rows = cur.fetchall()
    stale_ids = [
        int(row["id"])
        for row in rows
        if not str(row["normalization_version"] or "").strip()
    ]
    if stale_ids:
        _backfill_listing_normalization(stale_ids)
        with get_conn() as conn:
            placeholders = ",".join("?" for _ in stale_ids)
            refreshed = conn.execute(
                f"SELECT * FROM listings_raw WHERE id IN ({placeholders})",
                tuple(stale_ids),
            ).fetchall()
        refreshed_map = {int(row["id"]): row for row in refreshed}
        rows = [refreshed_map.get(int(row["id"]), row) for row in rows]
    if include_noise_filtered:
        return rows
    return [row for row in rows if not bool(row["normalization_blocked"])]


def list_open_listings_for_arbitrage(
    *,
    listing_hours: int = 72,
    limit: int = 2000,
    include_sources: tuple[str, ...] = (),
    include_simulation: bool = False,
) -> list[sqlite3.Row]:
    listing_window_hours = max(1, min(24 * 30, int(listing_hours)))
    row_limit = max(1, min(5000, int(limit)))
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=listing_window_hours)).isoformat()
    sql = """
    SELECT
        id,
        source,
        listing_id,
        seller_id,
        title,
        description,
        list_price,
        listed_at,
        status,
        normalized_title,
        normalized_key,
        item_type,
        normalization_confidence,
        normalization_blocked
    FROM listings_raw
    WHERE status = 'open'
      AND listed_at >= ?
      AND COALESCE(normalization_blocked, 0) = 0
      AND COALESCE(normalized_key, '') != ''
    """
    params: list[Any] = [cutoff]
    if not include_simulation:
        sql += " AND COALESCE(source, '') != ?"
        params.append("simulation_seed")
    normalized_sources = tuple(
        token.strip()
        for token in include_sources
        if str(token or "").strip()
    )
    if normalized_sources:
        placeholders = ",".join("?" for _ in normalized_sources)
        sql += f" AND source IN ({placeholders})"
        params.extend(normalized_sources)
    sql += " ORDER BY listed_at DESC LIMIT ?"
    params.append(row_limit)
    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return rows


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
    SELECT s.id, s.sold_price, s.sold_at, s.normalized_title, s.normalization_version
    FROM sales_raw s
    LEFT JOIN item_features f ON f.ref_type = 'sale' AND f.ref_id = s.id
    WHERE
        (f.card_name = ? OR s.normalized_title = ? OR s.title LIKE ?)
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
                features.card_name,
                f"%{features.card_name}%",
                features.rarity,
                features.rarity,
                features.edition,
                features.edition,
                limit,
            ),
        )
        rows = cur.fetchall()
    stale_ids = [
        int(row["id"])
        for row in rows
        if not str(row["normalization_version"] or "").strip()
    ]
    if stale_ids:
        _backfill_sale_normalization(stale_ids)
        with get_conn() as conn:
            placeholders = ",".join("?" for _ in stale_ids)
            refreshed = conn.execute(
                f"""
                SELECT s.id, s.sold_price, s.sold_at, s.normalized_title, s.normalization_version
                FROM sales_raw s
                WHERE s.id IN ({placeholders})
                """,
                tuple(stale_ids),
            ).fetchall()
        refreshed_map = {int(row["id"]): row for row in refreshed}
        rows = [refreshed_map.get(int(row["id"]), row) for row in rows]
    return rows


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


def list_opportunities(
    status: str | None = None,
    limit: int = 100,
    *,
    include_simulation: bool = False,
) -> list[sqlite3.Row]:
    base_sql = """
    SELECT o.*, l.listing_id, l.title, l.source, l.seller_id, l.list_price, l.item_type, l.normalized_key,
           v.expected_sale_price, v.suggested_list_price
    FROM opportunities o
    JOIN listings_raw l ON l.id = o.listing_row_id
    JOIN valuation_records v ON v.id = o.valuation_id
    """
    where_parts: list[str] = []
    params: list[Any] = []
    if status:
        where_parts.append("o.status = ?")
        params.append(status)
    if not include_simulation:
        where_parts.append("COALESCE(l.source, '') != ?")
        params.append("simulation_seed")

    sql = base_sql
    if where_parts:
        sql += f" WHERE {' AND '.join(where_parts)}"
    sql += " ORDER BY o.score DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
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


def cleanup_simulation_seed_data(
    *,
    note: str = "simulation seed archived from live workflow",
) -> dict[str, int]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT
                l.id AS listing_row_id,
                l.status AS listing_status,
                o.id AS opportunity_id,
                o.status AS opportunity_status
            FROM listings_raw l
            LEFT JOIN opportunities o ON o.listing_row_id = l.id
            WHERE COALESCE(l.source, '') = 'simulation_seed'
            ORDER BY l.id ASC
            """
        ).fetchall()

    listing_ids = [int(row["listing_row_id"]) for row in rows]
    queued_rows = [
        row
        for row in rows
        if row["opportunity_id"] is not None
        and str(row["opportunity_status"] or "") in {"pending_review", "blocked_risk"}
    ]

    reject_log_count = 0
    for row in queued_rows:
        log_id = create_opportunity_reject_log(
            int(row["opportunity_id"]),
            note=note,
            reject_mode="simulation_cleanup",
        )
        if log_id is not None:
            reject_log_count += 1

    with get_conn() as conn:
        archived_listing_count = 0
        if listing_ids:
            archived_listing_count = conn.execute(
                """
                UPDATE listings_raw
                SET status = 'archived'
                WHERE COALESCE(source, '') = 'simulation_seed'
                  AND status != 'archived'
                """
            ).rowcount

        queued_opportunity_count = 0
        if queued_rows:
            opportunity_ids = [int(row["opportunity_id"]) for row in queued_rows]
            placeholders = ",".join("?" for _ in opportunity_ids)
            queued_opportunity_count = conn.execute(
                f"""
                UPDATE opportunities
                SET status = 'rejected',
                    review_note = ?,
                    reviewed_at = CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})
                """,
                (note, *opportunity_ids),
            ).rowcount

    pending_review_count = sum(1 for row in queued_rows if str(row["opportunity_status"] or "") == "pending_review")
    blocked_risk_count = sum(1 for row in queued_rows if str(row["opportunity_status"] or "") == "blocked_risk")
    return {
        "simulation_listing_count": len(listing_ids),
        "archived_listing_count": int(archived_listing_count),
        "queued_simulation_opportunity_count": len(queued_rows),
        "pending_review_rejected_count": pending_review_count,
        "blocked_risk_rejected_count": blocked_risk_count,
        "updated_opportunity_count": int(queued_opportunity_count),
        "reject_log_count": int(reject_log_count),
    }


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
    try:
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
    except sqlite3.OperationalError:
        return []
    return [_serialize_autotrade_tuning_event_row(row) for row in rows]


def get_autotrade_tuning_event(event_id: int) -> dict[str, Any] | None:
    try:
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM autotrade_tuning_events WHERE id = ? LIMIT 1",
                (event_id,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
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
    try:
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
    except sqlite3.OperationalError:
        return []
    return [_serialize_autotrade_tuning_activity_row(row) for row in rows]


def get_autotrade_tuning_daily_report(hours: int = 24) -> dict[str, Any]:
    window_hours = max(1, min(24 * 30, int(hours)))
    try:
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
    except sqlite3.OperationalError:
        rows = []

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


def _serialize_validation_baseline_snapshot_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "bucket_type": str(row["bucket_type"] or ""),
        "bucket_key": str(row["bucket_key"] or ""),
        "status": str(row["status"] or ""),
        "ready": bool(row["ready"]),
        "ready_for_tune": bool(row["ready_for_tune"]),
        "ready_for_scale": bool(row["ready_for_scale"]),
        "direction": str(row["direction"] or ""),
        "summary": str(row["summary"] or ""),
        "blocking_codes": _load_json_array(row["blocking_codes_json"]),
        "captured_at": row["captured_at"],
        "updated_at": row["updated_at"],
        "snapshot": _load_json_object(row["snapshot_json"]),
    }


def upsert_validation_baseline_snapshot(
    *,
    bucket_type: str,
    bucket_key: str,
    status: str,
    ready: bool,
    ready_for_tune: bool,
    ready_for_scale: bool,
    direction: str,
    summary: str,
    blocking_codes: list[str] | None = None,
    snapshot: dict[str, Any] | None = None,
    captured_at: str = "",
) -> dict[str, Any]:
    normalized_bucket_type = str(bucket_type or "").strip().lower()
    normalized_bucket_key = str(bucket_key or "").strip()
    if normalized_bucket_type not in {"hour", "day"}:
        raise ValueError("bucket_type must be hour or day")
    if not normalized_bucket_key:
        raise ValueError("bucket_key is required")
    timestamp = str(captured_at or "").strip() or datetime.now(timezone.utc).isoformat()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO validation_baseline_snapshots(
                bucket_type,
                bucket_key,
                status,
                ready,
                ready_for_tune,
                ready_for_scale,
                direction,
                summary,
                blocking_codes_json,
                snapshot_json,
                captured_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(bucket_type, bucket_key) DO UPDATE SET
                status = excluded.status,
                ready = excluded.ready,
                ready_for_tune = excluded.ready_for_tune,
                ready_for_scale = excluded.ready_for_scale,
                direction = excluded.direction,
                summary = excluded.summary,
                blocking_codes_json = excluded.blocking_codes_json,
                snapshot_json = excluded.snapshot_json,
                captured_at = excluded.captured_at,
                updated_at = excluded.updated_at
            """,
            (
                normalized_bucket_type,
                normalized_bucket_key,
                str(status or "").strip(),
                1 if ready else 0,
                1 if ready_for_tune else 0,
                1 if ready_for_scale else 0,
                str(direction or "").strip(),
                str(summary or "").strip(),
                json.dumps(list(blocking_codes or []), ensure_ascii=True),
                json.dumps(snapshot or {}, ensure_ascii=True),
                timestamp,
                timestamp,
            ),
        )
        row = conn.execute(
            """
            SELECT *
            FROM validation_baseline_snapshots
            WHERE bucket_type = ? AND bucket_key = ?
            LIMIT 1
            """,
            (normalized_bucket_type, normalized_bucket_key),
        ).fetchone()
    return _serialize_validation_baseline_snapshot_row(row)


def list_validation_baseline_snapshots(
    *,
    bucket_type: str,
    limit: int = 24,
) -> list[dict[str, Any]]:
    normalized_bucket_type = str(bucket_type or "").strip().lower()
    if normalized_bucket_type not in {"hour", "day"}:
        return []
    capped_limit = max(1, min(200, int(limit)))
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM validation_baseline_snapshots
                WHERE bucket_type = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT ?
                """,
                (normalized_bucket_type, capped_limit),
            ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [_serialize_validation_baseline_snapshot_row(row) for row in rows]


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
    try:
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
    except sqlite3.OperationalError:
        return None
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
    try:
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.OperationalError:
        return []
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
    try:
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
    except sqlite3.OperationalError:
        return []
    return [_serialize_seller_control_event_row(row) for row in rows]


def list_seller_control_events_for_seller(
    *,
    source: str,
    seller_id: str,
    limit: int = 20,
) -> list[dict[str, Any]]:
    capped_limit = max(1, min(100, int(limit)))
    try:
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
    except sqlite3.OperationalError:
        return []
    return [_serialize_seller_control_event_row(row) for row in rows]


def get_seller_control_daily_report(hours: int = 24) -> dict[str, Any]:
    window_hours = max(1, min(24 * 30, int(hours)))
    try:
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
    except sqlite3.OperationalError:
        rows = []

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


def _serialize_source_control_state_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "source": str(row["source"] or ""),
        "state": str(row["state"] or "normal"),
        "reason": str(row["reason"] or ""),
        "frozen_until": row["frozen_until"],
        "metadata": _load_json_object(row["metadata_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_source_control_state(source: str) -> dict[str, Any] | None:
    try:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM source_control_states
                WHERE source = ?
                LIMIT 1
                """,
                (str(source or "").strip(),),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_source_control_state_row(row)


def list_source_control_states(
    *,
    state: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    capped_limit = max(1, min(500, int(limit)))
    sql = "SELECT * FROM source_control_states"
    params: list[Any] = []
    if state:
        sql += " WHERE state = ?"
        params.append(str(state or "").strip())
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(capped_limit)
    try:
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [_serialize_source_control_state_row(row) for row in rows]


def upsert_source_control_state(
    *,
    source: str,
    state: str,
    reason: str = "",
    frozen_until: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_source = str(source or "").strip()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO source_control_states(
                source, state, reason, frozen_until, metadata_json
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source) DO UPDATE SET
                state=excluded.state,
                reason=excluded.reason,
                frozen_until=excluded.frozen_until,
                metadata_json=excluded.metadata_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                normalized_source,
                str(state or "normal").strip(),
                str(reason or "").strip(),
                frozen_until,
                json.dumps(metadata or {}, ensure_ascii=True),
            ),
        )
        row = conn.execute(
            """
            SELECT *
            FROM source_control_states
            WHERE source = ?
            LIMIT 1
            """,
            (normalized_source,),
        ).fetchone()
    return _serialize_source_control_state_row(row)


def _serialize_source_control_event_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "source": str(row["source"] or ""),
        "event_type": str(row["event_type"] or ""),
        "reason": str(row["reason"] or ""),
        "previous_state": _load_json_object(row["previous_state_json"]),
        "next_state": _load_json_object(row["next_state_json"]),
        "created_at": row["created_at"],
    }


def create_source_control_event(
    *,
    source: str,
    event_type: str,
    reason: str,
    previous_state: dict[str, Any] | None,
    next_state: dict[str, Any] | None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO source_control_events(
                source,
                event_type,
                reason,
                previous_state_json,
                next_state_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(source or "").strip(),
                str(event_type or "").strip(),
                str(reason or "").strip(),
                json.dumps(previous_state or {}, ensure_ascii=True),
                json.dumps(next_state or {}, ensure_ascii=True),
            ),
        )
        row = conn.execute(
            "SELECT * FROM source_control_events WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _serialize_source_control_event_row(row)


def list_source_control_events(limit: int = 50) -> list[dict[str, Any]]:
    capped_limit = max(1, min(500, int(limit)))
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM source_control_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (capped_limit,),
            ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [_serialize_source_control_event_row(row) for row in rows]


def get_source_control_daily_report(hours: int = 24) -> dict[str, Any]:
    window_hours = max(1, min(24 * 30, int(hours)))
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM source_control_events
                WHERE created_at >= datetime('now', ?)
                ORDER BY id DESC
                """,
                (f"-{window_hours} hours",),
            ).fetchall()
    except sqlite3.OperationalError:
        rows = []

    items = [_serialize_source_control_event_row(row) for row in rows]
    counts_by_type: dict[str, int] = {}
    counts_by_source: dict[str, int] = {}
    for item in items:
        event_type = str(item["event_type"] or "unknown")
        counts_by_type[event_type] = counts_by_type.get(event_type, 0) + 1
        source_key = str(item["source"] or "")
        counts_by_source[source_key] = counts_by_source.get(source_key, 0) + 1

    hottest_sources = [
        {"source": source, "count": count}
        for source, count in sorted(
            counts_by_source.items(),
            key=lambda item: (-item[1], item[0]),
        )[:5]
    ]

    return {
        "hours": window_hours,
        "event_count": len(items),
        "counts_by_type": counts_by_type,
        "latest_event": items[0] if items else None,
        "hottest_sources": hottest_sources,
        "items": items[:10],
    }


def _serialize_cluster_control_state_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "risk_cluster": str(row["risk_cluster"] or ""),
        "state": str(row["state"] or "normal"),
        "reason": str(row["reason"] or ""),
        "frozen_until": row["frozen_until"],
        "metadata": _load_json_object(row["metadata_json"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def get_cluster_control_state(risk_cluster: str) -> dict[str, Any] | None:
    try:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM cluster_control_states
                WHERE risk_cluster = ?
                LIMIT 1
                """,
                (str(risk_cluster or "").strip(),),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_cluster_control_state_row(row)


def list_cluster_control_states(
    *,
    state: str | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    capped_limit = max(1, min(500, int(limit)))
    sql = "SELECT * FROM cluster_control_states"
    params: list[Any] = []
    if state:
        sql += " WHERE state = ?"
        params.append(str(state or "").strip())
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(capped_limit)
    try:
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [_serialize_cluster_control_state_row(row) for row in rows]


def upsert_cluster_control_state(
    *,
    risk_cluster: str,
    state: str,
    reason: str = "",
    frozen_until: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    normalized_cluster = str(risk_cluster or "").strip()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO cluster_control_states(
                risk_cluster, state, reason, frozen_until, metadata_json
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(risk_cluster) DO UPDATE SET
                state=excluded.state,
                reason=excluded.reason,
                frozen_until=excluded.frozen_until,
                metadata_json=excluded.metadata_json,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                normalized_cluster,
                str(state or "normal").strip(),
                str(reason or "").strip(),
                frozen_until,
                json.dumps(metadata or {}, ensure_ascii=True),
            ),
        )
        row = conn.execute(
            """
            SELECT *
            FROM cluster_control_states
            WHERE risk_cluster = ?
            LIMIT 1
            """,
            (normalized_cluster,),
        ).fetchone()
    return _serialize_cluster_control_state_row(row)


def _serialize_cluster_control_event_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "risk_cluster": str(row["risk_cluster"] or ""),
        "event_type": str(row["event_type"] or ""),
        "reason": str(row["reason"] or ""),
        "previous_state": _load_json_object(row["previous_state_json"]),
        "next_state": _load_json_object(row["next_state_json"]),
        "created_at": row["created_at"],
    }


def create_cluster_control_event(
    *,
    risk_cluster: str,
    event_type: str,
    reason: str,
    previous_state: dict[str, Any] | None,
    next_state: dict[str, Any] | None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO cluster_control_events(
                risk_cluster,
                event_type,
                reason,
                previous_state_json,
                next_state_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(risk_cluster or "").strip(),
                str(event_type or "").strip(),
                str(reason or "").strip(),
                json.dumps(previous_state or {}, ensure_ascii=True),
                json.dumps(next_state or {}, ensure_ascii=True),
            ),
        )
        row = conn.execute(
            "SELECT * FROM cluster_control_events WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _serialize_cluster_control_event_row(row)


def list_cluster_control_events(limit: int = 50) -> list[dict[str, Any]]:
    capped_limit = max(1, min(500, int(limit)))
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM cluster_control_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (capped_limit,),
            ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [_serialize_cluster_control_event_row(row) for row in rows]


def get_cluster_control_daily_report(hours: int = 24) -> dict[str, Any]:
    window_hours = max(1, min(24 * 30, int(hours)))
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM cluster_control_events
                WHERE created_at >= datetime('now', ?)
                ORDER BY id DESC
                """,
                (f"-{window_hours} hours",),
            ).fetchall()
    except sqlite3.OperationalError:
        rows = []

    items = [_serialize_cluster_control_event_row(row) for row in rows]
    counts_by_type: dict[str, int] = {}
    counts_by_cluster: dict[str, int] = {}
    for item in items:
        event_type = str(item["event_type"] or "unknown")
        counts_by_type[event_type] = counts_by_type.get(event_type, 0) + 1
        cluster_key = str(item["risk_cluster"] or "")
        counts_by_cluster[cluster_key] = counts_by_cluster.get(cluster_key, 0) + 1

    hottest_clusters = [
        {"risk_cluster": risk_cluster, "count": count}
        for risk_cluster, count in sorted(
            counts_by_cluster.items(),
            key=lambda item: (-item[1], item[0]),
        )[:5]
    ]

    return {
        "hours": window_hours,
        "event_count": len(items),
        "counts_by_type": counts_by_type,
        "latest_event": items[0] if items else None,
        "hottest_clusters": hottest_clusters,
        "items": items[:10],
    }


def _serialize_alert_delivery_event_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "channel": str(row["channel"] or ""),
        "provider": str(row["provider"] or ""),
        "channel_label": str(row["channel_label"] or ""),
        "delivery_stage": str(row["delivery_stage"] or ""),
        "alert_signature": str(row["alert_signature"] or ""),
        "alert_keys": _load_json_array(row["alert_keys_json"]),
        "alert_context": _load_json_object(row["alert_context_json"]),
        "alert_count": int(row["alert_count"] or 0),
        "subject": str(row["subject"] or ""),
        "reason": str(row["reason"] or ""),
        "success": bool(row["success"]),
        "source": str(row["source"] or ""),
        "created_at": row["created_at"],
    }


def create_alert_delivery_event(
    *,
    channel: str,
    provider: str = "",
    channel_label: str = "",
    delivery_stage: str = "",
    alert_signature: str,
    alert_keys: list[str] | None = None,
    alert_context: dict[str, Any] | None = None,
    alert_count: int,
    subject: str,
    reason: str,
    success: bool,
    source: str = "",
) -> dict[str, Any]:
    normalized_alert_keys = [
        str(item or "").strip()
        for item in list(alert_keys or [])
        if str(item or "").strip()
    ]
    normalized_alert_context = {
        str(key or "").strip(): value
        for key, value in dict(alert_context or {}).items()
        if str(key or "").strip()
    }
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO alert_delivery_events(
                channel,
                provider,
                channel_label,
                delivery_stage,
                alert_signature,
                alert_keys_json,
                alert_context_json,
                alert_count,
                subject,
                reason,
                success,
                source
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(channel or "").strip(),
                str(provider or "").strip(),
                str(channel_label or "").strip(),
                str(delivery_stage or "").strip(),
                str(alert_signature or "").strip(),
                json.dumps(normalized_alert_keys, ensure_ascii=True),
                json.dumps(normalized_alert_context, ensure_ascii=True),
                int(alert_count or 0),
                str(subject or "").strip(),
                str(reason or "").strip(),
                1 if success else 0,
                str(source or "").strip(),
            ),
        )
        row = conn.execute(
            "SELECT * FROM alert_delivery_events WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _serialize_alert_delivery_event_row(row)


def list_alert_delivery_events(
    *,
    channel: str | None = None,
    alert_key: str | None = None,
    limit: int = 20,
) -> list[dict[str, Any]]:
    capped_limit = max(1, min(200, int(limit)))
    sql = "SELECT * FROM alert_delivery_events"
    params: list[Any] = []
    if channel:
        sql += " WHERE channel = ?"
        params.append(str(channel or "").strip())
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(capped_limit)
    try:
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.OperationalError:
        return []
    items = [_serialize_alert_delivery_event_row(row) for row in rows]
    normalized_alert_key = str(alert_key or "").strip()
    if normalized_alert_key:
        items = [
            item for item in items
            if normalized_alert_key in list(item.get("alert_keys") or [])
        ]
    return items[:capped_limit]


def list_alert_delivery_events_for_alert_key(
    *,
    alert_key: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    normalized_key = str(alert_key or "").strip()
    if not normalized_key:
        return []
    capped_limit = max(1, min(200, int(limit)))
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM alert_delivery_events
                ORDER BY id DESC
                LIMIT ?
                """,
                (max(capped_limit * 8, 200),),
            ).fetchall()
    except sqlite3.OperationalError:
        return []
    matched: list[dict[str, Any]] = []
    for row in rows:
        item = _serialize_alert_delivery_event_row(row)
        alert_keys = {
            str(value or "").strip()
            for value in list(item.get("alert_keys") or [])
            if str(value or "").strip()
        }
        if normalized_key in alert_keys:
            matched.append(item)
            if len(matched) >= capped_limit:
                break
    return matched


def find_recent_alert_delivery_event(
    *,
    channel: str,
    alert_signature: str,
    within_minutes: int,
    success_only: bool = True,
) -> dict[str, Any] | None:
    minutes = max(1, min(24 * 60, int(within_minutes)))
    sql = """
        SELECT *
        FROM alert_delivery_events
        WHERE channel = ?
          AND alert_signature = ?
          AND created_at >= datetime('now', ?)
    """
    params: list[Any] = [
        str(channel or "").strip(),
        str(alert_signature or "").strip(),
        f"-{minutes} minutes",
    ]
    if success_only:
        sql += " AND success = 1"
    sql += " ORDER BY id DESC LIMIT 1"
    try:
        with get_conn() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_alert_delivery_event_row(row)


def _serialize_autotrade_alert_state_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "alert_signature": str(row["alert_signature"] or ""),
        "alert_code": str(row["alert_code"] or ""),
        "scope": str(row["scope"] or ""),
        "target": str(row["target"] or ""),
        "title": str(row["title"] or ""),
        "current_severity": str(row["current_severity"] or "warning"),
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "last_cleared_at": row["last_cleared_at"],
        "occurrence_count": int(row["occurrence_count"] or 0),
        "active": bool(row["active"]),
        "updated_at": row["updated_at"],
    }


def get_autotrade_alert_state(alert_signature: str) -> dict[str, Any] | None:
    try:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM autotrade_alert_states
                WHERE alert_signature = ?
                LIMIT 1
                """,
                (str(alert_signature or "").strip(),),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_autotrade_alert_state_row(row)


def list_autotrade_alert_states(
    *,
    active_only: bool = False,
    limit: int = 100,
) -> list[dict[str, Any]]:
    capped_limit = max(1, min(500, int(limit)))
    sql = "SELECT * FROM autotrade_alert_states"
    params: list[Any] = []
    if active_only:
        sql += " WHERE active = 1"
    sql += " ORDER BY updated_at DESC LIMIT ?"
    params.append(capped_limit)
    try:
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [_serialize_autotrade_alert_state_row(row) for row in rows]


def touch_autotrade_alert_state(
    *,
    alert_signature: str,
    alert_code: str,
    scope: str,
    target: str,
    title: str,
    current_severity: str,
    seen_at: str,
) -> dict[str, Any]:
    normalized_signature = str(alert_signature or "").strip()
    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO autotrade_alert_states(
                alert_signature,
                alert_code,
                scope,
                target,
                title,
                current_severity,
                first_seen_at,
                last_seen_at,
                occurrence_count,
                active
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, 1)
            ON CONFLICT(alert_signature) DO UPDATE SET
                alert_code=excluded.alert_code,
                scope=excluded.scope,
                target=excluded.target,
                title=excluded.title,
                current_severity=excluded.current_severity,
                first_seen_at=CASE
                    WHEN autotrade_alert_states.active = 1 THEN autotrade_alert_states.first_seen_at
                    ELSE excluded.first_seen_at
                END,
                last_seen_at=excluded.last_seen_at,
                last_cleared_at=NULL,
                occurrence_count=CASE
                    WHEN autotrade_alert_states.active = 1 THEN autotrade_alert_states.occurrence_count
                    ELSE autotrade_alert_states.occurrence_count + 1
                END,
                active=1,
                updated_at=CURRENT_TIMESTAMP
            """,
            (
                normalized_signature,
                str(alert_code or "").strip(),
                str(scope or "").strip(),
                str(target or "").strip(),
                str(title or "").strip(),
                str(current_severity or "warning").strip(),
                seen_at,
                seen_at,
            ),
        )
        row = conn.execute(
            """
            SELECT *
            FROM autotrade_alert_states
            WHERE alert_signature = ?
            LIMIT 1
            """,
            (normalized_signature,),
        ).fetchone()
    return _serialize_autotrade_alert_state_row(row)


def deactivate_autotrade_alert_states_except(
    *,
    active_signatures: list[str],
    cleared_at: str,
) -> int:
    normalized = [str(item or "").strip() for item in active_signatures if str(item or "").strip()]
    try:
        with get_conn() as conn:
            if normalized:
                placeholders = ",".join("?" for _ in normalized)
                cur = conn.execute(
                    f"""
                    UPDATE autotrade_alert_states
                    SET active = 0,
                        last_cleared_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE active = 1
                      AND alert_signature NOT IN ({placeholders})
                    """,
                    (cleared_at, *normalized),
                )
            else:
                cur = conn.execute(
                    """
                    UPDATE autotrade_alert_states
                    SET active = 0,
                        last_cleared_at = ?,
                        updated_at = CURRENT_TIMESTAMP
                    WHERE active = 1
                    """,
                    (cleared_at,),
                )
            return int(cur.rowcount or 0)
    except sqlite3.OperationalError:
        return 0


def override_autotrade_alert_state_timestamps(
    *,
    alert_signature: str,
    first_seen_at: str | None = None,
    last_seen_at: str | None = None,
) -> dict[str, Any] | None:
    updates: list[str] = []
    params: list[Any] = []
    if first_seen_at is not None:
        updates.append("first_seen_at = ?")
        params.append(first_seen_at)
    if last_seen_at is not None:
        updates.append("last_seen_at = ?")
        params.append(last_seen_at)
    if not updates:
        return get_autotrade_alert_state(alert_signature)
    params.extend([str(alert_signature or "").strip()])
    try:
        with get_conn() as conn:
            conn.execute(
                f"""
                UPDATE autotrade_alert_states
                SET {", ".join(updates)},
                    updated_at = CURRENT_TIMESTAMP
                WHERE alert_signature = ?
                """,
                tuple(params),
            )
            row = conn.execute(
                """
                SELECT *
                FROM autotrade_alert_states
                WHERE alert_signature = ?
                LIMIT 1
                """,
                (str(alert_signature or "").strip(),),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_autotrade_alert_state_row(row)


def _serialize_alert_signal_state_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "alert_key": str(row["alert_key"] or ""),
        "code": str(row["code"] or ""),
        "scope": str(row["scope"] or ""),
        "target": str(row["target"] or ""),
        "title": str(row["title"] or ""),
        "last_message": str(row["last_message"] or ""),
        "first_seen_at": row["first_seen_at"],
        "last_seen_at": row["last_seen_at"],
        "last_severity": str(row["last_severity"] or "info"),
        "acked_at": row["acked_at"],
        "acked_by": str(row["acked_by"] or ""),
        "snoozed_until": row["snoozed_until"],
        "snooze_reason": str(row["snooze_reason"] or ""),
        "incident_owner": str(row["incident_owner"] or ""),
        "incident_status": str(row["incident_status"] or "open"),
        "incident_priority": str(row["incident_priority"] or ""),
        "incident_sla_due_at": row["incident_sla_due_at"],
        "latest_case_note": str(row["latest_case_note"] or ""),
        "last_case_actor": str(row["last_case_actor"] or ""),
        "last_case_updated_at": row["last_case_updated_at"],
        "resolved_at": row["resolved_at"],
    }


def _serialize_alert_signal_event_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "alert_key": str(row["alert_key"] or ""),
        "action": str(row["action"] or ""),
        "actor": str(row["actor"] or ""),
        "reason": str(row["reason"] or ""),
        "previous_state": _load_json_object(row["previous_state_json"]),
        "next_state": _load_json_object(row["next_state_json"]),
        "created_at": row["created_at"],
    }


def create_alert_signal_event(
    *,
    alert_key: str,
    action: str,
    actor: str,
    reason: str,
    previous_state: dict[str, Any] | None,
    next_state: dict[str, Any] | None,
) -> dict[str, Any]:
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO alert_signal_events(
                alert_key,
                action,
                actor,
                reason,
                previous_state_json,
                next_state_json
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                str(alert_key or "").strip(),
                str(action or "").strip(),
                str(actor or "").strip(),
                str(reason or "").strip(),
                json.dumps(previous_state or {}, ensure_ascii=True),
                json.dumps(next_state or {}, ensure_ascii=True),
            ),
        )
        row = conn.execute(
            "SELECT * FROM alert_signal_events WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _serialize_alert_signal_event_row(row)


def list_alert_signal_events(
    *,
    alert_key: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    capped_limit = max(1, min(200, int(limit)))
    sql = "SELECT * FROM alert_signal_events"
    params: list[Any] = []
    if alert_key:
        sql += " WHERE alert_key = ?"
        params.append(str(alert_key or "").strip())
    sql += " ORDER BY id DESC LIMIT ?"
    params.append(capped_limit)
    try:
        with get_conn() as conn:
            rows = conn.execute(sql, tuple(params)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [_serialize_alert_signal_event_row(row) for row in rows]


def get_latest_alert_signal_event(
    *,
    alert_key: str,
    actions: tuple[str, ...] = (),
) -> dict[str, Any] | None:
    normalized_key = str(alert_key or "").strip()
    sql = "SELECT * FROM alert_signal_events WHERE alert_key = ?"
    params: list[Any] = [normalized_key]
    if actions:
        placeholders = ",".join("?" for _ in actions)
        sql += f" AND action IN ({placeholders})"
        params.extend(str(action or "").strip() for action in actions)
    sql += " ORDER BY id DESC LIMIT 1"
    try:
        with get_conn() as conn:
            row = conn.execute(sql, tuple(params)).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_alert_signal_event_row(row)


def _alert_incident_target(
    *,
    alert_key: str,
    previous_state: dict[str, Any] | None,
    next_state: dict[str, Any] | None,
) -> str:
    for state in (next_state or {}, previous_state or {}):
        text = str(state.get("title") or state.get("target") or "").strip()
        if text:
            return text
    return str(alert_key or "").strip()


def _serialize_alert_signal_incident_item(event: dict[str, Any]) -> dict[str, Any]:
    alert_key = str(event.get("alert_key") or "").strip()
    previous_state = dict(event.get("previous_state") or {})
    next_state = dict(event.get("next_state") or {})
    action = str(event.get("action") or "").strip()
    return {
        "id": f"signal:{int(event.get('id') or 0)}",
        "event_id": int(event.get("id") or 0),
        "kind": "signal",
        "alert_key": alert_key,
        "action": action,
        "actor": str(event.get("actor") or "").strip(),
        "reason": str(event.get("reason") or "").strip(),
        "summary": str(event.get("reason") or action or "").strip(),
        "channel": "",
        "channel_label": "",
        "provider": "",
        "delivery_stage": "",
        "success": None,
        "alert_count": 1,
        "target": _alert_incident_target(
            alert_key=alert_key,
            previous_state=previous_state,
            next_state=next_state,
        ),
        "previous_state": previous_state,
        "next_state": next_state,
        "created_at": event.get("created_at"),
    }


def _serialize_alert_delivery_incident_items(
    event: dict[str, Any],
    *,
    alert_key: str | None = None,
) -> list[dict[str, Any]]:
    normalized_key = str(alert_key or "").strip()
    alert_keys = [
        str(item or "").strip()
        for item in list(event.get("alert_keys") or [])
        if str(item or "").strip()
    ]
    if normalized_key:
        if normalized_key not in alert_keys:
            return []
        incident_keys = [normalized_key]
    else:
        incident_keys = alert_keys or [""]

    success = bool(event.get("success"))
    channel = str(event.get("channel") or "").strip()
    channel_label = str(event.get("channel_label") or channel.title() or "Alert").strip()
    action_channel = channel
    if channel == "webhook" and channel_label:
        normalized_label = channel_label.strip().lower().replace(" ", "_")
        if normalized_label in {"slack", "telegram", "webhook"}:
            action_channel = normalized_label
    delivery_stage = str(event.get("delivery_stage") or "").strip()
    reason = str(event.get("reason") or "").strip()
    subject = str(event.get("subject") or "").strip()
    summary = f"{channel_label} {'sent' if success else 'skipped'}"
    if delivery_stage:
        summary = f"{summary} / {delivery_stage}"
    if reason:
        summary = f"{summary} / {reason}"

    return [
        {
            "id": f"delivery:{int(event.get('id') or 0)}:{key or 'all'}",
            "event_id": int(event.get("id") or 0),
            "kind": "delivery",
            "alert_key": key,
            "action": f"{action_channel}_{'sent' if success else 'skipped'}",
            "actor": str(event.get("source") or "system").strip(),
            "reason": reason,
            "summary": summary,
            "channel": channel,
            "channel_label": channel_label,
            "provider": str(event.get("provider") or "").strip(),
            "delivery_stage": delivery_stage,
            "success": success,
            "alert_count": int(event.get("alert_count") or 0),
            "subject": subject,
            "target": key or channel_label,
            "previous_state": {},
            "next_state": {},
            "created_at": event.get("created_at"),
        }
        for key in incident_keys
    ]


def list_alert_incident_events(
    *,
    alert_key: str | None = None,
    limit: int = 50,
) -> list[dict[str, Any]]:
    capped_limit = max(1, min(200, int(limit)))
    signal_items = [
        _serialize_alert_signal_incident_item(item)
        for item in list_alert_signal_events(alert_key=alert_key, limit=max(capped_limit * 2, 100))
    ]
    delivery_events = list_alert_delivery_events(limit=max(capped_limit * 3, 120))
    delivery_items: list[dict[str, Any]] = []
    for event in delivery_events:
        delivery_items.extend(
            _serialize_alert_delivery_incident_items(event, alert_key=alert_key),
        )

    def _sort_key(item: dict[str, Any]) -> tuple[float, int]:
        created_at = str(item.get("created_at") or "").replace(" ", "T")
        try:
            created_value = datetime.fromisoformat(created_at.replace("Z", "+00:00")).timestamp()
        except ValueError:
            created_value = 0.0
        return created_value, int(item.get("event_id") or 0)

    items = sorted(
        signal_items + delivery_items,
        key=_sort_key,
        reverse=True,
    )
    return items[:capped_limit]


def list_alert_incident_timeline(
    *,
    alert_key: str,
    limit: int = 50,
) -> list[dict[str, Any]]:
    return list_alert_incident_events(
        alert_key=str(alert_key or "").strip() or None,
        limit=limit,
    )


INCIDENT_PRIORITY_RANK = {
    "low": 1,
    "normal": 2,
    "high": 3,
    "critical": 4,
}


def _normalize_incident_priority(priority: str | None, *, fallback: str = "normal") -> str:
    value = str(priority or "").strip().lower()
    return value if value in INCIDENT_PRIORITY_RANK else fallback


def _default_incident_priority_for_severity(severity: str | None) -> str:
    normalized = str(severity or "").strip().lower()
    if normalized == "error":
        return "high"
    if normalized == "info":
        return "low"
    return "normal"


def _incident_sla_minutes_for_priority(priority: str) -> int:
    normalized = _normalize_incident_priority(priority)
    if normalized == "critical":
        return 30
    if normalized == "high":
        return 60
    if normalized == "normal":
        return 120
    return 240


def _incident_sla_due_at(priority: str, *, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return (current + timedelta(minutes=_incident_sla_minutes_for_priority(priority))).replace(microsecond=0).isoformat()


def upsert_alert_signal_state(
    *,
    alert_key: str,
    code: str,
    scope: str,
    target: str,
    title: str,
    last_message: str,
    last_severity: str,
) -> dict[str, Any]:
    normalized_key = str(alert_key or "").strip()
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT *
            FROM alert_signal_states
            WHERE alert_key = ?
            LIMIT 1
            """,
            (normalized_key,),
        ).fetchone()
        if row and not row["resolved_at"]:
            conn.execute(
                """
                UPDATE alert_signal_states
                SET code = ?,
                    scope = ?,
                    target = ?,
                    title = ?,
                    last_message = ?,
                    last_severity = ?,
                    last_seen_at = CURRENT_TIMESTAMP,
                    incident_status = CASE
                        WHEN incident_status = 'resolved' THEN 'open'
                        ELSE incident_status
                    END,
                    resolved_at = NULL
                WHERE alert_key = ?
                """,
                (
                    str(code or "").strip(),
                    str(scope or "").strip(),
                    str(target or "").strip(),
                    str(title or "").strip(),
                    str(last_message or "").strip(),
                    str(last_severity or "info").strip(),
                    normalized_key,
                ),
            )
        else:
            conn.execute(
                """
                INSERT INTO alert_signal_states(
                    alert_key,
                    code,
                    scope,
                    target,
                    title,
                    last_message,
                    first_seen_at,
                    last_seen_at,
                    last_severity,
                    acked_at,
                    acked_by,
                    snoozed_until,
                    snooze_reason,
                    incident_owner,
                    incident_status,
                    incident_priority,
                    incident_sla_due_at,
                    latest_case_note,
                    last_case_actor,
                    last_case_updated_at,
                    resolved_at
                )
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, NULL, '', NULL, '', '', 'open', '', NULL, '', '', NULL, NULL)
                ON CONFLICT(alert_key) DO UPDATE SET
                    code = excluded.code,
                    scope = excluded.scope,
                    target = excluded.target,
                    title = excluded.title,
                    last_message = excluded.last_message,
                    first_seen_at = CASE
                        WHEN alert_signal_states.resolved_at IS NULL
                            THEN alert_signal_states.first_seen_at
                        ELSE CURRENT_TIMESTAMP
                    END,
                    last_seen_at = CURRENT_TIMESTAMP,
                    last_severity = excluded.last_severity,
                    acked_at = CASE
                        WHEN alert_signal_states.resolved_at IS NULL
                            THEN alert_signal_states.acked_at
                        ELSE NULL
                    END,
                    acked_by = CASE
                        WHEN alert_signal_states.resolved_at IS NULL
                            THEN alert_signal_states.acked_by
                        ELSE ''
                    END,
                    snoozed_until = CASE
                        WHEN alert_signal_states.resolved_at IS NULL
                            THEN alert_signal_states.snoozed_until
                        ELSE NULL
                    END,
                    snooze_reason = CASE
                        WHEN alert_signal_states.resolved_at IS NULL
                            THEN alert_signal_states.snooze_reason
                        ELSE ''
                    END,
                    incident_owner = CASE
                        WHEN alert_signal_states.resolved_at IS NULL
                            THEN alert_signal_states.incident_owner
                        ELSE ''
                    END,
                    incident_status = CASE
                        WHEN alert_signal_states.resolved_at IS NULL
                            THEN CASE
                                WHEN alert_signal_states.incident_status = 'resolved' THEN 'open'
                                ELSE alert_signal_states.incident_status
                            END
                        ELSE 'open'
                    END,
                    incident_priority = CASE
                        WHEN alert_signal_states.incident_priority = '' THEN ''
                        ELSE alert_signal_states.incident_priority
                    END,
                    incident_sla_due_at = CASE
                        WHEN alert_signal_states.incident_sla_due_at IS NULL
                            OR alert_signal_states.incident_sla_due_at = ''
                            THEN NULL
                        ELSE alert_signal_states.incident_sla_due_at
                    END,
                    latest_case_note = CASE
                        WHEN alert_signal_states.resolved_at IS NULL
                            THEN alert_signal_states.latest_case_note
                        ELSE ''
                    END,
                    last_case_actor = CASE
                        WHEN alert_signal_states.resolved_at IS NULL
                            THEN alert_signal_states.last_case_actor
                        ELSE ''
                    END,
                    last_case_updated_at = CASE
                        WHEN alert_signal_states.resolved_at IS NULL
                            THEN alert_signal_states.last_case_updated_at
                        ELSE NULL
                    END,
                    resolved_at = NULL
                """,
                (
                    normalized_key,
                    str(code or "").strip(),
                    str(scope or "").strip(),
                    str(target or "").strip(),
                    str(title or "").strip(),
                    str(last_message or "").strip(),
                    str(last_severity or "info").strip(),
                ),
            )
        next_row = conn.execute(
            """
            SELECT *
                FROM alert_signal_states
                WHERE alert_key = ?
                LIMIT 1
                """,
                (normalized_key,),
            ).fetchone()
    return _serialize_alert_signal_state_row(next_row)


def get_alert_signal_state(alert_key: str) -> dict[str, Any] | None:
    normalized_key = str(alert_key or "").strip()
    try:
        with get_conn() as conn:
            row = conn.execute(
                """
                SELECT *
                FROM alert_signal_states
                WHERE alert_key = ?
                LIMIT 1
                """,
                (normalized_key,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_alert_signal_state_row(row)


def list_active_alert_signal_states(limit: int = 200) -> list[dict[str, Any]]:
    capped_limit = max(1, min(500, int(limit)))
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM alert_signal_states
                WHERE resolved_at IS NULL
                ORDER BY last_seen_at DESC
                LIMIT ?
                """,
                (capped_limit,),
            ).fetchall()
    except sqlite3.OperationalError:
        return []
    return [_serialize_alert_signal_state_row(row) for row in rows]


def resolve_missing_alert_signal_states(active_keys: set[str]) -> int:
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM alert_signal_states
                WHERE resolved_at IS NULL
                """
            ).fetchall()
            missing_rows = [
                row
                for row in rows
                if str(row["alert_key"] or "") not in active_keys
            ]
            for row in missing_rows:
                current = _serialize_alert_signal_state_row(row)
                key = str(current.get("alert_key") or "")
                conn.execute(
                    """
                    UPDATE alert_signal_states
                    SET incident_status = 'resolved',
                        latest_case_note = CASE
                            WHEN latest_case_note = '' THEN 'alert cleared automatically'
                            ELSE latest_case_note
                        END,
                        last_case_actor = CASE
                            WHEN last_case_actor = '' THEN 'system'
                            ELSE last_case_actor
                        END,
                        last_case_updated_at = CURRENT_TIMESTAMP,
                        resolved_at = CURRENT_TIMESTAMP
                    WHERE alert_key = ?
                    """,
                    (key,),
                )
                next_row = conn.execute(
                    """
                    SELECT *
                    FROM alert_signal_states
                    WHERE alert_key = ?
                    LIMIT 1
                    """,
                    (key,),
                ).fetchone()
                next_state = _serialize_alert_signal_state_row(next_row)
                conn.execute(
                    """
                    INSERT INTO alert_signal_events(
                        alert_key,
                        action,
                        actor,
                        reason,
                        previous_state_json,
                        next_state_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        key,
                        "cleared",
                        "system",
                        "alert cleared automatically",
                        json.dumps(current or {}, ensure_ascii=True),
                        json.dumps(next_state or {}, ensure_ascii=True),
                    ),
                )
    except sqlite3.OperationalError:
        return 0
    return len(missing_rows)


def release_expired_alert_signal_snoozes(*, now: datetime | None = None) -> list[dict[str, Any]]:
    current_time = now or datetime.now(timezone.utc)
    released: list[dict[str, Any]] = []
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM alert_signal_states
                WHERE resolved_at IS NULL
                  AND snoozed_until IS NOT NULL
                  AND snoozed_until != ''
                """
            ).fetchall()
            for row in rows:
                current = _serialize_alert_signal_state_row(row)
                snoozed_until = str(current.get("snoozed_until") or "").strip()
                if not snoozed_until:
                    continue
                try:
                    parsed = datetime.fromisoformat(snoozed_until.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                parsed = parsed.astimezone(timezone.utc)
                if parsed > current_time:
                    continue
                conn.execute(
                    """
                    UPDATE alert_signal_states
                    SET snoozed_until = NULL,
                        snooze_reason = '',
                        resolved_at = NULL
                    WHERE alert_key = ?
                    """,
                    (str(current.get("alert_key") or ""),),
                )
                next_row = conn.execute(
                    """
                    SELECT *
                    FROM alert_signal_states
                    WHERE alert_key = ?
                    LIMIT 1
                    """,
                    (str(current.get("alert_key") or ""),),
                ).fetchone()
                next_state = _serialize_alert_signal_state_row(next_row)
                event_cur = conn.execute(
                    """
                    INSERT INTO alert_signal_events(
                        alert_key,
                        action,
                        actor,
                        reason,
                        previous_state_json,
                        next_state_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(current.get("alert_key") or ""),
                        "snooze_expired",
                        "system",
                        "snooze expired",
                        json.dumps(current or {}, ensure_ascii=True),
                        json.dumps(next_state or {}, ensure_ascii=True),
                    ),
                )
                event_row = conn.execute(
                    "SELECT * FROM alert_signal_events WHERE id = ?",
                    (int(event_cur.lastrowid),),
                ).fetchone()
                event = _serialize_alert_signal_event_row(event_row)
                released.append(event)
    except sqlite3.OperationalError:
        return []
    return released


def release_expired_alert_acknowledgements(
    *,
    now: datetime | None = None,
    timeout_minutes: int = 240,
) -> list[dict[str, Any]]:
    current_time = now or datetime.now(timezone.utc)
    timeout = max(1, int(timeout_minutes))
    released: list[dict[str, Any]] = []
    try:
        with get_conn() as conn:
            rows = conn.execute(
                """
                SELECT *
                FROM alert_signal_states
                WHERE resolved_at IS NULL
                  AND acked_at IS NOT NULL
                  AND acked_at != ''
                """
            ).fetchall()
            for row in rows:
                current = _serialize_alert_signal_state_row(row)
                acked_at = str(current.get("acked_at") or "").strip()
                if not acked_at:
                    continue
                try:
                    parsed = datetime.fromisoformat(acked_at.replace("Z", "+00:00"))
                except ValueError:
                    continue
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                parsed = parsed.astimezone(timezone.utc)
                age_minutes = (current_time - parsed).total_seconds() / 60.0
                if age_minutes < timeout:
                    continue
                conn.execute(
                    """
                    UPDATE alert_signal_states
                    SET acked_at = NULL,
                        acked_by = '',
                        resolved_at = NULL
                    WHERE alert_key = ?
                    """,
                    (str(current.get("alert_key") or ""),),
                )
                next_row = conn.execute(
                    """
                    SELECT *
                    FROM alert_signal_states
                    WHERE alert_key = ?
                    LIMIT 1
                    """,
                    (str(current.get("alert_key") or ""),),
                ).fetchone()
                next_state = _serialize_alert_signal_state_row(next_row)
                event_cur = conn.execute(
                    """
                    INSERT INTO alert_signal_events(
                        alert_key,
                        action,
                        actor,
                        reason,
                        previous_state_json,
                        next_state_json
                    )
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(current.get("alert_key") or ""),
                        "ack_expired",
                        "system",
                        "ack timeout expired",
                        json.dumps(current or {}, ensure_ascii=True),
                        json.dumps(next_state or {}, ensure_ascii=True),
                    ),
                )
                event_row = conn.execute(
                    "SELECT * FROM alert_signal_events WHERE id = ?",
                    (int(event_cur.lastrowid),),
                ).fetchone()
                released.append(_serialize_alert_signal_event_row(event_row))
    except sqlite3.OperationalError:
        return []
    return released


def override_alert_signal_state_timestamps(
    *,
    alert_key: str,
    first_seen_at: str | None = None,
    last_seen_at: str | None = None,
) -> dict[str, Any] | None:
    updates: list[str] = []
    params: list[Any] = []
    if first_seen_at is not None:
        updates.append("first_seen_at = ?")
        params.append(first_seen_at)
    if last_seen_at is not None:
        updates.append("last_seen_at = ?")
        params.append(last_seen_at)
    if not updates:
        return None
    params.append(str(alert_key or "").strip())
    try:
        with get_conn() as conn:
            conn.execute(
                f"""
                UPDATE alert_signal_states
                SET {", ".join(updates)}
                WHERE alert_key = ?
                """,
                tuple(params),
            )
            row = conn.execute(
                """
                SELECT *
                FROM alert_signal_states
                WHERE alert_key = ?
                LIMIT 1
                """,
                (str(alert_key or "").strip(),),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_alert_signal_state_row(row)


def acknowledge_alert_signal_state(
    *,
    alert_key: str,
    actor: str,
) -> dict[str, Any] | None:
    normalized_key = str(alert_key or "").strip()
    acknowledged_at = datetime.now(timezone.utc).isoformat()
    try:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE alert_signal_states
                SET acked_at = ?,
                    acked_by = ?,
                    snoozed_until = NULL,
                    snooze_reason = '',
                    resolved_at = NULL
                WHERE alert_key = ?
                """,
                (acknowledged_at, str(actor or "").strip(), normalized_key),
            )
            row = conn.execute(
                """
                SELECT *
                FROM alert_signal_states
                WHERE alert_key = ?
                LIMIT 1
                """,
                (normalized_key,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_alert_signal_state_row(row)


def snooze_alert_signal_state(
    *,
    alert_key: str,
    actor: str,
    minutes: int,
    reason: str = "",
) -> dict[str, Any] | None:
    normalized_key = str(alert_key or "").strip()
    snoozed_until = (datetime.now(timezone.utc) + timedelta(minutes=max(1, int(minutes)))).isoformat()
    try:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE alert_signal_states
                SET acked_at = NULL,
                    acked_by = '',
                    snoozed_until = ?,
                    snooze_reason = ?,
                    resolved_at = NULL
                WHERE alert_key = ?
                """,
                (
                    snoozed_until,
                    str(reason or "").strip(),
                    normalized_key,
                ),
            )
            row = conn.execute(
                """
                SELECT *
                FROM alert_signal_states
                WHERE alert_key = ?
                LIMIT 1
                """,
                (normalized_key,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_alert_signal_state_row(row)


def clear_alert_signal_operator_hold(alert_key: str) -> dict[str, Any] | None:
    normalized_key = str(alert_key or "").strip()
    try:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE alert_signal_states
                SET acked_at = NULL,
                    acked_by = '',
                    snoozed_until = NULL,
                    snooze_reason = '',
                    resolved_at = NULL
                WHERE alert_key = ?
                """,
                (normalized_key,),
            )
            row = conn.execute(
                """
                SELECT *
                FROM alert_signal_states
                WHERE alert_key = ?
                LIMIT 1
                """,
                (normalized_key,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_alert_signal_state_row(row)


def update_alert_signal_incident_state(
    *,
    alert_key: str,
    action: str,
    actor: str,
    owner: str | None = None,
    priority: str | None = None,
    note: str = "",
) -> dict[str, Any] | None:
    normalized_key = str(alert_key or "").strip()
    normalized_action = str(action or "").strip().lower()
    normalized_actor = str(actor or "").strip()
    normalized_owner = str(owner or "").strip()
    normalized_priority = _normalize_incident_priority(priority, fallback="")
    normalized_note = str(note or "").strip()
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    if normalized_action == "assign":
        status_value = "assigned"
    elif normalized_action == "handoff":
        status_value = "handed_off"
    elif normalized_action == "resolve":
        status_value = "resolved"
    elif normalized_action == "priority":
        status_value = ""
    elif normalized_action == "note":
        status_value = ""
    else:
        return None

    try:
        with get_conn() as conn:
            current_row = conn.execute(
                """
                SELECT *
                FROM alert_signal_states
                WHERE alert_key = ?
                LIMIT 1
                """,
                (normalized_key,),
            ).fetchone()
            if not current_row:
                return None
            current_state = _serialize_alert_signal_state_row(current_row)
            effective_priority = (
                normalized_priority
                or str(current_state.get("incident_priority") or "").strip()
                or _default_incident_priority_for_severity(current_state.get("last_severity"))
            )
            next_sla_due_at = _incident_sla_due_at(effective_priority)

            if normalized_action in {"assign", "handoff", "resolve"}:
                conn.execute(
                    """
                    UPDATE alert_signal_states
                    SET incident_owner = CASE
                            WHEN ? != '' THEN ?
                            ELSE incident_owner
                        END,
                        incident_status = ?,
                        incident_priority = CASE
                            WHEN incident_priority = '' THEN ?
                            ELSE incident_priority
                        END,
                        incident_sla_due_at = CASE
                            WHEN ? = 'resolved' THEN incident_sla_due_at
                            ELSE CASE
                                WHEN incident_sla_due_at IS NULL OR incident_sla_due_at = '' THEN ?
                                ELSE incident_sla_due_at
                            END
                        END,
                        latest_case_note = CASE
                            WHEN ? != '' THEN ?
                            ELSE latest_case_note
                        END,
                        last_case_actor = ?,
                        last_case_updated_at = ?
                    WHERE alert_key = ?
                    """,
                    (
                        normalized_owner,
                        normalized_owner,
                        status_value,
                        effective_priority,
                        status_value,
                        next_sla_due_at,
                        normalized_note,
                        normalized_note,
                        normalized_actor,
                        now,
                        normalized_key,
                    ),
                )
            elif normalized_action == "priority":
                conn.execute(
                    """
                    UPDATE alert_signal_states
                    SET incident_priority = ?,
                        incident_sla_due_at = ?,
                        latest_case_note = CASE
                            WHEN ? != '' THEN ?
                            ELSE latest_case_note
                        END,
                        last_case_actor = ?,
                        last_case_updated_at = ?
                    WHERE alert_key = ?
                    """,
                    (
                        effective_priority,
                        next_sla_due_at,
                        normalized_note,
                        normalized_note,
                        normalized_actor,
                        now,
                        normalized_key,
                    ),
                )
            else:
                conn.execute(
                    """
                    UPDATE alert_signal_states
                    SET latest_case_note = CASE
                            WHEN ? != '' THEN ?
                            ELSE latest_case_note
                        END,
                        last_case_actor = ?,
                        last_case_updated_at = ?
                    WHERE alert_key = ?
                    """,
                    (
                        normalized_note,
                        normalized_note,
                        normalized_actor,
                        now,
                        normalized_key,
                    ),
                )
            row = conn.execute(
                """
                SELECT *
                FROM alert_signal_states
                WHERE alert_key = ?
                LIMIT 1
                """,
                (normalized_key,),
            ).fetchone()
    except sqlite3.OperationalError:
        return None
    if not row:
        return None
    return _serialize_alert_signal_state_row(row)


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
    try:
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
    except sqlite3.OperationalError:
        return []
    return [_serialize_seller_control_preset_run_row(row) for row in rows]


def get_seller_control_preset(preset_id: int) -> dict[str, Any] | None:
    try:
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
    except sqlite3.OperationalError:
        return None
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
    try:
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
    except sqlite3.OperationalError:
        return []
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
            SELECT t.*, o.listing_row_id, l.title, l.list_price, l.source, l.seller_id
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
    SELECT t.*, o.listing_row_id, l.title, l.list_price, l.source AS listing_source
    FROM trades t
    JOIN opportunities o ON o.id = t.opportunity_id
    JOIN listings_raw l ON l.id = o.listing_row_id
    """
    where_parts: list[str] = ["COALESCE(l.source, '') != ?"]
    params: list[Any] = ["simulation_seed"]
    if status:
        where_parts.append("t.status = ?")
        params.append(status)
    sql = f"{base_sql} WHERE {' AND '.join(where_parts)} ORDER BY t.updated_at DESC LIMIT ?"
    params.append(limit)
    with get_conn() as conn:
        cur = conn.execute(sql, tuple(params))
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


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    pos = max(0.0, min(1.0, q)) * (len(ordered) - 1)
    lo = int(math.floor(pos))
    hi = min(len(ordered) - 1, int(math.ceil(pos)))
    if lo == hi:
        return float(ordered[lo])
    weight = pos - lo
    return float((ordered[lo] * (1 - weight)) + (ordered[hi] * weight))


def _normalized_market_regime_tag(
    *,
    open_listing_count: int,
    recent_sales_count: int,
    noise_listing_count: int,
    spread_ratio: float,
    price_gap_vs_sales: float,
) -> str:
    if recent_sales_count < 2:
        return "thin"
    if noise_listing_count >= open_listing_count and open_listing_count > 0:
        return "noisy"
    if spread_ratio >= 0.35:
        return "wide"
    if price_gap_vs_sales >= 0.15:
        return "overpriced"
    if open_listing_count >= 2 and recent_sales_count >= 2:
        return "tradable"
    return "mixed"


def _normalized_market_snapshot_is_tradable(item_type: str) -> bool:
    return str(item_type or "").strip() in TRADABLE_ITEM_TYPES


def get_normalized_market_snapshots(
    *,
    limit: int = 20,
    listing_hours: int = 24,
    sales_days: int = 7,
    scope: str = "full",
) -> list[dict[str, Any]]:
    listing_window_hours = max(1, min(24 * 30, int(listing_hours)))
    sales_window_days = max(1, min(90, int(sales_days)))
    scope_name = str(scope or "full").strip().lower()
    if scope_name not in {"full", "tradable"}:
        scope_name = "full"
    tradable_only = scope_name == "tradable"
    listing_cutoff = (datetime.now(timezone.utc) - timedelta(hours=listing_window_hours)).isoformat()
    sales_cutoff = (datetime.now(timezone.utc) - timedelta(days=sales_window_days)).isoformat()

    with get_conn() as conn:
        stale_listing_rows = conn.execute(
            """
            SELECT id
            FROM listings_raw
            WHERE status = 'open' AND (normalization_version = '' OR normalization_version IS NULL)
            ORDER BY id DESC
            LIMIT 500
            """
        ).fetchall()
        stale_sale_rows = conn.execute(
            """
            SELECT id
            FROM sales_raw
            WHERE normalization_version = '' OR normalization_version IS NULL
            ORDER BY id DESC
            LIMIT 500
            """
        ).fetchall()

    if stale_listing_rows:
        _backfill_listing_normalization([int(row["id"]) for row in stale_listing_rows])
    if stale_sale_rows:
        _backfill_sale_normalization([int(row["id"]) for row in stale_sale_rows])

    with get_conn() as conn:
        listing_rows = conn.execute(
            """
            SELECT normalized_key, normalized_title, item_type, list_price, listed_at, normalization_blocked, normalization_confidence, seller_id
            FROM listings_raw
            WHERE status = 'open' AND listed_at >= ?
            ORDER BY listed_at DESC
            """,
            (listing_cutoff,),
        ).fetchall()
        sale_rows = conn.execute(
            """
            SELECT normalized_key, normalized_title, item_type, sold_price, sold_at, normalization_confidence
            FROM sales_raw
            WHERE sold_at >= ?
            ORDER BY sold_at DESC
            """,
            (sales_cutoff,),
        ).fetchall()

    grouped: dict[str, dict[str, Any]] = {}

    for row in listing_rows:
        normalized_key = str(row["normalized_key"] or "").strip()
        if not normalized_key:
            continue
        bucket = grouped.setdefault(
            normalized_key,
            {
                "normalized_key": normalized_key,
                "normalized_title": str(row["normalized_title"] or ""),
                "item_type": str(row["item_type"] or "unknown"),
                "listing_prices": [],
                "listing_seller_ids": set(),
                "noise_listing_count": 0,
                "open_listing_count": 0,
                "latest_list_price": 0.0,
                "sample_confidence_sum": 0.0,
                "sample_confidence_count": 0,
            },
        )
        bucket["open_listing_count"] += 1
        bucket["listing_prices"].append(float(row["list_price"] or 0.0))
        seller_id = str(row["seller_id"] or "").strip()
        if seller_id:
            bucket["listing_seller_ids"].add(seller_id)
        if bool(row["normalization_blocked"]):
            bucket["noise_listing_count"] += 1
        if bucket["latest_list_price"] == 0.0:
            bucket["latest_list_price"] = float(row["list_price"] or 0.0)
        bucket["sample_confidence_sum"] += float(row["normalization_confidence"] or 0.0)
        bucket["sample_confidence_count"] += 1

    for row in sale_rows:
        normalized_key = str(row["normalized_key"] or "").strip()
        if not normalized_key:
            continue
        bucket = grouped.setdefault(
            normalized_key,
            {
                "normalized_key": normalized_key,
                "normalized_title": str(row["normalized_title"] or ""),
                "item_type": str(row["item_type"] or "unknown"),
                "listing_prices": [],
                "listing_seller_ids": set(),
                "noise_listing_count": 0,
                "open_listing_count": 0,
                "latest_list_price": 0.0,
                "sample_confidence_sum": 0.0,
                "sample_confidence_count": 0,
            },
        )
        bucket.setdefault("sold_prices", []).append(float(row["sold_price"] or 0.0))
        bucket["sample_confidence_sum"] += float(row["normalization_confidence"] or 0.0)
        bucket["sample_confidence_count"] += 1

    snapshots: list[dict[str, Any]] = []
    for bucket in grouped.values():
        listing_prices = [price for price in bucket.get("listing_prices", []) if price > 0]
        sold_prices = [price for price in bucket.get("sold_prices", []) if price > 0]
        if not listing_prices and not sold_prices:
            continue
        median_list_price = _median(listing_prices)
        median_sold_price = _median(sold_prices)
        latest_list_price = float(bucket.get("latest_list_price") or 0.0)
        spread_ratio = (
            (max(listing_prices) - min(listing_prices)) / max(median_list_price, 0.01)
            if len(listing_prices) >= 2 else 0.0
        )
        price_gap_vs_sales = (
            (median_list_price - median_sold_price) / max(median_sold_price, 0.01)
            if median_sold_price > 0 else 0.0
        )
        sample_confidence = (
            float(bucket["sample_confidence_sum"]) / float(bucket["sample_confidence_count"])
            if bucket["sample_confidence_count"] else 0.0
        )
        is_tradable = _normalized_market_snapshot_is_tradable(str(bucket["item_type"] or ""))
        if tradable_only and not is_tradable:
            continue
        regime_tag = _normalized_market_regime_tag(
            open_listing_count=int(bucket["open_listing_count"]),
            recent_sales_count=len(sold_prices),
            noise_listing_count=int(bucket["noise_listing_count"]),
            spread_ratio=float(spread_ratio),
            price_gap_vs_sales=float(price_gap_vs_sales),
        )
        summary = (
            f"{bucket['normalized_title'] or bucket['normalized_key']} | "
            f"open {int(bucket['open_listing_count'])} | "
            f"sales7d {len(sold_prices)} | "
            f"list median {median_list_price:.2f} | "
            f"sold median {median_sold_price:.2f} | "
            f"regime {regime_tag}"
        )
        snapshots.append(
            {
                "normalized_key": bucket["normalized_key"],
                "normalized_title": bucket["normalized_title"],
                "item_type": bucket["item_type"],
                "snapshot_scope": scope_name,
                "open_listing_count": int(bucket["open_listing_count"]),
                "recent_listing_count_24h": int(bucket["open_listing_count"]),
                "recent_sales_count_7d": len(sold_prices),
                "min_list_price": round(min(listing_prices), 2) if listing_prices else 0.0,
                "p25_list_price": round(_percentile(listing_prices, 0.25), 2) if listing_prices else 0.0,
                "median_list_price": round(median_list_price, 2),
                "max_list_price": round(max(listing_prices), 2) if listing_prices else 0.0,
                "latest_list_price": round(latest_list_price, 2),
                "median_sold_price_7d": round(median_sold_price, 2),
                "price_gap_vs_sales": round(price_gap_vs_sales, 4),
                "spread_ratio": round(spread_ratio, 4),
                "seller_count": len(bucket["listing_seller_ids"]),
                "noise_listing_count": int(bucket["noise_listing_count"]),
                "sample_confidence": round(sample_confidence, 4),
                "is_tradable": is_tradable,
                "regime_tag": regime_tag,
                "summary_text": summary,
            }
        )

    snapshots.sort(
        key=lambda item: (
            int(item["open_listing_count"]) + int(item["recent_sales_count_7d"]),
            float(item["sample_confidence"]),
            str(item["normalized_key"]),
        ),
        reverse=True,
    )
    return snapshots[: max(1, min(200, int(limit)))]


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
    created_at = _parse_db_timestamp(row["created_at"])
    holding_days = (
        max(0.0, (sold_at - created_at).total_seconds() / 86400.0)
        if created_at is not None
        else 0.0
    )

    return {
        "sold_at": sold_at,
        "approved_buy_price": approved_buy_price,
        "sold_price": sold_price,
        "gross_profit": gross_profit,
        "net_profit": net_profit,
        "roi": roi,
        "holding_days": holding_days,
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


def _build_source_execution_snapshot(rows: list[sqlite3.Row]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        source = str(row["listing_source"] or "unknown").strip() or "unknown"
        bucket = grouped.setdefault(
            source,
            {
                "execution_live_sample_size": 0,
                "execution_live_success_count": 0,
                "execution_live_failure_count": 0,
                "execution_live_business_ban_count": 0,
                "execution_live_last_failure_at": "",
                "by_action": {},
            },
        )
        action = str(row["action"] or "unknown").strip().lower() or "unknown"
        action_bucket = bucket["by_action"].setdefault(
            action,
            {
                "sample_size": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "business_ban_count": 0,
                "last_failure_at": "",
                "positive_streak": 0,
                "_history": [],
            },
        )
        bucket["execution_live_sample_size"] += 1
        action_bucket["sample_size"] += 1
        success = bool(row["success"])
        action_bucket["_history"].append((str(row["created_at"] or ""), success))
        if success:
            bucket["execution_live_success_count"] += 1
            action_bucket["success_count"] += 1
        else:
            bucket["execution_live_failure_count"] += 1
            action_bucket["failure_count"] += 1
            if not bucket["execution_live_last_failure_at"]:
                bucket["execution_live_last_failure_at"] = str(row["created_at"] or "")
            if not action_bucket["last_failure_at"]:
                action_bucket["last_failure_at"] = str(row["created_at"] or "")

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
            bucket["execution_live_business_ban_count"] += 1
            action_bucket["business_ban_count"] += 1

    for bucket in grouped.values():
        sample_size = int(bucket["execution_live_sample_size"] or 0)
        success_count = int(bucket["execution_live_success_count"] or 0)
        failure_count = int(bucket["execution_live_failure_count"] or 0)
        bucket["execution_live_success_rate"] = round(
            (success_count / sample_size) if sample_size else 0.0,
            4,
        )
        bucket["execution_live_failure_rate"] = round(
            (failure_count / sample_size) if sample_size else 0.0,
            4,
        )
        for action_bucket in bucket["by_action"].values():
            action_sample_size = int(action_bucket["sample_size"] or 0)
            action_success_count = int(action_bucket["success_count"] or 0)
            action_failure_count = int(action_bucket["failure_count"] or 0)
            positive_streak = 0
            for _, was_success in sorted(
                list(action_bucket.get("_history") or []),
                key=lambda item: item[0],
                reverse=True,
            ):
                if was_success:
                    positive_streak += 1
                    continue
                break
            action_bucket["success_rate"] = round(
                (action_success_count / action_sample_size) if action_sample_size else 0.0,
                4,
            )
            action_bucket["failure_rate"] = round(
                (action_failure_count / action_sample_size) if action_sample_size else 0.0,
                4,
            )
            action_bucket["positive_streak"] = positive_streak
            action_bucket.pop("_history", None)
    return grouped


def _execution_health_state(summary: dict[str, Any] | None) -> str:
    summary = summary or {}
    sample_size = int(summary.get("sample_size") or 0)
    if sample_size < int(settings.operating_state_min_execution_samples):
        return "normal"
    failure_rate = float(summary.get("failure_rate") or 0.0)
    business_ban_count = int(summary.get("business_ban_count") or 0)
    if (
        failure_rate >= float(settings.operating_state_recovery_failure_rate)
        or business_ban_count >= int(settings.operating_state_recovery_business_bans)
    ):
        return "recovery"
    if (
        failure_rate >= float(settings.operating_state_cautious_failure_rate)
        or business_ban_count >= int(settings.operating_state_cautious_business_bans)
    ):
        return "cautious"
    return "normal"


def _action_lane_from_execution_state(state: str) -> str:
    normalized = str(state or "").strip().lower()
    if normalized == "recovery":
        return "blocked"
    if normalized == "cautious":
        return "reduced"
    return "open"


def _build_source_profit_snapshot(
    rows: list[sqlite3.Row],
    *,
    since: datetime | None = None,
    execution_by_source: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    execution_by_source = execution_by_source or {}
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
                "holding_days_values": [],
            },
        )
        bucket["sold_count"] += 1
        if float(details["net_profit"]) > 0:
            bucket["profitable_sold_count"] += 1
        bucket["realized_net_profit"] += float(details["net_profit"])
        bucket["avg_realized_roi_values"].append(float(details["roi"]))
        bucket["holding_days_values"].append(float(details["holding_days"] or 0.0))

    items: list[dict[str, Any]] = []
    for bucket in grouped.values():
        sold_count = int(bucket["sold_count"])
        profitable_sold_count = int(bucket["profitable_sold_count"])
        roi_values = list(bucket["avg_realized_roi_values"])
        holding_days_values = list(bucket["holding_days_values"])
        realized_net_profit = round(float(bucket["realized_net_profit"]), 2)
        profit_hit_rate = round(
            (profitable_sold_count / sold_count) if sold_count else 0.0,
            4,
        )
        avg_realized_roi = round(
            (sum(roi_values) / len(roi_values)) if roi_values else 0.0,
            4,
        )
        avg_holding_days = round(
            (sum(holding_days_values) / len(holding_days_values)) if holding_days_values else 0.0,
            2,
        )
        median_holding_days = round(_median(holding_days_values), 2)
        strategy_mode = "hold"
        strategy_summary = "Insufficient edge to change source weighting."
        threshold_delta = {
            "min_score": 0.0,
            "min_roi": 0.0,
            "max_risk_score": 0.0,
        }
        intake_multiplier = 1.0
        capital_multiplier = 1.0

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
            capital_multiplier = 0.7
        elif realized_net_profit > 0 and profit_hit_rate >= 0.65 and avg_realized_roi >= 0.08:
            strategy_mode = "widen"
            strategy_summary = "Recent source quality is healthy. Widen the funnel slightly."
            threshold_delta = {
                "min_score": -2.0,
                "min_roi": -0.005,
                "max_risk_score": 2.0,
            }
            intake_multiplier = 1.15
            capital_multiplier = 1.15

        execution = execution_by_source.get(str(bucket["source"]), {})
        execution_sample_size = int(execution.get("execution_live_sample_size") or 0)
        execution_success_count = int(execution.get("execution_live_success_count") or 0)
        execution_failure_count = int(execution.get("execution_live_failure_count") or 0)
        execution_business_ban_count = int(execution.get("execution_live_business_ban_count") or 0)
        execution_success_rate = float(execution.get("execution_live_success_rate") or 0.0)
        execution_failure_rate = float(execution.get("execution_live_failure_rate") or 0.0)
        execution_last_failure_at = str(execution.get("execution_live_last_failure_at") or "")
        execution_by_action = dict(execution.get("by_action") or {})
        buy_execution = dict(execution_by_action.get("buy") or {})
        list_execution = dict(execution_by_action.get("list") or {})
        sell_execution = dict(execution_by_action.get("sell") or {})
        buy_execution_state = _execution_health_state(buy_execution)
        list_execution_state = _execution_health_state(list_execution)
        sell_execution_state = _execution_health_state(sell_execution)
        exit_execution_state = "recovery" if "recovery" in {list_execution_state, sell_execution_state} else (
            "cautious" if "cautious" in {list_execution_state, sell_execution_state} else "normal"
        )
        buy_positive_streak = int(buy_execution.get("positive_streak") or 0)
        list_positive_streak = int(list_execution.get("positive_streak") or 0)
        sell_positive_streak = int(sell_execution.get("positive_streak") or 0)
        source_release_streak = max(1, int(settings.auto_approve_source_observe_release_streak))
        source_recovery_progress = min(1.0, buy_positive_streak / float(source_release_streak))
        source_observe_base_multiplier = max(
            0.05,
            min(0.6, float(settings.auto_approve_source_observe_base_multiplier)),
        )
        source_observe_multiplier = round(
            source_observe_base_multiplier
            + ((0.6 - source_observe_base_multiplier) * source_recovery_progress),
            2,
        )
        recovery_profit_validated = (
            sold_count >= 2
            and realized_net_profit > 0
            and profit_hit_rate >= 0.65
            and avg_realized_roi >= 0.08
        )
        cashout_quality_validated = (
            recovery_profit_validated
            and avg_holding_days > 0
            and avg_holding_days <= float(settings.auto_approve_source_cashout_max_holding_days)
        )
        source_lane = "open"
        block_new_approvals = False
        list_action_lane = "open"
        sell_action_lane = "open"

        if execution_sample_size >= int(settings.operating_state_min_execution_samples):
            if (
                execution_failure_rate >= float(settings.operating_state_recovery_failure_rate)
                or execution_business_ban_count >= int(settings.operating_state_recovery_business_bans)
            ):
                strategy_mode = "tighten"
                strategy_summary = "Live execution quality is degraded. Tighten source intake."
                threshold_delta = {
                    "min_score": max(float(threshold_delta["min_score"]), 6.0),
                    "min_roi": max(float(threshold_delta["min_roi"]), 0.03),
                    "max_risk_score": min(float(threshold_delta["max_risk_score"]), -6.0),
                }
                intake_multiplier = min(float(intake_multiplier), 0.35)
                capital_multiplier = min(float(capital_multiplier), 0.35)
            elif (
                execution_failure_rate >= float(settings.operating_state_cautious_failure_rate)
                or execution_business_ban_count >= int(settings.operating_state_cautious_business_bans)
            ):
                strategy_mode = "tighten"
                strategy_summary = "Live execution quality is unstable. Reduce source intake."
                threshold_delta = {
                    "min_score": max(float(threshold_delta["min_score"]), 4.0),
                    "min_roi": max(float(threshold_delta["min_roi"]), 0.02),
                    "max_risk_score": min(float(threshold_delta["max_risk_score"]), -4.0),
                }
                intake_multiplier = min(float(intake_multiplier), 0.6)
                capital_multiplier = min(float(capital_multiplier), 0.7)

        if buy_execution_state == "recovery":
            if buy_positive_streak > 0:
                source_lane = "observe"
                strategy_mode = "tighten"
                strategy_summary = "Live buy execution is recovering. Re-enable with small flow."
                threshold_delta = {
                    "min_score": max(float(threshold_delta["min_score"]), 6.0),
                    "min_roi": max(float(threshold_delta["min_roi"]), 0.03),
                    "max_risk_score": min(float(threshold_delta["max_risk_score"]), -6.0),
                }
                intake_multiplier = min(float(intake_multiplier), source_observe_multiplier)
                capital_multiplier = min(float(capital_multiplier), max(0.5, source_observe_multiplier))
            else:
                source_lane = "blocked"
                block_new_approvals = True
                strategy_mode = "tighten"
                strategy_summary = "Live buy execution is degraded. Block new approvals for this source."
                threshold_delta = {
                    "min_score": max(float(threshold_delta["min_score"]), 8.0),
                    "min_roi": max(float(threshold_delta["min_roi"]), 0.05),
                    "max_risk_score": min(float(threshold_delta["max_risk_score"]), -8.0),
                }
                intake_multiplier = 0.0
                capital_multiplier = 0.0
        elif buy_execution_state == "cautious":
            source_lane = "observe"
            strategy_mode = "tighten"
            strategy_summary = "Live buy execution is unstable. Keep source in observe mode."
            threshold_delta = {
                "min_score": max(float(threshold_delta["min_score"]), 6.0),
                "min_roi": max(float(threshold_delta["min_roi"]), 0.03),
                "max_risk_score": min(float(threshold_delta["max_risk_score"]), -6.0),
            }
            intake_multiplier = min(float(intake_multiplier), max(0.35, source_observe_multiplier))
            capital_multiplier = min(float(capital_multiplier), 0.6)
        elif buy_positive_streak > 0:
            if buy_positive_streak >= source_release_streak and recovery_profit_validated:
                source_lane = "expand"
                strategy_mode = "widen"
                strategy_summary = "Live buy execution recovered and realized ROI validated. Restore source capacity."
                threshold_delta = {
                    "min_score": min(float(threshold_delta["min_score"]), 0.0),
                    "min_roi": min(float(threshold_delta["min_roi"]), 0.0),
                    "max_risk_score": max(float(threshold_delta["max_risk_score"]), 0.0),
                }
                intake_multiplier = max(float(intake_multiplier), 1.0)
                capital_multiplier = max(float(capital_multiplier), 1.2)
            else:
                source_lane = "observe"
                strategy_mode = "tighten"
                strategy_summary = "Live buy execution recovered, but realized ROI is not yet validated. Keep source in observe mode."
                threshold_delta = {
                    "min_score": max(float(threshold_delta["min_score"]), 3.0),
                    "min_roi": max(float(threshold_delta["min_roi"]), 0.015),
                    "max_risk_score": min(float(threshold_delta["max_risk_score"]), -3.0),
                }
                intake_multiplier = min(float(intake_multiplier), max(0.35, source_observe_multiplier))
                capital_multiplier = min(float(capital_multiplier), 0.75)
        elif exit_execution_state == "recovery":
            source_lane = "reduced"
            strategy_mode = "tighten"
            strategy_summary = "Exit execution is degraded. Reduce new exposure for this source."
            threshold_delta = {
                "min_score": max(float(threshold_delta["min_score"]), 5.0),
                "min_roi": max(float(threshold_delta["min_roi"]), 0.025),
                "max_risk_score": min(float(threshold_delta["max_risk_score"]), -5.0),
            }
            intake_multiplier = min(float(intake_multiplier), 0.5)
            capital_multiplier = min(float(capital_multiplier), 0.55)
        elif exit_execution_state == "cautious":
            source_lane = "reduced"
            strategy_mode = "tighten"
            strategy_summary = "Exit execution is unstable. Trim intake for this source."
            threshold_delta = {
                "min_score": max(float(threshold_delta["min_score"]), 4.0),
                "min_roi": max(float(threshold_delta["min_roi"]), 0.02),
                "max_risk_score": min(float(threshold_delta["max_risk_score"]), -4.0),
            }
            intake_multiplier = min(float(intake_multiplier), 0.7)
            capital_multiplier = min(float(capital_multiplier), 0.8)

        if list_execution_state == "recovery":
            list_action_lane = "observe" if list_positive_streak > 0 else "blocked"
        elif list_execution_state == "cautious":
            list_action_lane = "observe"
        elif list_positive_streak >= source_release_streak and cashout_quality_validated:
            list_action_lane = "expand"
        elif list_positive_streak > 0:
            list_action_lane = "observe"

        if sell_execution_state == "recovery":
            sell_action_lane = "observe" if sell_positive_streak > 0 else "blocked"
        elif sell_execution_state == "cautious":
            sell_action_lane = "observe"
        elif sell_positive_streak >= source_release_streak and cashout_quality_validated:
            sell_action_lane = "expand"
        elif sell_positive_streak > 0:
            sell_action_lane = "observe"

        if list_action_lane == "blocked" or sell_action_lane == "blocked":
            capital_multiplier = min(float(capital_multiplier), 0.5)
        elif list_action_lane in {"observe", "reduced"} or sell_action_lane in {"observe", "reduced"}:
            capital_multiplier = min(float(capital_multiplier), 0.8)
        elif (
            cashout_quality_validated
            and "expand" in {list_action_lane, sell_action_lane}
        ):
            capital_multiplier = max(float(capital_multiplier), 1.3)
        elif (
            source_lane == "expand"
            and list_action_lane == "expand"
            and sell_action_lane == "expand"
            and cashout_quality_validated
        ):
            capital_multiplier = max(float(capital_multiplier), 1.4)

        items.append(
            {
                "source": str(bucket["source"]),
                "sold_count": sold_count,
                "profitable_sold_count": profitable_sold_count,
                "realized_net_profit": realized_net_profit,
                "profit_hit_rate": profit_hit_rate,
                "avg_realized_roi": avg_realized_roi,
                "avg_holding_days": avg_holding_days,
                "median_holding_days": median_holding_days,
                "strategy_mode": strategy_mode,
                "strategy_summary": strategy_summary,
                "threshold_delta": threshold_delta,
                "intake_multiplier": intake_multiplier,
                "capital_multiplier": round(capital_multiplier, 2),
                "source_lane": source_lane,
                "block_new_approvals": block_new_approvals,
                "list_action_lane": list_action_lane,
                "sell_action_lane": sell_action_lane,
                "allow_auto_list": list_action_lane != "blocked",
                "allow_auto_sell": sell_action_lane != "blocked",
                "recovery_profit_validated": recovery_profit_validated,
                "cashout_quality_validated": cashout_quality_validated,
                "execution_live_sample_size": execution_sample_size,
                "execution_live_success_count": execution_success_count,
                "execution_live_failure_count": execution_failure_count,
                "execution_live_success_rate": round(execution_success_rate, 4),
                "execution_live_failure_rate": round(execution_failure_rate, 4),
                "execution_live_business_ban_count": execution_business_ban_count,
                "execution_live_last_failure_at": execution_last_failure_at,
                "execution_buy_state": buy_execution_state,
                "execution_list_state": list_execution_state,
                "execution_sell_state": sell_execution_state,
                "buy_positive_streak": buy_positive_streak,
                "list_positive_streak": list_positive_streak,
                "sell_positive_streak": sell_positive_streak,
                "source_release_streak": source_release_streak,
                "source_recovery_progress": round(source_recovery_progress, 4),
                "execution_by_action": execution_by_action,
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
            """
            SELECT COUNT(*) AS c
            FROM opportunities o
            JOIN listings_raw l ON l.id = o.listing_row_id
            WHERE o.status = 'pending_review'
              AND COALESCE(l.source, '') != 'simulation_seed'
            """
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
            WHERE COALESCE(l.source, '') != 'simulation_seed'
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
        execution_rows_7d = conn.execute(
            """
            SELECT
                e.*,
                l.source AS listing_source
            FROM execution_logs e
            JOIN trades t ON t.id = e.trade_id
            JOIN opportunities o ON o.id = t.opportunity_id
            JOIN listings_raw l ON l.id = o.listing_row_id
            WHERE e.created_at >= ? AND e.dry_run = 0
              AND COALESCE(l.source, '') != 'simulation_seed'
            ORDER BY e.id DESC
            """,
            (last_7d_start.isoformat(),),
        ).fetchall()
        source_execution_snapshot = _build_source_execution_snapshot(execution_rows_7d)
        source_snapshot = _build_source_profit_snapshot(
            trade_rows,
            since=last_7d_start,
            execution_by_source=source_execution_snapshot,
        )
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
            "source_execution_live_7d": list(source_execution_snapshot.values())[:5],
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
    SELECT e.*, t.status AS trade_status, t.approved_buy_price, t.target_sell_price, l.source AS listing_source
    FROM execution_logs e
    JOIN trades t ON t.id = e.trade_id
    JOIN opportunities o ON o.id = t.opportunity_id
    JOIN listings_raw l ON l.id = o.listing_row_id
    """
    params: list[Any] = ["simulation_seed"]
    where: list[str] = ["COALESCE(l.source, '') != ?"]
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


def _build_execution_log_summary(rows: list[sqlite3.Row]) -> dict[str, Any]:
    sample_size = len(rows)
    failure_count = 0
    business_ban_count = 0
    last_failure_at = ""
    by_action: dict[str, dict[str, Any]] = {}

    for row in rows:
        success = bool(row["success"])
        action = str(row["action"] or "unknown").strip().lower() or "unknown"
        action_bucket = by_action.setdefault(
            action,
            {
                "sample_size": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "business_ban_count": 0,
                "last_failure_at": "",
            },
        )
        action_bucket["sample_size"] += 1
        if not success:
            failure_count += 1
            action_bucket["failure_count"] += 1
            if not last_failure_at:
                last_failure_at = str(row["created_at"] or "")
            if not action_bucket["last_failure_at"]:
                action_bucket["last_failure_at"] = str(row["created_at"] or "")

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
            action_bucket["business_ban_count"] += 1

    success_count = sample_size - failure_count
    success_rate = (success_count / sample_size) if sample_size else 0.0
    failure_rate = (failure_count / sample_size) if sample_size else 0.0
    for bucket in by_action.values():
        action_sample_size = int(bucket["sample_size"] or 0)
        action_failure_count = int(bucket["failure_count"] or 0)
        action_success_count = action_sample_size - action_failure_count
        bucket["success_count"] = action_success_count
        bucket["success_rate"] = round(
            (action_success_count / action_sample_size) if action_sample_size else 0.0,
            4,
        )
        bucket["failure_rate"] = round(
            (action_failure_count / action_sample_size) if action_sample_size else 0.0,
            4,
        )
    return {
        "sample_size": sample_size,
        "success_count": success_count,
        "failure_count": failure_count,
        "success_rate": round(success_rate, 4),
        "failure_rate": round(failure_rate, 4),
        "business_ban_count": business_ban_count,
        "last_failure_at": last_failure_at,
        "by_action": by_action,
    }


def get_execution_log_summary(limit: int = 24, *, dry_run: bool | None = None) -> dict[str, Any]:
    try:
        rows = list_execution_logs(
            limit=max(1, min(500, int(limit))),
            dry_run=dry_run,
        )
    except sqlite3.OperationalError:
        return {
            "sample_size": 0,
            "success_count": 0,
            "failure_count": 0,
            "success_rate": 0.0,
            "failure_rate": 0.0,
            "business_ban_count": 0,
            "last_failure_at": "",
            "by_action": {},
        }
    summary = _build_execution_log_summary(rows)
    summary["dry_run_filter"] = dry_run
    return summary


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
    SELECT e.*, t.status AS trade_status, l.source AS listing_source
    FROM execution_logs e
    JOIN trades t ON t.id = e.trade_id
    JOIN opportunities o ON o.id = t.opportunity_id
    JOIN listings_raw l ON l.id = o.listing_row_id
    WHERE e.success = 0
      AND COALESCE(l.source, '') != 'simulation_seed'
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
