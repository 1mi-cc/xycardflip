from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi import Request

from ..config import settings
from ..services.market_monitor import monitor_service
from ..services.proxy_resolver import network_policy_status
from ..vnpy_system.event_engine import event_engine

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health(request: Request) -> dict[str, Any]:
    monitor_status = monitor_service.status()
    return {
        "status": "ok",
        "env": settings.app_env,
        "auto_start": {
            "monitor": settings.auto_start_monitor,
            "autotrade": settings.auto_start_autotrade,
            "execution_retry": settings.auto_start_execution_retry,
        },
        "startup_services": getattr(request.app.state, "startup_services", {}),
        "network_policy": network_policy_status(),
        "monitor_health": monitor_status.get("health", {}),
        "event_handlers": event_engine.handler_status(),
    }
