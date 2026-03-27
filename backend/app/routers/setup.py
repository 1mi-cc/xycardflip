from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi import HTTPException
from fastapi import Request
from pydantic import BaseModel

from ..auth_utils import extract_bearer_token
from ..auth_utils import fetch_user_by_session_token
from ..database import get_conn
from ..services.first_run_setup import apply_first_run_setup
from ..services.first_run_setup import get_first_run_setup_status
from ..services.first_run_setup import rollback_setting_audit
from ..services.first_run_setup import list_setting_audit_logs
from ..services.gemini_client import GeminiClient

router = APIRouter(prefix="/setup", tags=["setup"])


class FirstRunSetupIn(BaseModel):
    ui_auth_password: str | None = None
    ui_auth_nickname: str | None = None
    gemini_api_key: str | None = None
    gemini_key_source_path: str | None = None
    auto_tune_auto_apply_enabled: bool | None = None
    auto_tune_cooldown_hours: int | None = None
    auto_tune_min_closed_batches: int | None = None
    auto_tune_latest_min_sold_count: int | None = None
    auto_tune_previous_min_sold_count: int | None = None


def _require_setup_access(request: Request) -> str:
    status = get_first_run_setup_status()
    if status["bootstrap_password_mode"]:
        return "bootstrap_setup"

    token = extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="setup requires admin login")

    with get_conn() as conn:
        user_row = fetch_user_by_session_token(conn, token, touch_session=True)
        if user_row is None:
            raise HTTPException(status_code=401, detail="login expired")
        role = str(user_row["role"] or "").strip().lower()
        if role != "admin":
            raise HTTPException(status_code=403, detail="setup requires admin role")
        return str(user_row["username"] or "admin").strip() or "admin"


@router.get("/status")
def setup_status() -> dict[str, Any]:
    return get_first_run_setup_status()


@router.get("/audit")
def setup_audit(request: Request, limit: int = 50) -> dict[str, Any]:
    _require_setup_access(request)
    items = list_setting_audit_logs(limit=limit)
    return {
        "items": items,
        "count": len(items),
        "limit": limit,
    }


@router.post("/audit/{audit_id}/rollback")
def setup_audit_rollback(request: Request, audit_id: int) -> dict[str, Any]:
    actor = _require_setup_access(request)
    try:
        return rollback_setting_audit(audit_id, actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/test-gemini")
async def setup_test_gemini(request: Request) -> dict[str, Any]:
    _require_setup_access(request)
    client = GeminiClient()
    return await client.test_connection()


@router.post("/apply")
def setup_apply(request: Request, payload: FirstRunSetupIn) -> dict[str, Any]:
    actor = _require_setup_access(request)
    try:
        return apply_first_run_setup(payload.model_dump(), actor=actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
