from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..route_guard import require_cardflip_operate
from ..route_guard import require_cardflip_view
from ..services.market_monitor import monitor_service

router = APIRouter(
    prefix="/monitor",
    tags=["monitor"],
    dependencies=[Depends(require_cardflip_view)],
)


@router.get("/status")
def status() -> dict:
    return monitor_service.status()


@router.get("/health")
def health() -> dict:
    status = monitor_service.status()
    return {
        "is_running": status.get("is_running", False),
        "circuit_open": status.get("circuit_open", False),
        "circuit_reason": status.get("circuit_reason", ""),
        "health": status.get("health", {}),
        "last_error": status.get("last_error", ""),
    }


@router.post("/start", dependencies=[Depends(require_cardflip_operate)])
def start() -> dict:
    return monitor_service.start()


@router.post("/stop", dependencies=[Depends(require_cardflip_operate)])
def stop() -> dict:
    return monitor_service.stop()


@router.post("/run-once", dependencies=[Depends(require_cardflip_operate)])
def run_once() -> dict:
    try:
        return monitor_service.run_once()
    except Exception as exc:
        status = monitor_service.status()
        raise HTTPException(
            status_code=502,
            detail={
                "message": "monitor run failed",
                "error": str(exc),
                "last_error": status.get("last_error", ""),
                "circuit_open": bool(status.get("circuit_open")),
                "circuit_reason": status.get("circuit_reason", ""),
            },
        ) from exc


@router.post("/reset-circuit", dependencies=[Depends(require_cardflip_operate)])
def reset_circuit(reason: str = Query(default="manual reset")) -> dict:
    return monitor_service.reset_circuit(reason=reason)


@router.post("/refresh-cookie", dependencies=[Depends(require_cardflip_operate)])
def refresh_cookie(kill_browsers: bool = Query(True)) -> dict:
    return monitor_service.refresh_cookie_local(kill_browsers=kill_browsers)
