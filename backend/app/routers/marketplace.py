from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import repositories as repo
from ..route_guard import require_cardflip_operate
from ..route_guard import require_cardflip_view
from ..schemas import MarketplaceOfferIn
from ..services.arbitrage import get_arbitrage_source_health
from ..services.marketplace_jd import jd_open_client
from ..services.marketplace_jd import normalize_jd_snapshot
from ..services.marketplace_pinduoduo import normalize_pinduoduo_snapshot
from ..services.marketplace_pinduoduo import pinduoduo_open_client
from ..services.marketplace_shadow import marketplace_shadow_service
from ..services.marketplace_taobao import normalize_taobao_snapshot
from ..services.marketplace_taobao import taobao_top_client

router = APIRouter(
    prefix="/marketplace",
    tags=["marketplace"],
    dependencies=[Depends(require_cardflip_view)],
)

SHADOW_REVIEW_VERDICTS = {"", "valid_profit", "bad_match", "stale_price", "bad_baseline"}
SHADOW_OUTCOME_STATUSES = {"profitable", "unprofitable", "stale", "invalid"}


@router.post("/offers/ingest", dependencies=[Depends(require_cardflip_operate)])
def ingest_marketplace_offers(rows: list[MarketplaceOfferIn]) -> dict:
    inserted = repo.insert_marketplace_offers(rows)
    return {"inserted": inserted}


@router.post("/providers/taobao/ingest-snapshot", dependencies=[Depends(require_cardflip_operate)])
def ingest_taobao_snapshot(payload: dict) -> dict:
    rows = normalize_taobao_snapshot(payload)
    inserted = repo.insert_marketplace_offers(rows)
    return {
        "count": len(rows),
        "inserted": inserted,
        "platform": "taobao",
    }


@router.get("/providers/taobao/status")
def taobao_provider_status() -> dict:
    return taobao_top_client.status()


@router.post("/providers/taobao/sync-once", dependencies=[Depends(require_cardflip_operate)])
def taobao_sync_once(query_string: str = "") -> dict:
    result = taobao_top_client.sync_once(query_string_override=query_string)
    inserted = repo.insert_marketplace_offers(result["rows"])
    return {
        "count": int(result["count"]),
        "inserted": int(inserted),
        "platform": "taobao",
    }


@router.post("/providers/pinduoduo/ingest-snapshot", dependencies=[Depends(require_cardflip_operate)])
def ingest_pinduoduo_snapshot(payload: dict) -> dict:
    rows = normalize_pinduoduo_snapshot(payload)
    inserted = repo.insert_marketplace_offers(rows)
    return {
        "count": len(rows),
        "inserted": inserted,
        "platform": "pinduoduo",
    }


@router.get("/providers/pinduoduo/status")
def pinduoduo_provider_status() -> dict:
    return pinduoduo_open_client.status()


@router.post("/providers/pinduoduo/sync-once", dependencies=[Depends(require_cardflip_operate)])
def pinduoduo_sync_once(params_json: str = "", snapshot_url: str = "") -> dict:
    result = pinduoduo_open_client.sync_once(
        params_json_override=params_json,
        snapshot_provider_url_override=snapshot_url,
    )
    inserted = repo.insert_marketplace_offers(result["rows"])
    return {
        "count": int(result["count"]),
        "inserted": int(inserted),
        "platform": "pinduoduo",
    }


@router.post("/providers/jd/ingest-snapshot", dependencies=[Depends(require_cardflip_operate)])
def ingest_jd_snapshot(payload: dict) -> dict:
    rows = normalize_jd_snapshot(payload)
    inserted = repo.insert_marketplace_offers(rows)
    return {
        "count": len(rows),
        "inserted": inserted,
        "platform": "jd",
    }


@router.get("/providers/jd/status")
def jd_provider_status() -> dict:
    return jd_open_client.status()


@router.post("/providers/jd/sync-once", dependencies=[Depends(require_cardflip_operate)])
def jd_sync_once(param_json: str = "", snapshot_url: str = "") -> dict:
    result = jd_open_client.sync_once(
        param_json_override=param_json,
        snapshot_provider_url_override=snapshot_url,
    )
    inserted = repo.insert_marketplace_offers(result["rows"])
    return {
        "count": int(result["count"]),
        "inserted": int(inserted),
        "platform": "jd",
    }


@router.get("/offers")
def list_marketplace_offers(
    platform: str | None = None,
    status: str | None = Query(default=None, pattern="^(open|sold|closed|archived)$"),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    rows = repo.list_marketplace_offers(platform=platform, status=status, limit=limit)
    items = [
        {
            "id": int(row["id"]),
            "platform": str(row["platform"] or ""),
            "offer_id": str(row["offer_id"] or ""),
            "seller_id": str(row["seller_id"] or ""),
            "title": str(row["title"] or ""),
            "canonical_key": str(row["canonical_key"] or ""),
            "item_type": str(row["item_type"] or ""),
            "list_price": float(row["list_price"] or 0.0),
            "shipping_cost": float(row["shipping_cost"] or 0.0),
            "fee_rate": float(row["fee_rate"] or 0.0),
            "currency": str(row["currency"] or "CNY"),
            "listed_at": str(row["listed_at"] or ""),
            "status": str(row["status"] or ""),
            "listing_url": str(row["listing_url"] or ""),
        }
        for row in rows
    ]
    return {"items": items, "count": len(items)}


@router.get("/platforms/health")
def marketplace_platform_health(
    listing_hours: int = Query(default=24 * 30, ge=1, le=24 * 30),
    platforms: str | None = Query(default=None),
) -> dict:
    include_sources = tuple(
        token.strip()
        for token in str(platforms or "").split(",")
        if token.strip()
    )
    return get_arbitrage_source_health(
        listing_hours=listing_hours,
        include_sources=include_sources,
    )


@router.get("/providers/status")
def marketplace_provider_status(
    listing_hours: int = Query(default=24 * 30, ge=1, le=24 * 30),
) -> dict:
    items = repo.get_marketplace_provider_status(listing_hours=listing_hours)
    return {"items": items, "count": len(items)}


@router.get("/shadow/status")
def marketplace_shadow_status() -> dict:
    return marketplace_shadow_service.status()


@router.get("/shadow/virtual-report")
def marketplace_shadow_virtual_report(
    limit: int = Query(default=200, ge=1, le=500),
    stable_accept_count: int = Query(default=2, ge=2, le=20),
) -> dict:
    return marketplace_shadow_service.virtual_report(
        limit=limit,
        stable_accept_count=stable_accept_count,
    )


@router.post("/shadow/run-once", dependencies=[Depends(require_cardflip_operate)])
def marketplace_shadow_run_once(
    limit: int = Query(default=0, ge=0, le=100),
    force: bool = False,
    virtual_only: bool = Query(default=True),
    trigger_source: str = Query(default="operator"),
) -> dict:
    if not virtual_only:
        raise HTTPException(
            status_code=400,
            detail="marketplace shadow runs are virtual-only; virtual_only=false is disabled",
        )
    return marketplace_shadow_service.run_once(
        limit=limit if limit > 0 else None,
        trigger_source=trigger_source,
        force=force,
        virtual_only=virtual_only,
    )


@router.get("/shadow/intents")
def marketplace_shadow_intents(
    limit: int = Query(default=50, ge=1, le=500),
    decision_status: str | None = Query(default=None, pattern="^(accepted|blocked|error)$"),
) -> dict:
    items = repo.list_marketplace_shadow_intents(limit=limit, decision_status=decision_status)
    return {"items": items, "count": len(items)}


def _shadow_decision_pack(intent: dict) -> dict:
    snapshot = dict(intent.get("snapshot") or {})
    candidate = dict(snapshot.get("candidate") or {})
    decision = dict(snapshot.get("decision") or {})
    buy = dict(candidate.get("buy") or {})
    sell = dict(candidate.get("sell") or {})
    return {
        "intent_id": int(intent.get("id") or 0),
        "decision_status": str(intent.get("decision_status") or ""),
        "blocked_reason": str(intent.get("blocked_reason") or ""),
        "reviewed_at": str(intent.get("reviewed_at") or ""),
        "reviewed_by": str(intent.get("reviewed_by") or ""),
        "review_note": str(intent.get("review_note") or ""),
        "review_verdict": str(intent.get("review_verdict") or ""),
        "outcome": {
            "status": str(intent.get("outcome_status") or ""),
            "observed_buy_price": float(intent.get("observed_buy_price") or 0.0),
            "observed_sell_price": float(intent.get("observed_sell_price") or 0.0),
            "extra_cost": float(intent.get("observed_extra_cost") or 0.0),
            "observed_net_profit": float(intent.get("observed_net_profit") or 0.0),
            "observed_roi": float(intent.get("observed_roi") or 0.0),
            "note": str(intent.get("outcome_note") or ""),
            "at": str(intent.get("outcome_at") or ""),
            "by": str(intent.get("outcome_by") or ""),
        },
        "item_type": str(candidate.get("item_type") or decision.get("item_type") or ""),
        "virtual_only": bool(decision.get("virtual_only")),
        "threshold_source": str(decision.get("threshold_source") or ""),
        "min_net_profit": float(decision.get("min_net_profit") or 0.0),
        "min_roi": float(decision.get("min_roi") or 0.0),
        "min_confidence": float(decision.get("min_confidence") or 0.0),
        "confidence_score": float(intent.get("confidence_score") or 0.0),
        "estimated_net_profit": float(intent.get("estimated_net_profit") or 0.0),
        "estimated_roi": float(intent.get("estimated_roi") or 0.0),
        "buy": {
            "platform": str(buy.get("source") or intent.get("buy_platform") or ""),
            "listing_id": str(buy.get("listing_id") or intent.get("buy_listing_id") or ""),
            "title": str(buy.get("title") or ""),
            "list_price": float(buy.get("list_price") or 0.0),
            "listed_at": str(buy.get("listed_at") or ""),
        },
        "sell": {
            "platform": str(sell.get("source") or intent.get("sell_platform") or ""),
            "listing_id": str(sell.get("listing_id") or intent.get("sell_listing_id") or ""),
            "title": str(sell.get("title") or ""),
            "list_price": float(sell.get("list_price") or 0.0),
            "listed_at": str(sell.get("listed_at") or ""),
        },
    }


@router.get("/shadow/intents/{intent_id}")
def marketplace_shadow_intent_detail(intent_id: int) -> dict:
    intent = repo.get_marketplace_shadow_intent(intent_id)
    if not intent:
        raise HTTPException(status_code=404, detail="marketplace shadow intent not found")
    return {
        **intent,
        "decision_pack": _shadow_decision_pack(intent),
    }


@router.post("/shadow/intents/{intent_id}/review")
def marketplace_shadow_intent_review(
    intent_id: int,
    payload: dict | None = None,
    reviewer: dict = Depends(require_cardflip_operate),
) -> dict:
    note = str((payload or {}).get("note") or "").strip()[:500]
    verdict = str((payload or {}).get("verdict") or "").strip()
    if verdict not in SHADOW_REVIEW_VERDICTS:
        raise HTTPException(status_code=422, detail="invalid shadow review verdict")
    actor = str(reviewer.get("username") or reviewer.get("nickname") or "operator").strip()
    intent = repo.mark_marketplace_shadow_intent_reviewed(
        intent_id,
        reviewed_by=actor,
        review_note=note,
        review_verdict=verdict,
    )
    if not intent:
        raise HTTPException(status_code=404, detail="marketplace shadow intent not found")
    return {
        **intent,
        "decision_pack": _shadow_decision_pack(intent),
    }


@router.post("/shadow/intents/{intent_id}/outcome")
def marketplace_shadow_intent_outcome(
    intent_id: int,
    payload: dict,
    reviewer: dict = Depends(require_cardflip_operate),
) -> dict:
    intent = repo.get_marketplace_shadow_intent(intent_id)
    if not intent:
        raise HTTPException(status_code=404, detail="marketplace shadow intent not found")
    pack = _shadow_decision_pack(intent)
    if (
        str(intent.get("decision_status") or "") != "accepted"
        or not bool(pack.get("virtual_only"))
        or str(pack.get("item_type") or "") != "virtual_goods"
    ):
        raise HTTPException(status_code=400, detail="only accepted virtual shadow intents can record an outcome")

    outcome_status = str((payload or {}).get("outcome_status") or "").strip()
    if outcome_status not in SHADOW_OUTCOME_STATUSES:
        raise HTTPException(status_code=422, detail="invalid shadow outcome status")
    try:
        observed_buy_price = float((payload or {}).get("observed_buy_price") or 0.0)
        observed_sell_price = float((payload or {}).get("observed_sell_price") or 0.0)
        extra_cost = float((payload or {}).get("extra_cost") or 0.0)
    except (TypeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail="invalid observed outcome prices") from exc
    if observed_buy_price <= 0 or observed_sell_price <= 0 or extra_cost < 0:
        raise HTTPException(status_code=422, detail="observed prices must be positive and extra_cost must be non-negative")
    observed_net_profit = round(observed_sell_price - observed_buy_price - extra_cost, 4)
    observed_roi = round(observed_net_profit / observed_buy_price, 4)
    actor = str(reviewer.get("username") or reviewer.get("nickname") or "operator").strip()
    updated = repo.mark_marketplace_shadow_intent_outcome(
        intent_id,
        outcome_status=outcome_status,
        observed_buy_price=observed_buy_price,
        observed_sell_price=observed_sell_price,
        observed_extra_cost=extra_cost,
        observed_net_profit=observed_net_profit,
        observed_roi=observed_roi,
        outcome_by=actor,
        outcome_note=str((payload or {}).get("note") or "").strip()[:500],
    )
    if not updated:
        raise HTTPException(status_code=404, detail="marketplace shadow intent not found")
    return {
        **updated,
        "decision_pack": _shadow_decision_pack(updated),
    }


@router.get("/shadow/runs")
def marketplace_shadow_runs(
    limit: int = Query(default=20, ge=1, le=200),
) -> dict:
    items = repo.list_marketplace_shadow_runs(limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/offers/backfill", dependencies=[Depends(require_cardflip_operate)])
def backfill_marketplace_offers(
    sources: str = Query(default="xianyu_monitor"),
    limit: int = Query(default=500, ge=1, le=5000),
    listing_hours: int = Query(default=24 * 30, ge=1, le=24 * 30),
) -> dict:
    parsed_sources = tuple(
        token.strip()
        for token in str(sources or "").split(",")
        if token.strip()
    )
    inserted = repo.backfill_marketplace_offers_from_listings(
        sources=parsed_sources,
        limit=limit,
        listing_hours=listing_hours,
    )
    return {
        "inserted": inserted,
        "sources": list(parsed_sources),
        "limit": int(limit),
        "listing_hours": int(listing_hours),
    }
