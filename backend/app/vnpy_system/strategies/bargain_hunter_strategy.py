from __future__ import annotations

import logging

from ... import repositories as repo
from ...config import StrategyThresholds, settings
from ..event_engine import Event, EventType
from ..strategy_engine import Strategy

logger = logging.getLogger(__name__)


class BargainHunterStrategy(Strategy):
    """Simple bargain hunter strategy (simulation only)."""

    def __init__(self, main_engine, thresholds: StrategyThresholds | None = None) -> None:
        super().__init__("BargainHunter", main_engine)
        self.profile = settings.strategy_profile
        self.thresholds = thresholds or settings.strategy_thresholds
        self._apply_thresholds(self.thresholds)

    def on_start(self) -> None:
        logger.info(
            "[%s] started (min_roi=%.2f, max_risk_score=%.1f, min_score=%.1f, profile=%s)",
            self.name,
            self.min_roi,
            self.max_risk_score,
            self.min_score,
            self.profile,
        )

    def on_stop(self) -> None:
        logger.info("[%s] stopped", self.name)

    def on_item_analyzed(self, event: Event) -> None:
        if not self.active:
            return
        if event.event_type != EventType.ITEM_ANALYZED:
            return
        analysis = event.data.get("analysis") or {}
        status = analysis.get("status")
        score = float(analysis.get("score", 0))
        risk_score = float(analysis.get("risk", {}).get("score", 100))
        roi = float(analysis.get("profit", {}).get("roi", 0))

        hard_block = bool(analysis.get("risk", {}).get("hard_block"))
        if hard_block:
            should_review = False
        elif status == "blocked_risk":
            should_review = self.allow_blocked_review and score >= self.min_score and roi >= self.min_roi
        else:
            should_review = (
                score >= self.min_score
                and risk_score <= self.max_risk_score
                and roi >= self.min_roi
            )

        listing = analysis.get("listing", {})
        valuation = analysis.get("valuation", {})
        listing_row_id = int(listing.get("listing_row_id", 0))
        list_price = float(listing.get("list_price", 0))
        buy_limit = float(valuation.get("buy_limit", 0))
        sell_price = float(valuation.get("suggested_list_price", 0))

        if listing_row_id <= 0 or list_price <= 0 or sell_price <= 0:
            return

        self._sync_opportunity(
            listing_row_id=listing_row_id,
            should_review=should_review,
            score=score,
            roi=roi,
            risk_score=risk_score,
            hard_block=hard_block,
        )

        if not should_review or status != "pending_review":
            return

        buy_price = min(list_price, buy_limit) if buy_limit > 0 else list_price

        logger.info(
            "[%s] signal: row_id=%s score=%.1f roi=%.3f risk=%.1f buy=%.2f sell=%.2f",
            self.name,
            listing_row_id,
            score,
            roi,
            risk_score,
            buy_price,
            sell_price,
        )
        self.send_order(listing_row_id, buy_price, sell_price)

    def on_order_traded(self, event: Event) -> None:
        order = event.data.get("order") or {}
        if order.get("strategy_name") != self.name:
            return
        logger.info(
            "[%s] order filled: %s (buy=%.2f sell=%.2f)",
            self.name,
            order.get("order_id"),
            float(order.get("buy_price", 0)),
            float(order.get("sell_price", 0)),
        )

    def _sync_opportunity(
        self,
        *,
        listing_row_id: int,
        should_review: bool,
        score: float,
        roi: float,
        risk_score: float,
        hard_block: bool,
    ) -> None:
        opp = repo.get_opportunity_by_listing_row_id(listing_row_id)
        if not opp:
            return
        current_status = str(opp["status"])
        note = (
            f"strategy={self.name}; decision={'review' if should_review else 'ignore'};"
            f" status={current_status}; hard_block={hard_block};"
            f" score={score:.1f}; roi={roi:.3f}; risk_score={risk_score:.1f}"
        )
        if should_review:
            if current_status != "pending_review":
                repo.update_opportunity_status(int(opp["id"]), "pending_review", note)
        elif self.auto_reject_unqualified:
            if current_status == "pending_review":
                repo.update_opportunity_status(int(opp["id"]), "rejected", note)

    def apply_thresholds(self, thresholds: StrategyThresholds, profile: str | None = None) -> None:
        if profile:
            self.profile = profile
        self.thresholds = thresholds
        self._apply_thresholds(thresholds)

    def _apply_thresholds(self, thresholds: StrategyThresholds) -> None:
        self.min_score = float(thresholds.min_score)
        self.min_roi = float(thresholds.min_roi)
        self.max_risk_score = float(thresholds.max_risk_score)
        self.allow_blocked_review = bool(thresholds.allow_blocked_review)
        self.auto_reject_unqualified = bool(thresholds.auto_reject_unqualified)
