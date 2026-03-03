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
