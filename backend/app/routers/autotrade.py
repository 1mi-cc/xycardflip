from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..services.autotrade import auto_trade_service

router = APIRouter(prefix="/autotrade", tags=["autotrade"])


class AutoTradeConfigPatch(BaseModel):
    interval_sec: int | None = None
    batch_size: int | None = None
    min_score: float | None = None
    min_roi: float | None = None
    max_risk_score: float | None = None
    require_risk_score: bool | None = None
    auto_execute_buy_on_approve: bool | None = None
    auto_execute_buy_dry_run: bool | None = None
    auto_execute_list_on_buy_success: bool | None = None
    auto_execute_list_dry_run: bool | None = None
    auto_execute_list_discount_min_pct: float | None = None
    auto_execute_list_discount_max_pct: float | None = None
    auto_execute_sell_on_list_success: bool | None = None
    auto_execute_sell_dry_run: bool | None = None
    auto_execute_sell_price_multiplier: float | None = None


@router.get("/status")
def status() -> dict:
    return auto_trade_service.status()


@router.post("/start")
def start() -> dict:
    return auto_trade_service.start()


@router.post("/stop")
def stop() -> dict:
    return auto_trade_service.stop()


@router.post("/run-once")
def run_once(
    limit: int = Query(default=0, ge=0, le=500),
    force: bool = False,
) -> dict:
    return auto_trade_service.run_once(limit=limit if limit > 0 else None, force=force)


@router.post("/config")
def update_config(payload: AutoTradeConfigPatch) -> dict:
    return auto_trade_service.update_config(
        interval_sec=payload.interval_sec,
        batch_size=payload.batch_size,
        min_score=payload.min_score,
        min_roi=payload.min_roi,
        max_risk_score=payload.max_risk_score,
        require_risk_score=payload.require_risk_score,
        auto_execute_buy_on_approve=payload.auto_execute_buy_on_approve,
        auto_execute_buy_dry_run=payload.auto_execute_buy_dry_run,
        auto_execute_list_on_buy_success=payload.auto_execute_list_on_buy_success,
        auto_execute_list_dry_run=payload.auto_execute_list_dry_run,
        auto_execute_list_discount_min_pct=payload.auto_execute_list_discount_min_pct,
        auto_execute_list_discount_max_pct=payload.auto_execute_list_discount_max_pct,
        auto_execute_sell_on_list_success=payload.auto_execute_sell_on_list_success,
        auto_execute_sell_dry_run=payload.auto_execute_sell_dry_run,
        auto_execute_sell_price_multiplier=payload.auto_execute_sell_price_multiplier,
    )
