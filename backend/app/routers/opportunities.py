from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from .. import repositories as repo
from ..schemas import FeatureData
from ..services.feature_extractor import FeatureExtractor
from ..services.opportunity import score_opportunity
from ..services.risk_control import apply_risk_gate, assess_opportunity_risk, format_risk_note
from ..services.valuation import estimate_valuation

router = APIRouter(prefix="/opportunities", tags=["opportunities"])
extractor = FeatureExtractor()


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
    open_listings = repo.get_open_listings(limit=limit)
    created = 0
    ignored = 0
    blocked = 0
    for listing in open_listings:
        listing_row_id = int(listing["id"])
        feature_row = repo.get_features("listing", int(listing["id"]))
        if feature_row:
            feature = FeatureData(
                card_name=feature_row["card_name"],
                rarity=feature_row["rarity"],
                edition=feature_row["edition"],
                card_condition=feature_row["card_condition"],
                confidence=feature_row["confidence"],
            )
        else:
            feature, source = await extractor.extract(listing["title"], listing["description"])
            repo.save_features("listing", listing_row_id, feature, source)

        sales = repo.get_recent_sales(feature, limit=80)
        valuation = estimate_valuation(
            listing_row_id=listing_row_id,
            listing_price=float(listing["list_price"]),
            features=feature,
            comparable_prices=[float(row["sold_price"]) for row in sales],
        )
        valuation_id = repo.save_valuation(valuation)

        seller_open_count = repo.get_seller_open_listing_count(
            source=str(listing["source"]),
            seller_id=listing["seller_id"],
            exclude_row_id=listing_row_id,
        )
        risk = assess_opportunity_risk(
            list_price=float(listing["list_price"]),
            valuation=valuation,
            seller_open_listing_count=seller_open_count,
            listing_text=f"{listing['title']} {listing['description']}",
        )

        profit, roi, score, status = score_opportunity(
            list_price=float(listing["list_price"]),
            expected_sale_price=valuation.expected_sale_price,
            risk_score=risk.score,
        )
        status = apply_risk_gate(status, risk)
        repo.upsert_opportunity(
            listing_row_id=listing_row_id,
            valuation_id=valuation_id,
            expected_profit=profit,
            roi=roi,
            score=score,
            status=status,
            note=format_risk_note(risk),
        )
        if status == "pending_review":
            created += 1
        elif status == "blocked_risk":
            blocked += 1
        else:
            ignored += 1

    return {
        "processed": len(open_listings),
        "pending_review": created,
        "blocked_risk": blocked,
        "ignored": ignored,
    }


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
    repo.update_opportunity_status(opportunity_id, "rejected", note)
    return {"opportunity_id": opportunity_id, "status": "rejected"}


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
