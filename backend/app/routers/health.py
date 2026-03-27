from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi import Response

from ..config import settings
from ..database import get_database_health_snapshot
from ..database import get_data_integrity_status
from ..services.automation import automation_service
from ..services.autotrade import auto_trade_service
from ..services.execution import execution_service
from ..services.execution_retry import execution_retry_service
from ..services.gemini_client import GeminiClient
from ..services.market_monitor import monitor_service
from ..services.operating_state import operating_state_service
from ..services.proxy_resolver import network_policy_status
from ..services.startup_diagnostics import startup_configuration_checks
from ..services.supabase_sync import supabase_sync_service

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict[str, Any]:
    monitor_status = monitor_service.status()
    database_status = get_database_health_snapshot()
    gemini_runtime = GeminiClient().get_runtime_status()
    return {
        "status": "ok",
        "env": settings.app_env,
        "database": database_status,
        "gemini_runtime": gemini_runtime,
        "monitoring": {
            "uptime_kuma_enabled": settings.uptime_kuma_enabled,
        },
        "auto_start": {
            "monitor": settings.auto_start_monitor,
            "autotrade": settings.auto_start_autotrade,
            "execution_retry": settings.auto_start_execution_retry,
            "supabase_sync": settings.auto_start_supabase_sync,
        },
        "network_policy": network_policy_status(
            include_runtime=False,
            include_proxy_pool_api=False,
        ),
        "monitor_health": monitor_status.get("health", {}),
        "operating_state": operating_state_service.status(),
        "supabase_sync": supabase_sync_service.status(),
        "data_integrity": get_data_integrity_status(),
        "startup_checks": startup_configuration_checks(),
        "automation_guards": {
            "automation": automation_service.guard_status(),
            "autotrade": auto_trade_service.guard_status(),
            "execution_retry": execution_retry_service.guard_status(),
            "execution_retry_replay": execution_service.retry_guard_status(),
        },
    }


@router.get("/ready")
def ready(response: Response) -> dict[str, Any]:
    data_integrity = get_data_integrity_status()
    database_status = get_database_health_snapshot()
    operating_state = operating_state_service.status()

    reasons: list[str] = []
    if not bool(data_integrity.get("ok")):
        reasons.append("data_integrity_not_ok")
    for reason in database_status.get("degraded_reasons", []):
        reasons.append(f"database:{reason}")
    if str(operating_state.get("state") or "") == "recovery":
        reasons.append("operating_state:recovery")

    is_ready = not reasons
    response.status_code = 200 if is_ready else 503
    return {
        "status": "ready" if is_ready else "degraded",
        "ready": is_ready,
        "reasons": reasons,
        "database": {
            "journal_mode": database_status.get("journal_mode", ""),
            "degraded_reasons": database_status.get("degraded_reasons", []),
        },
        "data_integrity": {
            "ok": bool(data_integrity.get("ok")),
            "message": data_integrity.get("message", ""),
        },
        "operating_state": {
            "state": operating_state.get("state", ""),
            "reasons": operating_state.get("reasons", []),
        },
    }
