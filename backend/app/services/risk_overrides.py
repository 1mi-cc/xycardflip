from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Literal

from .. import repositories as repo
from ..config import settings

EXPIRING_SOON_HOURS = 6


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


def _hours_until(raw: str | None, *, now: datetime) -> float | None:
    until_at = _parse_timestamp(raw)
    if until_at is None:
        return None
    return round((until_at - now).total_seconds() / 3600.0, 2)


def _runtime_control_from_state(
    state: dict[str, Any] | None,
    *,
    observe_base_multiplier: float,
    observe_release_streak: int,
) -> dict[str, Any]:
    if not state:
        return {
            "state": "normal",
            "blocked": False,
            "intake_multiplier": 1.0,
            "recovery_progress": 1.0,
        }
    state_name = str(state.get("state") or "normal")
    until_at = _parse_timestamp(state.get("frozen_until"))
    now = datetime.now(timezone.utc)
    if until_at is not None and until_at <= now:
        state_name = "normal"
    if state_name == "frozen":
        return {
            "state": "frozen",
            "blocked": True,
            "intake_multiplier": 0.0,
            "recovery_progress": 0.0,
        }
    if state_name == "observe":
        metadata = state.get("metadata") or {}
        positive_streak = int(metadata.get("positive_streak") or 0)
        release_streak = max(1, int(observe_release_streak))
        base_multiplier = max(0.05, min(1.0, float(observe_base_multiplier)))
        recovery_progress = min(1.0, positive_streak / float(release_streak))
        multiplier = round(
            base_multiplier + ((1.0 - base_multiplier) * recovery_progress),
            2,
        )
        return {
            "state": "observe",
            "blocked": False,
            "intake_multiplier": multiplier,
            "recovery_progress": round(recovery_progress, 4),
            "positive_streak": positive_streak,
            "release_streak": release_streak,
        }
    return {
        "state": "normal",
        "blocked": False,
        "intake_multiplier": 1.0,
        "recovery_progress": 1.0,
    }


def _enrich_control_state(
    state: dict[str, Any],
    *,
    runtime_control: dict[str, Any],
    now: datetime,
) -> dict[str, Any]:
    hours_until_release = _hours_until(state.get("frozen_until"), now=now)
    expires_soon = bool(
        hours_until_release is not None
        and 0.0 < hours_until_release <= EXPIRING_SOON_HOURS
    )
    return {
        **state,
        "runtime_control": runtime_control,
        "hours_until_release": hours_until_release,
        "expires_soon": expires_soon,
    }


class RiskOverridesService:
    def _normalize_expired_source_states(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        restored: list[dict[str, Any]] = []
        for current in repo.list_source_control_states(limit=200):
            state_name = str(current.get("state") or "normal")
            until_at = _parse_timestamp(current.get("frozen_until"))
            if state_name == "normal" or until_at is None or until_at > now:
                continue
            next_state = repo.upsert_source_control_state(
                source=str(current.get("source") or ""),
                state="normal",
                reason="source control expired",
                frozen_until=None,
                metadata=current.get("metadata") or {},
            )
            repo.create_source_control_event(
                source=str(current.get("source") or ""),
                event_type="auto_restore",
                reason="source control expired",
                previous_state=current,
                next_state=next_state,
            )
            restored.append(next_state)
        return restored

    def _normalize_expired_cluster_states(self) -> list[dict[str, Any]]:
        now = datetime.now(timezone.utc)
        restored: list[dict[str, Any]] = []
        for current in repo.list_cluster_control_states(limit=200):
            state_name = str(current.get("state") or "normal")
            until_at = _parse_timestamp(current.get("frozen_until"))
            if state_name == "normal" or until_at is None or until_at > now:
                continue
            next_state = repo.upsert_cluster_control_state(
                risk_cluster=str(current.get("risk_cluster") or ""),
                state="normal",
                reason="cluster control expired",
                frozen_until=None,
                metadata=current.get("metadata") or {},
            )
            repo.create_cluster_control_event(
                risk_cluster=str(current.get("risk_cluster") or ""),
                event_type="auto_restore",
                reason="cluster control expired",
                previous_state=current,
                next_state=next_state,
            )
            restored.append(next_state)
        return restored

    def source_runtime_control(self, *, source: str) -> dict[str, Any]:
        state = repo.get_source_control_state(source)
        return _runtime_control_from_state(
            state,
            observe_base_multiplier=float(settings.auto_approve_source_observe_base_multiplier),
            observe_release_streak=int(settings.auto_approve_source_observe_release_streak),
        )

    def cluster_runtime_control(self, *, risk_cluster: str) -> dict[str, Any]:
        state = repo.get_cluster_control_state(risk_cluster)
        return _runtime_control_from_state(
            state,
            observe_base_multiplier=float(settings.auto_approve_source_observe_base_multiplier),
            observe_release_streak=int(settings.auto_approve_source_observe_release_streak),
        )

    def source_status_summary(self, limit: int = 8) -> dict[str, Any]:
        self._normalize_expired_source_states()
        now = datetime.now(timezone.utc)
        items: list[dict[str, Any]] = []
        active_freeze_count = 0
        active_observe_count = 0
        expiring_soon_count = 0
        for state in repo.list_source_control_states(limit=limit * 4):
            until_at = _parse_timestamp(state.get("frozen_until"))
            if until_at is not None and until_at <= now:
                continue
            state_name = str(state.get("state") or "normal")
            if state_name == "frozen":
                active_freeze_count += 1
            elif state_name == "observe":
                active_observe_count += 1
            else:
                continue
            enriched = _enrich_control_state(
                state,
                runtime_control=self.source_runtime_control(
                    source=str(state.get("source") or ""),
                ),
                now=now,
            )
            if enriched["expires_soon"]:
                expiring_soon_count += 1
            items.append(enriched)
        next_expiry_at = min(
            (
                str(item.get("frozen_until") or "")
                for item in items
                if str(item.get("frozen_until") or "").strip()
            ),
            default="",
        )
        return {
            "active_freeze_count": active_freeze_count,
            "active_observe_count": active_observe_count,
            "expiring_soon_count": expiring_soon_count,
            "next_expiry_at": next_expiry_at,
            "items": items[:limit],
            "recent_events": repo.list_source_control_events(limit=8),
            "daily_report": repo.get_source_control_daily_report(hours=24),
        }

    def cluster_status_summary(self, limit: int = 8) -> dict[str, Any]:
        self._normalize_expired_cluster_states()
        now = datetime.now(timezone.utc)
        items: list[dict[str, Any]] = []
        active_freeze_count = 0
        active_observe_count = 0
        expiring_soon_count = 0
        for state in repo.list_cluster_control_states(limit=limit * 4):
            until_at = _parse_timestamp(state.get("frozen_until"))
            if until_at is not None and until_at <= now:
                continue
            state_name = str(state.get("state") or "normal")
            if state_name == "frozen":
                active_freeze_count += 1
            elif state_name == "observe":
                active_observe_count += 1
            else:
                continue
            enriched = _enrich_control_state(
                state,
                runtime_control=self.cluster_runtime_control(
                    risk_cluster=str(state.get("risk_cluster") or ""),
                ),
                now=now,
            )
            if enriched["expires_soon"]:
                expiring_soon_count += 1
            items.append(enriched)
        next_expiry_at = min(
            (
                str(item.get("frozen_until") or "")
                for item in items
                if str(item.get("frozen_until") or "").strip()
            ),
            default="",
        )
        return {
            "active_freeze_count": active_freeze_count,
            "active_observe_count": active_observe_count,
            "expiring_soon_count": expiring_soon_count,
            "next_expiry_at": next_expiry_at,
            "items": items[:limit],
            "recent_events": repo.list_cluster_control_events(limit=8),
            "daily_report": repo.get_cluster_control_daily_report(hours=24),
        }

    def operator_alerts(self, limit: int = 12) -> list[dict[str, Any]]:
        alerts: list[dict[str, Any]] = []

        for item in self.source_status_summary(limit=limit * 2).get("items", []):
            if not bool(item.get("expires_soon")):
                continue
            state_name = str(item.get("state") or "normal")
            alerts.append(
                {
                    "code": "source_override_release_soon",
                    "severity": "warning" if state_name == "frozen" else "info",
                    "scope": "source_override",
                    "target": str(item.get("source") or ""),
                    "title": "Source override expires soon",
                    "message": (
                        f"{str(item.get('source') or '')} {state_name} override "
                        f"expires in {float(item.get('hours_until_release') or 0.0):.1f}h"
                    ).strip(),
                    "expires_at": item.get("frozen_until") or "",
                    "hours_until_release": item.get("hours_until_release"),
                }
            )

        for item in self.cluster_status_summary(limit=limit * 2).get("items", []):
            if not bool(item.get("expires_soon")):
                continue
            state_name = str(item.get("state") or "normal")
            alerts.append(
                {
                    "code": "cluster_override_release_soon",
                    "severity": "warning" if state_name == "frozen" else "info",
                    "scope": "cluster_override",
                    "target": str(item.get("risk_cluster") or ""),
                    "title": "Cluster override expires soon",
                    "message": (
                        f"{str(item.get('risk_cluster') or '')} {state_name} override "
                        f"expires in {float(item.get('hours_until_release') or 0.0):.1f}h"
                    ).strip(),
                    "expires_at": item.get("frozen_until") or "",
                    "hours_until_release": item.get("hours_until_release"),
                }
            )

        severity_rank = {"error": 0, "warning": 1, "info": 2}
        alerts.sort(
            key=lambda item: (
                severity_rank.get(str(item.get("severity") or "info"), 9),
                float(item.get("hours_until_release") or 9999.0),
                str(item.get("target") or ""),
            )
        )
        return alerts[:limit]

    def apply_manual_source_action(
        self,
        *,
        source: str,
        action: Literal["freeze", "observe", "normal"],
        reason: str = "",
        actor: str = "operator",
        duration_hours: int | None = None,
    ) -> dict[str, Any]:
        normalized_source = str(source or "").strip()
        if not normalized_source:
            raise ValueError("source is required")
        current = repo.get_source_control_state(normalized_source)
        now = datetime.now(timezone.utc)
        metadata = {
            **(current.get("metadata") or {} if current else {}),
            "manual_action": action,
            "manual_actor": str(actor or "operator").strip() or "operator",
        }

        if action == "freeze":
            hours = max(1, int(duration_hours or settings.auto_approve_seller_freeze_hours))
            next_state = repo.upsert_source_control_state(
                source=normalized_source,
                state="frozen",
                reason=reason or "manual freeze",
                frozen_until=(now + timedelta(hours=hours)).isoformat(),
                metadata=metadata,
            )
            event_type = "manual_freeze"
        elif action == "observe":
            hours = max(1, int(duration_hours or settings.auto_approve_seller_observe_hours))
            next_state = repo.upsert_source_control_state(
                source=normalized_source,
                state="observe",
                reason=reason or "manual observe",
                frozen_until=(now + timedelta(hours=hours)).isoformat(),
                metadata=metadata,
            )
            event_type = "manual_observe"
        else:
            next_state = repo.upsert_source_control_state(
                source=normalized_source,
                state="normal",
                reason=reason or "manual restore",
                frozen_until=None,
                metadata=metadata,
            )
            event_type = "manual_restore"

        event = repo.create_source_control_event(
            source=normalized_source,
            event_type=event_type,
            reason=reason or event_type.replace("_", " "),
            previous_state=current,
            next_state=next_state,
        )
        return {
            "ok": True,
            "source": normalized_source,
            "action": action,
            "state": next_state,
            "event": event,
            "status": self.source_status_summary(),
        }

    def apply_manual_cluster_action(
        self,
        *,
        risk_cluster: str,
        action: Literal["freeze", "observe", "normal"],
        reason: str = "",
        actor: str = "operator",
        duration_hours: int | None = None,
    ) -> dict[str, Any]:
        normalized_cluster = str(risk_cluster or "").strip()
        if not normalized_cluster:
            raise ValueError("risk_cluster is required")
        current = repo.get_cluster_control_state(normalized_cluster)
        now = datetime.now(timezone.utc)
        metadata = {
            **(current.get("metadata") or {} if current else {}),
            "manual_action": action,
            "manual_actor": str(actor or "operator").strip() or "operator",
        }

        if action == "freeze":
            hours = max(1, int(duration_hours or settings.auto_approve_seller_freeze_hours))
            next_state = repo.upsert_cluster_control_state(
                risk_cluster=normalized_cluster,
                state="frozen",
                reason=reason or "manual freeze",
                frozen_until=(now + timedelta(hours=hours)).isoformat(),
                metadata=metadata,
            )
            event_type = "manual_freeze"
        elif action == "observe":
            hours = max(1, int(duration_hours or settings.auto_approve_seller_observe_hours))
            next_state = repo.upsert_cluster_control_state(
                risk_cluster=normalized_cluster,
                state="observe",
                reason=reason or "manual observe",
                frozen_until=(now + timedelta(hours=hours)).isoformat(),
                metadata=metadata,
            )
            event_type = "manual_observe"
        else:
            next_state = repo.upsert_cluster_control_state(
                risk_cluster=normalized_cluster,
                state="normal",
                reason=reason or "manual restore",
                frozen_until=None,
                metadata=metadata,
            )
            event_type = "manual_restore"

        event = repo.create_cluster_control_event(
            risk_cluster=normalized_cluster,
            event_type=event_type,
            reason=reason or event_type.replace("_", " "),
            previous_state=current,
            next_state=next_state,
        )
        return {
            "ok": True,
            "risk_cluster": normalized_cluster,
            "action": action,
            "state": next_state,
            "event": event,
            "status": self.cluster_status_summary(),
        }


risk_overrides_service = RiskOverridesService()
