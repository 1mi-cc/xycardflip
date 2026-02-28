from __future__ import annotations

from fastapi import APIRouter

from ..services.market_monitor import monitor_service

router = APIRouter(prefix="/monitor", tags=["monitor"])


@router.get("/status")
def status() -> dict:
    return monitor_service.status()


@router.post("/start")
def start() -> dict:
    return monitor_service.start()


@router.post("/stop")
def stop() -> dict:
    return monitor_service.stop()


@router.post("/run-once")
def run_once() -> dict:
    return monitor_service.run_once()

