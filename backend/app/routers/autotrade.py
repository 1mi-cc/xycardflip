from __future__ import annotations

from fastapi import APIRouter, Query
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Literal

from .. import repositories as repo
from ..services.autotrade import auto_trade_service
from ..services.seller_controls import seller_controls_service

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
    max_consecutive_losses: int | None = None
    daily_loss_limit: float | None = None
    loss_recovery_enabled: bool | None = None
    loss_recovery_cooldown_hours: int | None = None
    tuning_auto_apply_enabled: bool | None = None
    tuning_cooldown_hours: int | None = None
    tuning_min_closed_batches: int | None = None
    tuning_latest_min_sold_count: int | None = None
    tuning_previous_min_sold_count: int | None = None


class AutoTradeTuningApplyIn(BaseModel):
    source: str = "manual_tune"
    applied_by: str = "operator"
    note: str = ""
    min_score: float | None = None
    min_roi: float | None = None
    max_risk_score: float | None = None
    require_risk_score: bool | None = None


class AutoTradeTuningRollbackIn(BaseModel):
    source: str = "rollback"
    applied_by: str = "operator"
    note: str = ""


class SellerControlManualActionIn(BaseModel):
    source: str
    seller_id: str
    action: Literal["freeze", "observe", "normal"]
    reason: str = ""
    actor: str = "operator"
    duration_hours: int | None = None


class SellerControlBatchItemIn(BaseModel):
    source: str
    seller_id: str


class SellerControlManualBatchActionIn(BaseModel):
    items: list[SellerControlBatchItemIn]
    action: Literal["freeze", "observe", "normal"]
    reason: str = ""
    actor: str = "operator"
    duration_hours: int | None = None


class SellerControlPresetUpsertIn(BaseModel):
    name: str
    base_preset: Literal["all", "manual", "losing", "observe", "frozen", "source"]
    source_filter: str = ""
    action: Literal["freeze", "observe", "normal"]
    reason: str = ""
    actor: str = "operator"
    duration_hours: int | None = None


class SellerControlPresetRunIn(BaseModel):
    action: Literal["freeze", "observe", "normal"]
    actor: str = "operator"
    reason: str = ""
    duration_hours: int | None = None
    matched_count: int = 0
    processed_count: int = 0
    matched_items: list[SellerControlBatchItemIn] = []


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
        max_consecutive_losses=payload.max_consecutive_losses,
        daily_loss_limit=payload.daily_loss_limit,
        loss_recovery_enabled=payload.loss_recovery_enabled,
        loss_recovery_cooldown_hours=payload.loss_recovery_cooldown_hours,
        tuning_auto_apply_enabled=payload.tuning_auto_apply_enabled,
        tuning_cooldown_hours=payload.tuning_cooldown_hours,
        tuning_min_closed_batches=payload.tuning_min_closed_batches,
        tuning_latest_min_sold_count=payload.tuning_latest_min_sold_count,
        tuning_previous_min_sold_count=payload.tuning_previous_min_sold_count,
    )


@router.get("/tuning-history")
def list_tuning_history(limit: int = Query(default=30, ge=1, le=200)) -> dict:
    return {
        "items": auto_trade_service.list_tuning_history(limit=limit),
        "limit": limit,
    }


@router.get("/tuning-activity")
def list_tuning_activity(limit: int = Query(default=50, ge=1, le=500)) -> dict:
    return {
        "items": auto_trade_service.list_tuning_activity(limit=limit),
        "limit": limit,
    }


@router.get("/tuning-daily-report")
def tuning_daily_report(hours: int = Query(default=24, ge=1, le=24 * 30)) -> dict:
    return auto_trade_service.tuning_daily_report(hours=hours)


@router.get("/tuning-evaluation")
def tuning_evaluation() -> dict:
    return auto_trade_service.evaluate_auto_tune()


@router.post("/tuning/apply")
def apply_tuning(payload: AutoTradeTuningApplyIn) -> dict:
    return auto_trade_service.apply_tuning(
        source=payload.source,
        applied_by=payload.applied_by,
        note=payload.note,
        min_score=payload.min_score,
        min_roi=payload.min_roi,
        max_risk_score=payload.max_risk_score,
        require_risk_score=payload.require_risk_score,
    )


@router.post("/tuning-history/{event_id}/rollback")
def rollback_tuning_history(event_id: int, payload: AutoTradeTuningRollbackIn) -> dict:
    return auto_trade_service.rollback_tuning_event(
        event_id=event_id,
        applied_by=payload.applied_by,
        note=payload.note,
        source=payload.source,
    )


@router.post("/seller-controls/manual-action")
def apply_seller_control_manual_action(payload: SellerControlManualActionIn) -> dict:
    return seller_controls_service.apply_manual_action(
        source=payload.source,
        seller_id=payload.seller_id,
        action=payload.action,
        reason=payload.reason,
        actor=payload.actor,
        duration_hours=payload.duration_hours,
    )


@router.post("/seller-controls/batch-manual-action")
def apply_seller_control_batch_manual_action(payload: SellerControlManualBatchActionIn) -> dict:
    return seller_controls_service.apply_manual_action_batch(
        items=[item.model_dump() for item in payload.items],
        action=payload.action,
        reason=payload.reason,
        actor=payload.actor,
        duration_hours=payload.duration_hours,
    )


@router.get("/seller-controls/presets")
def list_seller_control_presets(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    items = repo.list_seller_control_presets(limit=limit)
    return {
        "items": items,
        "count": len(items),
    }


@router.get("/seller-controls/presets/{preset_id}/runs")
def list_seller_control_preset_runs(preset_id: int, limit: int = Query(default=20, ge=1, le=50)) -> dict:
    preset = repo.get_seller_control_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="seller control preset not found")
    items = repo.list_seller_control_preset_runs(preset_id=preset_id, limit=limit)
    return {
        "preset": preset,
        "items": items,
        "limit": limit,
    }


@router.post("/seller-controls/presets")
def upsert_seller_control_preset(payload: SellerControlPresetUpsertIn) -> dict:
    preset = repo.upsert_seller_control_preset(
        name=payload.name,
        base_preset=payload.base_preset,
        source_filter=payload.source_filter,
        action=payload.action,
        reason=payload.reason,
        duration_hours=payload.duration_hours,
        actor=payload.actor,
    )
    return {
        "preset": preset,
        "items": repo.list_seller_control_presets(limit=50),
    }


@router.delete("/seller-controls/presets/{preset_id}")
def delete_seller_control_preset(preset_id: int) -> dict:
    try:
        deleted = repo.delete_seller_control_preset(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "deleted": deleted,
        "items": repo.list_seller_control_presets(limit=50),
    }


@router.post("/seller-controls/presets/{preset_id}/record-run")
def record_seller_control_preset_run(preset_id: int, payload: SellerControlPresetRunIn) -> dict:
    try:
        preset = repo.record_seller_control_preset_run(
            preset_id=preset_id,
            action=payload.action,
            actor=payload.actor,
            reason=payload.reason,
            duration_hours=payload.duration_hours,
            matched_count=payload.matched_count,
            processed_count=payload.processed_count,
            matched_items=[item.model_dump() for item in payload.matched_items],
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "preset": preset,
        "items": repo.list_seller_control_presets(limit=50),
    }
