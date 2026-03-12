from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.services.pricing_strategy import build_pricing_plan


def _iso_days_ago(days: int) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()


def test_pricing_modes_have_expected_ordering() -> None:
    base_kwargs = {
        "approved_buy_price": 100.0,
        "current_target_price": 145.0,
        "expected_sale_price": 160.0,
        "suggested_list_price": 155.0,
        "ci_low": 130.0,
        "ci_high": 180.0,
        "trade_created_at": _iso_days_ago(2),
        "similar_sold_prices": [145.0, 152.0, 158.0, 161.0],
        "active_trade_count": 8,
    }
    fast = build_pricing_plan(mode="fast_exit", **base_kwargs)
    balanced = build_pricing_plan(mode="balanced", **base_kwargs)
    profit = build_pricing_plan(mode="profit_max", **base_kwargs)

    assert fast["recommended_price"] <= balanced["recommended_price"] <= profit["recommended_price"]
    assert fast["price_floor"] <= fast["recommended_price"] <= fast["price_ceiling"]
    assert balanced["price_floor"] <= balanced["recommended_price"] <= balanced["price_ceiling"]
    assert profit["price_floor"] <= profit["recommended_price"] <= profit["price_ceiling"]


def test_pricing_urgency_turns_high_for_old_trade() -> None:
    result = build_pricing_plan(
        approved_buy_price=85.0,
        current_target_price=120.0,
        expected_sale_price=130.0,
        suggested_list_price=128.0,
        ci_low=110.0,
        ci_high=145.0,
        trade_created_at=_iso_days_ago(15),
        similar_sold_prices=[118.0, 121.0, 126.0],
        active_trade_count=3,
        mode="balanced",
    )
    assert result["urgency"] == "high"


def test_bullish_sentiment_raises_balanced_price() -> None:
    base_kwargs = dict(
        approved_buy_price=100.0,
        current_target_price=145.0,
        expected_sale_price=160.0,
        suggested_list_price=155.0,
        ci_low=130.0,
        ci_high=180.0,
        trade_created_at=_iso_days_ago(2),
        similar_sold_prices=[145.0, 152.0, 158.0, 161.0],
        active_trade_count=8,
        mode="balanced",
    )
    neutral = build_pricing_plan(**base_kwargs)
    bullish = build_pricing_plan(**base_kwargs, sentiment_adjustment=0.05, sentiment_label="bullish")

    assert bullish["recommended_price"] >= neutral["recommended_price"]
    assert bullish["sentiment_label"] == "bullish"
    assert bullish["sentiment_adjustment"] == 0.05


def test_bearish_sentiment_lowers_balanced_price() -> None:
    base_kwargs = dict(
        approved_buy_price=100.0,
        current_target_price=145.0,
        expected_sale_price=160.0,
        suggested_list_price=155.0,
        ci_low=130.0,
        ci_high=180.0,
        trade_created_at=_iso_days_ago(2),
        similar_sold_prices=[145.0, 152.0, 158.0, 161.0],
        active_trade_count=8,
        mode="balanced",
    )
    neutral = build_pricing_plan(**base_kwargs)
    bearish = build_pricing_plan(**base_kwargs, sentiment_adjustment=-0.05, sentiment_label="bearish")

    assert bearish["recommended_price"] <= neutral["recommended_price"]
    assert bearish["sentiment_label"] == "bearish"
    assert bearish["sentiment_adjustment"] == -0.05


def test_fast_exit_ignores_bullish_sentiment() -> None:
    """In fast_exit mode bullish sentiment must not raise the recommended price
    above the neutral baseline (the mode already wants a quick sale)."""
    base_kwargs = dict(
        approved_buy_price=100.0,
        current_target_price=130.0,
        expected_sale_price=150.0,
        suggested_list_price=148.0,
        ci_low=120.0,
        ci_high=165.0,
        trade_created_at=_iso_days_ago(1),
        similar_sold_prices=[135.0, 140.0, 145.0],
        active_trade_count=5,
        mode="fast_exit",
    )
    neutral = build_pricing_plan(**base_kwargs)
    bullish = build_pricing_plan(**base_kwargs, sentiment_adjustment=0.10, sentiment_label="bullish")

    # Bullish upward adjustment is blocked for fast_exit.
    assert bullish["recommended_price"] == neutral["recommended_price"]


def test_profit_max_limits_bearish_impact() -> None:
    """In profit_max mode strong bearish sentiment is capped at −5 %."""
    base_kwargs = dict(
        approved_buy_price=100.0,
        current_target_price=160.0,
        expected_sale_price=175.0,
        suggested_list_price=170.0,
        ci_low=150.0,
        ci_high=195.0,
        trade_created_at=_iso_days_ago(3),
        similar_sold_prices=[160.0, 165.0, 170.0],
        active_trade_count=4,
        mode="profit_max",
    )
    neutral = build_pricing_plan(**base_kwargs)
    # Request a −15 % bearish adjustment; should be capped at −5 %.
    bearish_strong = build_pricing_plan(
        **base_kwargs, sentiment_adjustment=-0.15, sentiment_label="bearish"
    )

    assert bearish_strong["recommended_price"] >= neutral["recommended_price"] * 0.94
    assert bearish_strong["sentiment_adjustment"] == -0.05


def test_sentiment_clamped_to_safe_range() -> None:
    """Sentiment values outside [−0.20, +0.20] must be clamped."""
    base_kwargs = dict(
        approved_buy_price=100.0,
        current_target_price=145.0,
        expected_sale_price=160.0,
        suggested_list_price=155.0,
        ci_low=130.0,
        ci_high=180.0,
        trade_created_at=_iso_days_ago(2),
        similar_sold_prices=[145.0, 152.0, 158.0],
        active_trade_count=5,
        mode="balanced",
    )
    extreme_up = build_pricing_plan(**base_kwargs, sentiment_adjustment=0.99)
    extreme_down = build_pricing_plan(**base_kwargs, sentiment_adjustment=-0.99)

    assert extreme_up["sentiment_adjustment"] == 0.20
    assert extreme_down["sentiment_adjustment"] == -0.20


def test_sentiment_label_appears_in_reasons() -> None:
    result = build_pricing_plan(
        approved_buy_price=100.0,
        current_target_price=145.0,
        expected_sale_price=160.0,
        suggested_list_price=155.0,
        ci_low=130.0,
        ci_high=180.0,
        trade_created_at=_iso_days_ago(2),
        similar_sold_prices=[145.0, 152.0],
        active_trade_count=5,
        mode="balanced",
        sentiment_adjustment=0.03,
        sentiment_label="bullish",
    )
    reasons_joined = " ".join(result["reasons"])
    assert "bullish" in reasons_joined
    assert "sentiment" in reasons_joined

