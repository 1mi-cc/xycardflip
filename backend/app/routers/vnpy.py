from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from ..route_guard import require_cardflip_operate
from ..route_guard import require_cardflip_view
from ..vnpy_system.system import system

router = APIRouter(
    prefix="/vnpy",
    tags=["vnpy"],
    dependencies=[Depends(require_cardflip_view)],
)


class KeywordsIn(BaseModel):
    keywords: list[str]


@router.get("/status")
def status() -> dict:
    return system.status()


@router.post("/start", dependencies=[Depends(require_cardflip_operate)])
def start() -> dict:
    return system.start()


@router.post("/stop", dependencies=[Depends(require_cardflip_operate)])
def stop() -> dict:
    return system.stop()


@router.post("/scan-once", dependencies=[Depends(require_cardflip_operate)])
def scan_once() -> dict:
    return system.scan_once()


@router.post("/keywords", dependencies=[Depends(require_cardflip_operate)])
def update_keywords(payload: KeywordsIn, mode: str = Query(default="set", pattern="^(set|add)$")) -> dict:
    if mode == "add":
        for kw in payload.keywords:
            system.add_keyword(kw)
    else:
        system.set_keywords(payload.keywords)
    return {"keywords": system.status().get("keywords", [])}


@router.get("/strategy-profile")
def get_strategy_profile() -> dict:
    status = system.status()
    return {
        "strategy_profile": status.get("strategy_profile"),
        "strategy_thresholds": status.get("strategy_thresholds"),
    }


@router.post("/strategy-profile", dependencies=[Depends(require_cardflip_operate)])
def set_strategy_profile(profile: str = Query(..., pattern="^(aggressive|balanced|conservative|agg|cons|fast|safe)$")) -> dict:
    return system.set_strategy_profile(profile)
