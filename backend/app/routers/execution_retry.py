from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from ..services.execution_retry import execution_retry_service

router = APIRouter(prefix="/execution-retry", tags=["execution-retry"])


class ExecutionRetryConfigPatch(BaseModel):
    interval_sec: int | None = None
    batch_size: int | None = None
    action: str | None = None
    dry_run: bool | None = None
    force: bool | None = None


@router.get("/status")
def status() -> dict:
    return execution_retry_service.status()


@router.post("/start")
def start() -> dict:
    return execution_retry_service.start()


@router.post("/stop")
def stop() -> dict:
    return execution_retry_service.stop()


@router.post("/run-once")
def run_once(
    limit: int = Query(default=0, ge=0, le=200),
    force: bool = False,
    action: str | None = Query(default=None, pattern="^(buy|list|sell|all)$"),
    dry_run: bool | None = None,
    execution_force: bool | None = None,
    confirm_token: str | None = None,
) -> dict:
    try:
        return execution_retry_service.run_once(
            limit=limit if limit > 0 else None,
            service_force=force,
            action=action,
            dry_run=dry_run,
            execution_force=execution_force,
            confirm_token=confirm_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/config")
def update_config(payload: ExecutionRetryConfigPatch) -> dict:
    return execution_retry_service.update_config(
        interval_sec=payload.interval_sec,
        batch_size=payload.batch_size,
        action=payload.action,
        dry_run=payload.dry_run,
        force=payload.force,
    )
