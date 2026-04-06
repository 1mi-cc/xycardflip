from __future__ import annotations

from fastapi import APIRouter, Depends
from fastapi import Query

from ..route_guard import require_cardflip_operate
from ..route_guard import require_cardflip_view
from ..services.supabase_sync import supabase_sync_service

router = APIRouter(
    prefix="/supabase",
    tags=["supabase"],
    dependencies=[Depends(require_cardflip_view)],
)


@router.get("/status")
def status() -> dict:
    return supabase_sync_service.status()


@router.post("/start", dependencies=[Depends(require_cardflip_operate)])
def start() -> dict:
    return supabase_sync_service.start()


@router.post("/stop", dependencies=[Depends(require_cardflip_operate)])
def stop() -> dict:
    return supabase_sync_service.stop()


@router.post("/run-once", dependencies=[Depends(require_cardflip_operate)])
def run_once(force: bool = Query(False)) -> dict:
    return supabase_sync_service.run_once(force=force)


@router.post("/reset-cursors", dependencies=[Depends(require_cardflip_operate)])
def reset_cursors(table: str = Query("", description="optional local table name")) -> dict:
    return supabase_sync_service.reset_cursors(table=table)
