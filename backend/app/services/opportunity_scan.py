from __future__ import annotations

from collections import defaultdict
from typing import Any

from .. import repositories as repo
from ..config import settings
from ..schemas import FeatureData
from .listing_normalizer import TRADABLE_ITEM_TYPES
from .feature_extractor import FeatureExtractor
from .opportunity import score_opportunity
from .risk_control import apply_risk_gate, assess_opportunity_risk, format_risk_note
from .seller_controls import seller_controls_service
from .valuation import estimate_valuation

_extractor = FeatureExtractor()
_MARKET_STATE_LISTING_HOURS = 24 * 30
_MARKET_STATE_SALES_DAYS = 30
_MARKET_STATE_BLOCKED_REGIMES = {"thin", "noisy"}
_MARKET_STATE_MIN_RECENT_SALES = 1


def _iter_chunks(items: list[Any], chunk_size: int) -> list[list[Any]]:
    size = max(1, int(chunk_size))
    return [items[index : index + size] for index in range(0, len(items), size)]


def _listing_item_type(row: Any) -> str:
    if isinstance(row, dict):
        item_type = str(row.get("item_type") or "").strip()
        normalized_key = str(row.get("normalized_key") or "").strip()
    else:
        item_type = str(row["item_type"] or "").strip()
        normalized_key = str(row["normalized_key"] or "").strip()
    if item_type:
        return item_type
    if ":" in normalized_key:
        return normalized_key.split(":", 1)[0].strip()
    return "unknown"


def _listing_normalized_key(row: Any) -> str:
    if isinstance(row, dict):
        return str(row.get("normalized_key") or "").strip()
    return str(row["normalized_key"] or "").strip()


def _source_scan_weights(metrics: dict[str, Any] | None) -> dict[str, float]:
    cockpit = (metrics or {}).get("profit_cockpit") or {}
    items = list(cockpit.get("source_leaderboard_7d") or [])
    weights: dict[str, float] = {}
    for item in items:
        source = str(item.get("source") or "").strip()
        if not source:
            continue
        weights[source] = max(0.2, float(item.get("intake_multiplier") or 1.0))
    return weights


def _allocate_source_scan_budget(
    listings: list[Any],
    *,
    limit: int,
    metrics: dict[str, Any] | None,
) -> tuple[list[Any], list[dict[str, Any]]]:
    requested_limit = max(1, int(limit or 1))
    source_weights = _source_scan_weights(metrics)
    grouped: dict[str, list[Any]] = defaultdict(list)
    for row in listings:
        source = str(row["source"] or "unknown").strip() or "unknown"
        grouped[source].append(row)

    sources = list(grouped.keys())
    if not sources:
        return [], []

    weights = {source: max(0.2, float(source_weights.get(source, 1.0))) for source in sources}
    total_weight = sum(weights.values()) or float(len(sources))
    quotas = {source: min(len(grouped[source]), int(requested_limit * (weights[source] / total_weight))) for source in sources}

    allocated = sum(quotas.values())
    if allocated == 0:
        first_source = max(sources, key=lambda source: weights[source])
        quotas[first_source] = min(len(grouped[first_source]), 1)
        allocated = quotas[first_source]

    remainders = sorted(
        sources,
        key=lambda source: (
            (requested_limit * (weights[source] / total_weight)) - quotas[source],
            weights[source],
            source,
        ),
        reverse=True,
    )
    while allocated < requested_limit:
        progressed = False
        for source in remainders:
            if quotas[source] >= len(grouped[source]):
                continue
            quotas[source] += 1
            allocated += 1
            progressed = True
            if allocated >= requested_limit:
                break
        if not progressed:
            break

    selected: list[Any] = []
    budget_items: list[dict[str, Any]] = []
    for source in sources:
        quota = quotas[source]
        selected.extend(grouped[source][:quota])
        budget_items.append(
            {
                "source": source,
                "weight": round(weights[source], 2),
                "quota": quota,
                "available": len(grouped[source]),
            }
        )

    if len(selected) < requested_limit:
        leftovers: list[Any] = []
        for source in sources:
            leftovers.extend(grouped[source][quotas[source]:])
        leftovers.sort(key=lambda row: str(row["listed_at"] or ""), reverse=True)
        for row in leftovers:
            if len(selected) >= requested_limit:
                break
            selected.append(row)

    budget_items.sort(key=lambda item: (item["quota"], item["weight"], item["available"]), reverse=True)
    return selected[:requested_limit], budget_items


async def scan_open_listings(limit: int = 50) -> dict[str, Any]:
    requested_limit = max(1, min(500, int(limit)))
    candidate_limit = min(500, max(requested_limit, requested_limit * 3))
    raw_open_listings = repo.get_open_listings(
        limit=candidate_limit,
        include_noise_filtered=True,
        include_simulation=False,
    )
    try:
        dashboard_metrics = repo.get_dashboard_metrics()
    except Exception:
        dashboard_metrics = {}
    seller_control_sync = seller_controls_service.sync_from_metrics(metrics=dashboard_metrics)
    noise_filtered = sum(1 for row in raw_open_listings if bool(row["normalization_blocked"]))
    candidate_listings = [row for row in raw_open_listings if not bool(row["normalization_blocked"])]
    tradable_market_map = {
        str(item.get("normalized_key") or "").strip(): item
        for item in repo.get_normalized_market_snapshots(
            limit=200,
            listing_hours=_MARKET_STATE_LISTING_HOURS,
            sales_days=_MARKET_STATE_SALES_DAYS,
            scope="tradable",
        )
    }
    open_listings, source_budget = _allocate_source_scan_budget(
        candidate_listings,
        limit=requested_limit,
        metrics=dashboard_metrics,
    )
    batch_size = max(1, min(500, int(settings.db_write_batch_size)))
    frozen_by_status = {"rejected", "approved_for_buy"}
    listing_ids = [int(row["id"]) for row in open_listings if row["id"] is not None]
    existing_status_map = repo.get_opportunity_status_map_by_listing_rows(listing_ids)
    created = 0
    ignored = 0
    blocked = 0
    failed = 0
    seller_frozen = 0
    market_quality_filtered = 0
    market_quality_reasons: dict[str, int] = {}
    for chunk in _iter_chunks(open_listings, batch_size):
        prepared_items: list[dict[str, Any]] = []
        prepared_status_counts = {"pending_review": 0, "blocked_risk": 0, "ignored": 0}

        for listing in chunk:
            try:
                listing_row_id = int(listing["id"])
                existing_status = existing_status_map.get(listing_row_id, "")
                if existing_status in frozen_by_status:
                    ignored += 1
                    continue
                if seller_controls_service.is_seller_frozen(
                    source=str(listing["source"]),
                    seller_id=listing["seller_id"],
                ):
                    seller_frozen += 1
                    ignored += 1
                    continue
                if repo.has_reject_history_for_listing_signature(
                    source=str(listing["source"]),
                    seller_id=listing["seller_id"],
                    title=str(listing["title"]),
                    exclude_listing_row_id=listing_row_id,
                ):
                    existing_opp = repo.get_opportunity_by_listing_row_id(listing_row_id)
                    if existing_opp and str(existing_opp["status"] or "") not in frozen_by_status:
                        repo.update_opportunity_status(
                            int(existing_opp["id"]),
                            "rejected",
                            "matched_reject_history_by_signature",
                        )
                    ignored += 1
                    continue
                if repo.has_frozen_opportunity_for_listing_fingerprint(
                    source=str(listing["source"]),
                    seller_id=listing["seller_id"],
                    title=str(listing["title"]),
                    list_price=float(listing["list_price"]),
                    exclude_listing_row_id=listing_row_id,
                ):
                    existing_opp = repo.get_opportunity_by_listing_row_id(listing_row_id)
                    if existing_opp and str(existing_opp["status"] or "") not in frozen_by_status:
                        repo.update_opportunity_status(
                            int(existing_opp["id"]),
                            "rejected",
                            "duplicate_fingerprint_of_frozen_opportunity",
                        )
                    ignored += 1
                    continue

                item_type = _listing_item_type(listing)
                normalized_key = _listing_normalized_key(listing)
                market_snapshot = tradable_market_map.get(normalized_key)
                market_reason = ""
                if item_type not in TRADABLE_ITEM_TYPES:
                    market_reason = "non_tradable_item_type"
                elif not normalized_key or market_snapshot is None:
                    market_reason = "missing_tradable_market_snapshot"
                elif int(market_snapshot.get("recent_sales_count_7d") or 0) < _MARKET_STATE_MIN_RECENT_SALES:
                    market_reason = "insufficient_recent_sales"
                elif str(market_snapshot.get("regime_tag") or "").strip() in _MARKET_STATE_BLOCKED_REGIMES:
                    market_reason = f"market_regime_{str(market_snapshot.get('regime_tag') or '').strip()}"
                if market_reason:
                    market_quality_filtered += 1
                    market_quality_reasons[market_reason] = market_quality_reasons.get(market_reason, 0) + 1
                    ignored += 1
                    continue

                extracted_feature: FeatureData | None = None
                extracted_by = ""
                feature_row = repo.get_features("listing", listing_row_id)
                if feature_row:
                    feature = FeatureData(
                        card_name=feature_row["card_name"],
                        rarity=feature_row["rarity"],
                        edition=feature_row["edition"],
                        card_condition=feature_row["card_condition"],
                        confidence=feature_row["confidence"],
                    )
                else:
                    extract_title = str(listing["normalized_title"] or "").strip() or str(listing["title"] or "")
                    feature, extracted_by = await _extractor.extract(extract_title, listing["description"])
                    extracted_feature = feature

                sales = repo.get_recent_sales(feature, limit=80)
                valuation = estimate_valuation(
                    listing_row_id=listing_row_id,
                    listing_price=float(listing["list_price"]),
                    features=feature,
                    comparable_prices=[float(row["sold_price"]) for row in sales],
                )

                seller_open_count = repo.get_seller_open_listing_count(
                    source=str(listing["source"]),
                    seller_id=listing["seller_id"],
                    exclude_row_id=listing_row_id,
                )
                risk = assess_opportunity_risk(
                    list_price=float(listing["list_price"]),
                    valuation=valuation,
                    seller_open_listing_count=seller_open_count,
                    listing_text=f"{listing['title']} {listing['description']}",
                )

                profit, roi, score, status = score_opportunity(
                    list_price=float(listing["list_price"]),
                    expected_sale_price=valuation.expected_sale_price,
                    risk_score=risk.score,
                )
                status = apply_risk_gate(status, risk)
                prepared_status_counts[
                    "pending_review"
                    if status == "pending_review"
                    else "blocked_risk"
                    if status == "blocked_risk"
                    else "ignored"
                ] += 1
                prepared_items.append(
                    {
                        "listing_row_id": listing_row_id,
                        "feature": extracted_feature,
                        "extracted_by": extracted_by,
                        "valuation": valuation,
                        "expected_profit": profit,
                        "roi": roi,
                        "score": score,
                        "status": status,
                        "note": format_risk_note(risk),
                    }
                )
            except Exception:
                failed += 1
                ignored += 1

        if not prepared_items:
            continue

        try:
            repo.persist_scan_batch(prepared_items)
        except Exception:
            failed += len(prepared_items)
            ignored += len(prepared_items)
            continue

        created += prepared_status_counts["pending_review"]
        blocked += prepared_status_counts["blocked_risk"]
        ignored += prepared_status_counts["ignored"]

    return {
        "requested_limit": requested_limit,
        "candidate_pool_size": len(raw_open_listings),
        "processed": len(open_listings),
        "noise_filtered": noise_filtered,
        "pending_review": created,
        "blocked_risk": blocked,
        "ignored": ignored,
        "failed": failed,
        "seller_frozen": seller_frozen,
        "market_quality_filtered": market_quality_filtered,
        "market_quality_reasons": market_quality_reasons,
        "source_budget": source_budget,
        "seller_controls": seller_control_sync.get("status") or {},
    }
