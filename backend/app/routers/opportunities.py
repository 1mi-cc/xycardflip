from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from .. import repositories as repo
from ..services.opportunity_scan import scan_open_listings

router = APIRouter(prefix="/opportunities", tags=["opportunities"])


def _parse_risk_score(note: str) -> float | None:
    text = (note or "").strip()
    if not text:
        return None
    for part in text.split(";"):
        seg = part.strip()
        if not seg.startswith("risk_score="):
            continue
        _, value = seg.split("=", 1)
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


@router.post("/scan")
async def scan_opportunities(limit: int = Query(default=50, ge=1, le=500)) -> dict[str, int]:
    return await scan_open_listings(limit=limit)


@router.get("")
def list_opportunities(status: str | None = None, limit: int = Query(default=100, ge=1, le=500)) -> dict:
    rows = repo.list_opportunities(status=status, limit=limit)
    items = [
        {
            "opportunity_id": row["id"],
            "listing_row_id": row["listing_row_id"],
            "title": row["title"],
            "list_price": row["list_price"],
            "expected_sale_price": row["expected_sale_price"],
            "suggested_list_price": row["suggested_list_price"],
            "expected_profit": row["expected_profit"],
            "roi": row["roi"],
            "score": row["score"],
            "status": row["status"],
            "risk_note": row["review_note"],
        }
        for row in rows
    ]
    return {"items": items, "count": len(items)}


@router.post("/{opportunity_id}/reject")
def reject_opportunity(opportunity_id: int, note: str = "manual reject") -> dict:
    target = repo.get_opportunity(opportunity_id)
    if not target:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    log_id = repo.create_opportunity_reject_log(
        opportunity_id,
        note=note,
        reject_mode="single_reject",
    )
    repo.update_opportunity_status(opportunity_id, "rejected", note)
    return {
        "opportunity_id": opportunity_id,
        "status": "rejected",
        "reject_log_id": log_id,
    }


@router.post("/{opportunity_id}/send-to-review")
def send_to_review(opportunity_id: int, note: str = "manual review override") -> dict:
    target = repo.get_opportunity(opportunity_id)
    if not target:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    if target["status"] != "blocked_risk":
        raise HTTPException(status_code=400, detail="Opportunity is not blocked_risk")
    repo.update_opportunity_status(opportunity_id, "pending_review", note)
    return {"opportunity_id": opportunity_id, "status": "pending_review"}


@router.post("/send-to-review/batch")
def send_to_review_batch(
    max_risk_score: float = Query(default=45.0, ge=0.0, le=100.0),
    limit: int = Query(default=200, ge=1, le=1000),
    note: str = "manual batch review override",
) -> dict:
    rows = repo.list_opportunities(status="blocked_risk", limit=limit)
    eligible_ids: list[int] = []
    skipped_no_score = 0
    for row in rows:
        score = _parse_risk_score(str(row["review_note"] or ""))
        if score is None:
            skipped_no_score += 1
            continue
        if score <= max_risk_score:
            eligible_ids.append(int(row["id"]))

    moved = 0
    for opp_id in eligible_ids:
        repo.update_opportunity_status(opp_id, "pending_review", note)
        moved += 1

    return {
        "scanned": len(rows),
        "eligible": len(eligible_ids),
        "moved": moved,
        "skipped_no_score": skipped_no_score,
        "max_risk_score": max_risk_score,
    }


@router.post("/reject/batch")
def reject_blocked_batch(
    limit: int = Query(default=200, ge=1, le=1000),
    note: str = "manual batch reject from blocked list",
) -> dict:
    rows = repo.list_opportunities(status="blocked_risk", limit=limit)
    rejected = 0
    logged = 0
    log_ids: list[int] = []
    for row in rows:
        opp_id = int(row["id"])
        log_id = repo.create_opportunity_reject_log(
            opp_id,
            note=note,
            reject_mode="blocked_batch_reject",
        )
        if log_id is not None:
            logged += 1
            log_ids.append(log_id)
        repo.update_opportunity_status(opp_id, "rejected", note)
        rejected += 1

    return {
        "scanned": len(rows),
        "rejected": rejected,
        "logged": logged,
        "reject_log_ids": log_ids,
        "limit": limit,
    }


@router.get("/reject-logs")
def list_reject_logs(
    limit: int = Query(default=200, ge=1, le=1000),
    opportunity_id: int | None = None,
) -> dict:
    rows = repo.list_opportunity_reject_logs(limit=limit, opportunity_id=opportunity_id)
    items = []
    for row in rows:
        try:
            snapshot = json.loads(str(row["snapshot_json"] or "{}"))
        except json.JSONDecodeError:
            snapshot = {}
        items.append(
            {
                "id": int(row["id"]),
                "opportunity_id": int(row["opportunity_id"]),
                "listing_row_id": int(row["listing_row_id"]),
                "reject_mode": str(row["reject_mode"] or ""),
                "note": str(row["note"] or ""),
                "title": row["title"],
                "list_price": row["list_price"],
                "current_status": row["current_status"],
                "created_at": row["created_at"],
                "snapshot": snapshot,
            }
        )
    return {
        "items": items,
        "count": len(items),
    }
