from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from ..vnpy_system.system import system

router = APIRouter(prefix="/vnpy", tags=["vnpy"])


class KeywordsIn(BaseModel):
    keywords: list[str]


@router.get("/status")
def status() -> dict:
    return system.status()


@router.post("/start")
def start() -> dict:
    return system.start()


@router.post("/stop")
def stop() -> dict:
    return system.stop()


@router.post("/scan-once")
def scan_once() -> dict:
    return system.scan_once()


@router.post("/keywords")
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


@router.post("/strategy-profile")
def set_strategy_profile(profile: str = Query(..., pattern="^(aggressive|balanced|conservative|agg|cons|fast|safe)$")) -> dict:
    return system.set_strategy_profile(profile)
