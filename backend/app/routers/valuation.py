from __future__ import annotations

from fastapi import APIRouter, HTTPException

from .. import repositories as repo
from ..schemas import FeatureData
from ..services.feature_extractor import FeatureExtractor
from ..services.risk_control import assess_opportunity_risk, format_risk_note
from ..services.valuation import estimate_valuation

router = APIRouter(prefix="/valuation", tags=["valuation"])
extractor = FeatureExtractor()


@router.post("/listings/{listing_row_id}/extract", response_model=FeatureData)
async def extract_listing_features(listing_row_id: int) -> FeatureData:
    listing = repo.get_listing(listing_row_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    feature, source = await extractor.extract(listing["title"], listing["description"])
    repo.save_features("listing", listing_row_id, feature, source)
    return feature


@router.post("/listings/{listing_row_id}/estimate")
async def estimate_listing_value(listing_row_id: int) -> dict:
    listing = repo.get_listing(listing_row_id)
    if not listing:
        raise HTTPException(status_code=404, detail="Listing not found")

    feature_row = repo.get_features("listing", listing_row_id)
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
    comparable_prices = [float(row["sold_price"]) for row in sales]
    result = estimate_valuation(
        listing_row_id=listing_row_id,
        listing_price=float(listing["list_price"]),
        features=feature,
        comparable_prices=comparable_prices,
    )
    seller_open_count = repo.get_seller_open_listing_count(
        source=str(listing["source"]),
        seller_id=listing["seller_id"],
        exclude_row_id=listing_row_id,
    )
    risk = assess_opportunity_risk(
        list_price=float(listing["list_price"]),
        valuation=result,
        seller_open_listing_count=seller_open_count,
        listing_text=f"{listing['title']} {listing['description']}",
    )
    valuation_id = repo.save_valuation(result)
    return {
        "valuation_id": valuation_id,
        "valuation": result.model_dump(),
        "risk": {
            "score": risk.score,
            "level": risk.level,
            "hard_block": risk.hard_block,
            "reasons": list(risk.reasons),
            "note": format_risk_note(risk),
        },
    }
