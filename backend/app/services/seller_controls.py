from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Literal
from typing import Any

from .. import repositories as repo
from ..config import settings


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


class SellerControlsService:
    def _seller_map(self, metrics: dict[str, Any] | None) -> dict[tuple[str, str], dict[str, Any]]:
        cockpit = (metrics or {}).get("profit_cockpit") or {}
        items = list(cockpit.get("seller_leaderboard_7d") or [])
        mapping: dict[tuple[str, str], dict[str, Any]] = {}
        for item in items:
            source = str(item.get("source") or "").strip()
            seller_id = str(item.get("seller_id") or "").strip()
            if not source or not seller_id:
                continue
            mapping[(source, seller_id)] = item
        return mapping

    def is_seller_frozen(self, *, source: str, seller_id: str | None) -> bool:
        normalized_seller = str(seller_id or "").strip()
        if not normalized_seller:
            return False
        state = repo.get_seller_control_state(source, normalized_seller)
        if not state or str(state.get("state") or "") != "frozen":
            return False
        frozen_until = _parse_timestamp(state.get("frozen_until"))
        if frozen_until is None:
            return True
        return frozen_until > datetime.now(timezone.utc)

    def runtime_control(self, *, source: str, seller_id: str | None) -> dict[str, Any]:
        normalized_seller = str(seller_id or "").strip()
        if not normalized_seller:
            return {
                "state": "normal",
                "blocked": False,
                "threshold_delta": {"min_score": 0.0, "min_roi": 0.0, "max_risk_score": 0.0},
                "intake_multiplier": 1.0,
                "recovery_progress": 1.0,
            }
        state = repo.get_seller_control_state(source, normalized_seller)
        if not state:
            return {
                "state": "normal",
                "blocked": False,
                "threshold_delta": {"min_score": 0.0, "min_roi": 0.0, "max_risk_score": 0.0},
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
                "threshold_delta": {"min_score": 99.0, "min_roi": 9.99, "max_risk_score": -99.0},
                "intake_multiplier": 0.0,
                "recovery_progress": 0.0,
            }
        if state_name == "observe":
            metadata = state.get("metadata") or {}
            positive_streak = int(metadata.get("positive_streak") or 0)
            release_streak = max(1, int(settings.auto_approve_seller_observe_release_streak))
            base_multiplier = max(
                0.1,
                min(1.0, float(settings.auto_approve_seller_observe_base_multiplier)),
            )
            recovery_progress = min(1.0, positive_streak / float(release_streak))
            multiplier = round(
                base_multiplier + ((1.0 - base_multiplier) * recovery_progress),
                2,
            )
            penalty_factor = max(0.0, 1.0 - recovery_progress)
            return {
                "state": "observe",
                "blocked": False,
                "threshold_delta": {
                    "min_score": round(2.0 * penalty_factor, 2),
                    "min_roi": round(0.01 * penalty_factor, 4),
                    "max_risk_score": round(-2.0 * penalty_factor, 2),
                },
                "intake_multiplier": multiplier,
                "recovery_progress": round(recovery_progress, 4),
                "positive_streak": positive_streak,
                "release_streak": release_streak,
            }
        return {
            "state": "normal",
            "blocked": False,
            "threshold_delta": {"min_score": 0.0, "min_roi": 0.0, "max_risk_score": 0.0},
            "intake_multiplier": 1.0,
            "recovery_progress": 1.0,
        }

    def status_summary(self, limit: int = 8) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        items: list[dict[str, Any]] = []
        active_freeze_count = 0
        active_observe_count = 0
        for state in repo.list_seller_control_states(limit=limit * 6):
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
            items.append(
                {
                    **state,
                    "runtime_control": self.runtime_control(
                        source=str(state.get("source") or ""),
                        seller_id=str(state.get("seller_id") or ""),
                    ),
                }
            )
        recent_events = repo.list_seller_control_events(limit=8)
        daily_report = repo.get_seller_control_daily_report(hours=24)
        return {
            "active_freeze_count": active_freeze_count,
            "active_observe_count": active_observe_count,
            "items": items[:limit],
            "recent_events": recent_events,
            "daily_report": daily_report,
        }

    def sync_from_metrics(
        self,
        *,
        metrics: dict[str, Any] | None = None,
        actor: str = "seller_guard_bot",
    ) -> dict[str, Any]:
        if not settings.auto_approve_seller_freeze_enabled:
            return {
                "enabled": False,
                "frozen": [],
                "unfrozen": [],
                "status": self.status_summary(),
            }

        metrics = metrics or repo.get_dashboard_metrics()
        seller_map = self._seller_map(metrics)
        now = datetime.now(timezone.utc)
        freeze_hours = max(1, int(settings.auto_approve_seller_freeze_hours))
        min_sold_count = max(1, int(settings.auto_approve_seller_freeze_min_sold_count))
        frozen: list[dict[str, Any]] = []
        unfrozen: list[dict[str, Any]] = []

        for (source, seller_id), item in seller_map.items():
            sold_count = int(item.get("sold_count") or 0)
            seller_lane = str(item.get("seller_lane") or "neutral")
            current = repo.get_seller_control_state(source, seller_id)
            current_state = str(current.get("state") or "normal") if current else "normal"

            if seller_lane == "blacklist" and sold_count >= min_sold_count:
                frozen_until = (now + timedelta(hours=freeze_hours)).isoformat()
                reason = str(item.get("lane_summary") or "seller performance degraded")
                next_state = repo.upsert_seller_control_state(
                    source=source,
                    seller_id=seller_id,
                    state="frozen",
                    reason=reason,
                    frozen_until=frozen_until,
                    metadata=item,
                )
                if current_state != "frozen":
                    repo.create_seller_control_event(
                        source=source,
                        seller_id=seller_id,
                        event_type="auto_freeze",
                        reason=reason,
                        previous_state=current,
                        next_state=next_state,
                    )
                    frozen.append(next_state)
                continue

            if current_state == "frozen":
                frozen_until = _parse_timestamp(current.get("frozen_until"))
                should_unfreeze = seller_lane != "blacklist" or (
                    frozen_until is not None and frozen_until <= now
                )
                if should_unfreeze:
                    reason = str(item.get("lane_summary") or "seller recovered")
                    if settings.auto_approve_seller_observe_enabled:
                        observe_until = (now + timedelta(hours=max(1, int(settings.auto_approve_seller_observe_hours)))).isoformat()
                        next_state = repo.upsert_seller_control_state(
                            source=source,
                            seller_id=seller_id,
                            state="observe",
                            reason=reason,
                            frozen_until=observe_until,
                            metadata=item,
                        )
                        repo.create_seller_control_event(
                            source=source,
                            seller_id=seller_id,
                            event_type="auto_observe",
                            reason=reason,
                            previous_state=current,
                            next_state=next_state,
                        )
                    else:
                        next_state = repo.upsert_seller_control_state(
                            source=source,
                            seller_id=seller_id,
                            state="normal",
                            reason=reason,
                            frozen_until=None,
                            metadata=item,
                        )
                        repo.create_seller_control_event(
                            source=source,
                            seller_id=seller_id,
                            event_type="auto_unfreeze",
                            reason=reason,
                            previous_state=current,
                            next_state=next_state,
                        )
                    unfrozen.append(next_state)
                continue

            if current_state == "observe":
                observe_until = _parse_timestamp(current.get("frozen_until"))
                positive_streak = int(item.get("positive_streak") or 0)
                release_streak = max(1, int(settings.auto_approve_seller_observe_release_streak))
                if seller_lane == "blacklist" and sold_count >= min_sold_count:
                    frozen_until = (now + timedelta(hours=freeze_hours)).isoformat()
                    reason = str(item.get("lane_summary") or "seller relapsed during observe")
                    next_state = repo.upsert_seller_control_state(
                        source=source,
                        seller_id=seller_id,
                        state="frozen",
                        reason=reason,
                        frozen_until=frozen_until,
                        metadata=item,
                    )
                    repo.create_seller_control_event(
                        source=source,
                        seller_id=seller_id,
                        event_type="observe_refreeze",
                        reason=reason,
                        previous_state=current,
                        next_state=next_state,
                    )
                    frozen.append(next_state)
                    continue
                if positive_streak >= release_streak or (observe_until is not None and observe_until <= now):
                    reason = str(item.get("lane_summary") or "seller observe window completed")
                    next_state = repo.upsert_seller_control_state(
                        source=source,
                        seller_id=seller_id,
                        state="normal",
                        reason=reason,
                        frozen_until=None,
                        metadata=item,
                    )
                    repo.create_seller_control_event(
                        source=source,
                        seller_id=seller_id,
                        event_type="observe_complete",
                        reason=reason,
                        previous_state=current,
                        next_state=next_state,
                    )
                    unfrozen.append(next_state)

        # Expired freezes with no longer-tracked sellers should also clear.
        for current in repo.list_seller_control_states(limit=200):
            key = (str(current.get("source") or ""), str(current.get("seller_id") or ""))
            if key in seller_map:
                continue
            until_at = _parse_timestamp(current.get("frozen_until"))
            if until_at is None or until_at > now:
                continue
            next_state = repo.upsert_seller_control_state(
                source=key[0],
                seller_id=key[1],
                state="normal",
                reason="seller control expired",
                frozen_until=None,
                metadata=current.get("metadata") or {},
            )
            repo.create_seller_control_event(
                source=key[0],
                seller_id=key[1],
                event_type="auto_unfreeze",
                reason="seller control expired",
                previous_state=current,
                next_state=next_state,
            )
            unfrozen.append(next_state)

        return {
            "enabled": True,
            "frozen": frozen,
            "unfrozen": unfrozen,
            "status": self.status_summary(),
        }

    def apply_manual_action(
        self,
        *,
        source: str,
        seller_id: str,
        action: Literal["freeze", "observe", "normal"],
        reason: str = "",
        actor: str = "operator",
        duration_hours: int | None = None,
    ) -> dict[str, Any]:
        normalized_source = str(source or "").strip()
        normalized_seller = str(seller_id or "").strip()
        if not normalized_source or not normalized_seller:
            raise ValueError("source and seller_id are required")

        current = repo.get_seller_control_state(normalized_source, normalized_seller)
        now = datetime.now(timezone.utc)
        metadata = {
            **(current.get("metadata") or {} if current else {}),
            "manual_action": action,
            "manual_actor": str(actor or "operator").strip() or "operator",
        }

        if action == "freeze":
            hours = max(1, int(duration_hours or settings.auto_approve_seller_freeze_hours))
            next_state = repo.upsert_seller_control_state(
                source=normalized_source,
                seller_id=normalized_seller,
                state="frozen",
                reason=reason or "manual freeze",
                frozen_until=(now + timedelta(hours=hours)).isoformat(),
                metadata=metadata,
            )
            event_type = "manual_freeze"
        elif action == "observe":
            hours = max(1, int(duration_hours or settings.auto_approve_seller_observe_hours))
            next_state = repo.upsert_seller_control_state(
                source=normalized_source,
                seller_id=normalized_seller,
                state="observe",
                reason=reason or "manual observe",
                frozen_until=(now + timedelta(hours=hours)).isoformat(),
                metadata=metadata,
            )
            event_type = "manual_observe"
        else:
            next_state = repo.upsert_seller_control_state(
                source=normalized_source,
                seller_id=normalized_seller,
                state="normal",
                reason=reason or "manual restore",
                frozen_until=None,
                metadata=metadata,
            )
            event_type = "manual_restore"

        event = repo.create_seller_control_event(
            source=normalized_source,
            seller_id=normalized_seller,
            event_type=event_type,
            reason=reason or event_type.replace("_", " "),
            previous_state=current,
            next_state=next_state,
        )
        return {
            "ok": True,
            "source": normalized_source,
            "seller_id": normalized_seller,
            "action": action,
            "state": next_state,
            "event": event,
            "status": self.status_summary(),
        }

    def apply_manual_action_batch(
        self,
        *,
        items: list[dict[str, Any]],
        action: Literal["freeze", "observe", "normal"],
        reason: str = "",
        actor: str = "operator",
        duration_hours: int | None = None,
    ) -> dict[str, Any]:
        results: list[dict[str, Any]] = []
        seen: set[tuple[str, str]] = set()
        for item in items:
            source = str((item or {}).get("source") or "").strip()
            seller_id = str((item or {}).get("seller_id") or "").strip()
            if not source or not seller_id:
                continue
            key = (source, seller_id)
            if key in seen:
                continue
            seen.add(key)
            results.append(
                self.apply_manual_action(
                    source=source,
                    seller_id=seller_id,
                    action=action,
                    reason=reason,
                    actor=actor,
                    duration_hours=duration_hours,
                )
            )
        return {
            "ok": True,
            "action": action,
            "processed": len(results),
            "items": results,
            "status": self.status_summary(),
        }


seller_controls_service = SellerControlsService()
