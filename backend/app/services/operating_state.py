from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from math import ceil
from typing import Any

from .. import repositories as repo
from ..config import settings
from .autotrade import auto_trade_service
from .execution_retry import execution_retry_service
from .market_monitor import monitor_service


_STATE_PRIORITY = {
    "normal": 0,
    "cautious": 1,
    "recovery": 2,
}


@dataclass(frozen=True)
class OperatingPolicy:
    state: str
    scan_limit_factor: float
    autotrade_limit_factor: float
    execution_retry_limit_factor: float
    allow_autotrade: bool
    allow_execution_retry: bool
    require_manual_review: bool


def _clamp_ratio(value: float) -> float:
    return max(0.05, min(1.0, float(value)))


def _escalate(current: str, target: str) -> str:
    if _STATE_PRIORITY[target] > _STATE_PRIORITY[current]:
        return target
    return current


def _policy_for_state(state: str) -> OperatingPolicy:
    if state == "recovery":
        factor = _clamp_ratio(settings.operating_state_recovery_limit_factor)
        return OperatingPolicy(
            state=state,
            scan_limit_factor=factor,
            autotrade_limit_factor=factor,
            execution_retry_limit_factor=factor,
            allow_autotrade=False,
            allow_execution_retry=False,
            require_manual_review=True,
        )
    if state == "cautious":
        factor = _clamp_ratio(settings.operating_state_cautious_limit_factor)
        return OperatingPolicy(
            state=state,
            scan_limit_factor=factor,
            autotrade_limit_factor=factor,
            execution_retry_limit_factor=factor,
            allow_autotrade=True,
            allow_execution_retry=True,
            require_manual_review=True,
        )
    return OperatingPolicy(
        state="normal",
        scan_limit_factor=1.0,
        autotrade_limit_factor=1.0,
        execution_retry_limit_factor=1.0,
        allow_autotrade=True,
        allow_execution_retry=True,
        require_manual_review=False,
    )


class OperatingStateService:
    """Aggregates runtime health into one safe automation posture."""

    def status(self) -> dict[str, Any]:
        monitor = monitor_service.status()
        autotrade = auto_trade_service.status()
        execution_retry = execution_retry_service.status()
        execution_health = repo.get_execution_log_summary(
            limit=settings.operating_state_execution_window,
        )

        state = "normal"
        reasons: list[str] = []
        monitor_health = monitor.get("health", {}) if isinstance(monitor, dict) else {}
        monitor_success_rate = float(monitor_health.get("success_rate") or 1.0)
        monitor_samples = int(monitor_health.get("samples") or 0)
        monitor_guard_triggered = bool(monitor_health.get("guard_triggered"))
        execution_sample_size = int(execution_health.get("sample_size") or 0)
        execution_failure_rate = float(execution_health.get("failure_rate") or 0.0)
        execution_business_ban_count = int(execution_health.get("business_ban_count") or 0)

        if bool(monitor.get("circuit_open")):
            state = _escalate(state, "recovery")
            reasons.append("monitor_circuit_open")

        if monitor_guard_triggered:
            state = _escalate(state, "recovery")
            reasons.append("monitor_health_guard_triggered")

        if monitor_samples >= int(settings.operating_state_min_monitor_samples):
            if monitor_success_rate <= float(settings.operating_state_recovery_success_rate):
                state = _escalate(state, "recovery")
                reasons.append(f"monitor_success_rate_recovery:{monitor_success_rate:.2f}")
            elif monitor_success_rate <= float(settings.operating_state_cautious_success_rate):
                state = _escalate(state, "cautious")
                reasons.append(f"monitor_success_rate_cautious:{monitor_success_rate:.2f}")

        if execution_sample_size >= int(settings.operating_state_min_execution_samples):
            if (
                execution_failure_rate >= float(settings.operating_state_recovery_failure_rate)
                or execution_business_ban_count >= int(settings.operating_state_recovery_business_bans)
            ):
                state = _escalate(state, "recovery")
                reasons.append(
                    "execution_health_recovery:"
                    f"failure_rate={execution_failure_rate:.2f},"
                    f"business_bans={execution_business_ban_count}"
                )
            elif (
                execution_failure_rate >= float(settings.operating_state_cautious_failure_rate)
                or execution_business_ban_count >= int(settings.operating_state_cautious_business_bans)
            ):
                state = _escalate(state, "cautious")
                reasons.append(
                    "execution_health_cautious:"
                    f"failure_rate={execution_failure_rate:.2f},"
                    f"business_bans={execution_business_ban_count}"
                )

        if execution_retry.get("last_error"):
            state = _escalate(state, "cautious")
            reasons.append("execution_retry_last_error")

        policy = _policy_for_state(state)
        return {
            "state": state,
            "reasons": reasons or ["healthy"],
            "recommendations": {
                "scan_limit_factor": policy.scan_limit_factor,
                "autotrade_limit_factor": policy.autotrade_limit_factor,
                "execution_retry_limit_factor": policy.execution_retry_limit_factor,
                "allow_autotrade": policy.allow_autotrade,
                "allow_execution_retry": policy.allow_execution_retry,
                "require_manual_review": policy.require_manual_review,
            },
            "signals": {
                "monitor_circuit_open": bool(monitor.get("circuit_open")),
                "monitor_health_samples": monitor_samples,
                "monitor_health_success_rate": round(monitor_success_rate, 4),
                "monitor_health_guard_triggered": monitor_guard_triggered,
                "execution_sample_size": execution_sample_size,
                "execution_success_rate": round(
                    float(execution_health.get("success_rate") or 0.0),
                    4,
                ),
                "execution_failure_rate": round(execution_failure_rate, 4),
                "execution_business_ban_count": execution_business_ban_count,
                "execution_last_failure_at": execution_health.get("last_failure_at", ""),
                "autotrade_running": bool(autotrade.get("running")),
                "execution_retry_running": bool(execution_retry.get("running")),
            },
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def scale_limit(
        requested_limit: int | None,
        configured_limit: int,
        factor: float,
        *,
        maximum: int,
    ) -> int:
        base = int(requested_limit or configured_limit or 1)
        normalized = max(1, min(maximum, base))
        if factor >= 0.999:
            return normalized
        return max(1, min(maximum, int(ceil(normalized * _clamp_ratio(factor)))))


operating_state_service = OperatingStateService()
