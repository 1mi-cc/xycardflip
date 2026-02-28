from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.params import Query

from .. import repositories as repo
from ..schemas import ApproveTradeIn, MarkListedIn, MarkSoldIn
from ..services.pricing_strategy import build_pricing_plan

router = APIRouter(prefix="/trades", tags=["trades"])


@router.post("/approve")
def approve_trade(payload: ApproveTradeIn) -> dict:
    opp = repo.get_opportunity(payload.opportunity_id)
    if not opp:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if opp["status"] != "pending_review":
        raise HTTPException(status_code=400, detail="Opportunity is not pending review")

    target_sell = float(opp["suggested_list_price"])
    trade_id = repo.create_trade(
        opportunity_id=payload.opportunity_id,
        approved_buy_price=payload.approved_buy_price,
        target_sell_price=target_sell,
        approved_by=payload.approved_by,
        note=payload.note,
    )
    repo.update_opportunity_status(payload.opportunity_id, "approved_for_buy", payload.note)
    return {"trade_id": trade_id, "status": "approved_for_buy", "target_sell_price": target_sell}


@router.get("")
def list_trades(status: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> dict:
    rows = repo.list_trades(status=status, limit=limit)
    items = [
        {
            "trade_id": row["id"],
            "opportunity_id": row["opportunity_id"],
            "listing_row_id": row["listing_row_id"],
            "title": row["title"],
            "source_list_price": row["list_price"],
            "approved_buy_price": row["approved_buy_price"],
            "target_sell_price": row["target_sell_price"],
            "listing_url": row["listing_url"],
            "sold_price": row["sold_price"],
            "status": row["status"],
            "approved_by": row["approved_by"],
            "note": row["note"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
        for row in rows
    ]
    return {"items": items, "count": len(items)}


def _extract_title_keywords(title: str) -> list[str]:
    tokens = [t for t in re.split(r"[^a-zA-Z0-9]+", title.lower()) if len(t) >= 3]
    unique: list[str] = []
    for token in tokens:
        if token not in unique:
            unique.append(token)
        if len(unique) >= 4:
            break
    return unique


def _build_trade_pricing_payload(
    trade_id: int, mode: Literal["balanced", "fast_exit", "profit_max"]
) -> dict:
    ctx = repo.get_trade_pricing_context(trade_id)
    if not ctx:
        raise HTTPException(status_code=404, detail="Trade not found")

    keywords = _extract_title_keywords(str(ctx["title"]))
    similar_prices: list[float] = []
    picked_keyword = ""
    for kw in keywords:
        prices = repo.list_recent_sold_trade_prices_by_title_keyword(kw, limit=40)
        if prices:
            similar_prices = prices
            picked_keyword = kw
            break

    active_count = repo.count_active_trades()
    plan = build_pricing_plan(
        approved_buy_price=float(ctx["approved_buy_price"]),
        current_target_price=float(ctx["target_sell_price"]),
        expected_sale_price=float(ctx["expected_sale_price"]),
        suggested_list_price=float(ctx["suggested_list_price"]),
        ci_low=float(ctx["ci_low"]),
        ci_high=float(ctx["ci_high"]),
        trade_created_at=str(ctx["trade_created_at"]),
        similar_sold_prices=similar_prices,
        active_trade_count=active_count,
        mode=mode,
    )
    return {
        "trade_id": int(ctx["trade_id"]),
        "status": str(ctx["status"]),
        "title": str(ctx["title"]),
        "mode": mode,
        "keyword": picked_keyword,
        "active_trade_count": active_count,
        "plan": plan,
    }


@router.get("/{trade_id}/pricing-plan")
def get_trade_pricing_plan(
    trade_id: int,
    mode: Literal["balanced", "fast_exit", "profit_max"] = "balanced",
) -> dict:
    return _build_trade_pricing_payload(trade_id, mode)


@router.post("/{trade_id}/apply-pricing-plan")
def apply_trade_pricing_plan(
    trade_id: int,
    mode: Literal["balanced", "fast_exit", "profit_max"] = "balanced",
    note: str = "auto pricing plan",
) -> dict:
    payload = _build_trade_pricing_payload(trade_id, mode)
    plan = payload["plan"]
    recommended = float(plan["recommended_price"])
    action = str(plan["action"])
    if action in {"set", "raise", "lower"}:
        repo.update_trade_target_price(
            trade_id=trade_id,
            target_sell_price=recommended,
            note=f"{note}; mode={mode}; action={action}",
        )
    return {
        "trade_id": trade_id,
        "applied": action in {"set", "raise", "lower"},
        "mode": mode,
        "action": action,
        "recommended_price": recommended,
    }


@router.post("/reprice-open")
def reprice_open_trades(
    mode: Literal["balanced", "fast_exit", "profit_max"] = "balanced",
    limit: int = Query(default=100, ge=1, le=500),
    apply: bool = False,
    note: str = "batch auto pricing plan",
) -> dict:
    ids = repo.list_open_trade_ids(limit=limit)
    updated = 0
    items: list[dict] = []
    for trade_id in ids:
        payload = _build_trade_pricing_payload(trade_id, mode)
        plan = payload["plan"]
        action = str(plan["action"])
        should_update = apply and action in {"set", "raise", "lower"}
        if should_update:
            repo.update_trade_target_price(
                trade_id=trade_id,
                target_sell_price=float(plan["recommended_price"]),
                note=f"{note}; mode={mode}; action={action}",
            )
            updated += 1
        items.append(
            {
                "trade_id": trade_id,
                "title": payload["title"],
                "mode": mode,
                "keyword": payload["keyword"],
                "action": action,
                "urgency": plan["urgency"],
                "current_target_price": plan["current_target_price"],
                "recommended_price": plan["recommended_price"],
                "price_floor": plan["price_floor"],
                "price_ceiling": plan["price_ceiling"],
                "holding_days": plan["holding_days"],
                "similar_sales_count": plan["similar_sales_count"],
                "applied": should_update,
            }
        )

    return {
        "mode": mode,
        "apply": apply,
        "processed": len(ids),
        "updated": updated,
        "items": items,
    }


@router.get("/{trade_id}")
def get_trade(trade_id: int) -> dict:
    row = repo.get_trade(trade_id)
    if not row:
        raise HTTPException(status_code=404, detail="Trade not found")
    return {
        "trade_id": row["id"],
        "opportunity_id": row["opportunity_id"],
        "listing_row_id": row["listing_row_id"],
        "title": row["title"],
        "source_list_price": row["list_price"],
        "approved_buy_price": row["approved_buy_price"],
        "target_sell_price": row["target_sell_price"],
        "listing_url": row["listing_url"],
        "sold_price": row["sold_price"],
        "status": row["status"],
        "approved_by": row["approved_by"],
        "note": row["note"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


@router.post("/{trade_id}/mark-listed")
def mark_listed(trade_id: int, payload: MarkListedIn) -> dict:
    if not repo.get_trade(trade_id):
        raise HTTPException(status_code=404, detail="Trade not found")
    repo.update_trade_listed(trade_id, payload.listing_url, payload.note)
    return {"trade_id": trade_id, "status": "listed_for_sale"}


@router.post("/{trade_id}/mark-sold")
def mark_sold(trade_id: int, payload: MarkSoldIn) -> dict:
    if not repo.get_trade(trade_id):
        raise HTTPException(status_code=404, detail="Trade not found")
    repo.update_trade_sold(trade_id, payload.sold_price, payload.note)
    return {"trade_id": trade_id, "status": "sold", "sold_price": payload.sold_price}


@router.get("/metrics")
def metrics() -> dict:
    return repo.get_dashboard_metrics()


@router.get("/metrics-summary")
def metrics_summary() -> dict:
    return repo.get_dashboard_metrics()
