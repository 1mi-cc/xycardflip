from __future__ import annotations

import asyncio
import logging
from typing import Any

from .. import repositories as repo
from ..schemas import FeatureData
from ..services.feature_extractor import FeatureExtractor
from ..services.opportunity import score_opportunity
from ..services.risk_control import apply_risk_gate, assess_opportunity_risk, format_risk_note
from ..services.valuation import estimate_valuation
from .event_engine import Event, EventType, event_engine
from .main_engine import MainEngine

logger = logging.getLogger(__name__)


class AnalysisEngine:
    """Analyze listings and emit strategy-ready events."""

    def __init__(self, main_engine: MainEngine) -> None:
        self.main_engine = main_engine
        self.extractor = FeatureExtractor()
        event_engine.register(EventType.ITEM_FOUND, self.on_item_found)

    def on_item_found(self, event: Event) -> None:
        listing_row_id = event.data.get("listing_row_id")
        if not listing_row_id:
            return
        listing = repo.get_listing(int(listing_row_id))
        if not listing:
            return
        try:
            analysis = self._analyze_listing(listing)
            self.main_engine.emit_event(
                EventType.ITEM_ANALYZED,
                {"listing_row_id": int(listing_row_id), "analysis": analysis},
            )
            if analysis.get("recommendation", {}).get("should_buy"):
                self.main_engine.emit_event(
                    EventType.ITEM_UNDERPRICED,
                    {"listing_row_id": int(listing_row_id), "analysis": analysis},
                )
        except Exception as exc:
            logger.error("analysis error: %s", exc, exc_info=True)

    def _analyze_listing(self, listing: Any) -> dict[str, Any]:
        listing_row_id = int(listing["id"])
        list_price = float(listing["list_price"])

        feature = self._ensure_features(listing_row_id, listing)
        sales = repo.get_recent_sales(feature, limit=80)
        valuation = estimate_valuation(
            listing_row_id=listing_row_id,
            listing_price=list_price,
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
            list_price=list_price,
            valuation=valuation,
            seller_open_listing_count=seller_open_count,
            listing_text=f"{listing['title']} {listing['description']}",
        )
        expected_profit, roi, score, status = score_opportunity(
            list_price=list_price,
            expected_sale_price=valuation.expected_sale_price,
            risk_score=risk.score,
        )
        status = apply_risk_gate(status, risk)
        repo.upsert_opportunity(
            listing_row_id=listing_row_id,
            valuation_id=valuation_id,
            expected_profit=expected_profit,
            roi=roi,
            score=score,
            status=status,
            note=format_risk_note(risk),
        )

        return {
            "listing": {
                "listing_row_id": listing_row_id,
                "listing_id": listing["listing_id"],
                "title": listing["title"],
                "list_price": list_price,
                "source": listing["source"],
                "seller_id": listing["seller_id"],
            },
            "feature": feature.model_dump(),
            "valuation": {
                "expected_sale_price": valuation.expected_sale_price,
                "buy_limit": valuation.buy_limit,
                "suggested_list_price": valuation.suggested_list_price,
                "ci_low": valuation.ci_low,
                "ci_high": valuation.ci_high,
                "model_confidence": valuation.model_confidence,
                "comparables_count": valuation.comparables_count,
                "reasoning": valuation.reasoning,
            },
            "risk": {
                "score": risk.score,
                "level": risk.level,
                "hard_block": risk.hard_block,
                "reasons": list(risk.reasons),
            },
            "profit": {"expected_profit": expected_profit, "roi": roi},
            "score": score,
            "status": status,
            "recommendation": {"should_buy": status == "pending_review" and not risk.hard_block},
        }

    def _ensure_features(self, listing_row_id: int, listing: Any) -> FeatureData:
        feature_row = repo.get_features("listing", listing_row_id)
        if feature_row:
            return FeatureData(
                card_name=feature_row["card_name"],
                rarity=feature_row["rarity"],
                edition=feature_row["edition"],
                card_condition=feature_row["card_condition"],
                confidence=float(feature_row["confidence"]),
                extras={},
            )

        feature, source = self._run_async(
            self.extractor.extract(str(listing["title"]), str(listing["description"]))
        )
        repo.save_features("listing", listing_row_id, feature, source)
        return feature

    def _run_async(self, coro):
        try:
            return asyncio.run(coro)
        except RuntimeError:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                future = asyncio.run_coroutine_threadsafe(coro, loop)
                return future.result()
            return loop.run_until_complete(coro)
