from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Literal

from .. import repositories as repo
from ..config import settings
from ..route_guard import require_cardflip_operate
from ..route_guard import require_cardflip_view
from ..services.autotrade_alerting import (
    build_alert_payload,
    dispatch_alert_email,
    list_alert_incident_timeline,
    public_cockpit_payload,
    dispatch_alert_slack,
    dispatch_alert_telegram,
    dispatch_alert_webhook,
)
from ..services.autotrade import auto_trade_service
from ..services.execution import execution_service
from ..services.operating_state import operating_state_service
from ..services.risk_overrides import risk_overrides_service
from ..services.seller_controls import seller_controls_service

router = APIRouter(
    prefix="/autotrade",
    tags=["autotrade"],
    dependencies=[Depends(require_cardflip_view)],
)


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
    alert_email_auto_enabled: bool | None = None
    alert_escalation_minutes: int | None = None
    alert_ack_timeout_minutes: int | None = None
    alert_renotify_minutes: int | None = None
    alert_email_cooldown_minutes: int | None = None
    alert_email_min_severity: Literal["info", "warning", "error"] | None = None
    alert_webhook_auto_enabled: bool | None = None
    alert_webhook_cooldown_minutes: int | None = None
    alert_webhook_min_severity: Literal["info", "warning", "error"] | None = None
    alert_slack_auto_enabled: bool | None = None
    alert_slack_cooldown_minutes: int | None = None
    alert_slack_min_severity: Literal["info", "warning", "error"] | None = None
    alert_slack_min_stage: int | None = None
    alert_telegram_auto_enabled: bool | None = None
    alert_telegram_cooldown_minutes: int | None = None
    alert_telegram_min_severity: Literal["info", "warning", "error"] | None = None
    alert_telegram_min_stage: int | None = None
    source_observe_base_multiplier: float | None = None
    source_observe_release_streak: int | None = None
    source_cashout_max_holding_days: float | None = None
    portfolio_max_deployed_capital: float | None = None
    max_source_capital_share: float | None = None
    max_cluster_batch_share: float | None = None
    max_cluster_capital_share: float | None = None


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


class SourceControlManualActionIn(BaseModel):
    source: str
    action: Literal["freeze", "observe", "normal"]
    reason: str = ""
    actor: str = "operator"
    duration_hours: int | None = None


class ClusterControlManualActionIn(BaseModel):
    risk_cluster: str
    action: Literal["freeze", "observe", "normal"]
    reason: str = ""
    actor: str = "operator"
    duration_hours: int | None = None


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


class AlertAcknowledgeIn(BaseModel):
    actor: str = "operator"


class AlertSnoozeIn(BaseModel):
    actor: str = "operator"
    minutes: int = 60
    reason: str = ""


class AlertIncidentAssignIn(BaseModel):
    actor: str = "operator"
    owner: str
    note: str = ""


class AlertIncidentNoteIn(BaseModel):
    actor: str = "operator"
    note: str


class AlertIncidentHandoffIn(BaseModel):
    actor: str = "operator"
    owner: str
    note: str = ""


class AlertIncidentResolveIn(BaseModel):
    actor: str = "operator"
    note: str = ""


class AlertIncidentPriorityIn(BaseModel):
    actor: str = "operator"
    priority: Literal["low", "normal", "high", "critical"]
    note: str = ""


@router.get("/status")
def status() -> dict:
    return auto_trade_service.status()


def _build_cockpit_payload() -> dict:
    dashboard = repo.get_dashboard_metrics()
    autotrade_status = auto_trade_service.status()
    operating_state = operating_state_service.status()
    execution_readiness = execution_service.webhook_readiness()
    alert_payload = build_alert_payload(
        enabled=bool(autotrade_status.get("enabled")),
        profit_guard=dict(autotrade_status.get("profit_guard") or {}),
        dashboard_metrics=dashboard,
        operating_state=operating_state,
        execution_readiness=execution_readiness,
        validation_baseline=dict(autotrade_status.get("validation_baseline") or {}),
    )

    return public_cockpit_payload({
        **alert_payload,
        "execution_readiness": execution_readiness,
        "operating_state": operating_state,
        "autotrade": autotrade_status,
        "source_overrides": risk_overrides_service.source_status_summary(),
        "cluster_overrides": risk_overrides_service.cluster_status_summary(),
        "profit_cockpit": dashboard.get("profit_cockpit") or {},
        "forward_validation": dashboard.get("forward_validation") or {},
    })


@router.get("/cockpit")
def cockpit() -> dict:
    return _build_cockpit_payload()


@router.post("/alerts/email", dependencies=[Depends(require_cardflip_operate)])
def send_cockpit_alert_email(force: bool = False) -> dict:
    return dispatch_alert_email(
        cockpit=_build_cockpit_payload(),
        source="operator",
        force=force,
    )


@router.post("/alerts/webhook", dependencies=[Depends(require_cardflip_operate)])
def send_cockpit_alert_webhook(force: bool = False) -> dict:
    return dispatch_alert_webhook(
        cockpit=_build_cockpit_payload(),
        source="operator",
        force=force,
    )


@router.post("/alerts/slack", dependencies=[Depends(require_cardflip_operate)])
def send_cockpit_alert_slack(force: bool = False) -> dict:
    return dispatch_alert_slack(
        cockpit=_build_cockpit_payload(),
        source="operator",
        force=force,
    )


@router.post("/alerts/telegram", dependencies=[Depends(require_cardflip_operate)])
def send_cockpit_alert_telegram(force: bool = False) -> dict:
    return dispatch_alert_telegram(
        cockpit=_build_cockpit_payload(),
        source="operator",
        force=force,
    )


@router.post("/alerts/{alert_key}/ack", dependencies=[Depends(require_cardflip_operate)])
def acknowledge_alert(alert_key: str, payload: AlertAcknowledgeIn) -> dict:
    previous_state = repo.get_alert_signal_state(alert_key)
    state = repo.acknowledge_alert_signal_state(
        alert_key=alert_key,
        actor=payload.actor,
    )
    if not state:
        raise HTTPException(status_code=404, detail="alert not found")
    event = repo.create_alert_signal_event(
        alert_key=alert_key,
        action="ack",
        actor=payload.actor,
        reason="alert acknowledged",
        previous_state=previous_state,
        next_state=state,
    )
    return {
        "ok": True,
        "state": state,
        "event": event,
        "cockpit": _build_cockpit_payload(),
    }


@router.post("/alerts/{alert_key}/snooze", dependencies=[Depends(require_cardflip_operate)])
def snooze_alert(alert_key: str, payload: AlertSnoozeIn) -> dict:
    previous_state = repo.get_alert_signal_state(alert_key)
    state = repo.snooze_alert_signal_state(
        alert_key=alert_key,
        actor=payload.actor,
        minutes=payload.minutes,
        reason=payload.reason,
    )
    if not state:
        raise HTTPException(status_code=404, detail="alert not found")
    event = repo.create_alert_signal_event(
        alert_key=alert_key,
        action="snooze",
        actor=payload.actor,
        reason=payload.reason or f"snooze {payload.minutes} minutes",
        previous_state=previous_state,
        next_state=state,
    )
    return {
        "ok": True,
        "state": state,
        "event": event,
        "cockpit": _build_cockpit_payload(),
    }


@router.post("/alerts/{alert_key}/resume", dependencies=[Depends(require_cardflip_operate)])
def resume_alert(alert_key: str, actor: str = "operator") -> dict:
    previous_state = repo.get_alert_signal_state(alert_key)
    state = repo.clear_alert_signal_operator_hold(alert_key)
    if not state:
        raise HTTPException(status_code=404, detail="alert not found")
    event = repo.create_alert_signal_event(
        alert_key=alert_key,
        action="resume",
        actor=actor,
        reason="alert resumed",
        previous_state=previous_state,
        next_state=state,
    )
    return {
        "ok": True,
        "actor": actor,
        "state": state,
        "event": event,
        "cockpit": _build_cockpit_payload(),
    }


@router.post("/alerts/{alert_key}/assign", dependencies=[Depends(require_cardflip_operate)])
def assign_alert_incident(alert_key: str, payload: AlertIncidentAssignIn) -> dict:
    previous_state = repo.get_alert_signal_state(alert_key)
    state = repo.update_alert_signal_incident_state(
        alert_key=alert_key,
        action="assign",
        actor=payload.actor,
        owner=payload.owner,
        note=payload.note,
    )
    if not state:
        raise HTTPException(status_code=404, detail="alert not found")
    event = repo.create_alert_signal_event(
        alert_key=alert_key,
        action="assign",
        actor=payload.actor,
        reason=payload.note or f"assigned to {payload.owner}",
        previous_state=previous_state,
        next_state=state,
    )
    return {"ok": True, "state": state, "event": event, "cockpit": _build_cockpit_payload()}


@router.post("/alerts/{alert_key}/note", dependencies=[Depends(require_cardflip_operate)])
def note_alert_incident(alert_key: str, payload: AlertIncidentNoteIn) -> dict:
    previous_state = repo.get_alert_signal_state(alert_key)
    state = repo.update_alert_signal_incident_state(
        alert_key=alert_key,
        action="note",
        actor=payload.actor,
        note=payload.note,
    )
    if not state:
        raise HTTPException(status_code=404, detail="alert not found")
    event = repo.create_alert_signal_event(
        alert_key=alert_key,
        action="note",
        actor=payload.actor,
        reason=payload.note or "incident note updated",
        previous_state=previous_state,
        next_state=state,
    )
    return {"ok": True, "state": state, "event": event, "cockpit": _build_cockpit_payload()}


@router.post("/alerts/{alert_key}/handoff", dependencies=[Depends(require_cardflip_operate)])
def handoff_alert_incident(alert_key: str, payload: AlertIncidentHandoffIn) -> dict:
    previous_state = repo.get_alert_signal_state(alert_key)
    state = repo.update_alert_signal_incident_state(
        alert_key=alert_key,
        action="handoff",
        actor=payload.actor,
        owner=payload.owner,
        note=payload.note,
    )
    if not state:
        raise HTTPException(status_code=404, detail="alert not found")
    event = repo.create_alert_signal_event(
        alert_key=alert_key,
        action="handoff",
        actor=payload.actor,
        reason=payload.note or f"handed off to {payload.owner}",
        previous_state=previous_state,
        next_state=state,
    )
    return {"ok": True, "state": state, "event": event, "cockpit": _build_cockpit_payload()}


@router.post("/alerts/{alert_key}/resolve", dependencies=[Depends(require_cardflip_operate)])
def resolve_alert_incident(alert_key: str, payload: AlertIncidentResolveIn) -> dict:
    previous_state = repo.get_alert_signal_state(alert_key)
    state = repo.update_alert_signal_incident_state(
        alert_key=alert_key,
        action="resolve",
        actor=payload.actor,
        note=payload.note,
    )
    if not state:
        raise HTTPException(status_code=404, detail="alert not found")
    event = repo.create_alert_signal_event(
        alert_key=alert_key,
        action="resolve",
        actor=payload.actor,
        reason=payload.note or "incident resolved",
        previous_state=previous_state,
        next_state=state,
    )
    return {"ok": True, "state": state, "event": event, "cockpit": _build_cockpit_payload()}


@router.post("/alerts/{alert_key}/priority", dependencies=[Depends(require_cardflip_operate)])
def prioritize_alert_incident(alert_key: str, payload: AlertIncidentPriorityIn) -> dict:
    previous_state = repo.get_alert_signal_state(alert_key)
    state = repo.update_alert_signal_incident_state(
        alert_key=alert_key,
        action="priority",
        actor=payload.actor,
        priority=payload.priority,
        note=payload.note,
    )
    if not state:
        raise HTTPException(status_code=404, detail="alert not found")
    event = repo.create_alert_signal_event(
        alert_key=alert_key,
        action="priority",
        actor=payload.actor,
        reason=payload.note or f"priority set to {payload.priority}",
        previous_state=previous_state,
        next_state=state,
    )
    return {"ok": True, "state": state, "event": event, "cockpit": _build_cockpit_payload()}


@router.get("/alerts/events")
def list_alert_events(
    limit: int = Query(default=50, ge=1, le=200),
    alert_key: str = Query(default=""),
) -> dict:
    normalized_key = str(alert_key or "").strip()
    if normalized_key:
        timeline = list_alert_incident_timeline(
            alert_key=normalized_key,
            limit=limit,
        )
        items = list(timeline.get("items") or [])
    else:
        items = repo.list_alert_incident_events(
            alert_key=None,
            limit=limit,
        )
    return {
        "items": items,
        "count": len(items),
    }


@router.post("/start", dependencies=[Depends(require_cardflip_operate)])
def start() -> dict:
    return auto_trade_service.start()


@router.post("/stop", dependencies=[Depends(require_cardflip_operate)])
def stop() -> dict:
    return auto_trade_service.stop()


@router.post("/run-once", dependencies=[Depends(require_cardflip_operate)])
def run_once(
    limit: int = Query(default=0, ge=0, le=500),
    force: bool = False,
) -> dict:
    return auto_trade_service.run_once(limit=limit if limit > 0 else None, force=force)


@router.post("/config", dependencies=[Depends(require_cardflip_operate)])
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
        alert_email_auto_enabled=payload.alert_email_auto_enabled,
        alert_escalation_minutes=payload.alert_escalation_minutes,
        alert_ack_timeout_minutes=payload.alert_ack_timeout_minutes,
        alert_renotify_minutes=payload.alert_renotify_minutes,
        alert_email_cooldown_minutes=payload.alert_email_cooldown_minutes,
        alert_email_min_severity=payload.alert_email_min_severity,
        alert_webhook_auto_enabled=payload.alert_webhook_auto_enabled,
        alert_webhook_cooldown_minutes=payload.alert_webhook_cooldown_minutes,
        alert_webhook_min_severity=payload.alert_webhook_min_severity,
        alert_slack_auto_enabled=payload.alert_slack_auto_enabled,
        alert_slack_cooldown_minutes=payload.alert_slack_cooldown_minutes,
        alert_slack_min_severity=payload.alert_slack_min_severity,
        alert_slack_min_stage=payload.alert_slack_min_stage,
        alert_telegram_auto_enabled=payload.alert_telegram_auto_enabled,
        alert_telegram_cooldown_minutes=payload.alert_telegram_cooldown_minutes,
        alert_telegram_min_severity=payload.alert_telegram_min_severity,
        alert_telegram_min_stage=payload.alert_telegram_min_stage,
        source_observe_base_multiplier=payload.source_observe_base_multiplier,
        source_observe_release_streak=payload.source_observe_release_streak,
        source_cashout_max_holding_days=payload.source_cashout_max_holding_days,
        portfolio_max_deployed_capital=payload.portfolio_max_deployed_capital,
        max_source_capital_share=payload.max_source_capital_share,
        max_cluster_batch_share=payload.max_cluster_batch_share,
        max_cluster_capital_share=payload.max_cluster_capital_share,
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


@router.post("/tuning/apply", dependencies=[Depends(require_cardflip_operate)])
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


@router.post("/tuning-history/{event_id}/rollback", dependencies=[Depends(require_cardflip_operate)])
def rollback_tuning_history(event_id: int, payload: AutoTradeTuningRollbackIn) -> dict:
    return auto_trade_service.rollback_tuning_event(
        event_id=event_id,
        applied_by=payload.applied_by,
        note=payload.note,
        source=payload.source,
    )


@router.post("/seller-controls/manual-action", dependencies=[Depends(require_cardflip_operate)])
def apply_seller_control_manual_action(payload: SellerControlManualActionIn) -> dict:
    return seller_controls_service.apply_manual_action(
        source=payload.source,
        seller_id=payload.seller_id,
        action=payload.action,
        reason=payload.reason,
        actor=payload.actor,
        duration_hours=payload.duration_hours,
    )


@router.post("/source-controls/manual-action", dependencies=[Depends(require_cardflip_operate)])
def apply_source_control_manual_action(payload: SourceControlManualActionIn) -> dict:
    return risk_overrides_service.apply_manual_source_action(
        source=payload.source,
        action=payload.action,
        reason=payload.reason,
        actor=payload.actor,
        duration_hours=payload.duration_hours,
    )


@router.post("/cluster-controls/manual-action", dependencies=[Depends(require_cardflip_operate)])
def apply_cluster_control_manual_action(payload: ClusterControlManualActionIn) -> dict:
    return risk_overrides_service.apply_manual_cluster_action(
        risk_cluster=payload.risk_cluster,
        action=payload.action,
        reason=payload.reason,
        actor=payload.actor,
        duration_hours=payload.duration_hours,
    )


@router.get("/source-controls/events")
def list_source_control_events(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    items = repo.list_source_control_events(limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/cluster-controls/events")
def list_cluster_control_events(limit: int = Query(default=50, ge=1, le=200)) -> dict:
    items = repo.list_cluster_control_events(limit=limit)
    return {"items": items, "count": len(items)}


@router.post("/seller-controls/batch-manual-action", dependencies=[Depends(require_cardflip_operate)])
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


@router.post("/seller-controls/presets", dependencies=[Depends(require_cardflip_operate)])
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


@router.delete("/seller-controls/presets/{preset_id}", dependencies=[Depends(require_cardflip_operate)])
def delete_seller_control_preset(preset_id: int) -> dict:
    try:
        deleted = repo.delete_seller_control_preset(preset_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {
        "deleted": deleted,
        "items": repo.list_seller_control_presets(limit=50),
    }


@router.post("/seller-controls/presets/{preset_id}/record-run", dependencies=[Depends(require_cardflip_operate)])
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
