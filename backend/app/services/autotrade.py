from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from .. import repositories as repo
from ..config import settings
from ..config import single_account_guardrail_status
from ..errors import BusyStateError
from .autotrade_alerting import (
    alerts_meet_min_severity,
    alert_delivery_lane,
    build_alert_payload,
    dispatch_alert_email,
    dispatch_alert_slack,
    dispatch_alert_telegram,
    dispatch_alert_webhook,
    highest_alert_severity,
    normalize_alert_severity,
)
from .listing_normalizer import TRADABLE_ITEM_TYPES
from .execution import execution_service
from .market_monitor import monitor_service
from .risk_overrides import risk_overrides_service
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
        alert_email_auto_enabled: bool | None = None,
        alert_escalation_minutes: int | None = None,
        alert_ack_timeout_minutes: int | None = None,
        alert_renotify_minutes: int | None = None,
        alert_email_cooldown_minutes: int | None = None,
        alert_email_min_severity: str | None = None,
        alert_webhook_auto_enabled: bool | None = None,
        alert_webhook_cooldown_minutes: int | None = None,
        alert_webhook_min_severity: str | None = None,
        alert_slack_auto_enabled: bool | None = None,
        alert_slack_cooldown_minutes: int | None = None,
        alert_slack_min_severity: str | None = None,
        alert_slack_min_stage: int | None = None,
        alert_telegram_auto_enabled: bool | None = None,
        alert_telegram_cooldown_minutes: int | None = None,
        alert_telegram_min_severity: str | None = None,
        alert_telegram_min_stage: int | None = None,
        source_observe_base_multiplier: float | None = None,
        source_observe_release_streak: int | None = None,
        source_cashout_max_holding_days: float | None = None,
        portfolio_max_deployed_capital: float | None = None,
        max_source_capital_share: float | None = None,
        max_cluster_batch_share: float | None = None,
        max_cluster_capital_share: float | None = None,
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
            if alert_email_auto_enabled is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_email_auto_enabled",
                    bool(alert_email_auto_enabled),
                )
            if alert_escalation_minutes is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_escalation_minutes",
                    max(1, min(24 * 60, int(alert_escalation_minutes))),
                )
            if alert_ack_timeout_minutes is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_ack_timeout_minutes",
                    max(1, min(24 * 60, int(alert_ack_timeout_minutes))),
                )
            if alert_renotify_minutes is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_renotify_minutes",
                    max(1, min(24 * 60, int(alert_renotify_minutes))),
                )
            if alert_email_cooldown_minutes is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_email_cooldown_minutes",
                    max(1, min(24 * 60, int(alert_email_cooldown_minutes))),
                )
            if alert_email_min_severity is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_email_min_severity",
                    normalize_alert_severity(alert_email_min_severity),
                )
            if alert_webhook_auto_enabled is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_webhook_auto_enabled",
                    bool(alert_webhook_auto_enabled),
                )
            if alert_webhook_cooldown_minutes is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_webhook_cooldown_minutes",
                    max(1, min(24 * 60, int(alert_webhook_cooldown_minutes))),
                )
            if alert_webhook_min_severity is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_webhook_min_severity",
                    normalize_alert_severity(alert_webhook_min_severity),
                )
            if alert_slack_auto_enabled is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_slack_auto_enabled",
                    bool(alert_slack_auto_enabled),
                )
            if alert_slack_cooldown_minutes is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_slack_cooldown_minutes",
                    max(1, min(24 * 60, int(alert_slack_cooldown_minutes))),
                )
            if alert_slack_min_severity is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_slack_min_severity",
                    normalize_alert_severity(alert_slack_min_severity),
                )
            if alert_slack_min_stage is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_slack_min_stage",
                    max(1, min(10, int(alert_slack_min_stage))),
                )
            if alert_telegram_auto_enabled is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_telegram_auto_enabled",
                    bool(alert_telegram_auto_enabled),
                )
            if alert_telegram_cooldown_minutes is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_telegram_cooldown_minutes",
                    max(1, min(24 * 60, int(alert_telegram_cooldown_minutes))),
                )
            if alert_telegram_min_severity is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_telegram_min_severity",
                    normalize_alert_severity(alert_telegram_min_severity),
                )
            if alert_telegram_min_stage is not None:
                object.__setattr__(
                    settings,
                    "autotrade_alert_telegram_min_stage",
                    max(1, min(10, int(alert_telegram_min_stage))),
                )
            if source_observe_base_multiplier is not None:
                object.__setattr__(
                    settings,
                    "auto_approve_source_observe_base_multiplier",
                    max(0.05, min(0.6, float(source_observe_base_multiplier))),
                )
            if source_observe_release_streak is not None:
                object.__setattr__(
                    settings,
                    "auto_approve_source_observe_release_streak",
                    max(1, min(50, int(source_observe_release_streak))),
                )
            if source_cashout_max_holding_days is not None:
                object.__setattr__(
                    settings,
                    "auto_approve_source_cashout_max_holding_days",
                    max(0.5, min(90.0, float(source_cashout_max_holding_days))),
                )
            if portfolio_max_deployed_capital is not None:
                object.__setattr__(
                    settings,
                    "auto_approve_portfolio_max_deployed_capital",
                    max(0.0, float(portfolio_max_deployed_capital)),
                )
            if max_source_capital_share is not None:
                object.__setattr__(
                    settings,
                    "auto_approve_max_source_capital_share",
                    max(0.1, min(1.0, float(max_source_capital_share))),
                )
            if max_cluster_batch_share is not None:
                object.__setattr__(
                    settings,
                    "auto_approve_max_cluster_batch_share",
                    max(0.1, min(1.0, float(max_cluster_batch_share))),
                )
            if max_cluster_capital_share is not None:
                object.__setattr__(
                    settings,
                    "auto_approve_max_cluster_capital_share",
                    max(0.1, min(1.0, float(max_cluster_capital_share))),
                )
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
        validation_baseline = self._validation_baseline_snapshot(report)
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

            if bool(settings.single_account_mode) and not bool(validation_baseline.get("ready_for_tune")):
                reasons.append("Single-account observation baseline is not ready")
                reasons.extend(
                    f"Baseline drift: {code}"
                    for code in list(validation_baseline.get("tune_blocking_codes") or [])[:3]
                )

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
            "validation_baseline": validation_baseline,
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
                "alert_email_auto_enabled": bool(settings.autotrade_alert_email_auto_enabled),
                "alert_ack_timeout_minutes": int(settings.autotrade_alert_ack_timeout_minutes),
                "alert_escalation_minutes": int(settings.autotrade_alert_escalation_minutes),
                "alert_renotify_minutes": int(settings.autotrade_alert_renotify_minutes),
                "alert_email_cooldown_minutes": int(settings.autotrade_alert_email_cooldown_minutes),
                "alert_email_min_severity": normalize_alert_severity(
                    settings.autotrade_alert_email_min_severity,
                ),
                "alert_webhook_auto_enabled": bool(settings.autotrade_alert_webhook_auto_enabled),
                "alert_webhook_cooldown_minutes": int(settings.autotrade_alert_webhook_cooldown_minutes),
                "alert_webhook_min_severity": normalize_alert_severity(
                    settings.autotrade_alert_webhook_min_severity,
                ),
                "alert_slack_auto_enabled": bool(settings.autotrade_alert_slack_auto_enabled),
                "alert_slack_cooldown_minutes": int(settings.autotrade_alert_slack_cooldown_minutes),
                "alert_slack_min_severity": normalize_alert_severity(
                    settings.autotrade_alert_slack_min_severity,
                ),
                "alert_slack_min_stage": int(settings.autotrade_alert_slack_min_stage),
                "alert_telegram_auto_enabled": bool(settings.autotrade_alert_telegram_auto_enabled),
                "alert_telegram_cooldown_minutes": int(settings.autotrade_alert_telegram_cooldown_minutes),
                "alert_telegram_min_severity": normalize_alert_severity(
                    settings.autotrade_alert_telegram_min_severity,
                ),
                "alert_telegram_min_stage": int(settings.autotrade_alert_telegram_min_stage),
                "source_observe_base_multiplier": float(settings.auto_approve_source_observe_base_multiplier),
                "source_observe_release_streak": int(settings.auto_approve_source_observe_release_streak),
                "source_cashout_max_holding_days": float(settings.auto_approve_source_cashout_max_holding_days),
                "portfolio_max_deployed_capital": float(settings.auto_approve_portfolio_max_deployed_capital),
                "max_source_capital_share": float(settings.auto_approve_max_source_capital_share),
                "max_cluster_batch_share": float(settings.auto_approve_max_cluster_batch_share),
                "max_cluster_capital_share": float(settings.auto_approve_max_cluster_capital_share),
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
            dashboard_metrics,
        )
        cluster_controls_map, cluster_controls = self._build_cluster_position_controls(
            int(snapshot["batch_size"]),
            pending_rows,
            dashboard_metrics,
        )
        _, seller_position_controls = self._build_seller_position_controls(
            int(snapshot["batch_size"]),
            seller_strategy_map,
            pending_rows,
        )
        snapshot["source_position_controls"] = position_controls[:5]
        snapshot["cluster_position_controls"] = cluster_controls[:5]
        snapshot["seller_position_controls"] = seller_position_controls[:8]
        snapshot["source_overrides"] = risk_overrides_service.source_status_summary()
        snapshot["cluster_overrides"] = risk_overrides_service.cluster_status_summary()
        snapshot["seller_controls"] = seller_control_sync.get("status") or {}
        snapshot["seller_control_presets"] = repo.list_seller_control_presets(limit=20)
        snapshot["validation_baseline"] = self._validation_baseline_snapshot(dashboard_metrics)
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

    def _validation_timeline_point(
        self,
        batch: dict[str, Any],
        *,
        sample_target: int,
        min_hit_rate: float,
        min_avg_roi: float,
        max_avg_holding_days: float,
    ) -> dict[str, Any]:
        sold_count = int(batch.get("sold_count") or 0)
        hit_rate = float(batch.get("profit_hit_rate") or 0.0)
        avg_roi = float(batch.get("avg_realized_roi") or 0.0)
        avg_holding_days = float(batch.get("avg_holding_days") or 0.0)
        realized_net_profit = float(batch.get("realized_net_profit") or 0.0)

        score = 0
        score += 2 if sold_count >= int(sample_target) else -2
        score += 2 if hit_rate >= float(min_hit_rate) else -2
        score += 2 if avg_roi >= float(min_avg_roi) else -2
        score += 1 if 0 < avg_holding_days <= float(max_avg_holding_days) else -1
        score += 1 if realized_net_profit > 0 else -1

        status = "weak"
        status_label = "Weak"
        tag_type = "error"
        if score >= 5:
            status = "strengthening"
            status_label = "Strengthening"
            tag_type = "success"
        elif score >= 2:
            status = "healthy"
            status_label = "Healthy"
            tag_type = "success"
        elif score >= 0:
            status = "mixed"
            status_label = "Mixed"
            tag_type = "warning"

        return {
            "id": int(batch.get("id") or 0),
            "name": str(batch.get("name") or f"batch-{batch.get('id') or '-'}"),
            "time": str(batch.get("closed_at") or batch.get("created_at") or ""),
            "sold_count": sold_count,
            "profit_hit_rate": round(hit_rate, 4),
            "avg_realized_roi": round(avg_roi, 4),
            "avg_holding_days": round(avg_holding_days, 2),
            "realized_net_profit": round(realized_net_profit, 2),
            "score": int(score),
            "status": status,
            "status_label": status_label,
            "tag_type": tag_type,
        }

    def _validation_timeline_snapshot(
        self,
        closed_batches: list[dict[str, Any]],
        *,
        sample_target: int,
        min_hit_rate: float,
        min_avg_roi: float,
        max_avg_holding_days: float,
    ) -> dict[str, Any]:
        points = [
            self._validation_timeline_point(
                batch,
                sample_target=sample_target,
                min_hit_rate=min_hit_rate,
                min_avg_roi=min_avg_roi,
                max_avg_holding_days=max_avg_holding_days,
            )
            for batch in reversed(list(closed_batches)[:5])
        ]
        if len(points) < 2:
            return {
                "direction": "insufficient",
                "summary": "Need at least two closed validation batches to judge the trend.",
                "delta_score": 0,
                "points": points,
            }

        delta_score = int(points[-1]["score"]) - int(points[0]["score"])
        direction = "stable"
        summary = "Observation quality is broadly stable across recent validation batches."
        if delta_score >= 2:
            direction = "improving"
            summary = "Observation quality is improving across recent validation batches."
        elif delta_score <= -2:
            direction = "worsening"
            summary = "Observation quality is deteriorating across recent validation batches."

        return {
            "direction": direction,
            "summary": summary,
            "delta_score": delta_score,
            "points": points,
        }

    @staticmethod
    def _validation_snapshot_trajectory(
        snapshot_history: dict[str, Any] | None,
    ) -> dict[str, Any]:
        history = list((snapshot_history or {}).get("hourly") or [])
        if len(history) < 2:
            return {
                "available": False,
                "direction": "insufficient",
                "health_delta": 0.0,
                "tune_regressed": False,
                "scale_regressed": False,
                "blocked_streak": 0,
                "worsening_streak": 0,
                "alert_level": "info",
                "summary": "Need more persisted hourly snapshots before judging drawdown.",
            }

        latest = history[-1]
        previous = history[-2]
        latest_snapshot = dict(latest.get("snapshot") or {})
        previous_snapshot = dict(previous.get("snapshot") or {})
        latest_health = float(
            latest_snapshot.get("scale_health_score")
            or latest_snapshot.get("health_score")
            or 0.0
        )
        previous_health = float(
            previous_snapshot.get("scale_health_score")
            or previous_snapshot.get("health_score")
            or 0.0
        )
        health_delta = round(latest_health - previous_health, 1)
        tune_regressed = bool(previous.get("ready_for_tune")) and not bool(latest.get("ready_for_tune"))
        scale_regressed = bool(previous.get("ready_for_scale")) and not bool(latest.get("ready_for_scale"))

        blocked_streak = 0
        for item in reversed(history):
            if bool(item.get("ready_for_scale")):
                break
            blocked_streak += 1

        worsening_streak = 0
        for item in reversed(history):
            if (
                str(item.get("direction") or "") == "worsening"
                or str(item.get("status") or "") in {"blocked", "build"}
            ):
                worsening_streak += 1
                continue
            break

        alert_level = "info"
        direction = "stable"
        summary = "Persisted baseline is broadly stable."
        if scale_regressed or worsening_streak >= 3 or health_delta <= -20.0:
            alert_level = "error"
            direction = "drawdown"
            summary = "Observation baseline regressed sharply and needs immediate review."
        elif tune_regressed or blocked_streak >= 2 or health_delta <= -10.0:
            alert_level = "warning"
            direction = "regressing"
            summary = "Observation baseline is regressing and should be watched closely."
        elif health_delta >= 10.0 and bool(latest.get("ready_for_tune")):
            alert_level = "success"
            direction = "recovering"
            summary = "Observation baseline is recovering versus the previous hourly snapshot."

        return {
            "available": True,
            "direction": direction,
            "health_delta": health_delta,
            "tune_regressed": tune_regressed,
            "scale_regressed": scale_regressed,
            "blocked_streak": blocked_streak,
            "worsening_streak": worsening_streak,
            "alert_level": alert_level,
            "summary": summary,
            "latest_bucket_key": str(latest.get("bucket_key") or ""),
            "previous_bucket_key": str(previous.get("bucket_key") or ""),
        }

    def _validation_baseline_snapshot(
        self,
        dashboard_metrics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        metrics = dashboard_metrics or repo.get_dashboard_metrics()
        tuning_policy = self.tuning_policy()
        cockpit = metrics.get("profit_cockpit") or {}
        last_7d = cockpit.get("last_7d") or {}
        source_items = list(cockpit.get("source_leaderboard_7d") or [])
        forward_validation = metrics.get("forward_validation") or {}
        closed_batches = [
            batch
            for batch in list(forward_validation.get("recent_batches") or [])
            if str(batch.get("status") or "").strip().lower() == "closed"
        ]
        latest_closed_batch = closed_batches[0] if closed_batches else None
        previous_closed_batch = closed_batches[1] if len(closed_batches) > 1 else None
        total_source_sold = sum(int(item.get("sold_count") or 0) for item in source_items)
        top_source = max(
            source_items,
            key=lambda item: int(item.get("sold_count") or 0),
            default={},
        )
        top_source_share = (
            (int(top_source.get("sold_count") or 0) / total_source_sold)
            if total_source_sold > 0
            else 0.0
        )
        execution_summary = repo.get_execution_log_summary(
            limit=settings.operating_state_execution_window,
            dry_run=False,
        )
        monitor_status = monitor_service.status()
        monitor_health = monitor_status.get("health", {}) if isinstance(monitor_status, dict) else {}
        operating_state_name = "normal"
        if bool(monitor_status.get("circuit_open")) or bool(monitor_health.get("guard_triggered")):
            operating_state_name = "recovery"
        elif (
            float(execution_summary.get("failure_rate") or 0.0)
            >= float(settings.operating_state_recovery_failure_rate)
            or int(execution_summary.get("business_ban_count") or 0)
            >= int(settings.operating_state_recovery_business_bans)
        ):
            operating_state_name = "recovery"
        elif (
            float(execution_summary.get("failure_rate") or 0.0)
            >= float(settings.operating_state_cautious_failure_rate)
            or int(execution_summary.get("business_ban_count") or 0)
            >= int(settings.operating_state_cautious_business_bans)
        ):
            operating_state_name = "cautious"
        execution_readiness = execution_service.webhook_readiness()
        operating_profile = single_account_guardrail_status()
        source_overrides = risk_overrides_service.source_status_summary(limit=200)
        cluster_overrides = risk_overrides_service.cluster_status_summary(limit=200)
        monitor_samples = int(monitor_health.get("samples") or 0)
        monitor_success_rate = float(monitor_health.get("success_rate") or 0.0)
        execution_failure_rate = float(execution_summary.get("failure_rate") or 0.0)
        execution_live_sample_size = int(execution_summary.get("sample_size") or 0)
        business_ban_count = int(execution_summary.get("business_ban_count") or 0)
        latest_closed_sold_count = int((latest_closed_batch or {}).get("sold_count") or 0)
        previous_closed_sold_count = int((previous_closed_batch or {}).get("sold_count") or 0)
        latest_closed_hit_rate = float((latest_closed_batch or {}).get("profit_hit_rate") or 0.0)
        latest_closed_avg_roi = float((latest_closed_batch or {}).get("avg_realized_roi") or 0.0)
        latest_closed_avg_holding_days = float((latest_closed_batch or {}).get("avg_holding_days") or 0.0)
        latest_closed_net_profit = float((latest_closed_batch or {}).get("realized_net_profit") or 0.0)
        required_monitor_samples = max(
            int(settings.monitor_health_min_samples),
            int(settings.operating_state_min_monitor_samples),
        )

        checks: list[dict[str, Any]] = []

        def add_check(
            *,
            code: str,
            label: str,
            ok: bool,
            detail: str,
            blocks_tune: bool,
            blocks_scale: bool,
        ) -> None:
            checks.append(
                {
                    "code": code,
                    "label": label,
                    "ok": bool(ok),
                    "detail": detail,
                    "blocks_tune": bool(blocks_tune),
                    "blocks_scale": bool(blocks_scale),
                }
            )

        add_check(
            code="closed_validation_batches",
            label="Closed validation batches",
            ok=len(closed_batches) >= int(tuning_policy["min_closed_batches"]),
            detail=(
                f"closed_batches={len(closed_batches)} / "
                f"required={int(tuning_policy['min_closed_batches'])}"
            ),
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="latest_closed_batch_sample",
            label="Latest closed batch sample",
            ok=latest_closed_batch is not None
            and latest_closed_sold_count >= int(tuning_policy["latest_min_sold_count"]),
            detail=(
                f"latest_closed_batch={str((latest_closed_batch or {}).get('name') or 'none')} / "
                f"sold={latest_closed_sold_count} / "
                f"required={int(tuning_policy['latest_min_sold_count'])}"
            ),
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="previous_closed_batch_sample",
            label="Previous closed batch sample",
            ok=int(tuning_policy["min_closed_batches"]) < 2
            or previous_closed_sold_count >= int(tuning_policy["previous_min_sold_count"]),
            detail=(
                f"previous_sold={previous_closed_sold_count} / "
                f"required={int(tuning_policy['previous_min_sold_count'])}"
            ),
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="recent_sold_count",
            label="Recent sold trades",
            ok=int(last_7d.get("sold_count") or 0) >= int(settings.single_account_validation_min_sold_count),
            detail=(
                f"sold_count_7d={int(last_7d.get('sold_count') or 0)} / "
                f"required={int(settings.single_account_validation_min_sold_count)}"
            ),
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="profit_hit_rate",
            label="Profit hit rate",
            ok=float(last_7d.get("profit_hit_rate") or 0.0)
            >= float(settings.single_account_validation_min_profit_hit_rate),
            detail=(
                f"profit_hit_rate_7d={float(last_7d.get('profit_hit_rate') or 0.0):.4f} / "
                f"required={float(settings.single_account_validation_min_profit_hit_rate):.4f}"
            ),
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="avg_realized_roi",
            label="Average realized ROI",
            ok=float(last_7d.get("avg_realized_roi") or 0.0)
            >= float(settings.single_account_validation_min_avg_roi),
            detail=(
                f"avg_realized_roi_7d={float(last_7d.get('avg_realized_roi') or 0.0):.4f} / "
                f"required={float(settings.single_account_validation_min_avg_roi):.4f}"
            ),
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="latest_closed_batch_hit_rate",
            label="Latest batch hit rate",
            ok=latest_closed_batch is not None
            and latest_closed_hit_rate >= float(settings.observation_baseline_min_hit_rate),
            detail=(
                f"latest_hit_rate={latest_closed_hit_rate:.4f} / "
                f"required={float(settings.observation_baseline_min_hit_rate):.4f}"
            ),
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="latest_closed_batch_avg_roi",
            label="Latest batch average ROI",
            ok=latest_closed_batch is not None
            and latest_closed_avg_roi >= float(settings.observation_baseline_min_avg_roi),
            detail=(
                f"latest_avg_roi={latest_closed_avg_roi:.4f} / "
                f"required={float(settings.observation_baseline_min_avg_roi):.4f}"
            ),
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="latest_closed_batch_holding_days",
            label="Latest batch holding days",
            ok=latest_closed_batch is not None
            and latest_closed_avg_holding_days <= float(settings.observation_baseline_max_avg_holding_days),
            detail=(
                f"latest_avg_holding_days={latest_closed_avg_holding_days:.2f} / "
                f"max={float(settings.observation_baseline_max_avg_holding_days):.2f}"
            ),
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="latest_closed_batch_net_profit",
            label="Latest batch net profit",
            ok=latest_closed_batch is not None and latest_closed_net_profit > 0.0,
            detail=f"latest_realized_net_profit={latest_closed_net_profit:.2f}",
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="monitor_success_rate",
            label="Monitor success rate",
            ok=monitor_samples >= required_monitor_samples
            and monitor_success_rate >= float(settings.observation_baseline_min_monitor_success_rate),
            detail=(
                f"monitor_samples={monitor_samples} / required={required_monitor_samples}, "
                f"monitor_success_rate={monitor_success_rate:.4f} / "
                f"required_rate={float(settings.observation_baseline_min_monitor_success_rate):.4f}"
            ),
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="operating_state",
            label="Operating state",
            ok=operating_state_name != "recovery",
            detail=f"operating_state={operating_state_name}",
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="active_freezes",
            label="Active freezes",
            ok=(
                int(source_overrides.get("active_freeze_count") or 0) == 0
                and int(cluster_overrides.get("active_freeze_count") or 0) == 0
            ),
            detail=(
                f"source_freeze={int(source_overrides.get('active_freeze_count') or 0)}, "
                f"cluster_freeze={int(cluster_overrides.get('active_freeze_count') or 0)}"
            ),
            blocks_tune=True,
            blocks_scale=True,
        )
        add_check(
            code="source_diversity",
            label="Source diversity",
            ok=len(source_items) >= int(settings.single_account_validation_min_source_count),
            detail=(
                f"source_count_7d={len(source_items)} / "
                f"required={int(settings.single_account_validation_min_source_count)}"
            ),
            blocks_tune=False,
            blocks_scale=True,
        )
        add_check(
            code="source_concentration",
            label="Source concentration",
            ok=top_source_share <= float(settings.single_account_validation_max_source_share),
            detail=(
                f"top_source={str(top_source.get('source') or '')}, "
                f"share={top_source_share:.4f} / "
                f"max={float(settings.single_account_validation_max_source_share):.4f}"
            ),
            blocks_tune=False,
            blocks_scale=True,
        )
        add_check(
            code="last_7d_net_profit",
            label="Recent net profit",
            ok=float(last_7d.get("realized_net_profit") or 0.0)
            >= float(settings.observation_baseline_min_last_7d_net_profit),
            detail=(
                f"realized_net_profit_7d={float(last_7d.get('realized_net_profit') or 0.0):.2f} / "
                f"required={float(settings.observation_baseline_min_last_7d_net_profit):.2f}"
            ),
            blocks_tune=False,
            blocks_scale=True,
        )
        add_check(
            code="execution_live_readiness",
            label="Live execution readiness",
            ok=bool(execution_readiness.get("live_ready")),
            detail=(
                f"live_ready={bool(execution_readiness.get('live_ready'))}, "
                f"provider={str(execution_readiness.get('provider') or '')}"
            ),
            blocks_tune=False,
            blocks_scale=True,
        )
        add_check(
            code="execution_live_samples",
            label="Live execution samples",
            ok=execution_live_sample_size >= int(settings.observation_baseline_min_live_execution_samples),
            detail=(
                f"sample_size={execution_live_sample_size} / "
                f"required={int(settings.observation_baseline_min_live_execution_samples)}"
            ),
            blocks_tune=False,
            blocks_scale=True,
        )
        add_check(
            code="execution_failure_rate",
            label="Live execution failure rate",
            ok=execution_failure_rate <= float(settings.observation_baseline_max_live_execution_failure_rate),
            detail=(
                f"failure_rate={execution_failure_rate:.4f} / "
                f"max={float(settings.observation_baseline_max_live_execution_failure_rate):.4f}"
            ),
            blocks_tune=False,
            blocks_scale=True,
        )
        add_check(
            code="execution_business_bans",
            label="Live execution bans",
            ok=business_ban_count <= int(settings.observation_baseline_max_live_execution_business_bans),
            detail=(
                f"business_ban_count={business_ban_count} / "
                f"max={int(settings.observation_baseline_max_live_execution_business_bans)}"
            ),
            blocks_tune=False,
            blocks_scale=True,
        )
        add_check(
            code="single_account_guardrails",
            label="Single-account guardrails",
            ok=not bool(operating_profile.get("enabled")) or bool(operating_profile.get("aligned")),
            detail=(
                f"mode={str(operating_profile.get('mode') or '')}, "
                f"failing={', '.join(list(operating_profile.get('failing_codes') or [])[:4])}"
            ),
            blocks_tune=False,
            blocks_scale=True,
        )

        timeline = self._validation_timeline_snapshot(
            closed_batches,
            sample_target=int(tuning_policy["latest_min_sold_count"]),
            min_hit_rate=float(settings.observation_baseline_min_hit_rate),
            min_avg_roi=float(settings.observation_baseline_min_avg_roi),
            max_avg_holding_days=float(settings.observation_baseline_max_avg_holding_days),
        )
        tune_blocking_codes = [
            str(item["code"])
            for item in checks
            if not bool(item["ok"]) and bool(item["blocks_tune"])
        ]
        scale_blocking_codes = [
            str(item["code"])
            for item in checks
            if not bool(item["ok"]) and bool(item["blocks_scale"])
        ]
        ready_for_tune = len(tune_blocking_codes) == 0
        ready_for_scale = len(scale_blocking_codes) == 0
        blocking_codes = scale_blocking_codes

        risk_block_codes = {"operating_state", "active_freezes", "execution_business_bans"}
        status = "ready"
        if not ready_for_scale:
            if any(code in risk_block_codes for code in scale_blocking_codes):
                status = "blocked"
            elif ready_for_tune:
                status = "observe"
            else:
                status = "build"
        baseline = {
            "enabled": bool(settings.single_account_mode),
            "ready": ready_for_scale,
            "ready_for_tune": ready_for_tune,
            "ready_for_scale": ready_for_scale,
            "status": status,
            "blocking_codes": blocking_codes,
            "tune_blocking_codes": tune_blocking_codes,
            "scale_blocking_codes": scale_blocking_codes,
            "checks": checks,
            "timeline": timeline,
            "policy": {
                "min_closed_batches": int(tuning_policy["min_closed_batches"]),
                "latest_min_sold_count": int(tuning_policy["latest_min_sold_count"]),
                "previous_min_sold_count": int(tuning_policy["previous_min_sold_count"]),
                "min_recent_sold_count": int(settings.single_account_validation_min_sold_count),
                "min_source_count": int(settings.single_account_validation_min_source_count),
                "min_profit_hit_rate": float(settings.single_account_validation_min_profit_hit_rate),
                "min_avg_roi": float(settings.single_account_validation_min_avg_roi),
                "min_latest_hit_rate": float(settings.observation_baseline_min_hit_rate),
                "min_latest_avg_roi": float(settings.observation_baseline_min_avg_roi),
                "max_latest_avg_holding_days": float(settings.observation_baseline_max_avg_holding_days),
                "min_monitor_success_rate": float(settings.observation_baseline_min_monitor_success_rate),
                "min_monitor_samples": required_monitor_samples,
                "max_source_share": float(settings.single_account_validation_max_source_share),
                "min_last_7d_net_profit": float(settings.observation_baseline_min_last_7d_net_profit),
                "min_live_execution_samples": int(settings.observation_baseline_min_live_execution_samples),
                "max_live_execution_failure_rate": float(settings.observation_baseline_max_live_execution_failure_rate),
                "max_live_execution_business_bans": int(settings.observation_baseline_max_live_execution_business_bans),
            },
            "metrics": {
                "sold_count_7d": int(last_7d.get("sold_count") or 0),
                "source_count_7d": len(source_items),
                "profit_hit_rate_7d": round(float(last_7d.get("profit_hit_rate") or 0.0), 4),
                "avg_realized_roi_7d": round(float(last_7d.get("avg_realized_roi") or 0.0), 4),
                "realized_net_profit_7d": round(float(last_7d.get("realized_net_profit") or 0.0), 2),
                "top_source": str(top_source.get("source") or ""),
                "top_source_share": round(top_source_share, 4),
                "business_ban_count": business_ban_count,
                "execution_live_sample_size": execution_live_sample_size,
                "execution_failure_rate": round(execution_failure_rate, 4),
                "monitor_samples": monitor_samples,
                "monitor_success_rate": round(monitor_success_rate, 4),
                "latest_closed_batch_id": (
                    int(latest_closed_batch.get("id") or 0) if latest_closed_batch else None
                ),
                "latest_closed_batch_sold_count": latest_closed_sold_count,
                "latest_closed_batch_hit_rate": round(latest_closed_hit_rate, 4),
                "latest_closed_batch_avg_roi": round(latest_closed_avg_roi, 4),
                "latest_closed_batch_avg_holding_days": round(latest_closed_avg_holding_days, 2),
                "latest_closed_batch_realized_net_profit": round(latest_closed_net_profit, 2),
                "previous_closed_batch_sold_count": previous_closed_sold_count,
            },
            "recommendation": (
                "Baseline is thick enough for the next controlled scale step."
                if ready_for_scale
                else (
                    "Threshold tuning can be reviewed, but keep the account in local observation mode."
                    if ready_for_tune
                    else (
                        "Stop automatic approvals and inspect live risk signals."
                        if status == "blocked"
                        else "Keep the account in observation mode until more sold evidence accumulates."
                    )
                )
            ),
        }
        snapshot_payload = {
            "status": baseline["status"],
            "ready": baseline["ready"],
            "ready_for_tune": baseline["ready_for_tune"],
            "ready_for_scale": baseline["ready_for_scale"],
            "direction": str(timeline.get("direction") or ""),
            "summary": str(timeline.get("summary") or ""),
            "blocking_codes": list(blocking_codes),
            "tune_blocking_codes": list(tune_blocking_codes),
            "scale_blocking_codes": list(scale_blocking_codes),
            "health_score": round((sum(1 for item in checks if bool(item["ok"])) / max(1, len(checks))) * 100.0, 1),
            "tune_health_score": round(
                (
                    (
                        sum(1 for item in checks if bool(item["blocks_tune"]))
                        - len(tune_blocking_codes)
                    )
                    / max(1, sum(1 for item in checks if bool(item["blocks_tune"])))
                )
                * 100.0,
                1,
            ),
            "scale_health_score": round(
                (
                    (
                        sum(1 for item in checks if bool(item["blocks_scale"]))
                        - len(scale_blocking_codes)
                    )
                    / max(1, sum(1 for item in checks if bool(item["blocks_scale"])))
                )
                * 100.0,
                1,
            ),
            "metrics": dict(baseline["metrics"]),
        }
        baseline["health_score"] = snapshot_payload["health_score"]
        baseline["tune_health_score"] = snapshot_payload["tune_health_score"]
        baseline["scale_health_score"] = snapshot_payload["scale_health_score"]
        now = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
        try:
            repo.upsert_validation_baseline_snapshot(
                bucket_type="hour",
                bucket_key=now.isoformat(),
                status=baseline["status"],
                ready=bool(baseline["ready"]),
                ready_for_tune=bool(baseline["ready_for_tune"]),
                ready_for_scale=bool(baseline["ready_for_scale"]),
                direction=str(timeline.get("direction") or ""),
                summary=str(timeline.get("summary") or ""),
                blocking_codes=list(blocking_codes),
                snapshot=snapshot_payload,
                captured_at=now.isoformat(),
            )
            repo.upsert_validation_baseline_snapshot(
                bucket_type="day",
                bucket_key=now.date().isoformat(),
                status=baseline["status"],
                ready=bool(baseline["ready"]),
                ready_for_tune=bool(baseline["ready_for_tune"]),
                ready_for_scale=bool(baseline["ready_for_scale"]),
                direction=str(timeline.get("direction") or ""),
                summary=str(timeline.get("summary") or ""),
                blocking_codes=list(blocking_codes),
                snapshot=snapshot_payload,
                captured_at=now.isoformat(),
            )
            baseline["snapshot_history"] = {
                "hourly": list(
                    reversed(
                        repo.list_validation_baseline_snapshots(
                            bucket_type="hour",
                            limit=12,
                        ),
                    )
                ),
                "daily": list(
                    reversed(
                        repo.list_validation_baseline_snapshots(
                            bucket_type="day",
                            limit=7,
                        ),
                    )
                ),
            }
        except Exception:
            baseline["snapshot_history"] = {"hourly": [], "daily": []}
        baseline["trajectory"] = self._validation_snapshot_trajectory(
            baseline.get("snapshot_history"),
        )
        return baseline

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
    def _source_action_exec_cap(*, lane: str, batch_limit: int) -> int:
        normalized_lane = str(lane or "open").strip().lower()
        if normalized_lane == "blocked":
            return 0
        if normalized_lane in {"observe", "reduced"}:
            return 1
        return max(1, int(batch_limit or 1))

    @staticmethod
    def _risk_cluster_key(row: Any) -> str:
        try:
            normalized_key = str(row["normalized_key"] or "").strip()
        except Exception:
            normalized_key = str(row.get("normalized_key") or "").strip() if isinstance(row, dict) else ""
        if normalized_key:
            return normalized_key
        try:
            item_type = str(row["item_type"] or "").strip()
        except Exception:
            item_type = str(row.get("item_type") or "").strip() if isinstance(row, dict) else ""
        if item_type:
            return f"item_type:{item_type}"
        try:
            source = str(row["source"] or "").strip()
        except Exception:
            source = str(row.get("source") or "").strip() if isinstance(row, dict) else ""
        return f"source:{source or 'unknown'}"

    @staticmethod
    def _build_source_position_controls(
        batch_limit: int,
        source_strategy_map: dict[str, dict[str, Any]],
        candidate_rows: list[Any],
        metrics: dict[str, Any] | None = None,
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        cockpit = (metrics or {}).get("profit_cockpit") or {}
        inventory = cockpit.get("inventory") or {}
        current_deployed_capital = float(inventory.get("deployed_capital") or 0.0)
        portfolio_capital_limit = max(0.0, float(settings.auto_approve_portfolio_max_deployed_capital or 0.0))
        remaining_portfolio_capital = (
            max(0.0, portfolio_capital_limit - current_deployed_capital)
            if portfolio_capital_limit > 0
            else 0.0
        )
        max_source_capital_share = max(
            0.1,
            min(1.0, float(settings.auto_approve_max_source_capital_share or 1.0)),
        )
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
        active_items: list[dict[str, Any]] = []
        total_pending_capacity = 0
        for source, bucket in grouped.items():
            strategy = source_strategy_map.get(source, {})
            intake_multiplier = float(strategy.get("intake_multiplier") or 1.0)
            capital_multiplier = float(strategy.get("capital_multiplier") or intake_multiplier or 1.0)
            source_lane = str(strategy.get("source_lane") or "open")
            block_new_approvals = bool(strategy.get("block_new_approvals"))
            pending_count = int(bucket["pending_count"] or 0)
            avg_list_price = (
                float(bucket["list_price_total"]) / pending_count if pending_count > 0 else 0.0
            )
            if block_new_approvals or source_lane == "blocked":
                item = {
                    "source": source,
                    "source_lane": source_lane,
                    "block_new_approvals": block_new_approvals,
                    "strategy_mode": str(strategy.get("strategy_mode") or "hold"),
                    "strategy_summary": str(strategy.get("strategy_summary") or ""),
                    "intake_multiplier": round(intake_multiplier, 2),
                    "capital_multiplier": round(capital_multiplier, 2),
                    "batch_cap": 0,
                    "capital_cap": 0.0,
                "pending_count": pending_count,
                "avg_list_price": round(avg_list_price, 2),
                "realized_net_profit": float(strategy.get("realized_net_profit") or 0.0),
                "portfolio_capital_limit": round(portfolio_capital_limit, 2),
                "remaining_portfolio_capital": round(remaining_portfolio_capital, 2),
                "max_source_capital_share": round(max_source_capital_share, 4),
                "portfolio_capital_budget": 0.0,
                "source_capital_share_limit_value": 0.0,
                "batch_weight": 0.0,
                "capital_weight": 0.0,
            }
                controls[source] = item
                items.append(item)
                continue
            batch_weight = max(0.05, intake_multiplier)
            capital_weight = max(0.05, capital_multiplier)
            active_item = {
                "source": source,
                "source_lane": source_lane,
                "block_new_approvals": block_new_approvals,
                "strategy_mode": str(strategy.get("strategy_mode") or "hold"),
                "strategy_summary": str(strategy.get("strategy_summary") or ""),
                "intake_multiplier": round(intake_multiplier, 2),
                "capital_multiplier": round(capital_multiplier, 2),
                "batch_cap": 0,
                "capital_cap": 0.0,
                "pending_count": pending_count,
                "avg_list_price": round(avg_list_price, 2),
                "realized_net_profit": float(strategy.get("realized_net_profit") or 0.0),
                "portfolio_capital_limit": round(portfolio_capital_limit, 2),
                "remaining_portfolio_capital": round(remaining_portfolio_capital, 2),
                "max_source_capital_share": round(max_source_capital_share, 4),
                "portfolio_capital_budget": 0.0,
                "source_capital_share_limit_value": 0.0,
                "batch_weight": round(batch_weight, 4),
                "capital_weight": round(capital_weight, 4),
            }
            active_items.append(active_item)
            total_pending_capacity += pending_count

        total_batch_slots = min(normalized_batch_limit, total_pending_capacity)
        if portfolio_capital_limit > 0 and remaining_portfolio_capital <= 0:
            total_batch_slots = 0
        if active_items and total_batch_slots > 0:
            effective_max_source_capital_share = (
                1.0 if len(active_items) == 1 else max_source_capital_share
            )
            total_batch_weight = sum(float(item["batch_weight"]) for item in active_items) or float(len(active_items))
            batch_allocated = 0
            for item in active_items:
                expected = total_batch_slots * (float(item["batch_weight"]) / total_batch_weight)
                item["batch_cap"] = min(int(item["pending_count"]), int(expected))
                item["_batch_remainder"] = expected - int(item["batch_cap"])
                batch_allocated += int(item["batch_cap"])

            if batch_allocated == 0:
                strongest = max(active_items, key=lambda item: (float(item["batch_weight"]), str(item["source"])))
                strongest["batch_cap"] = min(int(strongest["pending_count"]), 1)
                strongest["_batch_remainder"] = 0.0
                batch_allocated = int(strongest["batch_cap"])

            remainders = sorted(
                active_items,
                key=lambda item: (float(item.get("_batch_remainder") or 0.0), float(item["batch_weight"]), str(item["source"])),
                reverse=True,
            )
            while batch_allocated < total_batch_slots:
                progressed = False
                for item in remainders:
                    if int(item["batch_cap"]) >= int(item["pending_count"]):
                        continue
                    item["batch_cap"] = int(item["batch_cap"]) + 1
                    batch_allocated += 1
                    progressed = True
                    if batch_allocated >= total_batch_slots:
                        break
                if not progressed:
                    break

            total_allocated_batch = sum(int(item["batch_cap"]) for item in active_items)
            if total_allocated_batch > 0:
                base_total_capital = sum(float(item["avg_list_price"]) * int(item["batch_cap"]) for item in active_items)
                weighted_quality = (
                    sum(
                        int(item["batch_cap"]) * max(0.5, min(1.5, float(item["capital_multiplier"])))
                        for item in active_items
                    ) / total_allocated_batch
                )
                total_capital_budget = base_total_capital * weighted_quality
                if portfolio_capital_limit > 0:
                    total_capital_budget = min(total_capital_budget, remaining_portfolio_capital)
                total_capital_weight = sum(
                    max(0.05, float(item["capital_multiplier"])) * max(1, int(item["batch_cap"])) * max(0.01, float(item["avg_list_price"]))
                    for item in active_items
                ) or float(len(active_items))
                for item in active_items:
                    capital_share_weight = (
                        max(0.05, float(item["capital_multiplier"]))
                        * max(1, int(item["batch_cap"]))
                        * max(0.01, float(item["avg_list_price"]))
                    )
                    capital_share = total_capital_budget * (capital_share_weight / total_capital_weight)
                    source_capital_limit = (
                        total_capital_budget * effective_max_source_capital_share
                        if total_capital_budget > 0
                        else 0.0
                    )
                    allowed_capital = capital_share
                    if source_capital_limit > 0:
                        allowed_capital = min(allowed_capital, source_capital_limit)
                    if int(item["batch_cap"]) > 0 and portfolio_capital_limit <= 0:
                        allowed_capital = max(float(item["avg_list_price"]), allowed_capital)
                    item["capital_cap"] = round(
                        max(0.0, allowed_capital),
                        2,
                    )
                    item["portfolio_capital_budget"] = round(total_capital_budget, 2)
                    item["source_capital_share_limit_value"] = round(source_capital_limit, 2)
                for item in active_items:
                    item.pop("_batch_remainder", None)
            else:
                for item in active_items:
                    item["capital_cap"] = 0.0

        for item in active_items:
            controls[str(item["source"])] = item
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
    def _build_cluster_position_controls(
        batch_limit: int,
        candidate_rows: list[Any],
        metrics: dict[str, Any] | None = None,
    ) -> tuple[dict[str, dict[str, Any]], list[dict[str, Any]]]:
        cockpit = (metrics or {}).get("profit_cockpit") or {}
        inventory = cockpit.get("inventory") or {}
        current_deployed_capital = float(inventory.get("deployed_capital") or 0.0)
        portfolio_capital_limit = max(0.0, float(settings.auto_approve_portfolio_max_deployed_capital or 0.0))
        remaining_portfolio_capital = (
            max(0.0, portfolio_capital_limit - current_deployed_capital)
            if portfolio_capital_limit > 0
            else 0.0
        )
        max_cluster_batch_share = max(
            0.1,
            min(1.0, float(settings.auto_approve_max_cluster_batch_share or 1.0)),
        )
        max_cluster_capital_share = max(
            0.1,
            min(1.0, float(settings.auto_approve_max_cluster_capital_share or 1.0)),
        )

        grouped: dict[str, dict[str, Any]] = {}
        for row in candidate_rows:
            cluster_key = AutoTradeService._risk_cluster_key(row)
            try:
                source = str(row["source"] or "").strip() or "unknown"
            except Exception:
                source = str(row.get("source") or "").strip() or "unknown" if isinstance(row, dict) else "unknown"
            try:
                list_price = float(row["list_price"] or 0.0)
            except Exception:
                list_price = float(row.get("list_price") or 0.0) if isinstance(row, dict) else 0.0
            bucket = grouped.setdefault(
                cluster_key,
                {
                    "risk_cluster": cluster_key,
                    "pending_count": 0,
                    "list_price_total": 0.0,
                    "sources": set(),
                },
            )
            bucket["pending_count"] += 1
            bucket["list_price_total"] += list_price
            bucket["sources"].add(source)

        controls: dict[str, dict[str, Any]] = {}
        items: list[dict[str, Any]] = []
        normalized_batch_limit = max(1, int(batch_limit or 1))
        total_pending_capacity = sum(int(bucket["pending_count"] or 0) for bucket in grouped.values())
        total_batch_slots = min(normalized_batch_limit, total_pending_capacity)
        if portfolio_capital_limit > 0 and remaining_portfolio_capital <= 0:
            total_batch_slots = 0

        cluster_count = len(grouped)
        effective_batch_share = 1.0 if cluster_count <= 1 else max_cluster_batch_share
        effective_capital_share = 1.0 if cluster_count <= 1 else max_cluster_capital_share

        for cluster_key, bucket in grouped.items():
            pending_count = int(bucket["pending_count"] or 0)
            avg_list_price = (
                float(bucket["list_price_total"]) / pending_count if pending_count > 0 else 0.0
            )
            batch_cap = 0
            if total_batch_slots > 0:
                batch_cap = max(
                    1,
                    min(
                        pending_count,
                        int(round(total_batch_slots * effective_batch_share)),
                    ),
                )
            if portfolio_capital_limit > 0:
                capital_cap = round(max(0.0, remaining_portfolio_capital * effective_capital_share), 2)
            else:
                capital_cap = round(avg_list_price * max(0, batch_cap), 2)
            item = {
                "risk_cluster": cluster_key,
                "pending_count": pending_count,
                "avg_list_price": round(avg_list_price, 2),
                "source_count": len(bucket["sources"]),
                "sources": sorted(bucket["sources"]),
                "batch_cap": batch_cap,
                "capital_cap": capital_cap,
                "portfolio_capital_limit": round(portfolio_capital_limit, 2),
                "remaining_portfolio_capital": round(remaining_portfolio_capital, 2),
                "max_cluster_batch_share": round(effective_batch_share, 4),
                "max_cluster_capital_share": round(effective_capital_share, 4),
            }
            controls[cluster_key] = item
            items.append(item)

        items.sort(
            key=lambda item: (
                int(item["pending_count"]),
                int(item["source_count"]),
                str(item["risk_cluster"]),
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

    def _maybe_dispatch_alert_email(
        self,
        *,
        dashboard_metrics: dict[str, Any],
        profit_guard: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        if not bool(settings.autotrade_alert_email_auto_enabled):
            return {
                "enabled": False,
                "sent": False,
                "reason": "auto_alert_email_disabled",
            }

        from .operating_state import operating_state_service

        operating_state = operating_state_service.status()
        execution_readiness = execution_service.webhook_readiness()
        alert_payload = build_alert_payload(
            enabled=bool(settings.auto_approve_enabled),
            profit_guard=profit_guard,
            dashboard_metrics=dashboard_metrics,
            operating_state=operating_state,
            execution_readiness=execution_readiness,
            validation_baseline=self._validation_baseline_snapshot(dashboard_metrics),
        )
        alerts = list(alert_payload.get("alerts") or [])
        if not alerts:
            return {
                "enabled": True,
                "sent": False,
                "reason": "no_active_alerts",
            }
        min_severity = normalize_alert_severity(settings.autotrade_alert_email_min_severity)
        highest_severity = highest_alert_severity(alerts)
        if not alerts_meet_min_severity(alerts, min_severity=min_severity):
            return {
                "enabled": True,
                "sent": False,
                "reason": "min_severity_not_met",
                "min_severity": min_severity,
                "highest_severity": highest_severity,
            }
        return {
            "enabled": True,
            **dispatch_alert_email(
                cockpit={
                    **alert_payload,
                    "execution_readiness": execution_readiness,
                    "operating_state": operating_state,
                },
                source=source,
                force=False,
            ),
        }

    def _maybe_dispatch_alert_slack(
        self,
        *,
        dashboard_metrics: dict[str, Any],
        profit_guard: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        if not bool(settings.autotrade_alert_slack_auto_enabled):
            return {
                "enabled": False,
                "sent": False,
                "reason": "auto_alert_slack_disabled",
            }

        from .operating_state import operating_state_service

        operating_state = operating_state_service.status()
        execution_readiness = execution_service.webhook_readiness()
        alert_payload = build_alert_payload(
            enabled=bool(settings.auto_approve_enabled),
            profit_guard=profit_guard,
            dashboard_metrics=dashboard_metrics,
            operating_state=operating_state,
            execution_readiness=execution_readiness,
            validation_baseline=self._validation_baseline_snapshot(dashboard_metrics),
        )
        alerts = [
            item
            for item in list(alert_payload.get("alerts") or [])
            if alert_delivery_lane(item) == "slack"
        ]
        if not alerts:
            return {
                "enabled": True,
                "sent": False,
                "reason": "no_slack_stage_alerts",
            }
        min_severity = normalize_alert_severity(settings.autotrade_alert_slack_min_severity)
        highest_severity = highest_alert_severity(alerts)
        if not alerts_meet_min_severity(alerts, min_severity=min_severity):
            return {
                "enabled": True,
                "sent": False,
                "reason": "min_severity_not_met",
                "min_severity": min_severity,
                "highest_severity": highest_severity,
            }
        return {
            "enabled": True,
            **dispatch_alert_slack(
                cockpit={
                    **alert_payload,
                    "alerts": alerts,
                    "execution_readiness": execution_readiness,
                    "operating_state": operating_state,
                },
                source=source,
                force=False,
            ),
        }

    def _maybe_dispatch_alert_telegram(
        self,
        *,
        dashboard_metrics: dict[str, Any],
        profit_guard: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        if not bool(settings.autotrade_alert_telegram_auto_enabled):
            return {
                "enabled": False,
                "sent": False,
                "reason": "auto_alert_telegram_disabled",
            }

        from .operating_state import operating_state_service

        operating_state = operating_state_service.status()
        execution_readiness = execution_service.webhook_readiness()
        alert_payload = build_alert_payload(
            enabled=bool(settings.auto_approve_enabled),
            profit_guard=profit_guard,
            dashboard_metrics=dashboard_metrics,
            operating_state=operating_state,
            execution_readiness=execution_readiness,
            validation_baseline=self._validation_baseline_snapshot(dashboard_metrics),
        )
        alerts = [
            item
            for item in list(alert_payload.get("alerts") or [])
            if alert_delivery_lane(item) == "telegram"
        ]
        if not alerts:
            return {
                "enabled": True,
                "sent": False,
                "reason": "no_telegram_stage_alerts",
            }
        min_severity = normalize_alert_severity(settings.autotrade_alert_telegram_min_severity)
        highest_severity = highest_alert_severity(alerts)
        if not alerts_meet_min_severity(alerts, min_severity=min_severity):
            return {
                "enabled": True,
                "sent": False,
                "reason": "min_severity_not_met",
                "min_severity": min_severity,
                "highest_severity": highest_severity,
            }
        return {
            "enabled": True,
            **dispatch_alert_telegram(
                cockpit={
                    **alert_payload,
                    "alerts": alerts,
                    "execution_readiness": execution_readiness,
                    "operating_state": operating_state,
                },
                source=source,
                force=False,
            ),
        }

    def _maybe_dispatch_alert_webhook(
        self,
        *,
        dashboard_metrics: dict[str, Any],
        profit_guard: dict[str, Any],
        source: str,
    ) -> dict[str, Any]:
        if not bool(settings.autotrade_alert_webhook_auto_enabled):
            return {
                "enabled": False,
                "sent": False,
                "reason": "auto_alert_webhook_disabled",
            }
        legacy_provider = str(settings.alert_webhook_provider or "").strip().lower()
        if legacy_provider == "slack" and bool(settings.autotrade_alert_slack_auto_enabled):
            return {
                "enabled": False,
                "sent": False,
                "reason": "dedicated_slack_channel_enabled",
            }
        if legacy_provider == "telegram" and bool(settings.autotrade_alert_telegram_auto_enabled):
            return {
                "enabled": False,
                "sent": False,
                "reason": "dedicated_telegram_channel_enabled",
            }

        from .operating_state import operating_state_service

        operating_state = operating_state_service.status()
        execution_readiness = execution_service.webhook_readiness()
        alert_payload = build_alert_payload(
            enabled=bool(settings.auto_approve_enabled),
            profit_guard=profit_guard,
            dashboard_metrics=dashboard_metrics,
            operating_state=operating_state,
            execution_readiness=execution_readiness,
            validation_baseline=self._validation_baseline_snapshot(dashboard_metrics),
        )
        alerts = [
            item
            for item in list(alert_payload.get("alerts") or [])
            if bool(item.get("external_escalation_ready"))
        ]
        if not alerts:
            return {
                "enabled": True,
                "sent": False,
                "reason": "no_escalated_alerts",
            }
        min_severity = normalize_alert_severity(settings.autotrade_alert_webhook_min_severity)
        highest_severity = highest_alert_severity(alerts)
        if not alerts_meet_min_severity(alerts, min_severity=min_severity):
            return {
                "enabled": True,
                "sent": False,
                "reason": "min_severity_not_met",
                "min_severity": min_severity,
                "highest_severity": highest_severity,
            }
        return {
            "enabled": True,
            **dispatch_alert_webhook(
                cockpit={
                    **alert_payload,
                    "alerts": alerts,
                    "execution_readiness": execution_readiness,
                    "operating_state": operating_state,
                },
                source=source,
                force=False,
            ),
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
            validation_baseline = self._validation_baseline_snapshot(dashboard_metrics)
            source_strategy_map = self._source_strategy_map(dashboard_metrics)
            seller_strategy_map = self._seller_strategy_map(dashboard_metrics)
            source_override_status = risk_overrides_service.source_status_summary(limit=200)
            cluster_override_status = risk_overrides_service.cluster_status_summary(limit=200)
            source_override_map = {
                str(item.get("source") or "").strip(): item
                for item in list(source_override_status.get("items") or [])
                if str(item.get("source") or "").strip()
            }
            cluster_override_map = {
                str(item.get("risk_cluster") or "").strip(): item
                for item in list(cluster_override_status.get("items") or [])
                if str(item.get("risk_cluster") or "").strip()
            }
            if profit_guard["blocked"]:
                loss_recovery = self._maybe_apply_loss_recovery_tuning(
                    profit_guard=profit_guard,
                    applied_by="profit_guard_bot" if loss_recovery_enabled else "operator",
                )
                alert_dispatch = self._maybe_dispatch_alert_email(
                    dashboard_metrics=dashboard_metrics,
                    profit_guard=profit_guard,
                    source="autotrade_bot",
                )
                alert_slack_dispatch = self._maybe_dispatch_alert_slack(
                    dashboard_metrics=dashboard_metrics,
                    profit_guard=profit_guard,
                    source="autotrade_bot",
                )
                alert_telegram_dispatch = self._maybe_dispatch_alert_telegram(
                    dashboard_metrics=dashboard_metrics,
                    profit_guard=profit_guard,
                    source="autotrade_bot",
                )
                alert_webhook_dispatch = self._maybe_dispatch_alert_webhook(
                    dashboard_metrics=dashboard_metrics,
                    profit_guard=profit_guard,
                    source="autotrade_bot",
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
                    "validation_baseline": validation_baseline,
                    "loss_recovery": loss_recovery,
                    "alert_dispatch": alert_dispatch,
                    "alert_slack_dispatch": alert_slack_dispatch,
                    "alert_telegram_dispatch": alert_telegram_dispatch,
                    "alert_webhook_dispatch": alert_webhook_dispatch,
                }

            if bool(settings.single_account_mode) and not bool(validation_baseline.get("ready")):
                block_reason = ", ".join(list(validation_baseline.get("blocking_codes") or [])[:3]) or (
                    "single_account_observation_baseline_not_ready"
                )
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
                    "reason": "single_account_validation_baseline_not_ready",
                    "blocked": True,
                    "profit_guard": profit_guard,
                    "validation_baseline": validation_baseline,
                    "loss_recovery": {
                        "enabled": bool(loss_recovery_enabled),
                        "applied": False,
                        "reason": "single_account_validation_baseline_not_ready",
                    },
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
                dashboard_metrics,
            )
            cluster_position_control_map, cluster_position_controls = self._build_cluster_position_controls(
                batch_limit,
                rows,
                dashboard_metrics,
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
            skipped_cluster_batch_cap = 0
            skipped_cluster_capital = 0
            skipped_non_tradable = 0
            skipped_seller_blacklist = 0
            skipped_seller_batch_cap = 0
            skipped_seller_capital = 0
            idempotent_hits = 0
            errors = 0
            picked_ids: list[int] = []
            source_approved_counts: dict[str, int] = {}
            source_approved_capital: dict[str, float] = {}
            cluster_approved_counts: dict[str, int] = {}
            cluster_approved_capital: dict[str, float] = {}
            seller_approved_counts: dict[str, int] = {}
            seller_approved_capital: dict[str, float] = {}
            buy_exec_attempted = 0
            buy_exec_succeeded = 0
            buy_exec_failed = 0
            list_exec_attempted = 0
            list_exec_succeeded = 0
            list_exec_failed = 0
            list_exec_skipped_source_action = 0
            list_exec_skipped_source_action_cap = 0
            source_list_exec_counts: dict[str, int] = {}

            for row in rows:
                if approved >= batch_limit:
                    break
                opportunity_id = int(row["id"])
                source = str(row["source"] or "unknown").strip() or "unknown"
                try:
                    item_type = str(row["item_type"] or "").strip()
                except Exception:
                    item_type = str(row.get("item_type") or "").strip() if isinstance(row, dict) else ""
                try:
                    normalized_key = str(row["normalized_key"] or "").strip()
                except Exception:
                    normalized_key = str(row.get("normalized_key") or "").strip() if isinstance(row, dict) else ""
                if not item_type and ":" in normalized_key:
                    item_type = normalized_key.split(":", 1)[0].strip()
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
                source_override = source_override_map.get(source) or {}
                seller_strategy = seller_strategy_map.get(seller_key, {})
                threshold_delta = source_strategy.get("threshold_delta") or {}
                seller_threshold_delta = seller_strategy.get("threshold_delta") or {}
                seller_runtime_delta = seller_runtime.get("threshold_delta") or {}
                list_action_lane = str(source_strategy.get("list_action_lane") or "open")
                allow_auto_list = bool(source_strategy.get("allow_auto_list", True))
                list_action_cap = self._source_action_exec_cap(
                    lane=list_action_lane,
                    batch_limit=batch_limit,
                )
                if item_type and item_type not in TRADABLE_ITEM_TYPES:
                    skipped_non_tradable += 1
                    continue
                risk_cluster = self._risk_cluster_key(row)
                cluster_override = cluster_override_map.get(risk_cluster) or {}
                source_override_state = str(source_override.get("state") or "normal")
                cluster_override_state = str(cluster_override.get("state") or "normal")
                if source_override_state == "frozen":
                    skipped_source_batch_cap += 1
                    continue
                if cluster_override_state == "frozen":
                    skipped_cluster_batch_cap += 1
                    continue
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
                if source_override_state == "observe":
                    position_control = {
                        **position_control,
                        "batch_cap": min(int(position_control["batch_cap"]), 1),
                        "capital_cap": min(float(position_control["capital_cap"]), approved_buy_price),
                    }
                if current_source_count >= int(position_control["batch_cap"]):
                    skipped_source_batch_cap += 1
                    continue
                if current_source_capital + approved_buy_price > float(position_control["capital_cap"]) + 1e-9:
                    skipped_source_capital += 1
                    continue
                cluster_position_control = cluster_position_control_map.get(risk_cluster) or {
                    "batch_cap": batch_limit,
                    "capital_cap": approved_buy_price * batch_limit,
                }
                current_cluster_count = int(cluster_approved_counts.get(risk_cluster) or 0)
                current_cluster_capital = float(cluster_approved_capital.get(risk_cluster) or 0.0)
                if cluster_override_state == "observe":
                    cluster_position_control = {
                        **cluster_position_control,
                        "batch_cap": min(int(cluster_position_control["batch_cap"]), 1),
                        "capital_cap": min(float(cluster_position_control["capital_cap"]), approved_buy_price),
                    }
                if current_cluster_count >= int(cluster_position_control["batch_cap"]):
                    skipped_cluster_batch_cap += 1
                    continue
                if current_cluster_capital + approved_buy_price > float(cluster_position_control["capital_cap"]) + 1e-9:
                    skipped_cluster_capital += 1
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
                    cluster_approved_counts[risk_cluster] = current_cluster_count + 1
                    cluster_approved_capital[risk_cluster] = current_cluster_capital + approved_buy_price
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
                                if not allow_auto_list or list_action_lane == "blocked":
                                    list_exec_skipped_source_action += 1
                                elif int(source_list_exec_counts.get(source) or 0) >= int(list_action_cap):
                                    list_exec_skipped_source_action_cap += 1
                                else:
                                    list_exec_attempted += 1
                                    list_res = execution_service.execute_list(
                                        trade_id=trade_id,
                                        dry_run=auto_execute_list_dry_run,
                                        note="auto listed after buy execution",
                                    )
                                    if list_res.get("success"):
                                        list_exec_succeeded += 1
                                        source_list_exec_counts[source] = int(source_list_exec_counts.get(source) or 0) + 1
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

            alert_dispatch = self._maybe_dispatch_alert_email(
                dashboard_metrics=dashboard_metrics,
                profit_guard=profit_guard,
                source="autotrade_bot",
            )
            alert_slack_dispatch = self._maybe_dispatch_alert_slack(
                dashboard_metrics=dashboard_metrics,
                profit_guard=profit_guard,
                source="autotrade_bot",
            )
            alert_telegram_dispatch = self._maybe_dispatch_alert_telegram(
                dashboard_metrics=dashboard_metrics,
                profit_guard=profit_guard,
                source="autotrade_bot",
            )
            alert_webhook_dispatch = self._maybe_dispatch_alert_webhook(
                dashboard_metrics=dashboard_metrics,
                profit_guard=profit_guard,
                source="autotrade_bot",
            )

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
                "skipped_cluster_batch_cap": skipped_cluster_batch_cap,
                "skipped_cluster_capital": skipped_cluster_capital,
                "skipped_non_tradable": skipped_non_tradable,
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
                "list_exec_skipped_source_action": list_exec_skipped_source_action,
                "list_exec_skipped_source_action_cap": list_exec_skipped_source_action_cap,
                "list_exec_dry_run": auto_execute_list_dry_run,
                "profit_guard": profit_guard,
                "validation_baseline": validation_baseline,
                "loss_recovery": loss_recovery,
                "source_strategies": list(source_strategy_map.values())[:5],
                "source_position_controls": source_position_controls[:5],
                "cluster_position_controls": cluster_position_controls[:5],
                "seller_strategies": list(seller_strategy_map.values())[:8],
                "seller_position_controls": seller_position_controls[:8],
                "seller_controls": seller_control_sync.get("status") or {},
                "alert_dispatch": alert_dispatch,
                "alert_slack_dispatch": alert_slack_dispatch,
                "alert_telegram_dispatch": alert_telegram_dispatch,
                "alert_webhook_dispatch": alert_webhook_dispatch,
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
