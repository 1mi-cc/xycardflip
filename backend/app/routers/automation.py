from __future__ import annotations

from fastapi import APIRouter, Query

from ..config import settings
from ..services.automation import automation_service

router = APIRouter(prefix="/automation", tags=["automation"])


@router.get("/status")
def status() -> dict:
    return automation_service.status()


@router.post("/start")
def start(
    include_monitor: bool = settings.automation_default_include_monitor,
    include_autotrade: bool = settings.automation_default_include_autotrade,
    include_execution_retry: bool = settings.automation_default_include_execution_retry,
    include_supabase_sync: bool = settings.automation_default_include_supabase_sync,
) -> dict:
    return automation_service.start(
        include_monitor=include_monitor,
        include_autotrade=include_autotrade,
        include_execution_retry=include_execution_retry,
        include_supabase_sync=include_supabase_sync,
    )


@router.post("/stop")
def stop(
    include_monitor: bool = settings.automation_default_include_monitor,
    include_autotrade: bool = settings.automation_default_include_autotrade,
    include_execution_retry: bool = settings.automation_default_include_execution_retry,
    include_supabase_sync: bool = settings.automation_default_include_supabase_sync,
) -> dict:
    return automation_service.stop(
        include_monitor=include_monitor,
        include_autotrade=include_autotrade,
        include_execution_retry=include_execution_retry,
        include_supabase_sync=include_supabase_sync,
    )


@router.post("/run-once")
def run_once(
    include_monitor: bool = settings.automation_default_include_monitor,
    include_scan: bool = settings.automation_default_include_scan,
    include_autotrade: bool = settings.automation_default_include_autotrade,
    include_execution_retry: bool = settings.automation_default_include_execution_retry,
    include_supabase_sync: bool = settings.automation_default_include_supabase_sync,
    scan_limit: int = Query(default=0, ge=0, le=500),
    autotrade_limit: int = Query(default=0, ge=0, le=500),
    execution_retry_limit: int = Query(default=0, ge=0, le=200),
    force: bool = False,
    confirm_token: str | None = None,
) -> dict:
    return automation_service.run_once(
        include_monitor=include_monitor,
        include_scan=include_scan,
        include_autotrade=include_autotrade,
        include_execution_retry=include_execution_retry,
        include_supabase_sync=include_supabase_sync,
        scan_limit=scan_limit if scan_limit > 0 else None,
        autotrade_limit=autotrade_limit if autotrade_limit > 0 else None,
        execution_retry_limit=execution_retry_limit if execution_retry_limit > 0 else None,
        force=force,
        confirm_token=confirm_token,
    )


@router.post("/simulation-bootstrap")
def simulation_bootstrap(
    count: int = Query(default=6, ge=1, le=30),
) -> dict:
    return automation_service.bootstrap_simulation_data(count=count)
