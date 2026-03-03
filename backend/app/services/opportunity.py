from __future__ import annotations

from ..config import settings


def score_opportunity(
    list_price: float,
    expected_sale_price: float,
    risk_score: float = 0.0,
) -> tuple[float, float, float, str]:
    fee = settings.platform_fee_rate * expected_sale_price
    risk_cut = settings.risk_discount * expected_sale_price
    net_profit = expected_sale_price - list_price - settings.default_shipping_cost - fee - risk_cut
    roi = net_profit / list_price if list_price > 0 else 0

    risk_penalty = min(40.0, max(0.0, risk_score) * 0.35)
    quality = (roi * 100) + (net_profit / 10) - risk_penalty
    score = round(max(0.0, min(100.0, quality)), 2)

    status = "pending_review"
    if net_profit < settings.min_profit or roi < settings.min_roi:
        status = "ignored"

    return round(net_profit, 2), round(roi, 4), score, status
