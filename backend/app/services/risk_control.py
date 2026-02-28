from __future__ import annotations

from dataclasses import dataclass

from ..config import settings
from ..schemas import ValuationOut


@dataclass(frozen=True)
class RiskAssessment:
    score: float
    level: str
    hard_block: bool
    reasons: tuple[str, ...]


def assess_opportunity_risk(
    *,
    list_price: float,
    valuation: ValuationOut,
    seller_open_listing_count: int = 0,
    listing_text: str = "",
) -> RiskAssessment:
    score = 0.0
    hard_block = False
    reasons: list[str] = []

    if valuation.buy_limit <= 0:
        hard_block = True
        score += 100
        reasons.append("buy_limit_non_positive")
    elif list_price > valuation.buy_limit:
        hard_block = True
        score += 100
        reasons.append("list_price_above_buy_limit")

    if valuation.comparables_count < settings.risk_min_comparables:
        deficit = settings.risk_min_comparables - valuation.comparables_count
        penalty = min(25.0, 8.0 + deficit * 3.0)
        score += penalty
        reasons.append("too_few_comparables")

    if valuation.model_confidence < settings.risk_min_model_confidence:
        delta = settings.risk_min_model_confidence - valuation.model_confidence
        penalty = min(25.0, max(5.0, delta * 100.0))
        score += penalty
        reasons.append("low_model_confidence")

    expected = max(valuation.expected_sale_price, 0.01)
    spread_ratio = (valuation.ci_high - valuation.ci_low) / expected
    if spread_ratio > settings.risk_max_ci_spread_ratio:
        penalty = min(20.0, (spread_ratio - settings.risk_max_ci_spread_ratio) * 70.0)
        score += penalty
        reasons.append("wide_price_interval")

    if valuation.buy_limit > 0:
        margin_ratio = (valuation.buy_limit - list_price) / valuation.buy_limit
    else:
        margin_ratio = -1.0
    if margin_ratio < settings.risk_min_margin_ratio:
        penalty = min(20.0, (settings.risk_min_margin_ratio - margin_ratio) * 60.0)
        score += penalty
        reasons.append("insufficient_margin_safety")

    if seller_open_listing_count >= settings.risk_seller_open_listing_limit:
        overflow = seller_open_listing_count - settings.risk_seller_open_listing_limit + 1
        penalty = min(18.0, 6.0 + overflow * 1.5)
        score += penalty
        reasons.append("seller_listing_concentration")

    lower_text = listing_text.lower()
    suspicious_keywords = [
        token.strip().lower()
        for token in settings.risk_suspicious_keywords.split(",")
        if token.strip()
    ]
    if suspicious_keywords and any(token in lower_text for token in suspicious_keywords):
        score += settings.risk_keyword_penalty
        reasons.append("suspicious_listing_keywords")

    score = round(max(0.0, min(100.0, score)), 2)
    level = _risk_level(score)
    return RiskAssessment(
        score=score,
        level=level,
        hard_block=hard_block,
        reasons=tuple(reasons),
    )


def apply_risk_gate(base_status: str, risk: RiskAssessment) -> str:
    if risk.hard_block or risk.score >= settings.risk_block_score:
        return "blocked_risk"
    if base_status != "pending_review":
        return base_status
    return "pending_review"


def format_risk_note(risk: RiskAssessment) -> str:
    if not risk.reasons:
        return f"risk_score={risk.score}; risk_level={risk.level}; reasons=none"
    joined = ",".join(risk.reasons)
    return f"risk_score={risk.score}; risk_level={risk.level}; reasons={joined}"


def _risk_level(score: float) -> str:
    if score >= settings.risk_block_score:
        return "high"
    if score >= settings.risk_review_score:
        return "medium"
    return "low"
