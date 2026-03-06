from __future__ import annotations

from fastapi import APIRouter
from fastapi import Query

from ..services.supabase_sync import supabase_sync_service

router = APIRouter(prefix="/supabase", tags=["supabase"])


@router.get("/status")
def status() -> dict:
    return supabase_sync_service.status()


@router.post("/start")
def start() -> dict:
    return supabase_sync_service.start()


@router.post("/stop")
def stop() -> dict:
    return supabase_sync_service.stop()


@router.post("/run-once")
def run_once(force: bool = Query(False)) -> dict:
    return supabase_sync_service.run_once(force=force)


@router.post("/reset-cursors")
def reset_cursors(table: str = Query("", description="optional local table name")) -> dict:
    return supabase_sync_service.reset_cursors(table=table)
