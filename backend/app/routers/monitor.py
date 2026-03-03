from __future__ import annotations

from fastapi import APIRouter, Query

from ..services.market_monitor import monitor_service

router = APIRouter(prefix="/monitor", tags=["monitor"])


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


@router.post("/start")
def start() -> dict:
    return monitor_service.start()


@router.post("/stop")
def stop() -> dict:
    return monitor_service.stop()


@router.post("/run-once")
def run_once() -> dict:
    return monitor_service.run_once()


@router.post("/refresh-cookie")
def refresh_cookie(kill_browsers: bool = Query(True)) -> dict:
    return monitor_service.refresh_cookie_local(kill_browsers=kill_browsers)
