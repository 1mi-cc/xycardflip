from __future__ import annotations

from fastapi import APIRouter, Query

from ..services.autotrade import auto_trade_service

router = APIRouter(prefix="/autotrade", tags=["autotrade"])


@router.get("/status")
def status() -> dict:
    return auto_trade_service.status()


@router.post("/start")
def start() -> dict:
    return auto_trade_service.start()


@router.post("/stop")
def stop() -> dict:
    return auto_trade_service.stop()


@router.post("/run-once")
def run_once(
    limit: int = Query(default=0, ge=0, le=500),
    force: bool = False,
) -> dict:
    return auto_trade_service.run_once(limit=limit if limit > 0 else None, force=force)
