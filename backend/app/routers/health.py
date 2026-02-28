from __future__ import annotations

from fastapi import APIRouter

from ..config import settings

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health() -> dict[str, str]:
    return {"status": "ok", "env": settings.app_env}

