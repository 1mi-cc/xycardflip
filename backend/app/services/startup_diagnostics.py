from __future__ import annotations

from typing import Any

from ..config import settings
from ..config import single_account_guardrail_status
from .execution import execution_service
from .gemini_client import GeminiClient


def startup_configuration_checks() -> dict[str, Any]:
    items: list[dict[str, str]] = []
    readiness = execution_service.webhook_readiness()
    gemini_runtime = GeminiClient().get_runtime_status()
    guardrails = single_account_guardrail_status()

    if bool(guardrails.get("enabled")) and not bool(guardrails.get("aligned")):
        drift = ", ".join(str(code) for code in guardrails.get("failing_codes", []))
        items.append(
            {
                "severity": "warning",
                "code": "single_account_guardrails_drift",
                "message": (
                    "Single-account local mode is enabled but guardrails drifted"
                    + (f": {drift}" if drift else "")
                ),
            }
        )

    if bool(readiness.get("live_enabled")) and not bool(readiness.get("live_ready")):
        missing = ", ".join(str(part) for part in readiness.get("missing", []))
        items.append(
            {
                "severity": "critical",
                "code": "execution_live_not_ready",
                "message": (
                    "Live execution is enabled but webhook readiness is incomplete"
                    + (f": {missing}" if missing else "")
                ),
            }
        )

    if settings.auto_tune_auto_apply_enabled and settings.auto_tune_min_closed_batches < 2:
        items.append(
            {
                "severity": "warning",
                "code": "auto_tune_batches_too_low",
                "message": "AUTO_TUNE_MIN_CLOSED_BATCHES should be at least 2 for safer auto-apply",
            }
        )

    if settings.auto_tune_auto_apply_enabled and settings.auto_tune_cooldown_hours < 6:
        items.append(
            {
                "severity": "warning",
                "code": "auto_tune_cooldown_too_low",
                "message": "AUTO_TUNE_COOLDOWN_HOURS below 6h may cause threshold oscillation",
            }
        )

    if settings.auto_tune_auto_apply_enabled and settings.auto_tune_latest_min_sold_count < 5:
        items.append(
            {
                "severity": "warning",
                "code": "auto_tune_latest_sample_too_low",
                "message": "AUTO_TUNE_LATEST_MIN_SOLD_COUNT below 5 weakens evidence quality",
            }
        )

    if settings.auto_tune_auto_apply_enabled and settings.auto_tune_previous_min_sold_count < 3:
        items.append(
            {
                "severity": "warning",
                "code": "auto_tune_previous_sample_too_low",
                "message": "AUTO_TUNE_PREVIOUS_MIN_SOLD_COUNT below 3 weakens trend confirmation",
            }
        )

    if not str(settings.ui_auth_password or "").strip():
        items.append(
            {
                "severity": "info",
                "code": "bootstrap_password_mode",
                "message": "UI_AUTH_PASSWORD is empty; startup will use one-time bootstrap credentials",
            }
        )

    if gemini_runtime["external_source_configured"] and not gemini_runtime["external_source_found"]:
        items.append(
            {
                "severity": "warning",
                "code": "gemini_external_source_missing",
                "message": (
                    "GEMINI_KEY_SOURCE_PATH is configured but the external Gemini pool was not found"
                ),
            }
        )

    highest = "ok"
    for severity in ("critical", "warning", "info"):
        if any(item["severity"] == severity for item in items):
            highest = severity
            break

    return {
        "status": highest,
        "items": items,
        "count": len(items),
    }
