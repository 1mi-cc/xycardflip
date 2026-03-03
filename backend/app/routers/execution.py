from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import repositories as repo
from ..services.execution import execution_service

router = APIRouter(prefix="/execution", tags=["execution"])


def _raise_for_value_error(exc: ValueError) -> None:
    message = str(exc)
    if message == "Trade not found":
        raise HTTPException(status_code=404, detail=message) from exc
    raise HTTPException(status_code=400, detail=message) from exc


@router.get("/status")
def status() -> dict:
    return execution_service.status()


@router.post("/buy/{trade_id}")
def execute_buy(
    trade_id: int,
    dry_run: bool = True,
    force: bool = False,
    confirm_token: str | None = None,
) -> dict:
    try:
        return execution_service.execute_buy(
            trade_id=trade_id,
            dry_run=dry_run,
            force=force,
            confirm_token=confirm_token,
        )
    except ValueError as exc:
        _raise_for_value_error(exc)


@router.post("/list/{trade_id}")
def execute_list(
    trade_id: int,
    dry_run: bool = True,
    force: bool = False,
    confirm_token: str | None = None,
    listing_url: str = "",
    note: str = "",
    update_trade_state: bool = True,
) -> dict:
    try:
        return execution_service.execute_list(
            trade_id=trade_id,
            dry_run=dry_run,
            force=force,
            confirm_token=confirm_token,
            listing_url=listing_url,
            note=note,
            update_trade_state=update_trade_state,
        )
    except ValueError as exc:
        _raise_for_value_error(exc)


@router.post("/sell/{trade_id}")
def execute_sell(
    trade_id: int,
    dry_run: bool = True,
    force: bool = False,
    confirm_token: str | None = None,
    sold_price: float | None = Query(default=None, gt=0),
    note: str = "",
    update_trade_state: bool = True,
) -> dict:
    try:
        return execution_service.execute_sell(
            trade_id=trade_id,
            dry_run=dry_run,
            force=force,
            confirm_token=confirm_token,
            sold_price=sold_price,
            note=note,
            update_trade_state=update_trade_state,
        )
    except ValueError as exc:
        _raise_for_value_error(exc)


@router.post("/retry-failed")
def retry_failed(
    action: str | None = Query(default=None, pattern="^(buy|list|sell)$"),
    limit: int = Query(default=20, ge=1, le=200),
    dry_run: bool = True,
    force: bool = False,
    confirm_token: str | None = None,
) -> dict:
    try:
        return execution_service.retry_failed(
            action=action,
            limit=limit,
            dry_run=dry_run,
            force=force,
            confirm_token=confirm_token,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/logs")
def list_logs(
    trade_id: int | None = None,
    action: str | None = Query(default=None, pattern="^(buy|list|sell)$"),
    provider: str | None = None,
    dry_run: bool | None = None,
    success: bool | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    rows = repo.list_execution_logs(
        trade_id=trade_id,
        action=action,
        provider=provider,
        dry_run=dry_run,
        success=success,
        limit=limit,
    )
    items = [
        {
            "id": row["id"],
            "trade_id": row["trade_id"],
            "action": row["action"],
            "provider": row["provider"],
            "dry_run": bool(row["dry_run"]),
            "success": bool(row["success"]),
            "error": row["error"],
            "request_json": row["request_json"],
            "response_json": row["response_json"],
            "trade_status": row["trade_status"],
            "approved_buy_price": row["approved_buy_price"],
            "target_sell_price": row["target_sell_price"],
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"items": items, "count": len(items)}
