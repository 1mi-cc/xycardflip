from __future__ import annotations

from statistics import median

from ..config import settings
from ..schemas import FeatureData, ValuationOut


def _condition_multiplier(card_condition: str) -> float:
    norm = card_condition.lower()
    if "mint" in norm or norm == "nm":
        return 1.05
    if "near mint" in norm:
        return 1.03
    if "lp" in norm:
        return 0.96
    if "played" in norm:
        return 0.9
    if "damaged" in norm:
        return 0.75
    return 1.0


def estimate_valuation(
    listing_row_id: int,
    listing_price: float,
    features: FeatureData,
    comparable_prices: list[float],
) -> ValuationOut:
    prices = sorted(price for price in comparable_prices if price > 0)
    if prices:
        filtered = _trim_outliers_iqr(prices)
        filtered_sorted = sorted(filtered)
        count = len(filtered_sorted)

        p25 = _percentile(filtered_sorted, 0.25)
        p50 = _percentile(filtered_sorted, 0.50)
        p75 = _percentile(filtered_sorted, 0.75)

        base = ((p50 * 0.65) + (((p25 + p75) / 2.0) * 0.35))
        spread_ratio = (p75 - p25) / max(p50, 0.01)
        confidence = min(0.95, max(0.25, 0.42 + count * 0.02 - spread_ratio * 0.2))

        low = max(0.01, p25 * 0.98)
        high = max(low, p75 * 1.02)
        reason = (
            f"Robust estimate from {count} comparable sales "
            f"(p25={p25:.2f}, median={p50:.2f}, p75={p75:.2f})."
        )
    else:
        base = listing_price * 1.10
        low = listing_price * 0.88
        high = listing_price * 1.30
        count = 0
        confidence = 0.28
        reason = "Fallback estimate because no comparable sales found."

    condition_factor = _condition_multiplier(features.card_condition)
    expected_sale_price = round(base * condition_factor, 2)
    ci_low = round(low * condition_factor * 0.98, 2)
    ci_high = round(high * condition_factor * 1.02, 2)
    if ci_high < ci_low:
        ci_high = ci_low

    model_confidence = round(confidence * features.confidence, 3)

    costs = settings.default_shipping_cost + settings.platform_fee_rate * expected_sale_price
    interval_guard = max(0.0, (ci_high - ci_low) * 0.20)
    confidence_guard = max(0.0, (1.0 - model_confidence) * expected_sale_price * 0.08)
    buy_limit = round(
        max(
            0.01,
            expected_sale_price - costs - settings.min_profit - interval_guard - confidence_guard,
        ),
        2,
    )
    suggested_list_price = round(max(expected_sale_price, expected_sale_price * 1.03), 2)

    return ValuationOut(
        listing_row_id=listing_row_id,
        expected_sale_price=expected_sale_price,
        buy_limit=buy_limit,
        suggested_list_price=suggested_list_price,
        ci_low=ci_low,
        ci_high=ci_high,
        model_confidence=model_confidence,
        comparables_count=count,
        reasoning=reason,
    )


def _trim_outliers_iqr(values: list[float]) -> list[float]:
    if len(values) < 6:
        return values

    sorted_values = sorted(values)
    q1 = _percentile(sorted_values, 0.25)
    q3 = _percentile(sorted_values, 0.75)
    iqr = q3 - q1
    if iqr <= 0:
        return sorted_values

    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    filtered = [v for v in sorted_values if lower <= v <= upper]
    return filtered or sorted_values


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])

    pos = max(0.0, min(1.0, q)) * (len(values) - 1)
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    if lo == hi:
        return float(values[lo])

    weight = pos - lo
    return (values[lo] * (1 - weight)) + (values[hi] * weight)
