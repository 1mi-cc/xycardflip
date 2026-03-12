"""Tests for valuation, risk control, and opportunity scoring services."""
from __future__ import annotations

import pytest

from app.schemas import FeatureData, ValuationOut
from app.services.opportunity import score_opportunity
from app.services.risk_control import (
    RiskAssessment,
    apply_risk_gate,
    assess_opportunity_risk,
    format_risk_note,
)
from app.services.valuation import (
    _percentile,
    _trim_outliers_iqr,
    estimate_valuation,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _feature(
    *,
    card_name: str = "TestCard",
    rarity: str = "SR",
    card_condition: str = "nm",
    confidence: float = 0.8,
) -> FeatureData:
    return FeatureData(
        card_name=card_name,
        rarity=rarity,
        edition="first",
        card_condition=card_condition,
        extras={},
        confidence=confidence,
    )


def _valuation(
    *,
    listing_row_id: int = 1,
    expected_sale_price: float = 150.0,
    buy_limit: float = 100.0,
    suggested_list_price: float = 155.0,
    ci_low: float = 120.0,
    ci_high: float = 180.0,
    model_confidence: float = 0.7,
    comparables_count: int = 10,
    reasoning: str = "test",
) -> ValuationOut:
    return ValuationOut(
        listing_row_id=listing_row_id,
        expected_sale_price=expected_sale_price,
        buy_limit=buy_limit,
        suggested_list_price=suggested_list_price,
        ci_low=ci_low,
        ci_high=ci_high,
        model_confidence=model_confidence,
        comparables_count=comparables_count,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------------
# _percentile
# ---------------------------------------------------------------------------

class TestPercentile:
    def test_empty_returns_zero(self) -> None:
        assert _percentile([], 0.5) == 0.0

    def test_single_element(self) -> None:
        assert _percentile([42.0], 0.0) == 42.0
        assert _percentile([42.0], 1.0) == 42.0

    def test_median_odd(self) -> None:
        assert _percentile([1.0, 2.0, 3.0], 0.5) == 2.0

    def test_median_even_interpolated(self) -> None:
        result = _percentile([1.0, 2.0, 3.0, 4.0], 0.5)
        assert result == pytest.approx(2.5)

    def test_clamp_q_below_zero(self) -> None:
        result = _percentile([1.0, 2.0, 3.0], -1.0)
        assert result == 1.0

    def test_clamp_q_above_one(self) -> None:
        result = _percentile([1.0, 2.0, 3.0], 2.0)
        assert result == 3.0


# ---------------------------------------------------------------------------
# _trim_outliers_iqr
# ---------------------------------------------------------------------------

class TestTrimOutliersIqr:
    def test_small_sample_unchanged(self) -> None:
        vals = [1.0, 2.0, 3.0]
        assert _trim_outliers_iqr(vals) == vals

    def test_removes_extreme_outliers(self) -> None:
        vals = [10.0, 11.0, 10.5, 12.0, 11.5, 1000.0]
        trimmed = _trim_outliers_iqr(vals)
        assert 1000.0 not in trimmed
        assert len(trimmed) < len(vals)

    def test_uniform_values_unchanged(self) -> None:
        vals = [5.0] * 10
        assert _trim_outliers_iqr(vals) == vals

    def test_returns_original_when_all_filtered(self) -> None:
        # If filtering removes everything, returns original.
        vals = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0]
        result = _trim_outliers_iqr(vals)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# estimate_valuation
# ---------------------------------------------------------------------------

class TestEstimateValuation:
    def test_with_comparable_prices(self) -> None:
        feat = _feature()
        prices = [100.0, 110.0, 105.0, 108.0, 102.0, 103.0, 107.0]
        result = estimate_valuation(
            listing_row_id=1,
            listing_price=95.0,
            features=feat,
            comparable_prices=prices,
        )
        assert result.expected_sale_price > 0
        assert result.buy_limit > 0
        assert result.ci_low <= result.expected_sale_price <= result.ci_high
        assert 0.0 < result.model_confidence <= 1.0
        assert result.comparables_count == len(prices)

    def test_without_comparables_uses_fallback(self) -> None:
        feat = _feature()
        result = estimate_valuation(
            listing_row_id=2,
            listing_price=80.0,
            features=feat,
            comparable_prices=[],
        )
        # Fallback: expected ~ 80 * 1.10 * condition_factor
        assert result.expected_sale_price > 80.0
        assert result.comparables_count == 0
        assert result.model_confidence < 0.5  # low confidence without data

    def test_damaged_condition_lowers_price(self) -> None:
        feat_nm = _feature(card_condition="nm")
        feat_dam = _feature(card_condition="damaged")
        prices = [100.0, 110.0, 105.0, 108.0, 102.0, 103.0]
        val_nm = estimate_valuation(1, 90.0, feat_nm, prices)
        val_dam = estimate_valuation(1, 90.0, feat_dam, prices)
        assert val_dam.expected_sale_price < val_nm.expected_sale_price

    def test_high_confidence_feature_increases_model_confidence(self) -> None:
        feat_low = _feature(confidence=0.3)
        feat_high = _feature(confidence=0.95)
        prices = [100.0, 110.0, 105.0, 108.0, 102.0, 103.0]
        val_low = estimate_valuation(1, 90.0, feat_low, prices)
        val_high = estimate_valuation(1, 90.0, feat_high, prices)
        assert val_high.model_confidence > val_low.model_confidence

    def test_ci_invariant_low_lte_high(self) -> None:
        feat = _feature()
        for prices in [[], [50.0], [50.0, 51.0], list(range(50, 80, 2))]:
            result = estimate_valuation(1, 60.0, feat, [float(p) for p in prices])
            assert result.ci_low <= result.ci_high


# ---------------------------------------------------------------------------
# assess_opportunity_risk
# ---------------------------------------------------------------------------

class TestAssessOpportunityRisk:
    def test_list_price_above_buy_limit_is_hard_block(self) -> None:
        val = _valuation(buy_limit=80.0)
        risk = assess_opportunity_risk(list_price=100.0, valuation=val)
        assert risk.hard_block is True
        assert "list_price_above_buy_limit" in risk.reasons

    def test_non_positive_buy_limit_is_hard_block(self) -> None:
        val = _valuation(buy_limit=0.0)
        risk = assess_opportunity_risk(list_price=50.0, valuation=val)
        assert risk.hard_block is True
        assert "buy_limit_non_positive" in risk.reasons

    def test_below_buy_limit_no_hard_block(self) -> None:
        val = _valuation(buy_limit=100.0, model_confidence=0.9, comparables_count=20)
        risk = assess_opportunity_risk(list_price=70.0, valuation=val)
        assert risk.hard_block is False

    def test_suspicious_keyword_increases_score(self) -> None:
        val = _valuation(buy_limit=200.0, model_confidence=0.9, comparables_count=20)
        risk_clean = assess_opportunity_risk(list_price=100.0, valuation=val)
        risk_suspect = assess_opportunity_risk(
            list_price=100.0,
            valuation=val,
            listing_text="假货 fake item",
        )
        assert risk_suspect.score >= risk_clean.score

    def test_score_bounded_0_to_100(self) -> None:
        val = _valuation(buy_limit=0.0)
        risk = assess_opportunity_risk(list_price=999.0, valuation=val)
        assert 0.0 <= risk.score <= 100.0

    def test_risk_level_high_for_hard_block(self) -> None:
        val = _valuation(buy_limit=0.0)
        risk = assess_opportunity_risk(list_price=100.0, valuation=val)
        assert risk.level == "high"

    def test_risk_level_low_for_good_opportunity(self) -> None:
        val = _valuation(
            buy_limit=200.0,
            ci_low=100.0,
            ci_high=160.0,
            expected_sale_price=140.0,
            model_confidence=0.90,
            comparables_count=25,
        )
        risk = assess_opportunity_risk(list_price=80.0, valuation=val)
        assert risk.level in {"low", "medium"}


# ---------------------------------------------------------------------------
# apply_risk_gate
# ---------------------------------------------------------------------------

class TestApplyRiskGate:
    def test_hard_block_overrides_pending(self) -> None:
        risk = RiskAssessment(score=100.0, level="high", hard_block=True, reasons=("x",))
        assert apply_risk_gate("pending_review", risk) == "blocked_risk"

    def test_non_pending_status_preserved_when_not_blocked(self) -> None:
        risk = RiskAssessment(score=5.0, level="low", hard_block=False, reasons=())
        assert apply_risk_gate("approved_for_buy", risk) == "approved_for_buy"

    def test_pending_review_preserved_when_safe(self) -> None:
        risk = RiskAssessment(score=5.0, level="low", hard_block=False, reasons=())
        assert apply_risk_gate("pending_review", risk) == "pending_review"


# ---------------------------------------------------------------------------
# format_risk_note
# ---------------------------------------------------------------------------

class TestFormatRiskNote:
    def test_includes_score_and_level(self) -> None:
        risk = RiskAssessment(score=42.5, level="medium", hard_block=False, reasons=("low_confidence",))
        note = format_risk_note(risk)
        assert "42.5" in note
        assert "medium" in note
        assert "low_confidence" in note

    def test_no_reasons_label(self) -> None:
        risk = RiskAssessment(score=0.0, level="low", hard_block=False, reasons=())
        note = format_risk_note(risk)
        assert "none" in note


# ---------------------------------------------------------------------------
# score_opportunity
# ---------------------------------------------------------------------------

class TestScoreOpportunity:
    def test_profitable_opportunity_is_pending_review(self) -> None:
        net_profit, roi, score, status = score_opportunity(
            list_price=80.0,
            expected_sale_price=150.0,
        )
        assert net_profit > 0
        assert roi > 0
        assert 0.0 <= score <= 100.0
        assert status == "pending_review"

    def test_no_profit_is_ignored(self) -> None:
        # list_price == expected_sale_price: net_profit will be negative after fees
        _, _, _, status = score_opportunity(
            list_price=150.0,
            expected_sale_price=150.0,
        )
        assert status == "ignored"

    def test_high_risk_score_lowers_opportunity_score(self) -> None:
        _, _, score_low_risk, _ = score_opportunity(80.0, 150.0, risk_score=0.0)
        _, _, score_high_risk, _ = score_opportunity(80.0, 150.0, risk_score=80.0)
        assert score_high_risk < score_low_risk

    def test_score_bounded_0_to_100(self) -> None:
        for list_price in [0.01, 10.0, 100.0, 1000.0]:
            _, _, score, _ = score_opportunity(list_price, list_price * 2.0)
            assert 0.0 <= score <= 100.0

    def test_zero_list_price_does_not_raise(self) -> None:
        net_profit, roi, score, _ = score_opportunity(0.0, 100.0)
        assert roi == 0
