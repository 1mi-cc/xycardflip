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
