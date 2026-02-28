from __future__ import annotations

from datetime import datetime, timezone
from statistics import median, pstdev
from typing import Literal

from ..config import settings

PricingMode = Literal["balanced", "fast_exit", "profit_max"]


def build_pricing_plan(
    *,
    approved_buy_price: float,
    current_target_price: float,
    expected_sale_price: float,
    suggested_list_price: float,
    ci_low: float,
    ci_high: float,
    trade_created_at: str,
    similar_sold_prices: list[float],
    active_trade_count: int,
    mode: PricingMode = "balanced",
) -> dict:
    created_at = _parse_iso_datetime(trade_created_at)
    holding_days = _compute_holding_days(created_at)

    anchor = _compute_anchor_price(
        expected_sale_price=expected_sale_price,
        suggested_list_price=suggested_list_price,
        similar_sold_prices=similar_sold_prices,
    )
    volatility_ratio = _compute_volatility_ratio(
        similar_sold_prices=similar_sold_prices,
        expected_sale_price=expected_sale_price,
        ci_low=ci_low,
        ci_high=ci_high,
    )

    mode_factor = _mode_factor(mode)
    age_discount = min(
        settings.pricing_max_age_discount,
        holding_days * settings.pricing_age_discount_per_day,
    )
    if mode == "profit_max":
        age_discount *= 0.6
    elif mode == "fast_exit":
        age_discount *= 1.25

    inventory_pressure = 0.0
    if active_trade_count > settings.pricing_inventory_soft_cap:
        inventory_pressure = min(
            0.12,
            (active_trade_count - settings.pricing_inventory_soft_cap) * 0.01,
        )
        if mode == "profit_max":
            inventory_pressure *= 0.7
        elif mode == "fast_exit":
            inventory_pressure *= 1.2

    volatility_discount = min(
        settings.pricing_max_volatility_discount,
        volatility_ratio * settings.pricing_volatility_discount_factor,
    )

    raw_price = anchor * mode_factor
    raw_price *= max(0.60, 1.0 - age_discount - inventory_pressure - volatility_discount)

    min_profitable = _min_profitable_sell_price(approved_buy_price)
    lower_guard = max(min_profitable, ci_low * 0.95 if ci_low > 0 else min_profitable)
    upper_guard = max(lower_guard, ci_high * 1.03 if ci_high > 0 else expected_sale_price * 1.15)

    if mode == "profit_max":
        upper_guard *= 1.03
    elif mode == "fast_exit":
        upper_guard *= 0.98

    recommended = _clamp(raw_price, lower_guard, upper_guard)
    action = _recommend_action(current_target_price, recommended)
    urgency = _urgency_level(holding_days, inventory_pressure)

    reasons = [
        f"mode={mode}",
        f"holding_days={holding_days}",
        f"volatility_ratio={volatility_ratio:.4f}",
        f"inventory_pressure={inventory_pressure:.4f}",
        f"min_profitable={min_profitable:.2f}",
        f"anchor={anchor:.2f}",
    ]

    return {
        "mode": mode,
        "recommended_price": round(recommended, 2),
        "current_target_price": round(current_target_price, 2),
        "expected_sale_price": round(expected_sale_price, 2),
        "price_floor": round(lower_guard, 2),
        "price_ceiling": round(upper_guard, 2),
        "holding_days": holding_days,
        "urgency": urgency,
        "action": action,
        "volatility_ratio": round(volatility_ratio, 4),
        "similar_sales_count": len(similar_sold_prices),
        "reasons": reasons,
    }


def _compute_anchor_price(
    *,
    expected_sale_price: float,
    suggested_list_price: float,
    similar_sold_prices: list[float],
) -> float:
    anchor = (expected_sale_price * 0.45) + (suggested_list_price * 0.55)
    if similar_sold_prices:
        local_mid = median(similar_sold_prices)
        anchor = (anchor * 0.7) + (local_mid * 0.3)
    return max(0.01, anchor)


def _compute_volatility_ratio(
    *,
    similar_sold_prices: list[float],
    expected_sale_price: float,
    ci_low: float,
    ci_high: float,
) -> float:
    clean = [p for p in similar_sold_prices if p > 0]
    if len(clean) >= 3:
        avg = sum(clean) / len(clean)
        if avg > 0:
            return max(0.0, min(1.0, pstdev(clean) / avg))
    if expected_sale_price > 0:
        return max(0.0, min(1.0, (ci_high - ci_low) / expected_sale_price))
    return 0.0


def _min_profitable_sell_price(approved_buy_price: float) -> float:
    fee_rate = max(0.0, min(0.95, settings.platform_fee_rate))
    denominator = max(0.05, 1.0 - fee_rate)
    return (
        approved_buy_price + settings.default_shipping_cost + settings.min_profit
    ) / denominator


def _mode_factor(mode: PricingMode) -> float:
    if mode == "fast_exit":
        return settings.pricing_mode_fast_exit_factor
    if mode == "profit_max":
        return settings.pricing_mode_profit_max_factor
    return settings.pricing_mode_balanced_factor


def _urgency_level(holding_days: int, inventory_pressure: float) -> str:
    if holding_days >= settings.pricing_urgent_days or inventory_pressure >= 0.08:
        return "high"
    if holding_days >= settings.pricing_stale_days or inventory_pressure >= 0.03:
        return "medium"
    return "low"


def _recommend_action(current_target_price: float, recommended: float) -> str:
    if current_target_price <= 0:
        return "set"
    diff_ratio = (recommended - current_target_price) / current_target_price
    if diff_ratio >= 0.03:
        return "raise"
    if diff_ratio <= -0.03:
        return "lower"
    return "keep"


def _compute_holding_days(created_at: datetime) -> int:
    now = datetime.now(timezone.utc)
    delta_sec = (now - created_at).total_seconds()
    return max(0, int(delta_sec // 86400))


def _parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _clamp(value: float, floor: float, ceiling: float) -> float:
    return max(floor, min(ceiling, value))

