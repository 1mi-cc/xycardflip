from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any
from zoneinfo import ZoneInfo

from .. import repositories as repo
from ..config import settings
from .notifier import (
    alert_email_ready,
    alert_slack_ready,
    alert_telegram_ready,
    alert_webhook_channel_label,
    alert_webhook_provider,
    alert_webhook_ready,
    format_cockpit_alert_email,
    format_cockpit_alert_webhook,
    send_alert_email,
    send_alert_slack,
    send_alert_telegram,
    send_alert_webhook,
)
from .risk_overrides import risk_overrides_service

LOW_CAPITAL_ALERT_RATIO = 0.15
SEVERITY_RANK = {"info": 1, "warning": 2, "error": 3}
PRIORITY_RANK = {"low": 1, "normal": 2, "high": 3, "critical": 4}
REACTIVATION_ACTIONS = ("resume", "snooze_expired", "ack_expired")


def normalize_alert_severity(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    return value if value in SEVERITY_RANK else "warning"


def normalize_incident_priority(raw: str | None) -> str:
    value = str(raw or "").strip().lower()
    return value if value in PRIORITY_RANK else "normal"


def incident_sla_minutes(priority: str) -> int:
    normalized = normalize_incident_priority(priority)
    if normalized == "critical":
        return 15
    if normalized == "high":
        return 60
    if normalized == "normal":
        return 240
    return 720


def _parse_timestamp(raw: str | None) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _build_alert_key(alert: dict[str, Any]) -> str:
    payload = (
        f"{str(alert.get('code') or '').strip()}::"
        f"{str(alert.get('target') or '').strip()}"
    ).encode("utf-8")
    return hashlib.sha1(payload).hexdigest()


def _is_future_timestamp(raw: str | None, *, now: datetime) -> bool:
    parsed = _parse_timestamp(raw)
    return bool(parsed is not None and parsed > now)


def _incident_rota_now() -> datetime:
    return datetime.now(timezone.utc)


def _incident_rota_timezone() -> timezone | ZoneInfo:
    timezone_name = str(settings.autotrade_incident_rota_timezone or "").strip() or "UTC"
    try:
        return ZoneInfo(timezone_name)
    except Exception:
        return timezone.utc


def _weekday_token_matches(day_token: str, weekday: int) -> bool:
    normalized = str(day_token or "").strip().lower()
    if normalized in {"", "daily", "all"}:
        return True
    if normalized == "weekday":
        return weekday < 5
    if normalized == "weekend":
        return weekday >= 5
    names = {
        "mon": 0,
        "tue": 1,
        "wed": 2,
        "thu": 3,
        "fri": 4,
        "sat": 5,
        "sun": 6,
    }
    if "," in normalized:
        return any(_weekday_token_matches(part, weekday) for part in normalized.split(","))
    if "-" in normalized:
        start_token, end_token = [part.strip() for part in normalized.split("-", 1)]
        if start_token in names and end_token in names:
            start_index = names[start_token]
            end_index = names[end_token]
            if start_index <= end_index:
                return start_index <= weekday <= end_index
            return weekday >= start_index or weekday <= end_index
    return names.get(normalized) == weekday


def _hour_range_matches(start_hour: int, end_hour: int, current_hour: int) -> bool:
    if start_hour == end_hour:
        return True
    if start_hour < end_hour:
        return start_hour <= current_hour < end_hour
    return current_hour >= start_hour or current_hour < end_hour


def _owner_from_schedule(schedule: str, *, now_local: datetime) -> str:
    schedule_text = str(schedule or "").strip()
    if not schedule_text:
        return ""
    for raw_entry in schedule_text.split(";"):
        entry = str(raw_entry or "").strip()
        if not entry or "=" not in entry:
            continue
        window, owner = [part.strip() for part in entry.split("=", 1)]
        if not owner:
            continue
        day_part = "daily"
        hour_part = window
        if "@" in window:
            day_part, hour_part = [part.strip() for part in window.split("@", 1)]
        if "-" not in hour_part:
            continue
        start_text, end_text = [part.strip() for part in hour_part.split("-", 1)]
        try:
            start_hour = max(0, min(23, int(start_text)))
            end_hour = max(0, min(24, int(end_text)))
        except ValueError:
            continue
        if (
            _weekday_token_matches(day_part, now_local.weekday())
            and _hour_range_matches(start_hour, end_hour, now_local.hour)
        ):
            return owner
    return ""


def _scheduled_owner(route_key: str, *, now_local: datetime) -> str:
    mapping = {
        "default": str(settings.autotrade_incident_default_owner_schedule or "").strip(),
        "high": str(settings.autotrade_incident_high_priority_owner_schedule or "").strip(),
        "critical": str(settings.autotrade_incident_critical_priority_owner_schedule or "").strip(),
        "slack": str(settings.autotrade_incident_slack_owner_schedule or "").strip(),
        "telegram": str(settings.autotrade_incident_telegram_owner_schedule or "").strip(),
    }
    return _owner_from_schedule(mapping.get(route_key, ""), now_local=now_local)


def _static_owner(route_key: str) -> str:
    mapping = {
        "default": str(settings.autotrade_incident_default_owner or "").strip(),
        "high": str(settings.autotrade_incident_high_priority_owner or "").strip(),
        "critical": str(settings.autotrade_incident_critical_priority_owner or "").strip(),
        "slack": str(settings.autotrade_incident_slack_owner or "").strip(),
        "telegram": str(settings.autotrade_incident_telegram_owner or "").strip(),
    }
    return mapping.get(route_key, "")


def auto_routed_incident_owner(*, priority: str, delivery_lane: str) -> str:
    if not bool(settings.autotrade_incident_auto_assign_enabled):
        return ""
    now_local = _incident_rota_now().astimezone(_incident_rota_timezone())
    normalized_lane = str(delivery_lane or "").strip().lower()
    normalized_priority = normalize_incident_priority(priority)
    route_order: list[str] = []
    if normalized_priority == "critical":
        route_order.append("critical")
    if normalized_lane == "telegram":
        route_order.append("telegram")
    if normalized_lane == "slack":
        route_order.append("slack")
    if normalized_priority == "high":
        route_order.append("high")
    route_order.append("default")
    for route_key in route_order:
        owner = _scheduled_owner(route_key, now_local=now_local)
        if owner:
            return owner
    for route_key in route_order:
        owner = _static_owner(route_key)
        if owner:
            return owner
    return ""


def _delivery_timeline_stage(*, lane: str, reason: str) -> str:
    normalized_lane = str(lane or "").strip().lower()
    normalized_reason = str(reason or "").strip().lower()
    if normalized_lane == "telegram":
        return "reactivation_telegram" if normalized_reason in REACTIVATION_ACTIONS else "followup_telegram"
    if normalized_lane in {"slack", "external"}:
        if normalized_reason in REACTIVATION_ACTIONS:
            return "reactivation_slack"
        if normalized_reason == "initial_escalation":
            return "initial_slack"
        return "followup_slack"
    return "reactivation_email" if normalized_reason in REACTIVATION_ACTIONS else "initial_email"


def _build_delivery_event_metadata(
    alerts: list[dict[str, Any]],
    *,
    default_stage: str,
) -> tuple[str, list[str], dict[str, Any]]:
    delivery_stage = str(default_stage or "").strip()
    alert_keys: list[str] = []
    alert_context: dict[str, Any] = {}
    for item in alerts:
        alert_key = str(item.get("alert_key") or "").strip()
        if not alert_key:
            continue
        alert_keys.append(alert_key)
        alert_context[alert_key] = {
            "delivery_lane": str(item.get("delivery_lane") or "").strip(),
            "delivery_stage": str(item.get("delivery_stage") or "").strip(),
            "delivery_lane_reason": str(item.get("delivery_lane_reason") or "").strip(),
            "effective_severity": normalize_alert_severity(
                item.get("effective_severity") or item.get("severity"),
            ),
            "renotify_stage": int(item.get("renotify_stage") or 0),
            "reactivation_token": int(item.get("reactivation_token") or 0),
        }
    return delivery_stage, alert_keys, alert_context


def _timeline_delivery_action(event: dict[str, Any], *, alert_key: str) -> tuple[str, str]:
    channel_label = str(event.get("channel_label") or event.get("channel") or "Delivery").strip()
    channel_slug = channel_label.lower().replace(" ", "_")
    reason = str(event.get("reason") or "").strip()
    context = dict(event.get("alert_context") or {}).get(alert_key) or {}
    delivery_stage = str(event.get("delivery_stage") or context.get("delivery_stage") or "").strip()
    if bool(event.get("success")):
        return f"{channel_slug}_sent", delivery_stage or "delivery_sent"
    if reason == "cooldown_active":
        return f"{channel_slug}_cooldown", delivery_stage or "delivery_cooldown"
    if reason.startswith("no_"):
        return f"{channel_slug}_skipped", delivery_stage or "delivery_skipped"
    return f"{channel_slug}_failed", delivery_stage or "delivery_failed"


def highest_alert_severity(alerts: list[dict[str, Any]]) -> str:
    highest = "info"
    highest_rank = 0
    for item in alerts:
        severity = normalize_alert_severity(item.get("effective_severity") or item.get("severity"))
        rank = SEVERITY_RANK.get(severity, 0)
        if rank > highest_rank:
            highest = severity
            highest_rank = rank
    return highest


def alerts_meet_min_severity(
    alerts: list[dict[str, Any]],
    *,
    min_severity: str,
) -> bool:
    minimum = normalize_alert_severity(min_severity)
    threshold_rank = SEVERITY_RANK.get(minimum, 2)
    return any(
        SEVERITY_RANK.get(
            normalize_alert_severity(item.get("effective_severity") or item.get("severity")),
            0,
        ) >= threshold_rank
        for item in alerts
    )


def _channel_provider(channel: str) -> str:
    if channel == "email":
        return "smtp"
    if channel in {"slack", "telegram"}:
        return channel
    return alert_webhook_provider()


def _channel_label(channel: str) -> str:
    mapping = {"email": "Email", "slack": "Slack", "telegram": "Telegram"}
    return mapping.get(channel, alert_webhook_channel_label())


def _channel_ready(channel: str) -> bool:
    if channel == "email":
        return alert_email_ready()
    if channel == "slack":
        return alert_slack_ready()
    if channel == "telegram":
        return alert_telegram_ready()
    return alert_webhook_ready()


def _channel_cooldown_minutes(channel: str) -> int:
    if channel == "email":
        return max(1, int(settings.autotrade_alert_email_cooldown_minutes))
    if channel == "slack":
        return max(1, int(settings.autotrade_alert_slack_cooldown_minutes))
    if channel == "telegram":
        return max(1, int(settings.autotrade_alert_telegram_cooldown_minutes))
    return max(1, int(settings.autotrade_alert_webhook_cooldown_minutes))


def _channel_min_stage(channel: str) -> int:
    if channel == "slack":
        return max(1, int(settings.autotrade_alert_slack_min_stage))
    if channel == "telegram":
        return max(1, int(settings.autotrade_alert_telegram_min_stage))
    if channel == "webhook":
        return 1
    return 0


def _send_channel_notification(
    channel: str,
    *,
    subject: str = "",
    body: str = "",
    payload: dict[str, Any] | None = None,
) -> bool:
    if channel == "email":
        return send_alert_email(subject, body)
    text = str((payload or {}).get("text") or "").strip()
    if channel == "slack":
        return send_alert_slack(text)
    if channel == "telegram":
        return send_alert_telegram(text)
    return send_alert_webhook(payload or {})


def _select_channel_alerts(
    cockpit: dict[str, Any],
    *,
    channel: str,
    force: bool = False,
) -> list[dict[str, Any]]:
    all_alerts = list(cockpit.get("alerts") or [])
    selected: list[dict[str, Any]] = []
    for item in all_alerts:
        if not force and bool(item.get("operator_suppressed")):
            continue
        if force:
            selected.append(item)
            continue
        if channel == "email":
            selected.append(item)
            continue
        if channel == "slack":
            if alert_delivery_lane(item) == "slack":
                selected.append(item)
            continue
        if channel == "telegram":
            if alert_delivery_lane(item) == "telegram":
                selected.append(item)
            continue
        if channel == "webhook":
            if bool(item.get("external_escalation_ready")) or bool(item.get("escalated")):
                selected.append(item)
            continue
    return selected


def alert_delivery_lane(alert: dict[str, Any]) -> str:
    configured_lane = str(alert.get("delivery_lane") or "").strip().lower()
    if configured_lane in {"email", "slack", "telegram", "webhook"}:
        return configured_lane
    if configured_lane == "external":
        return "slack"
    latest_action = str(alert.get("last_operator_event") or "").strip().lower()
    renotify_stage = int(alert.get("renotify_stage") or 0)
    if latest_action in {"ack_expired", "snooze_expired"} or (bool(alert.get("escalated")) and renotify_stage > 0):
        return "telegram"
    incident_stage = max(0, int(alert.get("incident_stage") or 0))
    slack_min_stage = _channel_min_stage("slack")
    telegram_min_stage = max(slack_min_stage + 1, _channel_min_stage("telegram"))
    if incident_stage >= telegram_min_stage:
        return "telegram"
    if incident_stage >= slack_min_stage:
        return "slack"
    if bool(alert.get("escalated")):
        return "slack"
    return "email"


def alert_delivery_lane_reason(alert: dict[str, Any]) -> str:
    configured_reason = str(alert.get("delivery_lane_reason") or "").strip().lower()
    if configured_reason:
        return configured_reason
    latest_action = str(alert.get("last_operator_event") or "").strip().lower()
    renotify_stage = int(alert.get("renotify_stage") or 0)
    if latest_action == "resume":
        return "resume"
    if latest_action == "ack_expired":
        return "ack_timeout_expired"
    if latest_action == "snooze_expired":
        return "snooze_expired"
    if bool(alert.get("escalated")) and renotify_stage > 0:
        return "renotify_followup"
    if bool(alert.get("escalated")):
        return "initial_escalation"
    return "active_alert"


def alert_external_escalation_ready(alert: dict[str, Any]) -> bool:
    if "external_escalation_ready" in alert:
        return bool(alert.get("external_escalation_ready"))
    return bool(alert.get("escalated")) and alert_delivery_lane(alert) in {"slack", "telegram", "webhook"}


def _delivery_stage_for_channel(channel: str, alerts: list[dict[str, Any]]) -> str:
    normalized = str(channel or "").strip().lower()
    reasons = {alert_delivery_lane_reason(item) for item in alerts}
    if normalized == "email":
        if "ack_timeout_expired" in reasons or "snooze_expired" in reasons or "resume" in reasons:
            return "reactivation_email"
        return "initial_email"
    if normalized == "slack":
        if "ack_timeout_expired" in reasons:
            return "ack_timeout_slack"
        if "snooze_expired" in reasons:
            return "snooze_expiry_slack"
        if "renotify_followup" in reasons:
            return "followup_slack"
        return "initial_slack"
    if normalized == "telegram":
        if "ack_timeout_expired" in reasons:
            return "ack_timeout_telegram"
        if "snooze_expired" in reasons:
            return "snooze_expiry_telegram"
        return "followup_telegram"
    if "ack_timeout_expired" in reasons:
        return "ack_timeout_external"
    if "snooze_expired" in reasons:
        return "snooze_expiry_external"
    if "renotify_followup" in reasons:
        return "renotify_external"
    return "external_escalation"


def build_blocking_alert(reason: str) -> dict[str, Any]:
    mapping = {
        "AUTO_APPROVE_ENABLED=false": ("warning", "自动审批已关闭", "当前没有开启自动审批。"),
        "operating_state_recovery": ("warning", "系统处在恢复期", "当前处在恢复模式，建议先盯紧风险和执行情况。"),
        "execution_webhook_not_ready": ("error", "执行通道还没准备好", "已经配置实盘执行，但执行通道当前不可用。"),
        "portfolio_capital_exhausted": ("warning", "可用资金已经打满", "当前没有多余资金给新的审批机会。"),
    }
    severity, title, message = mapping.get(
        reason,
        ("warning", "AutoTrade blocked", str(reason or "A cockpit blocking reason is active.")),
    )
    return {
        "code": f"blocking:{reason}",
        "severity": severity,
        "scope": "system",
        "target": "",
        "title": title,
        "message": message,
    }


def _default_incident_priority_for_severity(severity: str | None) -> str:
    normalized = normalize_alert_severity(severity)
    if normalized == "error":
        return "high"
    if normalized == "info":
        return "low"
    return "normal"


def _priority_floor(*priorities: str | None) -> str:
    selected = "low"
    for raw in priorities:
        normalized = normalize_incident_priority(raw)
        if PRIORITY_RANK.get(normalized, 0) > PRIORITY_RANK.get(selected, 0):
            selected = normalized
    return selected


def _action_item(
    *,
    code: str,
    detail: str,
    execution_mode: str = "suppressed",
) -> dict[str, str]:
    return {
        "code": str(code or "").strip(),
        "detail": str(detail or "").strip(),
        "execution_mode": str(execution_mode or "suppressed").strip(),
    }


def _validation_internal_auto_response_plan(
    *,
    alert_code: str,
    baseline: dict[str, Any],
    trajectory: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    blocking_codes = [str(code) for code in list(baseline.get("blocking_codes") or [])[:3]]
    blocking_text = ", ".join(blocking_codes) if blocking_codes else "current validation blockers"
    actions = [
        _action_item(
            code="review_validation_state",
            detail="Review validation baseline, latest snapshots, and incident timeline internally.",
            execution_mode="manual_review",
        ),
    ]
    if alert_code == "validation_baseline_tune_blocked":
        actions.insert(
            0,
            _action_item(
                code="hold_threshold_tuning",
                detail=f"Do not apply threshold changes until {blocking_text} clears.",
                execution_mode="suppressed",
            ),
        )
    elif alert_code == "validation_baseline_scale_blocked":
        actions.extend(
            [
                _action_item(
                    code="hold_scale",
                    detail=f"Keep volume capped and do not expand while {blocking_text} remains active.",
                    execution_mode="suppressed",
                ),
                _action_item(
                    code="review_live_readiness",
                    detail="Review execution readiness and recent hourly snapshots before considering scale-out.",
                    execution_mode="manual_review",
                ),
            ]
        )
    elif alert_code == "validation_baseline_regressed":
        actions.extend(
            [
                _action_item(
                    code="pause_widening",
                    detail="Pause any widening moves and inspect the last hourly snapshots for new blockers.",
                    execution_mode="suppressed",
                ),
            ]
        )
        if trajectory:
            actions.append(
                _action_item(
                    code="review_regression_delta",
                    detail=(
                        f"Health delta {float(trajectory.get('health_delta') or 0.0):+.1f}; "
                        f"blocked streak {int(trajectory.get('blocked_streak') or 0)}."
                    ),
                    execution_mode="manual_review",
                ),
            )
    elif alert_code == "validation_baseline_drawdown":
        actions.extend(
            [
                _action_item(
                    code="manual_mode_hold",
                    detail="Keep the system in manual observation mode until the drawdown alert clears.",
                    execution_mode="suppressed",
                ),
            ]
        )
        if trajectory:
            actions.append(
                _action_item(
                    code="review_drawdown_trace",
                    detail=(
                        f"Health delta {float(trajectory.get('health_delta') or 0.0):+.1f}; "
                        f"worsening streak {int(trajectory.get('worsening_streak') or 0)}."
                    ),
                    execution_mode="manual_review",
                ),
            )
    return actions[:4]


_INTERNAL_ALERT_FIELDS = {"internal_auto_response_plan"}


def _public_alert(alert: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in dict(alert or {}).items()
        if key not in _INTERNAL_ALERT_FIELDS
    }


def public_cockpit_payload(cockpit: dict[str, Any]) -> dict[str, Any]:
    payload = dict(cockpit or {})
    alerts_value = payload.get("alerts")
    if isinstance(alerts_value, list):
        payload["alerts"] = [_public_alert(item) for item in alerts_value]
    elif isinstance(alerts_value, dict):
        alerts_dict = dict(alerts_value)
        alerts_dict["items"] = [
            _public_alert(item)
            for item in list(alerts_dict.get("items") or [])
        ]
        payload["alerts"] = alerts_dict
    return payload


def _isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat()


def _priority_sla_due_at(
    *,
    first_seen_at: str | None,
    priority: str,
    now: datetime,
) -> str:
    first_seen = _parse_timestamp(first_seen_at) or now
    return _isoformat_utc(first_seen + timedelta(minutes=incident_sla_minutes(priority)))


def _remaining_minutes(*, due_at: datetime, now: datetime) -> int:
    return int((due_at - now).total_seconds() // 60)


def _latest_operator_signal(alert_key: str) -> dict[str, str]:
    event = repo.get_latest_alert_signal_event(
        alert_key=alert_key,
        actions=(
            "ack",
            "snooze",
            "resume",
            "ack_expired",
            "snooze_expired",
            "resolve",
            "reopened",
            "cleared",
        ),
    )
    if not event:
        return {"action": "", "reason": ""}
    return {
        "action": str(event.get("action") or "").strip().lower(),
        "reason": str(event.get("reason") or "").strip(),
    }


def _apply_time_escalation(
    alert: dict[str, Any],
    *,
    now: datetime,
) -> dict[str, Any]:
    item = dict(alert)
    first_seen = _parse_timestamp(item.get("first_seen_at")) or now
    age_minutes = max(0, int((now - first_seen).total_seconds() // 60))
    escalation_minutes = max(1, int(settings.autotrade_alert_escalation_minutes))
    renotify_minutes = max(1, int(settings.autotrade_alert_renotify_minutes))

    effective_severity = normalize_alert_severity(item.get("severity"))
    escalated = age_minutes >= escalation_minutes
    renotify_stage = 0
    incident_stage = 0
    escalates_at = _isoformat_utc(first_seen + timedelta(minutes=escalation_minutes))
    next_renotify_at = ""

    if escalated:
        renotify_stage = max(0, int((age_minutes - escalation_minutes) // renotify_minutes))
        incident_stage = 1 + renotify_stage
        if effective_severity == "info":
            effective_severity = "warning"
        elif effective_severity == "warning":
            effective_severity = "error"
        next_renotify_at = _isoformat_utc(
            first_seen
            + timedelta(minutes=escalation_minutes + ((renotify_stage + 1) * renotify_minutes))
        )
        escalates_at = ""

    item.update(
        {
            "age_minutes": age_minutes,
            "effective_severity": effective_severity,
            "escalated": escalated,
            "incident_stage": incident_stage,
            "renotify_stage": renotify_stage,
            "escalates_at": escalates_at,
            "next_renotify_at": next_renotify_at,
        }
    )
    return item


def _merge_state_into_alert(
    alert: dict[str, Any],
    *,
    state: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    item = dict(alert)
    acked_at = _parse_timestamp(state.get("acked_at"))
    snoozed_until = _parse_timestamp(state.get("snoozed_until"))
    ack_expires_at = ""
    if acked_at is not None:
        ack_expires_at = _isoformat_utc(
            acked_at + timedelta(minutes=max(1, int(settings.autotrade_alert_ack_timeout_minutes)))
        )
    latest_signal = _latest_operator_signal(str(state.get("alert_key") or ""))
    item.update(
        {
            "alert_key": str(state.get("alert_key") or item.get("alert_key") or ""),
            "first_seen_at": state.get("first_seen_at"),
            "last_seen_at": state.get("last_seen_at"),
            "acknowledged": acked_at is not None,
            "acked_at": state.get("acked_at"),
            "acked_by": str(state.get("acked_by") or ""),
            "ack_expires_at": ack_expires_at,
            "snoozed": snoozed_until is not None and snoozed_until > now,
            "snoozed_until": state.get("snoozed_until"),
            "snooze_reason": str(state.get("snooze_reason") or ""),
            "incident_owner": str(state.get("incident_owner") or ""),
            "incident_status": str(state.get("incident_status") or "open"),
            "incident_priority": str(state.get("incident_priority") or item.get("incident_priority") or ""),
            "latest_case_note": str(state.get("latest_case_note") or ""),
            "last_case_actor": str(state.get("last_case_actor") or ""),
            "last_case_updated_at": state.get("last_case_updated_at"),
            "resolved_at": state.get("resolved_at"),
            "last_operator_event": latest_signal["action"],
            "last_operator_reason": latest_signal["reason"],
        }
    )
    item["operator_suppressed"] = bool(item.get("acknowledged") or item.get("snoozed"))
    return item


def _build_alert_signature(
    *,
    channel: str,
    alerts: list[dict[str, Any]],
) -> str:
    signature_payload = {
        "channel": str(channel or "").strip().lower(),
        "alerts": sorted(
            [
                {
                    "alert_key": str(item.get("alert_key") or ""),
                    "effective_severity": normalize_alert_severity(
                        item.get("effective_severity") or item.get("severity"),
                    ),
                    "incident_stage": int(item.get("incident_stage") or 0),
                    "renotify_stage": int(item.get("renotify_stage") or 0),
                    "delivery_lane": str(item.get("delivery_lane") or ""),
                    "delivery_lane_reason": str(item.get("delivery_lane_reason") or ""),
                    "incident_priority": str(item.get("incident_priority") or ""),
                    "last_operator_event": str(item.get("last_operator_event") or ""),
                }
                for item in alerts
            ],
            key=lambda item: item["alert_key"],
        ),
    }
    encoded = json.dumps(signature_payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    return hashlib.sha1(encoded).hexdigest()


def _cooldown_active(
    *,
    channel: str,
    alert_signature: str,
    cooldown_minutes: int,
    now: datetime,
) -> bool:
    for event in repo.list_alert_delivery_events(channel=channel, limit=25):
        if str(event.get("alert_signature") or "") != alert_signature:
            continue
        created_at = _parse_timestamp(event.get("created_at"))
        if created_at is None:
            continue
        age_minutes = (now - created_at).total_seconds() / 60.0
        if age_minutes < max(1, int(cooldown_minutes)):
            return True
    return False


def _event_history(channel: str) -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    recent = repo.list_alert_delivery_events(channel=channel, limit=5)
    return (recent[0] if recent else None), recent


def _apply_incident_automation(
    alert: dict[str, Any],
    *,
    state: dict[str, Any],
    previous_state: dict[str, Any] | None,
    now: datetime,
) -> tuple[dict[str, Any], str]:
    current_state = dict(state)

    if (
        previous_state
        and (
            previous_state.get("resolved_at")
            or str(previous_state.get("incident_status") or "").strip().lower() == "resolved"
        )
        and str(current_state.get("incident_status") or "").strip().lower() != "resolved"
    ):
        repo.create_alert_signal_event(
            alert_key=str(current_state.get("alert_key") or ""),
            action="reopened",
            actor="system",
            reason="alert condition resumed",
            previous_state=previous_state,
            next_state=current_state,
        )

    stored_priority = str(current_state.get("incident_priority") or "").strip().lower()
    severity_priority = _default_incident_priority_for_severity(alert.get("effective_severity"))
    configured_priority = str(alert.get("incident_priority") or "").strip().lower()
    priority_floor = _priority_floor(severity_priority, configured_priority)
    if stored_priority:
        current_priority = normalize_incident_priority(stored_priority)
        if PRIORITY_RANK.get(priority_floor, 0) > PRIORITY_RANK.get(current_priority, 0):
            current_priority = priority_floor
    else:
        current_priority = priority_floor

    due_at_text = ""
    stored_due_at_text = str(current_state.get("incident_sla_due_at") or "").strip()
    if stored_due_at_text and current_priority == normalize_incident_priority(stored_priority or current_priority):
        due_at_text = stored_due_at_text
    if not due_at_text:
        due_at_text = _priority_sla_due_at(
            first_seen_at=current_state.get("first_seen_at"),
            priority=current_priority,
            now=now,
        )
    due_at = _parse_timestamp(due_at_text) or now
    sla_breached = due_at <= now

    if (
        bool(settings.autotrade_incident_auto_escalate_on_sla_breach)
        and sla_breached
        and current_priority != "critical"
    ):
        previous = dict(current_state)
        updated = repo.update_alert_signal_incident_state(
            alert_key=str(current_state.get("alert_key") or ""),
            action="priority",
            actor="system",
            priority="critical",
            note="incident SLA breached automatically",
        )
        if updated:
            current_state = dict(updated)
            current_priority = "critical"
            due_at_text = str(current_state.get("incident_sla_due_at") or "").strip() or due_at_text
            due_at = _parse_timestamp(due_at_text) or now
            sla_breached = due_at <= now
            repo.create_alert_signal_event(
                alert_key=str(current_state.get("alert_key") or ""),
                action="sla_breached",
                actor="system",
                reason="incident SLA breached automatically",
                previous_state=previous,
                next_state=current_state,
            )

    preview = {
        **alert,
        "incident_priority": current_priority,
    }
    preview["delivery_lane"] = alert_delivery_lane(preview)
    routed_owner = auto_routed_incident_owner(
        priority=current_priority,
        delivery_lane=str(preview.get("delivery_lane") or ""),
    )
    current_owner = str(current_state.get("incident_owner") or "").strip()
    current_actor = str(current_state.get("last_case_actor") or "").strip().lower()
    manual_owner_locked = bool(current_owner and current_actor not in {"", "system"})
    if routed_owner and routed_owner != current_owner and not manual_owner_locked:
        previous = dict(current_state)
        if current_owner:
            updated = repo.update_alert_signal_incident_state(
                alert_key=str(current_state.get("alert_key") or ""),
                action="handoff",
                actor="system",
                owner=routed_owner,
                note="owner re-routed automatically",
            )
            event_action = "auto_handoff"
            event_reason = f"auto-routed to {routed_owner}"
        else:
            updated = repo.update_alert_signal_incident_state(
                alert_key=str(current_state.get("alert_key") or ""),
                action="assign",
                actor="system",
                owner=routed_owner,
                note="owner assigned automatically",
            )
            event_action = "auto_assign"
            event_reason = f"auto-assigned to {routed_owner}"
        if updated:
            current_state = dict(updated)
            repo.create_alert_signal_event(
                alert_key=str(current_state.get("alert_key") or ""),
                action=event_action,
                actor="system",
                reason=event_reason,
                previous_state=previous,
                next_state=current_state,
            )

    persisted_priority = str(current_state.get("incident_priority") or "").strip().lower()
    if persisted_priority:
        current_priority = normalize_incident_priority(persisted_priority)
        if PRIORITY_RANK.get(priority_floor, 0) > PRIORITY_RANK.get(current_priority, 0):
            current_priority = priority_floor
    due_at_text = str(current_state.get("incident_sla_due_at") or "").strip() or _priority_sla_due_at(
        first_seen_at=current_state.get("first_seen_at"),
        priority=current_priority,
        now=now,
    )
    due_at = _parse_timestamp(due_at_text) or now
    return current_state, current_priority


def build_alert_payload(
    *,
    enabled: bool,
    profit_guard: dict[str, Any],
    dashboard_metrics: dict[str, Any],
    operating_state: dict[str, Any],
    execution_readiness: dict[str, Any],
    validation_baseline: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    repo.release_expired_alert_signal_snoozes(now=now)
    repo.release_expired_alert_acknowledgements(
        now=now,
        timeout_minutes=max(1, int(settings.autotrade_alert_ack_timeout_minutes)),
    )

    profit_cockpit = dict(dashboard_metrics.get("profit_cockpit") or {})
    inventory = dict(profit_cockpit.get("inventory") or {})
    capital_limit = max(0.0, float(settings.auto_approve_portfolio_max_deployed_capital or 0.0))
    deployed_capital = max(0.0, float(inventory.get("deployed_capital") or 0.0))
    remaining_capital = (
        max(0.0, capital_limit - deployed_capital)
        if capital_limit > 0
        else 0.0
    )

    blocking_reasons: list[str] = []
    raw_alerts: list[dict[str, Any]] = []

    if not enabled:
        blocking_reasons.append("AUTO_APPROVE_ENABLED=false")
    if str(operating_state.get("state") or "").strip().lower() == "recovery":
        blocking_reasons.append("operating_state_recovery")
    if bool(execution_readiness.get("webhook_provider")) and not bool(execution_readiness.get("live_ready")):
        blocking_reasons.append("execution_webhook_not_ready")
    baseline = dict(validation_baseline or {})
    if bool(settings.single_account_mode) and baseline:
        if not bool(baseline.get("ready")):
            blocking_reasons.append("single_account_validation_scale_not_ready")
    if capital_limit > 0 and remaining_capital <= 0:
        blocking_reasons.append("portfolio_capital_exhausted")

    for reason in blocking_reasons:
        raw_alerts.append(build_blocking_alert(reason))

    if capital_limit > 0 and remaining_capital > 0:
        ratio = remaining_capital / capital_limit if capital_limit > 0 else 1.0
        if ratio <= LOW_CAPITAL_ALERT_RATIO:
            raw_alerts.append(
                {
                    "code": "portfolio_capital_low",
                    "severity": "warning",
                    "scope": "portfolio",
                    "target": "",
                    "title": "Portfolio capital running low",
                    "message": f"Only {round(remaining_capital, 2)} capital remains.",
                }
            )

    if bool(settings.single_account_mode) and baseline:
        baseline_codes = list(baseline.get("blocking_codes") or [])
        if not bool(baseline.get("ready_for_tune")):
            raw_alerts.append(
                {
                    "code": "validation_baseline_tune_blocked",
                    "severity": "error" if str(baseline.get("status") or "") == "blocked" else "warning",
                    "scope": "validation",
                    "target": str(baseline.get("status") or "").strip(),
                    "title": "Observation baseline blocked threshold tuning",
                    "message": ", ".join(baseline_codes[:3]) or "Validation evidence is still too thin.",
                    "internal_auto_response_plan": _validation_internal_auto_response_plan(
                        alert_code="validation_baseline_tune_blocked",
                        baseline=baseline,
                    ),
                }
            )
        elif not bool(baseline.get("ready")):
            raw_alerts.append(
                {
                    "code": "validation_baseline_scale_blocked",
                    "severity": "warning",
                    "scope": "validation",
                    "target": str(baseline.get("status") or "").strip(),
                    "title": "Observation baseline not ready for scale-out",
                    "message": ", ".join(baseline_codes[:3]) or "Keep the account in observation mode.",
                    "internal_auto_response_plan": _validation_internal_auto_response_plan(
                        alert_code="validation_baseline_scale_blocked",
                        baseline=baseline,
                    ),
                }
            )
        trajectory = dict(baseline.get("trajectory") or {})
        if bool(trajectory.get("available")) and str(trajectory.get("alert_level") or "") in {"warning", "error"}:
            code = "validation_baseline_drawdown"
            title = "Observation baseline drawdown warning"
            incident_priority = "critical"
            if bool(trajectory.get("scale_regressed")) or bool(trajectory.get("tune_regressed")):
                code = "validation_baseline_regressed"
                title = "Observation baseline regressed"
                incident_priority = "high"
            detail_parts = []
            if trajectory.get("health_delta") is not None:
                detail_parts.append(f"health delta {float(trajectory.get('health_delta') or 0.0):+.1f}")
            if int(trajectory.get("blocked_streak") or 0) > 0:
                detail_parts.append(f"blocked streak {int(trajectory.get('blocked_streak') or 0)}")
            if int(trajectory.get("worsening_streak") or 0) > 0:
                detail_parts.append(f"worsening streak {int(trajectory.get('worsening_streak') or 0)}")
            detail_text = " / ".join(detail_parts)
            raw_alerts.append(
                {
                    "code": code,
                    "severity": "error" if str(trajectory.get("alert_level")) == "error" else "warning",
                    "scope": "validation",
                    "target": str(trajectory.get("direction") or "").strip(),
                    "title": title,
                    "message": (
                        f"{str(trajectory.get('summary') or 'Observation baseline is deteriorating.')}"
                        + (f" ({detail_text})" if detail_text else "")
                    ),
                    "incident_priority": incident_priority,
                    "trajectory": trajectory,
                    "internal_auto_response_plan": _validation_internal_auto_response_plan(
                        alert_code=code,
                        baseline=baseline,
                        trajectory=trajectory,
                    ),
                }
            )

    raw_alerts.extend(risk_overrides_service.operator_alerts(limit=12))

    active_keys: set[str] = set()
    alerts: list[dict[str, Any]] = []

    for base_alert in raw_alerts:
        alert_key = _build_alert_key(base_alert)
        previous_state = repo.get_alert_signal_state(alert_key)
        state = repo.upsert_alert_signal_state(
            alert_key=alert_key,
            code=str(base_alert.get("code") or "").strip(),
            scope=str(base_alert.get("scope") or "").strip(),
            target=str(base_alert.get("target") or "").strip(),
            title=str(base_alert.get("title") or "").strip(),
            last_message=str(base_alert.get("message") or "").strip(),
            last_severity=normalize_alert_severity(base_alert.get("severity")),
        )
        active_keys.add(alert_key)
        merged = _merge_state_into_alert(
            {**base_alert, "alert_key": alert_key},
            state=state,
            now=now,
        )
        merged = _apply_time_escalation(merged, now=now)
        state, current_priority = _apply_incident_automation(
            merged,
            state=state,
            previous_state=previous_state,
            now=now,
        )
        merged = _merge_state_into_alert(
            merged,
            state=state,
            now=now,
        )
        merged["incident_priority"] = current_priority
        sla_due_at = str(state.get("incident_sla_due_at") or "").strip() or _priority_sla_due_at(
            first_seen_at=state.get("first_seen_at"),
            priority=current_priority,
            now=now,
        )
        due_at = _parse_timestamp(sla_due_at) or now
        merged["sla_due_at"] = sla_due_at
        merged["sla_minutes"] = incident_sla_minutes(current_priority)
        merged["sla_remaining_minutes"] = _remaining_minutes(due_at=due_at, now=now)
        merged["sla_breached"] = due_at <= now
        merged["delivery_lane"] = alert_delivery_lane(merged)
        merged["delivery_lane_reason"] = alert_delivery_lane_reason(merged)
        merged["external_escalation_ready"] = alert_external_escalation_ready(merged)
        merged["auto_routed_owner"] = auto_routed_incident_owner(
            priority=current_priority,
            delivery_lane=str(merged.get("delivery_lane") or ""),
        )
        alerts.append(merged)

    if bool(settings.autotrade_incident_auto_resolve_enabled):
        repo.resolve_missing_alert_signal_states(active_keys)

    counts_by_severity = {"error": 0, "warning": 0, "info": 0}
    for item in alerts:
        counts_by_severity[normalize_alert_severity(item.get("effective_severity") or item.get("severity"))] += 1

    alerts.sort(
        key=lambda item: (
            -PRIORITY_RANK.get(normalize_incident_priority(item.get("incident_priority")), 0),
            0 if bool(item.get("sla_breached")) else 1,
            -SEVERITY_RANK.get(
                normalize_alert_severity(item.get("effective_severity") or item.get("severity")),
                0,
            ),
            -int(item.get("age_minutes") or 0),
            str(item.get("title") or ""),
        )
    )

    last_email_event, recent_email_events = _event_history("email")
    last_slack_event, recent_slack_events = _event_history("slack")
    last_telegram_event, recent_telegram_events = _event_history("telegram")
    last_webhook_event, recent_webhook_events = _event_history("webhook")

    return {
        "ready": bool(enabled) and not blocking_reasons,
        "blocking_reasons": blocking_reasons,
        "alerts": alerts,
        "alert_summary": {
            "count": len(alerts),
            "counts_by_severity": counts_by_severity,
        },
        "portfolio": {
            "capital_limit": round(capital_limit, 2),
            "deployed_capital": round(deployed_capital, 2),
            "remaining_capital": round(remaining_capital, 2),
        },
        "profit_guard": dict(profit_guard or {}),
        "incident_automation": {
            "auto_assign_enabled": bool(settings.autotrade_incident_auto_assign_enabled),
            "auto_resolve_enabled": bool(settings.autotrade_incident_auto_resolve_enabled),
            "auto_escalate_on_sla_breach": bool(settings.autotrade_incident_auto_escalate_on_sla_breach),
            "default_owner": str(settings.autotrade_incident_default_owner or "").strip(),
            "default_owner_schedule": str(settings.autotrade_incident_default_owner_schedule or "").strip(),
            "high_priority_owner": str(settings.autotrade_incident_high_priority_owner or "").strip(),
            "high_priority_owner_schedule": str(settings.autotrade_incident_high_priority_owner_schedule or "").strip(),
            "critical_priority_owner": str(settings.autotrade_incident_critical_priority_owner or "").strip(),
            "critical_priority_owner_schedule": str(settings.autotrade_incident_critical_priority_owner_schedule or "").strip(),
            "slack_owner": str(settings.autotrade_incident_slack_owner or "").strip(),
            "slack_owner_schedule": str(settings.autotrade_incident_slack_owner_schedule or "").strip(),
            "telegram_owner": str(settings.autotrade_incident_telegram_owner or "").strip(),
            "telegram_owner_schedule": str(settings.autotrade_incident_telegram_owner_schedule or "").strip(),
            "rota_timezone": str(settings.autotrade_incident_rota_timezone or "").strip() or "UTC",
        },
        "alert_delivery": {
            "email_enabled": bool(settings.alert_email_enabled),
            "email_ready": alert_email_ready(),
            "auto_email_enabled": bool(settings.autotrade_alert_email_auto_enabled),
            "auto_email_min_severity": normalize_alert_severity(settings.autotrade_alert_email_min_severity),
            "alert_ack_timeout_minutes": max(1, int(settings.autotrade_alert_ack_timeout_minutes)),
            "alert_escalation_minutes": max(1, int(settings.autotrade_alert_escalation_minutes)),
            "alert_renotify_minutes": max(1, int(settings.autotrade_alert_renotify_minutes)),
            "email_cooldown_minutes": max(1, int(settings.autotrade_alert_email_cooldown_minutes)),
            "slack_enabled": bool(settings.alert_slack_enabled),
            "slack_ready": alert_slack_ready(),
            "auto_slack_enabled": bool(settings.autotrade_alert_slack_auto_enabled),
            "auto_slack_min_severity": normalize_alert_severity(settings.autotrade_alert_slack_min_severity),
            "slack_min_stage": max(1, int(settings.autotrade_alert_slack_min_stage)),
            "slack_cooldown_minutes": max(1, int(settings.autotrade_alert_slack_cooldown_minutes)),
            "telegram_enabled": bool(settings.alert_telegram_enabled),
            "telegram_ready": alert_telegram_ready(),
            "auto_telegram_enabled": bool(settings.autotrade_alert_telegram_auto_enabled),
            "auto_telegram_min_severity": normalize_alert_severity(settings.autotrade_alert_telegram_min_severity),
            "telegram_min_stage": max(1, int(settings.autotrade_alert_telegram_min_stage)),
            "telegram_cooldown_minutes": max(1, int(settings.autotrade_alert_telegram_cooldown_minutes)),
            "webhook_enabled": bool(settings.alert_webhook_enabled),
            "webhook_ready": alert_webhook_ready(),
            "webhook_provider": alert_webhook_provider(),
            "webhook_channel_label": alert_webhook_channel_label(),
            "auto_webhook_enabled": bool(settings.autotrade_alert_webhook_auto_enabled),
            "auto_webhook_min_severity": normalize_alert_severity(settings.autotrade_alert_webhook_min_severity),
            "webhook_cooldown_minutes": max(1, int(settings.autotrade_alert_webhook_cooldown_minutes)),
            "last_email_event": last_email_event,
            "recent_email_events": recent_email_events,
            "last_slack_event": last_slack_event,
            "recent_slack_events": recent_slack_events,
            "last_telegram_event": last_telegram_event,
            "recent_telegram_events": recent_telegram_events,
            "last_webhook_event": last_webhook_event,
            "recent_webhook_events": recent_webhook_events,
        },
    }


def list_alert_incident_timeline(
    *,
    alert_key: str,
    limit: int = 50,
) -> dict[str, Any]:
    normalized_key = str(alert_key or "").strip()
    items = repo.list_alert_incident_timeline(
        alert_key=normalized_key,
        limit=limit,
    )
    return {
        "alert_key": normalized_key,
        "count": len(items),
        "items": items,
    }


def _dispatch_text_channel(
    channel: str,
    *,
    cockpit: dict[str, Any],
    source: str,
    force: bool,
) -> dict[str, Any]:
    now = datetime.now(timezone.utc).replace(microsecond=0)
    ready = _channel_ready(channel)
    ready_field = f"{channel}_ready"
    selected_alerts = _select_channel_alerts(cockpit, channel=channel, force=force)
    if not selected_alerts:
        empty_reason = {
            "email": "no_active_alerts",
            "slack": "no_slack_stage_alerts",
            "telegram": "no_telegram_stage_alerts",
            "webhook": "no_escalated_alerts",
        }.get(channel, "no_active_alerts")
        return {
            "channel": channel,
            "provider": _channel_provider(channel),
            "channel_label": _channel_label(channel),
            "ready": ready,
            ready_field: ready,
            "sent": False,
            "reason": empty_reason,
            "alert_count": 0,
            "event": None,
        }

    alert_signature = _build_alert_signature(channel=channel, alerts=selected_alerts)
    delivery_stage = _delivery_stage_for_channel(channel, selected_alerts)
    delivery_stage, alert_keys, alert_context = _build_delivery_event_metadata(
        selected_alerts,
        default_stage=delivery_stage,
    )
    provider = _channel_provider(channel)
    channel_label = _channel_label(channel)

    if channel == "email":
        subject, body = format_cockpit_alert_email(
            cockpit={**cockpit, "alerts": selected_alerts},
        )
        payload = {"text": body}
    else:
        payload = format_cockpit_alert_webhook(
            cockpit={**cockpit, "alerts": selected_alerts},
            alerts=selected_alerts,
        )
        subject = f"[CardFlip Autotrade] {channel_label} alert"
        body = str(payload.get("text") or "").strip()

    cooldown_minutes = _channel_cooldown_minutes(channel)
    if not force and _cooldown_active(
        channel=channel,
        alert_signature=alert_signature,
        cooldown_minutes=cooldown_minutes,
        now=now,
    ):
        event = repo.create_alert_delivery_event(
            channel=channel,
            provider=provider,
            channel_label=channel_label,
            delivery_stage=delivery_stage,
            alert_signature=alert_signature,
            alert_keys=alert_keys,
            alert_context=alert_context,
            alert_count=len(selected_alerts),
            subject=subject,
            reason="cooldown_active",
            success=False,
            source=source,
        )
        return {
            "channel": channel,
            "provider": provider,
            "channel_label": channel_label,
            "ready": True,
            ready_field: ready,
            "sent": False,
            "reason": "cooldown_active",
            "alert_count": len(selected_alerts),
            "event": event,
        }

    success = _send_channel_notification(
        channel,
        subject=subject,
        body=body,
        payload=payload,
    )
    event = repo.create_alert_delivery_event(
        channel=channel,
        provider=provider,
        channel_label=channel_label,
        delivery_stage=delivery_stage,
        alert_signature=alert_signature,
        alert_keys=alert_keys,
        alert_context=alert_context,
        alert_count=len(selected_alerts),
        subject=subject,
        reason="sent" if success else "send_failed",
        success=success,
        source=source,
    )
    return {
        "channel": channel,
        "provider": provider,
        "channel_label": channel_label,
        "ready": ready,
        ready_field: ready,
        "sent": success,
        "reason": "sent" if success else "send_failed",
        "alert_count": len(selected_alerts),
        "event": event,
    }


def dispatch_alert_email(
    *,
    cockpit: dict[str, Any],
    source: str = "system",
    force: bool = False,
) -> dict[str, Any]:
    return _dispatch_text_channel(
        "email",
        cockpit=cockpit,
        source=source,
        force=force,
    )


def dispatch_alert_webhook(
    *,
    cockpit: dict[str, Any],
    source: str = "system",
    force: bool = False,
) -> dict[str, Any]:
    return _dispatch_text_channel(
        "webhook",
        cockpit=cockpit,
        source=source,
        force=force,
    )


def dispatch_alert_slack(
    *,
    cockpit: dict[str, Any],
    source: str = "system",
    force: bool = False,
) -> dict[str, Any]:
    return _dispatch_text_channel(
        "slack",
        cockpit=cockpit,
        source=source,
        force=force,
    )


def dispatch_alert_telegram(
    *,
    cockpit: dict[str, Any],
    source: str = "system",
    force: bool = False,
) -> dict[str, Any]:
    return _dispatch_text_channel(
        "telegram",
        cockpit=cockpit,
        source=source,
        force=force,
    )
