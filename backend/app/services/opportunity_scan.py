from __future__ import annotations

from .. import repositories as repo
from ..schemas import FeatureData
from .feature_extractor import FeatureExtractor
from .opportunity import score_opportunity
from .risk_control import apply_risk_gate, assess_opportunity_risk, format_risk_note
from .valuation import estimate_valuation

_extractor = FeatureExtractor()


async def scan_open_listings(limit: int = 50) -> dict[str, int]:
    open_listings = repo.get_open_listings(limit=max(1, min(500, int(limit))))
    frozen_by_status = {"rejected", "approved_for_buy"}
    listing_ids = [int(row["id"]) for row in open_listings if row["id"] is not None]
    existing_status_map = repo.get_opportunity_status_map_by_listing_rows(listing_ids)
    created = 0
    ignored = 0
    blocked = 0
    failed = 0
    for listing in open_listings:
        try:
            listing_row_id = int(listing["id"])
            existing_status = existing_status_map.get(listing_row_id, "")
            if existing_status in frozen_by_status:
                ignored += 1
                continue
            if repo.has_reject_history_for_listing_signature(
                source=str(listing["source"]),
                seller_id=listing["seller_id"],
                title=str(listing["title"]),
                exclude_listing_row_id=listing_row_id,
            ):
                existing_opp = repo.get_opportunity_by_listing_row_id(listing_row_id)
                if existing_opp and str(existing_opp["status"] or "") not in frozen_by_status:
                    repo.update_opportunity_status(
                        int(existing_opp["id"]),
                        "rejected",
                        "matched_reject_history_by_signature",
                    )
                ignored += 1
                continue
            if repo.has_frozen_opportunity_for_listing_fingerprint(
                source=str(listing["source"]),
                seller_id=listing["seller_id"],
                title=str(listing["title"]),
                list_price=float(listing["list_price"]),
                exclude_listing_row_id=listing_row_id,
            ):
                existing_opp = repo.get_opportunity_by_listing_row_id(listing_row_id)
                if existing_opp and str(existing_opp["status"] or "") not in frozen_by_status:
                    repo.update_opportunity_status(
                        int(existing_opp["id"]),
                        "rejected",
                        "duplicate_fingerprint_of_frozen_opportunity",
                    )
                ignored += 1
                continue
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
                feature, source = await _extractor.extract(listing["title"], listing["description"])
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
        except Exception:
            failed += 1
            ignored += 1

    return {
        "processed": len(open_listings),
        "pending_review": created,
        "blocked_risk": blocked,
        "ignored": ignored,
        "failed": failed,
    }
