from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi import Request

from ..config import settings
from ..database import get_data_integrity_status
from ..services.automation import automation_service
from ..services.autotrade import auto_trade_service
from ..services.execution import execution_service
from ..services.execution_retry import execution_retry_service
from ..services.market_monitor import monitor_service
from ..services.operating_state import operating_state_service
from ..services.proxy_resolver import network_policy_status
from ..services.supabase_sync import supabase_sync_service
from ..vnpy_system.event_engine import event_engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health(request: Request) -> dict[str, Any]:
    monitor_status = monitor_service.status()
    return {
        "status": "ok",
        "env": settings.app_env,
        "monitoring": {
            "uptime_kuma_enabled": settings.uptime_kuma_enabled,
            "uptime_kuma_url": settings.uptime_kuma_url,
        },
        "auto_start": {
            "monitor": settings.auto_start_monitor,
            "autotrade": settings.auto_start_autotrade,
            "execution_retry": settings.auto_start_execution_retry,
            "supabase_sync": settings.auto_start_supabase_sync,
        },
        "startup_services": getattr(request.app.state, "startup_services", {}),
        "network_policy": network_policy_status(),
        "monitor_health": monitor_status.get("health", {}),
        "operating_state": operating_state_service.status(),
        "supabase_sync": supabase_sync_service.status(),
        "data_integrity": get_data_integrity_status(),
        "automation_guards": {
            "automation": automation_service.guard_status(),
            "autotrade": auto_trade_service.guard_status(),
            "execution_retry": execution_retry_service.guard_status(),
            "execution_retry_replay": execution_service.retry_guard_status(),
        },
        "event_handlers": event_engine.handler_status(),
    }
