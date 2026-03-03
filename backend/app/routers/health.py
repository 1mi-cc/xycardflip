from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi import Request

from ..config import settings
from ..services.proxy_resolver import network_policy_status

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health(request: Request) -> dict[str, Any]:
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
    }
