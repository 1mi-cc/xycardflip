from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import re
from typing import Any

from ..database import get_conn


_NON_WORD_RE = re.compile(r"[^0-9a-zA-Z\u4e00-\u9fff]+")
_SPACE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class ArbitrageListing:
    row_id: int
    source: str
    listing_id: str
    title: str
    normalized_key: str
    item_type: str
    list_price: float
    listed_at: str


def _canonicalize_title(text: str) -> str:
    lowered = str(text or "").strip().lower()
    if not lowered:
        return ""
    collapsed = _NON_WORD_RE.sub(" ", lowered)
    return _SPACE_RE.sub(" ", collapsed).strip()[:120]


def _build_group_key(*, normalized_key: str, title: str, listing_id: str, row_id: int) -> str:
    normalized_text = str(normalized_key or "").strip()
    if normalized_text and not normalized_text.startswith("unknown:"):
        return normalized_text[:120]
    canonical_title = _canonicalize_title(title)
    if canonical_title:
        return f"title:{canonical_title}"
    listing_text = str(listing_id or "").strip()
    return f"listing:{listing_text}" if listing_text else f"row:{int(row_id)}"


def _load_open_listings(
    *,
    listing_hours: int,
    include_sources: tuple[str, ...] = (),
    keyword: str = "",
) -> list[ArbitrageListing]:
    source_values = [str(item or "").strip() for item in include_sources if str(item or "").strip()]
    keyword_text = str(keyword or "").strip().lower()
    listed_after = (datetime.now(timezone.utc) - timedelta(hours=max(1, int(listing_hours)))).isoformat()

    sql = """
    SELECT id, source, listing_id, title, normalized_key, item_type, list_price, listed_at
    FROM listings_raw
    WHERE status = 'open'
      AND COALESCE(source, '') != 'simulation_seed'
      AND listed_at >= ?
    """
    params: list[Any] = [listed_after]
    if source_values:
        placeholders = ",".join("?" for _ in source_values)
        sql += f" AND source IN ({placeholders})"
        params.extend(source_values)
    sql += " ORDER BY listed_at DESC LIMIT 2000"

    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    items: list[ArbitrageListing] = []
    for row in rows:
        title = str(row["title"] or "").strip()
        group_key = _build_group_key(
            normalized_key=str(row["normalized_key"] or ""),
            title=title,
            listing_id=str(row["listing_id"] or ""),
            row_id=int(row["id"]),
        )
        haystack = f"{title} {group_key} {row['source'] or ''}".lower()
        if keyword_text and keyword_text not in haystack:
            continue
        items.append(
            ArbitrageListing(
                row_id=int(row["id"]),
                source=str(row["source"] or "").strip() or "unknown",
                listing_id=str(row["listing_id"] or "").strip(),
                title=title,
                normalized_key=str(row["normalized_key"] or "").strip(),
                item_type=str(row["item_type"] or "").strip(),
                list_price=float(row["list_price"] or 0.0),
                listed_at=str(row["listed_at"] or ""),
            )
        )
    return items


def _load_marketplace_offers(
    *,
    listing_hours: int,
    include_sources: tuple[str, ...] = (),
    keyword: str = "",
) -> list[ArbitrageListing]:
    source_values = [str(item or "").strip().lower() for item in include_sources if str(item or "").strip()]
    keyword_text = str(keyword or "").strip().lower()
    listed_after = (datetime.now(timezone.utc) - timedelta(hours=max(1, int(listing_hours)))).isoformat()

    sql = """
    SELECT id, platform, offer_id, title, canonical_key, item_type, list_price, listed_at
    FROM marketplace_offers
    WHERE status = 'open'
      AND listed_at >= ?
    """
    params: list[Any] = [listed_after]
    if source_values:
        placeholders = ",".join("?" for _ in source_values)
        sql += f" AND platform IN ({placeholders})"
        params.extend(source_values)
    sql += " ORDER BY listed_at DESC LIMIT 2000"

    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    items: list[ArbitrageListing] = []
    for row in rows:
        title = str(row["title"] or "").strip()
        group_key = _build_group_key(
            normalized_key=str(row["canonical_key"] or ""),
            title=title,
            listing_id=str(row["offer_id"] or ""),
            row_id=int(row["id"]),
        )
        haystack = f"{title} {group_key} {row['platform'] or ''}".lower()
        if keyword_text and keyword_text not in haystack:
            continue
        items.append(
            ArbitrageListing(
                row_id=int(row["id"]),
                source=str(row["platform"] or "").strip() or "unknown",
                listing_id=str(row["offer_id"] or "").strip(),
                title=title,
                normalized_key=str(row["canonical_key"] or "").strip(),
                item_type=str(row["item_type"] or "").strip(),
                list_price=float(row["list_price"] or 0.0),
                listed_at=str(row["listed_at"] or ""),
            )
        )
    return items


def _group_marketplace_listings(listings: list[ArbitrageListing]) -> tuple[dict[str, list[ArbitrageListing]], dict[str, int]]:
    groups: dict[str, list[ArbitrageListing]] = defaultdict(list)
    source_counts: dict[str, int] = defaultdict(int)
    for item in listings:
        key = _build_group_key(
            normalized_key=item.normalized_key,
            title=item.title,
            listing_id=item.listing_id,
            row_id=item.row_id,
        )
        groups[key].append(item)
        source_counts[item.source] += 1
    return groups, source_counts


def _evaluate_group(
    rows: list[ArbitrageListing],
    *,
    buy_fee_rate: float,
    sell_fee_rate: float,
    shipping_cost: float,
) -> dict[str, Any] | None:
    distinct_sources = sorted({row.source for row in rows})
    if len(distinct_sources) < 2:
        return None

    sorted_rows = sorted(rows, key=lambda row: row.list_price)
    buy_row = sorted_rows[0]
    sell_row = next((row for row in reversed(sorted_rows) if row.source != buy_row.source), None)
    if sell_row is None:
        return None

    gross_spread = float(sell_row.list_price - buy_row.list_price)
    effective_buy_cost = float(buy_row.list_price * (1 + buy_fee_rate))
    effective_sell_return = float(sell_row.list_price * (1 - sell_fee_rate))
    expected_profit = float(effective_sell_return - effective_buy_cost - shipping_cost)
    roi = float(expected_profit / effective_buy_cost) if effective_buy_cost > 0 else 0.0
    reference_title = max(rows, key=lambda row: len(row.title or "")).title or buy_row.title or sell_row.title
    return {
        "reference_title": reference_title,
        "source_count": len(distinct_sources),
        "sources": distinct_sources,
        "listing_count": len(rows),
        "buy_source": buy_row.source,
        "sell_source": sell_row.source,
        "buy_price": buy_row.list_price,
        "sell_price": sell_row.list_price,
        "buy": {
            "source": buy_row.source,
            "listing_id": buy_row.listing_id,
            "title": buy_row.title,
            "list_price": buy_row.list_price,
            "listed_at": buy_row.listed_at,
        },
        "sell": {
            "source": sell_row.source,
            "listing_id": sell_row.listing_id,
            "title": sell_row.title,
            "list_price": sell_row.list_price,
            "listed_at": sell_row.listed_at,
        },
        "gross_spread": gross_spread,
        "expected_profit": expected_profit,
        "estimated_net_profit": expected_profit,
        "roi": roi,
        "estimated_roi": roi,
    }


def build_cross_platform_arbitrage_candidates(
    *,
    limit: int = 12,
    listing_hours: int = 24 * 30,
    min_distinct_sources: int = 2,
    min_expected_profit: float = 0.0,
    min_roi: float = 0.0,
    include_sources: tuple[str, ...] = (),
    keyword: str = "",
    buy_fee_rate: float = 0.0,
    sell_fee_rate: float = 0.0,
    shipping_cost: float = 0.0,
) -> dict[str, Any]:
    marketplace_listings = _load_marketplace_offers(
        listing_hours=listing_hours,
        include_sources=include_sources,
        keyword=keyword,
    )
    listings = marketplace_listings

    groups, source_counts = _group_marketplace_listings(listings)

    candidates: list[dict[str, Any]] = []
    for key, rows in groups.items():
        candidate = _evaluate_group(
            rows,
            buy_fee_rate=buy_fee_rate,
            sell_fee_rate=sell_fee_rate,
            shipping_cost=shipping_cost,
        )
        if candidate is None:
            continue
        if int(candidate["source_count"]) < max(2, int(min_distinct_sources)):
            continue
        if float(candidate["expected_profit"]) < float(min_expected_profit):
            continue
        if float(candidate["roi"]) < float(min_roi):
            continue
        candidate["arbitrage_key"] = key
        candidate["item_type"] = rows[0].item_type if rows else "unknown"
        candidates.append(candidate)

    candidates.sort(
        key=lambda item: (
            float(item["estimated_net_profit"]),
            float(item["estimated_roi"]),
            int(item["source_count"]),
        ),
        reverse=True,
    )

    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "assumptions": {
            "listing_hours": int(listing_hours),
            "min_distinct_sources": int(min_distinct_sources),
            "buy_fee_rate": float(buy_fee_rate),
            "sell_fee_rate": float(sell_fee_rate),
            "shipping_cost": float(shipping_cost),
            "min_expected_profit": float(min_expected_profit),
            "min_roi": float(min_roi),
            "include_sources": list(include_sources),
            "keyword": str(keyword or "").strip(),
            "data_mode": "marketplace_offers",
        },
        "summary": {
            "scanned_listing_count": len(listings),
            "candidate_group_count": len(groups),
            "opportunity_count": len(candidates),
            "source_count": len(source_counts),
            "best_estimated_net_profit": float(candidates[0]["estimated_net_profit"]) if candidates else 0.0,
            "best_estimated_roi": float(candidates[0]["estimated_roi"]) if candidates else 0.0,
        },
        "count": len(candidates),
        "source_distribution": [
            {"source": source, "count": count}
            for source, count in sorted(source_counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "items": candidates[: max(1, int(limit))],
    }


def build_arbitrage_matching_preview(
    *,
    limit: int = 20,
    listing_hours: int = 24 * 30,
    include_sources: tuple[str, ...] = (),
    keyword: str = "",
    buy_fee_rate: float = 0.0,
    sell_fee_rate: float = 0.0,
    shipping_cost: float = 0.0,
) -> dict[str, Any]:
    listings = _load_marketplace_offers(
        listing_hours=listing_hours,
        include_sources=include_sources,
        keyword=keyword,
    )
    groups, _source_counts = _group_marketplace_listings(listings)
    items: list[dict[str, Any]] = []
    for key, rows in groups.items():
        sorted_rows = sorted(rows, key=lambda row: (row.source, row.list_price, row.listed_at))
        distinct_sources = sorted({row.source for row in rows})
        candidate = _evaluate_group(
            rows,
            buy_fee_rate=buy_fee_rate,
            sell_fee_rate=sell_fee_rate,
            shipping_cost=shipping_cost,
        )
        if len(distinct_sources) < 2:
            status = "single_platform_only"
            reason = "Only one platform is present in this match group."
        elif candidate and float(candidate["estimated_net_profit"]) <= 0:
            status = "no_positive_spread"
            reason = "Cross-platform match exists, but the estimated net profit is not positive."
        elif candidate:
            status = "arbitrage_ready"
            reason = "Cross-platform match found with positive net spread."
        else:
            status = "grouped_no_sell_leg"
            reason = "Cross-platform match exists, but no valid sell leg was found."
        items.append(
            {
                "arbitrage_key": key,
                "reference_title": max(rows, key=lambda row: len(row.title or "")).title if rows else "",
                "status": status,
                "reason": reason,
                "source_count": len(distinct_sources),
                "sources": distinct_sources,
                "listing_count": len(rows),
                "estimated_net_profit": float(candidate["estimated_net_profit"]) if candidate else 0.0,
                "estimated_roi": float(candidate["estimated_roi"]) if candidate else 0.0,
                "offers": [
                    {
                        "source": row.source,
                        "listing_id": row.listing_id,
                        "title": row.title,
                        "item_type": row.item_type,
                        "list_price": row.list_price,
                        "listed_at": row.listed_at,
                    }
                    for row in sorted_rows
                ],
            }
        )
    items.sort(
        key=lambda item: (
            1 if item["status"] == "arbitrage_ready" else 0,
            float(item["estimated_net_profit"]),
            int(item["source_count"]),
            int(item["listing_count"]),
        ),
        reverse=True,
    )
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "count": len(items),
        "listing_hours": int(listing_hours),
        "data_mode": "marketplace_offers",
        "items": items[: max(1, int(limit))],
    }


def get_arbitrage_source_health(
    *,
    listing_hours: int = 24 * 30,
    include_sources: tuple[str, ...] = (),
) -> dict[str, Any]:
    marketplace_listings = _load_marketplace_offers(
        listing_hours=listing_hours,
        include_sources=include_sources,
    )
    listings = marketplace_listings
    grouped: dict[str, dict[str, Any]] = {}
    distinct_sources_by_group: dict[str, set[str]] = defaultdict(set)
    for item in listings:
        bucket = grouped.setdefault(
            item.source,
            {
                "source": item.source,
                "listing_count": 0,
                "distinct_group_count": 0,
                "latest_listed_at": "",
                "avg_price": 0.0,
            },
        )
        bucket["listing_count"] += 1
        bucket["latest_listed_at"] = max(str(bucket["latest_listed_at"] or ""), item.listed_at)
        bucket["avg_price"] += float(item.list_price)
        group_key = _build_group_key(
            normalized_key=item.normalized_key,
            title=item.title,
            listing_id=item.listing_id,
            row_id=item.row_id,
        )
        distinct_sources_by_group[group_key].add(item.source)

    for bucket in grouped.values():
        listing_count = max(1, int(bucket["listing_count"]))
        bucket["avg_price"] = round(float(bucket["avg_price"]) / listing_count, 2)

    distinct_groups_by_source: dict[str, set[str]] = defaultdict(set)
    for item in listings:
        key = _build_group_key(
            normalized_key=item.normalized_key,
            title=item.title,
            listing_id=item.listing_id,
            row_id=item.row_id,
        )
        distinct_groups_by_source[item.source].add(key)
    for source, keys in distinct_groups_by_source.items():
        if source in grouped:
            grouped[source]["distinct_group_count"] = len(keys)

    items = sorted(grouped.values(), key=lambda item: (-int(item["listing_count"]), str(item["source"])))
    cross_source_products = sum(1 for sources in distinct_sources_by_group.values() if len(sources) >= 2)
    return {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "listing_hours": int(listing_hours),
        "data_mode": "marketplace_offers",
        "count": len(items),
        "cross_source_products": int(cross_source_products),
        "items": items,
    }


def build_arbitrage_opportunities(
    *,
    limit: int = 20,
    window_hours: int = 48,
    keyword: str = "",
    sources: list[str] | None = None,
    min_platforms: int = 2,
    buy_fee_rate: float = 0.0,
    sell_fee_rate: float = 0.0,
    shipping_cost: float = 0.0,
    min_net_profit: float = 0.0,
    min_roi: float = 0.0,
) -> dict[str, Any]:
    return build_cross_platform_arbitrage_candidates(
        limit=limit,
        listing_hours=window_hours,
        min_distinct_sources=min_platforms,
        min_expected_profit=min_net_profit,
        min_roi=min_roi,
        include_sources=tuple(sources or ()),
        keyword=keyword,
        buy_fee_rate=buy_fee_rate,
        sell_fee_rate=sell_fee_rate,
        shipping_cost=shipping_cost,
    )
