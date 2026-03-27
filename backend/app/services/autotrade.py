from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from .. import repositories as repo
from ..config import settings
from ..errors import BusyStateError
from .execution import execution_service
from .seller_controls import seller_controls_service


def _parse_risk_score(note: str) -> float | None:
    text = (note or "").strip()
    if not text:
        return None
    for part in text.split(";"):
        seg = part.strip()
        if not seg.startswith("risk_score="):
            continue
        _, value = seg.split("=", 1)
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


class AutoTradeService:
    """Background auto-approval service for pending opportunities."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._running = False
        self._last_run_at = ""
        self._last_error = ""
        self._last_busy_at = ""
        self._last_busy_reason = ""
        self._total_runs = 0
        self._total_approved = 0
        self._interval_sec = max(5, int(settings.auto_approve_interval_sec))
        self._batch_size = max(1, int(settings.auto_approve_batch_size))
        self._min_score = float(settings.auto_approve_min_score)
        self._min_roi = float(settings.auto_approve_min_roi)
        self._max_risk_score = float(settings.auto_approve_max_risk_score)
        self._require_risk_score = bool(settings.auto_approve_require_risk_score)
        self._auto_execute_buy_on_approve = bool(settings.auto_execute_buy_on_approve)
        self._auto_execute_buy_dry_run = bool(settings.auto_execute_buy_dry_run)
        self._auto_execute_list_on_buy_success = bool(settings.auto_execute_list_on_buy_success)
        self._auto_execute_list_dry_run = bool(settings.auto_execute_list_dry_run)
        self._max_consecutive_losses = max(0, int(settings.auto_approve_max_consecutive_losses))
        self._daily_loss_limit = max(0.0, float(settings.auto_approve_daily_loss_limit))
        self._loss_recovery_enabled = bool(settings.auto_approve_loss_recovery_enabled)
        self._loss_recovery_cooldown_hours = max(
            0,
            int(settings.auto_approve_loss_recovery_cooldown_hours),
        )
        self._tuning_auto_apply_enabled = bool(settings.auto_tune_auto_apply_enabled)
        self._tuning_cooldown_hours = max(0, int(settings.auto_tune_cooldown_hours))
        self._tuning_min_closed_batches = max(1, int(settings.auto_tune_min_closed_batches))
        self._tuning_latest_min_sold_count = max(1, int(settings.auto_tune_latest_min_sold_count))
        self._tuning_previous_min_sold_count = max(1, int(settings.auto_tune_previous_min_sold_count))

    def update_config(
        self,
        *,
        interval_sec: int | None = None,
        batch_size: int | None = None,
        min_score: float | None = None,
        min_roi: float | None = None,
        max_risk_score: float | None = None,
        require_risk_score: bool | None = None,
        auto_execute_buy_on_approve: bool | None = None,
        auto_execute_buy_dry_run: bool | None = None,
        auto_execute_list_on_buy_success: bool | None = None,
        auto_execute_list_dry_run: bool | None = None,
        max_consecutive_losses: int | None = None,
        daily_loss_limit: float | None = None,
        loss_recovery_enabled: bool | None = None,
        loss_recovery_cooldown_hours: int | None = None,
        tuning_auto_apply_enabled: bool | None = None,
        tuning_cooldown_hours: int | None = None,
        tuning_min_closed_batches: int | None = None,
        tuning_latest_min_sold_count: int | None = None,
        tuning_previous_min_sold_count: int | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if interval_sec is not None:
                self._interval_sec = max(5, min(3600, int(interval_sec)))
            if batch_size is not None:
                self._batch_size = max(1, min(500, int(batch_size)))
            if min_score is not None:
                self._min_score = max(0.0, min(100.0, float(min_score)))
            if min_roi is not None:
                self._min_roi = max(0.0, min(10.0, float(min_roi)))
            if max_risk_score is not None:
                self._max_risk_score = max(0.0, min(100.0, float(max_risk_score)))
            if require_risk_score is not None:
                self._require_risk_score = bool(require_risk_score)
            if auto_execute_buy_on_approve is not None:
                self._auto_execute_buy_on_approve = bool(auto_execute_buy_on_approve)
            if auto_execute_buy_dry_run is not None:
                self._auto_execute_buy_dry_run = bool(auto_execute_buy_dry_run)
            if auto_execute_list_on_buy_success is not None:
                self._auto_execute_list_on_buy_success = bool(auto_execute_list_on_buy_success)
            if auto_execute_list_dry_run is not None:
                self._auto_execute_list_dry_run = bool(auto_execute_list_dry_run)
            if max_consecutive_losses is not None:
                self._max_consecutive_losses = max(0, min(20, int(max_consecutive_losses)))
            if daily_loss_limit is not None:
                self._daily_loss_limit = max(0.0, min(1000000.0, float(daily_loss_limit)))
            if loss_recovery_enabled is not None:
                self._loss_recovery_enabled = bool(loss_recovery_enabled)
            if loss_recovery_cooldown_hours is not None:
                self._loss_recovery_cooldown_hours = max(
                    0,
                    min(24 * 365, int(loss_recovery_cooldown_hours)),
                )
            if tuning_auto_apply_enabled is not None:
                self._tuning_auto_apply_enabled = bool(tuning_auto_apply_enabled)
            if tuning_cooldown_hours is not None:
                self._tuning_cooldown_hours = max(0, min(24 * 365, int(tuning_cooldown_hours)))
            if tuning_min_closed_batches is not None:
                self._tuning_min_closed_batches = max(1, min(10, int(tuning_min_closed_batches)))
            if tuning_latest_min_sold_count is not None:
                self._tuning_latest_min_sold_count = max(1, min(100, int(tuning_latest_min_sold_count)))
            if tuning_previous_min_sold_count is not None:
                self._tuning_previous_min_sold_count = max(1, min(100, int(tuning_previous_min_sold_count)))
        return self.status()

    def tuning_snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "min_score": self._min_score,
                "min_roi": self._min_roi,
                "max_risk_score": self._max_risk_score,
                "require_risk_score": self._require_risk_score,
            }

    def tuning_policy(self) -> dict[str, Any]:
        with self._lock:
            return {
                "auto_apply_enabled": self._tuning_auto_apply_enabled,
                "cooldown_hours": self._tuning_cooldown_hours,
                "min_closed_batches": self._tuning_min_closed_batches,
                "latest_min_sold_count": self._tuning_latest_min_sold_count,
                "previous_min_sold_count": self._tuning_previous_min_sold_count,
            }

    def list_tuning_history(self, limit: int = 30) -> list[dict[str, Any]]:
        return repo.list_autotrade_tuning_events(limit=limit)

    def list_tuning_activity(self, limit: int = 50) -> list[dict[str, Any]]:
        return repo.list_autotrade_tuning_activity(limit=limit)

    def tuning_daily_report(self, hours: int = 24) -> dict[str, Any]:
        return repo.get_autotrade_tuning_daily_report(hours=hours)

    def _record_tuning_activity(
        self,
        *,
        decision_type: str,
        trigger_source: str,
        actor: str,
        summary: str,
        details: dict[str, Any] | None = None,
        related_event_id: int | None = None,
    ) -> dict[str, Any]:
        return repo.create_autotrade_tuning_activity(
            decision_type=decision_type,
            trigger_source=trigger_source,
            actor=actor,
            summary=summary,
            details=details,
            related_event_id=related_event_id,
        )

    def apply_tuning(
        self,
        *,
        source: str,
        applied_by: str,
        note: str = "",
        decision_type: str = "tuning_applied",
        min_score: float | None = None,
        min_roi: float | None = None,
        max_risk_score: float | None = None,
        require_risk_score: bool | None = None,
        rollback_of_event_id: int | None = None,
    ) -> dict[str, Any]:
        previous_config = self.tuning_snapshot()
        status = self.update_config(
            min_score=min_score,
            min_roi=min_roi,
            max_risk_score=max_risk_score,
            require_risk_score=require_risk_score,
        )
        event = repo.create_autotrade_tuning_event(
            source=source,
            applied_by=applied_by,
            note=note,
            previous_config=previous_config,
            next_config=self.tuning_snapshot(),
            rollback_of_event_id=rollback_of_event_id,
        )
        self._record_tuning_activity(
            decision_type=decision_type,
            trigger_source=source,
            actor=applied_by,
            summary=note or decision_type,
            details={
                "previous_config": previous_config,
                "next_config": self.tuning_snapshot(),
                "rollback_of_event_id": rollback_of_event_id,
            },
            related_event_id=int(event["id"]),
        )
        return {
            "status": status,
            "event": event,
        }

    def rollback_tuning_event(
        self,
        *,
        event_id: int,
        applied_by: str,
        note: str = "",
        source: str = "rollback",
    ) -> dict[str, Any]:
        target_event = repo.get_autotrade_tuning_event(event_id)
        if not target_event:
            raise ValueError("autotrade tuning event not found")
        previous_config = target_event.get("previous_config") or {}
        return self.apply_tuning(
            source=source,
            applied_by=applied_by,
            note=note or f"rollback event #{event_id}",
            decision_type="tuning_rollback",
            min_score=previous_config.get("min_score"),
            min_roi=previous_config.get("min_roi"),
            max_risk_score=previous_config.get("max_risk_score"),
            require_risk_score=previous_config.get("require_risk_score"),
            rollback_of_event_id=event_id,
        )

    @staticmethod
    def _round_tune_float(value: float, digits: int = 4) -> float:
        return round(float(value or 0.0), digits)

    def _build_tuning_proposal(
        self,
        source: dict[str, Any] | None,
        current_config: dict[str, Any],
    ) -> dict[str, Any] | None:
        if not source:
            return None

        sold_count = int(source.get("sold_count") or 0)
        hit_rate = float(source.get("profit_hit_rate") or 0.0)
        avg_roi = float(source.get("avg_realized_roi") or 0.0)
        holding_days = float(source.get("avg_holding_days") or 0.0)
        recent_net_profit = float(source.get("realized_net_profit") or 0.0)

        source_id = source.get("id")
        source_name = source.get("name") or f"batch #{source_id or '-'}"
        current = {
            "min_score": float(current_config.get("min_score") or 0.0),
            "min_roi": float(current_config.get("min_roi") or 0.0),
            "max_risk_score": float(current_config.get("max_risk_score") or 0.0),
        }
        next_config = dict(current)
        reasons = [
            f"Source {source_name}",
            f"Sold {sold_count}",
            f"Hit {hit_rate:.2%}",
            f"ROI {avg_roi:.2%}",
            f"Hold {holding_days:.1f}d",
        ]

        title = "Hold current thresholds"
        summary = "Validation does not justify threshold changes yet."
        tag_type = "info"
        direction = "hold"

        if sold_count < 3:
            return {
                "title": "Need more sold samples",
                "summary": (
                    "Wait until this validation set has at least 3 sold trades before "
                    "micro-tuning thresholds."
                ),
                "tag_type": tag_type,
                "direction": direction,
                "reasons": reasons,
                "source_name": source_name,
                "source_id": source_id,
                "should_apply": False,
                "current": current,
                "next": dict(current),
                "delta": {
                    "min_score": 0.0,
                    "min_roi": 0.0,
                    "max_risk_score": 0.0,
                },
            }

        if recent_net_profit < 0 or hit_rate < 0.4 or avg_roi < 0:
            next_config["min_score"] = max(0.0, min(100.0, current["min_score"] + 4))
            next_config["min_roi"] = max(0.0, min(3.0, current["min_roi"] + 0.02))
            next_config["max_risk_score"] = max(0.0, min(100.0, current["max_risk_score"] - 5))
            title = "Tighten entry quality"
            summary = (
                "Validation is underperforming. Raise score/ROI gates and reduce tolerated risk."
            )
            tag_type = "warning"
            direction = "tighten"
        elif hit_rate >= 0.65 and avg_roi >= 0.12 and 0 < holding_days <= 5:
            next_config["min_score"] = max(0.0, min(100.0, current["min_score"] - 4))
            next_config["min_roi"] = max(0.0, min(3.0, current["min_roi"] - 0.015))
            next_config["max_risk_score"] = max(0.0, min(100.0, current["max_risk_score"] + 4))
            title = "Widen the funnel"
            summary = "This batch is clearing quickly with healthy ROI. You can admit more candidates."
            tag_type = "success"
            direction = "widen"
        elif holding_days >= 10 and avg_roi < 0.08:
            next_config["min_score"] = max(0.0, min(100.0, current["min_score"] + 2))
            next_config["min_roi"] = max(0.0, min(3.0, current["min_roi"] + 0.01))
            next_config["max_risk_score"] = max(0.0, min(100.0, current["max_risk_score"] - 3))
            title = "Protect capital turnover"
            summary = (
                "Holding time is too long for the realized ROI. Slightly tighten the entry gate."
            )
            tag_type = "warning"
            direction = "tighten"
        elif hit_rate >= 0.55 and avg_roi >= 0.08 and 0 < holding_days <= 7:
            next_config["min_score"] = max(0.0, min(100.0, current["min_score"] - 2))
            next_config["min_roi"] = max(0.0, min(3.0, current["min_roi"] - 0.005))
            next_config["max_risk_score"] = max(0.0, min(100.0, current["max_risk_score"] + 2))
            title = "Small aggressive nudge"
            summary = (
                "Validation is healthy. A modest widening should increase throughput without changing regime."
            )
            tag_type = "success"
            direction = "widen"

        delta = {
            "min_score": self._round_tune_float(next_config["min_score"] - current["min_score"], 0),
            "min_roi": self._round_tune_float(next_config["min_roi"] - current["min_roi"], 4),
            "max_risk_score": self._round_tune_float(
                next_config["max_risk_score"] - current["max_risk_score"],
                0,
            ),
        }
        should_apply = any(abs(float(value or 0.0)) > 0 for value in delta.values())

        return {
            "title": title,
            "summary": summary,
            "tag_type": tag_type,
            "direction": direction,
            "reasons": reasons,
            "source_name": source_name,
            "source_id": source_id,
            "should_apply": should_apply,
            "current": current,
            "next": {
                "min_score": self._round_tune_float(next_config["min_score"], 0),
                "min_roi": self._round_tune_float(next_config["min_roi"], 4),
                "max_risk_score": self._round_tune_float(next_config["max_risk_score"], 0),
            },
            "delta": delta,
        }

    @staticmethod
    def _parse_event_created_at(event: dict[str, Any]) -> datetime | None:
        raw = str(event.get("created_at") or "").strip()
        if not raw:
            return None
        normalized = raw.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    def evaluate_auto_tune(self) -> dict[str, Any]:
        policy = self.tuning_policy()
        current_config = self.tuning_snapshot()
        report = repo.get_dashboard_metrics()
        forward_validation = report.get("forward_validation") or {}
        recent_batches = (
            list(forward_validation.get("recent_batches") or [])
            if isinstance(forward_validation, dict)
            else []
        )
        active_batch = (
            forward_validation.get("active_batch")
            if isinstance(forward_validation, dict)
            else None
        )

        source = next(
            (batch for batch in recent_batches if str(batch.get("status") or "") == "closed"),
            None,
        ) or active_batch
        proposal = self._build_tuning_proposal(source, current_config)
        reasons: list[str] = []

        if not proposal:
            reasons.append("No validation batch available")
        else:
            if not proposal.get("should_apply"):
                reasons.append("Current batch does not justify a threshold change")

            closed_batches = [
                batch for batch in recent_batches if str(batch.get("status") or "") == "closed"
            ]
            required_batches = max(1, int(policy["min_closed_batches"]))
            if len(closed_batches) < required_batches:
                reasons.append(
                    f"Need {required_batches} closed validation batches before applying auto-tune"
                )
            else:
                latest_sold = int(closed_batches[0].get("sold_count") or 0)
                if latest_sold < int(policy["latest_min_sold_count"]):
                    reasons.append(
                        f"Latest closed batch needs at least {int(policy['latest_min_sold_count'])} sold trades"
                    )

                if required_batches >= 2:
                    previous_sold = int(closed_batches[1].get("sold_count") or 0)
                    if previous_sold < int(policy["previous_min_sold_count"]):
                        reasons.append(
                            f"Previous closed batch needs at least {int(policy['previous_min_sold_count'])} sold trades"
                        )

                direction_samples = closed_batches[:required_batches]
                directions = {
                    str(
                        (self._build_tuning_proposal(batch, current_config) or {}).get("direction")
                        or "hold"
                    )
                    for batch in direction_samples
                }
                if len(directions) > 1:
                    reasons.append(
                        f"Last {required_batches} closed batches disagree on direction"
                    )

            latest_event = next(iter(repo.list_autotrade_tuning_events(limit=1)), None)
            if latest_event:
                latest_at = self._parse_event_created_at(latest_event)
                if latest_at is not None:
                    elapsed_hours = (
                        datetime.now(timezone.utc) - latest_at
                    ).total_seconds() / 3600.0
                    cooldown_hours = float(policy["cooldown_hours"])
                    if elapsed_hours < cooldown_hours:
                        reasons.append(
                            f"Cooldown active for another {max(0.0, cooldown_hours - elapsed_hours):.1f}h"
                        )

        return {
            "policy": policy,
            "proposal": proposal,
            "guard": {
                "ready": len(reasons) == 0,
                "reasons": reasons if reasons else ["Guardrails passed"],
            },
        }

    def maybe_auto_apply_tuning(self, *, trigger_source: str, applied_by: str) -> dict[str, Any]:
        evaluation = self.evaluate_auto_tune()
        policy = evaluation["policy"]
        if not policy["auto_apply_enabled"]:
            self._record_tuning_activity(
                decision_type="auto_tune_disabled",
                trigger_source=trigger_source,
                actor=applied_by,
                summary="Auto-tune auto-apply is disabled",
                details={
                    "policy": policy,
                    "guard_reasons": [],
                    "proposal": evaluation.get("proposal"),
                },
            )
            return {
                "enabled": False,
                "applied": False,
                "reason": "auto_apply_disabled",
                "evaluation": evaluation,
            }
        if not evaluation["guard"]["ready"]:
            self._record_tuning_activity(
                decision_type="auto_tune_blocked",
                trigger_source=trigger_source,
                actor=applied_by,
                summary="Auto-tune blocked by guardrails",
                details={
                    "policy": policy,
                    "guard_reasons": evaluation["guard"]["reasons"],
                    "proposal": evaluation.get("proposal"),
                },
            )
            return {
                "enabled": True,
                "applied": False,
                "reason": "guard_blocked",
                "evaluation": evaluation,
            }
        proposal = evaluation.get("proposal") or {}
        result = self.apply_tuning(
            source=trigger_source,
            applied_by=applied_by,
            note=f"{proposal.get('title') or 'auto tune'}; {proposal.get('source_name') or ''}".strip(),
            decision_type="auto_tune_applied",
            min_score=(proposal.get("next") or {}).get("min_score"),
            min_roi=(proposal.get("next") or {}).get("min_roi"),
            max_risk_score=(proposal.get("next") or {}).get("max_risk_score"),
            require_risk_score=self.tuning_snapshot().get("require_risk_score"),
        )
        return {
            "enabled": True,
            "applied": True,
            "event": result.get("event"),
            "status": result.get("status"),
            "evaluation": evaluation,
        }

    def status(self) -> dict[str, Any]:
        with self._lock:
            snapshot = {
                "enabled": settings.auto_approve_enabled,
                "running": self._running,
                "busy": self._run_lock.locked(),
                "interval_sec": self._interval_sec,
                "batch_size": self._batch_size,
                "min_score": self._min_score,
                "min_roi": self._min_roi,
                "max_risk_score": self._max_risk_score,
                "require_risk_score": self._require_risk_score,
                "approved_by": settings.auto_approve_approved_by,
                "auto_execute_buy_on_approve": self._auto_execute_buy_on_approve,
                "auto_execute_buy_dry_run": self._auto_execute_buy_dry_run,
                "auto_execute_list_on_buy_success": self._auto_execute_list_on_buy_success,
                "auto_execute_list_dry_run": self._auto_execute_list_dry_run,
                "max_consecutive_losses": self._max_consecutive_losses,
                "daily_loss_limit": self._daily_loss_limit,
                "loss_recovery_enabled": self._loss_recovery_enabled,
                "loss_recovery_cooldown_hours": self._loss_recovery_cooldown_hours,
                "tuning_auto_apply_enabled": self._tuning_auto_apply_enabled,
                "tuning_cooldown_hours": self._tuning_cooldown_hours,
                "tuning_min_closed_batches": self._tuning_min_closed_batches,
                "tuning_latest_min_sold_count": self._tuning_latest_min_sold_count,
                "tuning_previous_min_sold_count": self._tuning_previous_min_sold_count,
                "last_run_at": self._last_run_at,
                "last_error": self._last_error,
                "last_busy_at": self._last_busy_at,
                "last_busy_reason": self._last_busy_reason,
                "total_runs": self._total_runs,
                "total_approved": self._total_approved,
            }
        dashboard_metrics = repo.get_dashboard_metrics()
        seller_control_sync = seller_controls_service.sync_from_metrics(metrics=dashboard_metrics)
        snapshot["profit_guard"] = self._profit_guard_snapshot(
            max_consecutive_losses=int(snapshot["max_consecutive_losses"]),
            daily_loss_limit=float(snapshot["daily_loss_limit"]),
            metrics=dashboard_metrics,
        )
        try:
            pending_rows = repo.list_opportunities(
                status="pending_review",
                limit=max(50, int(snapshot["batch_size"]) * 5),
            )
        except Exception:
            pending_rows = []
        source_strategy_map = self._source_strategy_map(dashboard_metrics)
        seller_strategy_map = self._seller_strategy_map(dashboard_metrics)
        _, position_controls = self._build_source_position_controls(
            int(snapshot["batch_size"]),
            source_strategy_map,
            pending_rows,
        )
        _, seller_position_controls = self._build_seller_position_controls(
            int(snapshot["batch_size"]),
            seller_strategy_map,
            pending_rows,
        )
        snapshot["source_position_controls"] = position_controls[:5]
        snapshot["seller_position_controls"] = seller_position_controls[:8]
        snapshot["seller_controls"] = seller_control_sync.get("status") or {}
        snapshot["seller_control_presets"] = repo.list_seller_control_presets(limit=20)
        snapshot["loss_recovery_state"] = {
            "enabled": bool(snapshot["loss_recovery_enabled"]),
            "active": False,
            "event_id": None,
            "source": "",
        }
        active_recovery_event = self._active_loss_recovery_event(
            {
                "min_score": snapshot["min_score"],
                "min_roi": snapshot["min_roi"],
                "max_risk_score": snapshot["max_risk_score"],
                "require_risk_score": snapshot["require_risk_score"],
            },
        )
        if active_recovery_event:
            snapshot["loss_recovery_state"] = {
                "enabled": bool(snapshot["loss_recovery_enabled"]),
                "active": True,
                "event_id": int(active_recovery_event.get("id") or 0) or None,
                "source": str(active_recovery_event.get("source") or ""),
            }
        return snapshot

    def guard_status(self) -> dict[str, Any]:
        with self._lock:
            busy = self._run_lock.locked()
            last_busy_at = self._last_busy_at
            last_busy_reason = self._last_busy_reason
        profit_guard = self._profit_guard_snapshot()
        return {
            "service": "autotrade",
            "busy": busy,
            "last_busy_at": last_busy_at,
            "last_busy_reason": last_busy_reason,
            "profit_guard_blocked": bool(profit_guard["blocked"]),
            "profit_guard_reasons": list(profit_guard["reasons"]),
        }

    def _mark_busy(self, reason: str) -> None:
        with self._lock:
            self._last_busy_at = datetime.now(timezone.utc).isoformat()
            self._last_busy_reason = reason

    def _profit_guard_snapshot(
        self,
        *,
        max_consecutive_losses: int | None = None,
        daily_loss_limit: float | None = None,
        metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if max_consecutive_losses is None or daily_loss_limit is None:
            with self._lock:
                max_consecutive_losses = self._max_consecutive_losses
                daily_loss_limit = self._daily_loss_limit

        metrics = metrics or repo.get_dashboard_metrics()
        cockpit = metrics.get("profit_cockpit") or {}
        today = cockpit.get("today") or {}
        last_7d = cockpit.get("last_7d") or {}
        loss_streak = cockpit.get("loss_streak") or {}

        current_losses = int(loss_streak.get("current_consecutive_losses") or 0)
        today_net_profit = float(today.get("realized_net_profit") or 0.0)
        reasons: list[str] = []

        if max_consecutive_losses > 0 and current_losses >= max_consecutive_losses:
            reasons.append(
                f"Loss streak reached {current_losses} trades (limit {max_consecutive_losses})"
            )
        if daily_loss_limit > 0 and today_net_profit <= -abs(daily_loss_limit):
            reasons.append(
                f"Today's realized net profit dropped to {today_net_profit:.2f} (limit -{abs(daily_loss_limit):.2f})"
            )

        return {
            "enabled": bool(max_consecutive_losses > 0 or daily_loss_limit > 0),
            "blocked": bool(reasons),
            "reasons": reasons,
            "max_consecutive_losses": int(max_consecutive_losses),
            "daily_loss_limit": round(float(daily_loss_limit or 0.0), 2),
            "current_consecutive_losses": current_losses,
            "current_loss_total": float(loss_streak.get("current_loss_total") or 0.0),
            "today_realized_net_profit": round(today_net_profit, 2),
            "today_sold_count": int(today.get("sold_count") or 0),
            "last_7d_realized_net_profit": round(float(last_7d.get("realized_net_profit") or 0.0), 2),
            "best_source_7d": cockpit.get("best_source_7d"),
            "weakest_source_7d": cockpit.get("weakest_source_7d"),
        }

    @staticmethod
    def _source_strategy_map(metrics: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        cockpit = (metrics or {}).get("profit_cockpit") or {}
        items = list(cockpit.get("source_leaderboard_7d") or [])
        return {
            str(item.get("source") or "").strip(): item
            for item in items
            if str(item.get("source") or "").strip()
        }

    @staticmethod
    def _seller_strategy_map(metrics: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
        cockpit = (metrics or {}).get("profit_cockpit") or {}
        items = list(cockpit.get("seller_leaderboard_7d") or [])
        return {
            str(item.get("seller_key") or "").strip(): item
            for item in items
            if str(item.get("seller_key") or "").strip()
        }

    @staticmethod
    def _build_source_position_controls(
        batch_limit: int,
        source_strategy_map: dict[str, dict[str, Any]],
        candidate_rows: list[Any],
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in candidate_rows:
            source = str(row["source"] or "unknown").strip() or "unknown"
            bucket = grouped.setdefault(
                source,
                {
                    "source": source,
                    "pending_count": 0,
                    "list_price_total": 0.0,
                },
            )
            bucket["pending_count"] += 1
            bucket["list_price_total"] += float(row["list_price"] or 0.0)

        controls: dict[str, dict[str, Any]] = {}
        items: list[dict[str, Any]] = []
        normalized_batch_limit = max(1, int(batch_limit or 1))
        for source, bucket in grouped.items():
            strategy = source_strategy_map.get(source, {})
            intake_multiplier = float(strategy.get("intake_multiplier") or 1.0)
            pending_count = int(bucket["pending_count"] or 0)
            avg_list_price = (
                float(bucket["list_price_total"]) / pending_count if pending_count > 0 else 0.0
            )
            batch_cap = max(
                1,
                min(
                    pending_count,
                    normalized_batch_limit,
                    int(round(normalized_batch_limit * max(0.2, intake_multiplier))),
                ),
            )
            capital_cap = round(
                max(
                    avg_list_price,
                    avg_list_price * batch_cap * max(0.75, intake_multiplier),
                ),
                2,
            )
            item = {
                "source": source,
                "strategy_mode": str(strategy.get("strategy_mode") or "hold"),
                "strategy_summary": str(strategy.get("strategy_summary") or ""),
                "intake_multiplier": round(intake_multiplier, 2),
                "batch_cap": batch_cap,
                "capital_cap": capital_cap,
                "pending_count": pending_count,
                "avg_list_price": round(avg_list_price, 2),
                "realized_net_profit": float(strategy.get("realized_net_profit") or 0.0),
            }
            controls[source] = item
            items.append(item)

        items.sort(
            key=lambda item: (
                {"tighten": 0, "hold": 1, "widen": 2}.get(str(item["strategy_mode"]), 1),
                float(item["realized_net_profit"]),
                int(item["pending_count"]),
            ),
            reverse=True,
        )
        return controls, items

    @staticmethod
    def _build_seller_position_controls(
        batch_limit: int,
        seller_strategy_map: dict[str, dict[str, Any]],
        candidate_rows: list[Any],
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        grouped: dict[str, dict[str, Any]] = {}
        for row in candidate_rows:
            source = str(row["source"] or "unknown").strip() or "unknown"
            try:
                seller_raw = row["seller_id"]
            except Exception:
                seller_raw = row.get("seller_id") if isinstance(row, dict) else ""
            seller_id = str(seller_raw or "").strip()
            if not seller_id:
                continue
            seller_key = f"{source}::{seller_id}"
            bucket = grouped.setdefault(
                seller_key,
                {
                    "source": source,
                    "seller_id": seller_id,
                    "seller_key": seller_key,
                    "pending_count": 0,
                    "list_price_total": 0.0,
                },
            )
            bucket["pending_count"] += 1
            bucket["list_price_total"] += float(row["list_price"] or 0.0)

        controls: dict[str, dict[str, Any]] = {}
        items: list[dict[str, Any]] = []
        normalized_batch_limit = max(1, int(batch_limit or 1))
        for seller_key, bucket in grouped.items():
            strategy = seller_strategy_map.get(seller_key, {})
            intake_multiplier = float(strategy.get("intake_multiplier") or 1.0)
            pending_count = int(bucket["pending_count"] or 0)
            avg_list_price = (
                float(bucket["list_price_total"]) / pending_count if pending_count > 0 else 0.0
            )
            seller_lane = str(strategy.get("seller_lane") or "neutral")
            if seller_lane == "blacklist":
                batch_cap = 0
                capital_cap = 0.0
            else:
                batch_cap = max(
                    1,
                    min(
                        pending_count,
                        normalized_batch_limit,
                        int(round(normalized_batch_limit * max(0.2, intake_multiplier))),
                    ),
                )
                capital_cap = round(
                    max(
                        avg_list_price,
                        avg_list_price * batch_cap * max(0.75, intake_multiplier),
                    ),
                    2,
                )
            item = {
                "source": str(bucket["source"]),
                "seller_id": str(bucket["seller_id"]),
                "seller_key": seller_key,
                "seller_lane": seller_lane,
                "lane_summary": str(strategy.get("lane_summary") or ""),
                "intake_multiplier": round(intake_multiplier, 2),
                "batch_cap": batch_cap,
                "capital_cap": capital_cap,
                "pending_count": pending_count,
                "avg_list_price": round(avg_list_price, 2),
                "realized_net_profit": float(strategy.get("realized_net_profit") or 0.0),
                "reputation_score": float(strategy.get("reputation_score") or 0.0),
            }
            controls[seller_key] = item
            items.append(item)

        items.sort(
            key=lambda item: (
                {"blacklist": 0, "neutral": 1, "whitelist": 2}.get(str(item["seller_lane"]), 1),
                float(item["realized_net_profit"]),
                int(item["pending_count"]),
            ),
            reverse=True,
        )
        return controls, items

    def _latest_loss_recovery_event(self) -> dict[str, Any] | None:
        events = repo.list_autotrade_tuning_events(limit=20)
        return next(
            (
                event
                for event in events
                if str(event.get("source") or "").strip().startswith("loss_recovery_guard")
            ),
            None,
        )

    def _configs_match(
        self,
        left: dict[str, Any] | None,
        right: dict[str, Any] | None,
    ) -> bool:
        left = left or {}
        right = right or {}
        return (
            self._round_tune_float(float(left.get("min_score") or 0.0), 0)
            == self._round_tune_float(float(right.get("min_score") or 0.0), 0)
            and self._round_tune_float(float(left.get("min_roi") or 0.0), 4)
            == self._round_tune_float(float(right.get("min_roi") or 0.0), 4)
            and self._round_tune_float(float(left.get("max_risk_score") or 0.0), 0)
            == self._round_tune_float(float(right.get("max_risk_score") or 0.0), 0)
            and bool(left.get("require_risk_score")) == bool(right.get("require_risk_score"))
        )

    def _active_loss_recovery_event(
        self,
        current_config: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        current = current_config or self.tuning_snapshot()
        events = repo.list_autotrade_tuning_events(limit=50)
        return next(
            (
                event
                for event in events
                if str(event.get("source") or "").strip().startswith("loss_recovery_guard")
                and self._configs_match(current, event.get("next_config"))
            ),
            None,
        )

    def _maybe_apply_loss_recovery_tuning(
        self,
        *,
        profit_guard: dict[str, Any],
        applied_by: str = "profit_guard_bot",
    ) -> dict[str, Any]:
        with self._lock:
            enabled = self._loss_recovery_enabled
            cooldown_hours = self._loss_recovery_cooldown_hours

        if not enabled:
            return {
                "enabled": False,
                "applied": False,
                "reason": "loss_recovery_disabled",
            }
        if not profit_guard.get("blocked"):
            return {
                "enabled": True,
                "applied": False,
                "reason": "profit_guard_clear",
            }

        latest_event = self._latest_loss_recovery_event()
        if latest_event:
            latest_at = self._parse_event_created_at(latest_event)
            if latest_at is not None:
                elapsed_hours = (
                    datetime.now(timezone.utc) - latest_at
                ).total_seconds() / 3600.0
                if elapsed_hours < cooldown_hours:
                    return {
                        "enabled": True,
                        "applied": False,
                        "reason": "loss_recovery_cooldown",
                        "cooldown_hours_remaining": round(
                            max(0.0, cooldown_hours - elapsed_hours),
                            2,
                        ),
                        "latest_event": latest_event,
                    }

        current = self.tuning_snapshot()
        next_config = {
            "min_score": min(100.0, float(current["min_score"]) + 4.0),
            "min_roi": min(10.0, float(current["min_roi"]) + 0.02),
            "max_risk_score": max(0.0, float(current["max_risk_score"]) - 4.0),
            "require_risk_score": bool(current["require_risk_score"]),
        }

        if (
            float(next_config["min_score"]) == float(current["min_score"])
            and float(next_config["min_roi"]) == float(current["min_roi"])
            and float(next_config["max_risk_score"]) == float(current["max_risk_score"])
        ):
            return {
                "enabled": True,
                "applied": False,
                "reason": "loss_recovery_no_headroom",
            }

        reasons = list(profit_guard.get("reasons") or [])
        note = "Loss recovery tighten"
        if reasons:
            note = f"{note}; {' | '.join(reasons[:2])}"

        result = self.apply_tuning(
            source="loss_recovery_guard",
            applied_by=applied_by,
            note=note,
            decision_type="loss_recovery_tighten",
            min_score=next_config["min_score"],
            min_roi=next_config["min_roi"],
            max_risk_score=next_config["max_risk_score"],
            require_risk_score=next_config["require_risk_score"],
        )
        return {
            "enabled": True,
            "applied": True,
            "event": result.get("event"),
            "status": result.get("status"),
        }

    def _maybe_release_loss_recovery_tuning(
        self,
        *,
        profit_guard: dict[str, Any],
        applied_by: str = "profit_guard_bot",
    ) -> dict[str, Any]:
        with self._lock:
            enabled = self._loss_recovery_enabled
            cooldown_hours = self._loss_recovery_cooldown_hours

        if not enabled:
            return {
                "enabled": False,
                "applied": False,
                "reason": "loss_recovery_disabled",
            }
        if profit_guard.get("blocked"):
            return {
                "enabled": True,
                "applied": False,
                "reason": "profit_guard_blocked",
            }

        current = self.tuning_snapshot()
        active_event = self._active_loss_recovery_event(current)
        if not active_event:
            return {
                "enabled": True,
                "applied": False,
                "reason": "loss_recovery_not_active",
            }

        latest_at = self._parse_event_created_at(active_event)
        if latest_at is not None:
            elapsed_hours = (
                datetime.now(timezone.utc) - latest_at
            ).total_seconds() / 3600.0
            if elapsed_hours < cooldown_hours:
                return {
                    "enabled": True,
                    "applied": False,
                    "reason": "loss_recovery_cooldown",
                    "cooldown_hours_remaining": round(
                        max(0.0, cooldown_hours - elapsed_hours),
                        2,
                    ),
                    "latest_event": active_event,
                }

        current_losses = int(profit_guard.get("current_consecutive_losses") or 0)
        today_net_profit = float(profit_guard.get("today_realized_net_profit") or 0.0)
        last_7d_net_profit = float(profit_guard.get("last_7d_realized_net_profit") or 0.0)
        today_sold_count = int(profit_guard.get("today_sold_count") or 0)
        if current_losses > 0:
            return {
                "enabled": True,
                "applied": False,
                "reason": "loss_streak_not_cleared",
            }
        if today_net_profit <= 0 and (last_7d_net_profit <= 0 or today_sold_count == 0):
            return {
                "enabled": True,
                "applied": False,
                "reason": "recovery_not_confirmed",
            }

        previous_config = active_event.get("previous_config") or {}
        note = "Loss recovery release; profitable flow resumed"
        result = self.apply_tuning(
            source="loss_recovery_release",
            applied_by=applied_by,
            note=note,
            decision_type="loss_recovery_release",
            min_score=previous_config.get("min_score"),
            min_roi=previous_config.get("min_roi"),
            max_risk_score=previous_config.get("max_risk_score"),
            require_risk_score=previous_config.get("require_risk_score"),
            rollback_of_event_id=active_event.get("id"),
        )
        return {
            "enabled": True,
            "applied": True,
            "event": result.get("event"),
            "status": result.get("status"),
        }

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._running:
                return {"started": False, "reason": "already running"}
            if not settings.auto_approve_enabled:
                return {"started": False, "reason": "AUTO_APPROVE_ENABLED=false"}
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="auto-trade-service")
            self._running = True
            self._thread.start()
            return {"started": True}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if not self._running:
                return {"stopped": False, "reason": "not running"}
            self._stop_event.set()
            thread = self._thread
        if thread:
            thread.join(timeout=5)
        with self._lock:
            self._running = False
        return {"stopped": True}

    def run_once(self, limit: int | None = None, force: bool = False) -> dict[str, Any]:
        if not force and not settings.auto_approve_enabled:
            return {
                "enabled": False,
                "approved": 0,
                "reason": "AUTO_APPROVE_ENABLED=false",
            }
        if not self._run_lock.acquire(blocking=False):
            self._mark_busy("run_once_in_progress")
            raise BusyStateError(
                service="autotrade",
                reason="run_once_in_progress",
                message="autotrade run is already in progress",
            )

        try:
            with self._lock:
                configured_batch_size = self._batch_size
                min_score = self._min_score
                min_roi = self._min_roi
                max_risk_score = self._max_risk_score
                require_risk_score = self._require_risk_score
                auto_execute_buy_on_approve = self._auto_execute_buy_on_approve
                auto_execute_buy_dry_run = self._auto_execute_buy_dry_run
                auto_execute_list_on_buy_success = self._auto_execute_list_on_buy_success
                auto_execute_list_dry_run = self._auto_execute_list_dry_run
                max_consecutive_losses = self._max_consecutive_losses
                daily_loss_limit = self._daily_loss_limit
                loss_recovery_enabled = self._loss_recovery_enabled

            batch_limit = configured_batch_size
            if limit is not None:
                batch_limit = max(1, min(500, int(limit)))

            dashboard_metrics = repo.get_dashboard_metrics()
            seller_control_sync = seller_controls_service.sync_from_metrics(metrics=dashboard_metrics)
            profit_guard = self._profit_guard_snapshot(
                max_consecutive_losses=max_consecutive_losses,
                daily_loss_limit=daily_loss_limit,
                metrics=dashboard_metrics,
            )
            source_strategy_map = self._source_strategy_map(dashboard_metrics)
            seller_strategy_map = self._seller_strategy_map(dashboard_metrics)
            if profit_guard["blocked"]:
                loss_recovery = self._maybe_apply_loss_recovery_tuning(
                    profit_guard=profit_guard,
                    applied_by="profit_guard_bot" if loss_recovery_enabled else "operator",
                )
                block_reason = " | ".join(profit_guard["reasons"]) or "profit guard blocked"
                with self._lock:
                    self._last_run_at = datetime.now(timezone.utc).isoformat()
                    self._last_error = block_reason
                    self._total_runs += 1
                return {
                    "enabled": settings.auto_approve_enabled,
                    "approved": 0,
                    "errors": 0,
                    "considered": 0,
                    "batch_limit": batch_limit,
                    "reason": "profit_guard_blocked",
                    "blocked": True,
                    "profit_guard": profit_guard,
                    "loss_recovery": loss_recovery,
                }

            loss_recovery = self._maybe_release_loss_recovery_tuning(
                profit_guard=profit_guard,
                applied_by="profit_guard_bot" if loss_recovery_enabled else "operator",
            )
            if loss_recovery.get("applied"):
                with self._lock:
                    min_score = self._min_score
                    min_roi = self._min_roi
                    max_risk_score = self._max_risk_score
                    require_risk_score = self._require_risk_score

            rows = repo.list_opportunities(status="pending_review", limit=max(50, batch_limit * 5))
            source_position_control_map, source_position_controls = self._build_source_position_controls(
                batch_limit,
                source_strategy_map,
                rows,
            )
            seller_position_control_map, seller_position_controls = self._build_seller_position_controls(
                batch_limit,
                seller_strategy_map,
                rows,
            )
            approved = 0
            skipped_score = 0
            skipped_risk = 0
            skipped_roi = 0
            skipped_missing_risk = 0
            skipped_not_pending = 0
            skipped_source_batch_cap = 0
            skipped_source_capital = 0
            skipped_seller_blacklist = 0
            skipped_seller_batch_cap = 0
            skipped_seller_capital = 0
            idempotent_hits = 0
            errors = 0
            picked_ids: list[int] = []
            source_approved_counts: dict[str, int] = {}
            source_approved_capital: dict[str, float] = {}
            seller_approved_counts: dict[str, int] = {}
            seller_approved_capital: dict[str, float] = {}
            buy_exec_attempted = 0
            buy_exec_succeeded = 0
            buy_exec_failed = 0
            list_exec_attempted = 0
            list_exec_succeeded = 0
            list_exec_failed = 0

            for row in rows:
                if approved >= batch_limit:
                    break
                opportunity_id = int(row["id"])
                source = str(row["source"] or "unknown").strip() or "unknown"
                try:
                    seller_raw = row["seller_id"]
                except Exception:
                    seller_raw = row.get("seller_id") if isinstance(row, dict) else ""
                seller_id = str(seller_raw or "").strip()
                seller_key = f"{source}::{seller_id}" if seller_id else ""
                seller_runtime = seller_controls_service.runtime_control(
                    source=source,
                    seller_id=seller_id,
                )
                if seller_runtime["blocked"]:
                    skipped_seller_blacklist += 1
                    continue
                source_strategy = source_strategy_map.get(source, {})
                seller_strategy = seller_strategy_map.get(seller_key, {})
                threshold_delta = source_strategy.get("threshold_delta") or {}
                seller_threshold_delta = seller_strategy.get("threshold_delta") or {}
                seller_runtime_delta = seller_runtime.get("threshold_delta") or {}
                effective_min_score = max(
                    0.0,
                    min(
                        100.0,
                        min_score
                        + float(threshold_delta.get("min_score") or 0.0)
                        + float(seller_threshold_delta.get("min_score") or 0.0)
                        + float(seller_runtime_delta.get("min_score") or 0.0),
                    ),
                )
                effective_min_roi = max(
                    0.0,
                    min(
                        10.0,
                        min_roi
                        + float(threshold_delta.get("min_roi") or 0.0)
                        + float(seller_threshold_delta.get("min_roi") or 0.0)
                        + float(seller_runtime_delta.get("min_roi") or 0.0),
                    ),
                )
                effective_max_risk_score = max(
                    0.0,
                    min(
                        100.0,
                        max_risk_score
                        + float(threshold_delta.get("max_risk_score") or 0.0)
                        + float(seller_threshold_delta.get("max_risk_score") or 0.0)
                        + float(seller_runtime_delta.get("max_risk_score") or 0.0),
                    ),
                )
                score = float(row["score"])
                roi = float(row["roi"])
                list_price = float(row["list_price"])
                risk_score = _parse_risk_score(str(row["review_note"] or ""))

                if str(seller_strategy.get("seller_lane") or "neutral") == "blacklist":
                    skipped_seller_blacklist += 1
                    continue

                if score < effective_min_score:
                    skipped_score += 1
                    continue
                if roi < effective_min_roi:
                    skipped_roi += 1
                    continue
                if risk_score is None and require_risk_score:
                    skipped_missing_risk += 1
                    continue
                if risk_score is not None and risk_score > effective_max_risk_score:
                    skipped_risk += 1
                    continue

                approved_buy_price = round(max(0.01, list_price), 2)
                position_control = source_position_control_map.get(source) or {
                    "batch_cap": batch_limit,
                    "capital_cap": approved_buy_price * batch_limit,
                }
                current_source_count = int(source_approved_counts.get(source) or 0)
                current_source_capital = float(source_approved_capital.get(source) or 0.0)
                if current_source_count >= int(position_control["batch_cap"]):
                    skipped_source_batch_cap += 1
                    continue
                if current_source_capital + approved_buy_price > float(position_control["capital_cap"]) + 1e-9:
                    skipped_source_capital += 1
                    continue
                seller_position_control = seller_position_control_map.get(seller_key) or {
                    "batch_cap": batch_limit,
                    "capital_cap": approved_buy_price * batch_limit,
                    "seller_lane": "neutral",
                }
                runtime_intake_multiplier = float(seller_runtime.get("intake_multiplier") or 1.0)
                if runtime_intake_multiplier <= 0:
                    skipped_seller_blacklist += 1
                    continue
                seller_position_control = {
                    **seller_position_control,
                    "batch_cap": max(
                        1,
                        min(
                            int(seller_position_control["batch_cap"]),
                            int(
                                round(
                                    int(seller_position_control["batch_cap"])
                                    * runtime_intake_multiplier,
                                )
                            ),
                        ),
                    ),
                    "capital_cap": round(
                        float(seller_position_control["capital_cap"]) * runtime_intake_multiplier,
                        2,
                    ),
                    "seller_lane": (
                        str(seller_runtime.get("state") or "neutral")
                        if str(seller_runtime.get("state") or "normal") != "normal"
                        else str(seller_strategy.get("seller_lane") or "neutral")
                    ),
                }
                current_seller_count = int(seller_approved_counts.get(seller_key) or 0)
                current_seller_capital = float(seller_approved_capital.get(seller_key) or 0.0)
                if current_seller_count >= int(seller_position_control["batch_cap"]):
                    skipped_seller_batch_cap += 1
                    continue
                if current_seller_capital + approved_buy_price > float(seller_position_control["capital_cap"]) + 1e-9:
                    skipped_seller_capital += 1
                    continue
                note = (
                    f"{settings.auto_approve_note}; score={score:.2f}; roi={roi:.4f}; "
                    f"risk_score={risk_score if risk_score is not None else 'na'}; "
                    f"source={source}; source_mode={source_strategy.get('strategy_mode') or 'hold'}; "
                    f"source_min_score={effective_min_score:.0f}; source_min_roi={effective_min_roi:.4f}; "
                    f"source_max_risk={effective_max_risk_score:.0f}; "
                    f"source_batch_cap={int(position_control['batch_cap'])}; "
                    f"source_capital_cap={float(position_control['capital_cap']):.2f}; "
                    f"seller_id={seller_id or 'na'}; "
                    f"seller_lane={seller_position_control.get('seller_lane') or seller_strategy.get('seller_lane') or 'neutral'}; "
                    f"seller_batch_cap={int(seller_position_control['batch_cap'])}; "
                    f"seller_capital_cap={float(seller_position_control['capital_cap']):.2f}"
                )

                try:
                    approval = repo.approve_opportunity_idempotent(
                        opportunity_id=opportunity_id,
                        approved_buy_price=approved_buy_price,
                        approved_by=settings.auto_approve_approved_by,
                        note=note,
                    )
                    if approval.get("idempotent"):
                        idempotent_hits += 1
                        continue
                    if not approval.get("created"):
                        skipped_not_pending += 1
                        continue

                    trade_id = int(approval["trade_id"])
                    approved += 1
                    picked_ids.append(opportunity_id)
                    source_approved_counts[source] = current_source_count + 1
                    source_approved_capital[source] = current_source_capital + approved_buy_price
                    seller_approved_counts[seller_key] = current_seller_count + 1
                    seller_approved_capital[seller_key] = current_seller_capital + approved_buy_price
                    if auto_execute_buy_on_approve:
                        buy_exec_attempted += 1
                        exec_res = execution_service.execute_buy(
                            trade_id=trade_id,
                            dry_run=auto_execute_buy_dry_run,
                        )
                        if exec_res.get("success"):
                            buy_exec_succeeded += 1
                            if auto_execute_list_on_buy_success:
                                list_exec_attempted += 1
                                list_res = execution_service.execute_list(
                                    trade_id=trade_id,
                                    dry_run=auto_execute_list_dry_run,
                                    note="auto listed after buy execution",
                                )
                                if list_res.get("success"):
                                    list_exec_succeeded += 1
                                else:
                                    list_exec_failed += 1
                        else:
                            buy_exec_failed += 1
                except Exception:
                    errors += 1

            with self._lock:
                self._last_run_at = datetime.now(timezone.utc).isoformat()
                self._last_error = "" if errors == 0 else f"errors={errors}"
                self._total_runs += 1
                self._total_approved += approved

            return {
                "enabled": settings.auto_approve_enabled,
                "blocked": False,
                "approved": approved,
                "errors": errors,
                "considered": len(rows),
                "batch_limit": batch_limit,
                "skipped_score": skipped_score,
                "skipped_roi": skipped_roi,
                "skipped_risk": skipped_risk,
                "skipped_missing_risk": skipped_missing_risk,
                "skipped_not_pending": skipped_not_pending,
                "skipped_source_batch_cap": skipped_source_batch_cap,
                "skipped_source_capital": skipped_source_capital,
                "skipped_seller_blacklist": skipped_seller_blacklist,
                "skipped_seller_batch_cap": skipped_seller_batch_cap,
                "skipped_seller_capital": skipped_seller_capital,
                "idempotent_hits": idempotent_hits,
                "opportunity_ids": picked_ids,
                "buy_exec_attempted": buy_exec_attempted,
                "buy_exec_succeeded": buy_exec_succeeded,
                "buy_exec_failed": buy_exec_failed,
                "buy_exec_dry_run": auto_execute_buy_dry_run,
                "list_exec_attempted": list_exec_attempted,
                "list_exec_succeeded": list_exec_succeeded,
                "list_exec_failed": list_exec_failed,
                "list_exec_dry_run": auto_execute_list_dry_run,
                "profit_guard": profit_guard,
                "loss_recovery": loss_recovery,
                "source_strategies": list(source_strategy_map.values())[:5],
                "source_position_controls": source_position_controls[:5],
                "seller_strategies": list(seller_strategy_map.values())[:8],
                "seller_position_controls": seller_position_controls[:8],
                "seller_controls": seller_control_sync.get("status") or {},
            }
        finally:
            self._run_lock.release()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except BusyStateError:
                pass
            except Exception as exc:  # pragma: no cover
                with self._lock:
                    self._last_error = str(exc)
            with self._lock:
                interval_sec = self._interval_sec
            if self._stop_event.wait(timeout=max(5, int(interval_sec))):
                break
        with self._lock:
            self._running = False


auto_trade_service = AutoTradeService()
