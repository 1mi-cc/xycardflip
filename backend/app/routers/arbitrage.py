from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from .. import repositories as repo
from ..route_guard import require_cardflip_operate
from ..route_guard import require_cardflip_view
from ..schemas import MarketplaceOfferIn
from ..services.arbitrage import build_cross_platform_arbitrage_candidates
from ..services.arbitrage import get_arbitrage_source_health

router = APIRouter(
    prefix="/arbitrage",
    tags=["arbitrage"],
    dependencies=[Depends(require_cardflip_view)],
)


def _parse_sources(raw: str | None) -> tuple[str, ...]:
    text = str(raw or "").strip()
    if not text:
        return ()
    return tuple(
        token.strip()
        for token in text.split(",")
        if token.strip()
    )


@router.get("/candidates")
def list_arbitrage_candidates(
    limit: int = Query(default=12, ge=1, le=100),
    listing_hours: int = Query(default=24 * 30, ge=1, le=24 * 30),
    min_distinct_sources: int = Query(default=2, ge=2, le=10),
    min_expected_profit: float = Query(default=0.0, ge=0.0, le=1000000.0),
    min_roi: float = Query(default=0.0, ge=0.0, le=10.0),
    sources: str | None = Query(default=None),
) -> dict:
    return build_cross_platform_arbitrage_candidates(
        limit=limit,
        listing_hours=listing_hours,
        min_distinct_sources=min_distinct_sources,
        min_expected_profit=min_expected_profit,
        min_roi=min_roi,
        include_sources=_parse_sources(sources),
    )


@router.get("/sources/health")
def arbitrage_sources_health(
    listing_hours: int = Query(default=24 * 30, ge=1, le=24 * 30),
    sources: str | None = Query(default=None),
) -> dict:
    return get_arbitrage_source_health(
        listing_hours=listing_hours,
        include_sources=_parse_sources(sources),
    )


@router.post("/offers/import", dependencies=[Depends(require_cardflip_operate)])
def import_marketplace_offers(rows: list[MarketplaceOfferIn]) -> dict:
    inserted = repo.insert_marketplace_offers(rows)
    return {"inserted": inserted}


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
