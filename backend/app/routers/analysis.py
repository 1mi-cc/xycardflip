from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from statistics import mean, stdev
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .. import repositories as repo
from ..auth_utils import build_user_profile
from ..auth_utils import require_current_user
from ..config import settings
from ..config import single_account_guardrail_status
from ..database import get_database_health_snapshot
from ..database import get_conn
from ..database import get_data_integrity_status
from ..route_guard import require_cardflip_operate
from ..route_guard import require_cardflip_view
from ..services.automation import automation_service
from ..services.autotrade import auto_trade_service
from ..services.autotrade_alerting import build_alert_payload
from ..services.autotrade_alerting import public_cockpit_payload
from ..services.execution import execution_service
from ..services.execution_retry import execution_retry_service
from ..services.market_monitor import monitor_service
from ..services.marketplace_normalizer import explain_marketplace_match
from ..services.operating_state import operating_state_service
from ..services.arbitrage import build_arbitrage_opportunities
from ..services.arbitrage import build_arbitrage_matching_preview
from ..services.risk_overrides import risk_overrides_service
from ..services.strategy_advisor import build_market_snapshot_documents
from ..services.strategy_advisor import get_strategy_proposal
from ..services.supabase_sync import supabase_sync_service
from ..services.startup_diagnostics import startup_configuration_checks

router = APIRouter(
    prefix="/analysis",
    tags=["analysis"],
    dependencies=[Depends(require_cardflip_view)],
)


class ArbitrageMatchValidateIn(BaseModel):
    left_title: str
    right_title: str
    left_key: str = ""
    right_key: str = ""


class ArbitrageMatchBatchItemIn(BaseModel):
    left_title: str
    right_title: str
    left_key: str = ""
    right_key: str = ""


class ArbitrageMatchSampleIn(ArbitrageMatchBatchItemIn):
    expected_verdict: str = ""
    note: str = ""


class ArbitrageReviewQueueLabelIn(BaseModel):
    expected_verdict: Literal["same_group", "close_match", "different_group"]
    note: str = ""

MAX_ANALYSIS_LIMIT = 500
RECOMMENDATION_AUTOTRADE_CAP = 200
DEFAULT_SUGGESTED_MIN_SCORE = 60.0
HIGH_RISK_AVG_THRESHOLD = 50.0
HIGH_RISK_SUGGESTED_MIN_SCORE = 70.0
NEGATIVE_MOMENTUM_THRESHOLD = -3.0
NEGATIVE_MOMENTUM_SUGGESTED_MIN_SCORE = 75.0


def _require_admin_profile(request: Request) -> dict[str, Any]:
    with get_conn() as conn:
        user_row = require_current_user(conn, request)
        profile = build_user_profile(user_row)
    if not bool(profile.get("isAdmin")):
        raise HTTPException(status_code=403, detail="admin overview requires admin role")
    return profile


def _health_reasons(
    *,
    database_status: dict[str, Any],
    data_integrity: dict[str, Any],
    operating_state: dict[str, Any],
) -> list[str]:
    reasons: list[str] = []
    if not bool(data_integrity.get("ok")):
        reasons.append("data_integrity_not_ok")
    for reason in list(database_status.get("degraded_reasons") or []):
        reasons.append(f"database:{reason}")
    if str(operating_state.get("state") or "").strip().lower() == "recovery":
        reasons.append("operating_state:recovery")
    return reasons


def _service_snapshot(service: dict[str, Any], *, keys: tuple[str, ...]) -> dict[str, Any]:
    return {key: service.get(key) for key in keys}


def _admin_overview_payload(*, viewer: dict[str, Any]) -> dict[str, Any]:
    metrics = repo.get_dashboard_metrics()
    profit_cockpit = dict(metrics.get("profit_cockpit") or {})
    operating_state = operating_state_service.status()
    autotrade_status = auto_trade_service.status()
    execution_readiness = execution_service.webhook_readiness()
    operating_profile = single_account_guardrail_status()
    alert_payload = build_alert_payload(
        enabled=bool(autotrade_status.get("enabled")),
        profit_guard=dict(autotrade_status.get("profit_guard") or {}),
        dashboard_metrics=metrics,
        operating_state=operating_state,
        execution_readiness=execution_readiness,
        validation_baseline=dict(autotrade_status.get("validation_baseline") or {}),
    )
    database_status = get_database_health_snapshot()
    data_integrity = get_data_integrity_status()
    health_reasons = _health_reasons(
        database_status=database_status,
        data_integrity=data_integrity,
        operating_state=operating_state,
    )
    automation_status = automation_service.status()
    monitor_status = monitor_service.status()
    execution_retry_status = execution_retry_service.status()
    supabase_status = supabase_sync_service.status()

    return public_cockpit_payload({
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "viewer": viewer,
        "profitability": {
            "pending_review_count": int(metrics.get("pending_review_count") or 0),
            "total_trade_count": int(metrics.get("total_trade_count") or 0),
            "active_trades_count": int(metrics.get("active_trades_count") or 0),
            "sold_count": int(metrics.get("sold_count") or 0),
            "gross_profit": float(metrics.get("gross_profit") or 0.0),
            "realized_net_profit": float(metrics.get("realized_net_profit") or 0.0),
            "profit_hit_rate": float(metrics.get("profit_hit_rate") or 0.0),
            "avg_realized_roi": float(metrics.get("avg_realized_roi") or 0.0),
            "avg_holding_days": float(metrics.get("avg_holding_days") or 0.0),
            "median_holding_days": float(metrics.get("median_holding_days") or 0.0),
            "profit_cockpit": profit_cockpit,
            "forward_validation": dict(metrics.get("forward_validation") or {}),
        },
        "runtime": {
            "server_ready": not health_reasons,
            "health_status": "ready" if not health_reasons else "degraded",
            "health_reasons": health_reasons,
            "database": {
                "journal_mode": str(database_status.get("journal_mode") or ""),
                "degraded_reasons": list(database_status.get("degraded_reasons") or []),
            },
            "data_integrity": data_integrity,
            "operating_state": operating_state,
            "operating_profile": operating_profile,
            "execution_readiness": execution_readiness,
            "automation": _service_snapshot(
                automation_status,
                keys=(
                    "busy",
                    "all_running",
                    "default_include_monitor",
                    "default_include_scan",
                    "default_include_autotrade",
                    "default_include_execution_retry",
                    "default_include_supabase_sync",
                    "auto_start_monitor",
                    "auto_start_autotrade",
                    "auto_start_execution_retry",
                    "auto_start_supabase_sync",
                    "last_run_at",
                    "last_run_result",
                    "last_busy_at",
                    "last_busy_reason",
                ),
            ),
            "services": {
                "monitor": _service_snapshot(
                    monitor_status,
                    keys=(
                        "is_running",
                        "runs",
                        "last_run_at",
                        "last_inserted",
                        "last_error",
                        "circuit_open",
                        "circuit_reason",
                        "health",
                        "last_scan",
                    ),
                ),
                "autotrade": _service_snapshot(
                    autotrade_status,
                    keys=(
                        "enabled",
                        "running",
                        "busy",
                        "last_run_at",
                        "last_error",
                        "last_busy_at",
                        "last_busy_reason",
                        "total_runs",
                        "total_approved",
                        "profit_guard",
                        "validation_baseline",
                        "loss_recovery_state",
                    ),
                ),
                "execution_retry": _service_snapshot(
                    execution_retry_status,
                    keys=(
                        "enabled",
                        "running",
                        "busy",
                        "last_run_at",
                        "last_error",
                        "last_busy_at",
                        "last_busy_reason",
                        "total_runs",
                        "total_retried",
                        "total_succeeded",
                        "total_failed",
                    ),
                ),
                "supabase_sync": _service_snapshot(
                    supabase_status,
                    keys=(
                        "enabled",
                        "configured",
                        "is_running",
                        "last_run_at_unix",
                        "last_result",
                        "last_error",
                    ),
                ),
            },
        },
        "alerts": {
            "summary": dict(alert_payload.get("alert_summary") or {}),
            "items": list(alert_payload.get("alerts") or [])[:8],
            "portfolio": dict(alert_payload.get("portfolio") or {}),
            "incident_automation": dict(alert_payload.get("incident_automation") or {}),
            "delivery": dict(alert_payload.get("alert_delivery") or {}),
        },
        "deployment_readiness": {
            "startup_checks": startup_configuration_checks(),
            "operating_profile": operating_profile,
            "execution_readiness": execution_readiness,
            "validation_baseline": dict(autotrade_status.get("validation_baseline") or {}),
            "alert_delivery": dict(alert_payload.get("alert_delivery") or {}),
            "auto_start": {
                "monitor": bool(automation_status.get("auto_start_monitor")),
                "autotrade": bool(automation_status.get("auto_start_autotrade")),
                "execution_retry": bool(automation_status.get("auto_start_execution_retry")),
                "supabase_sync": bool(automation_status.get("auto_start_supabase_sync")),
            },
        },
        "overrides": {
            "source": risk_overrides_service.source_status_summary(limit=6),
            "cluster": risk_overrides_service.cluster_status_summary(limit=6),
        },
    })


def _parse_risk_score(note: str) -> float | None:
    text = (note or "").strip()
    if not text:
        return None
    for part in text.split(";"):
        seg = part.strip()
        if not seg.startswith("risk_score="):
            continue
        _, value = seg.split("=", 1)
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


def _price_history(limit: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT source, title, sold_price, sold_at
            FROM sales_raw
            ORDER BY sold_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "source": str(row["source"] or ""),
            "title": str(row["title"] or ""),
            "price": float(row["sold_price"]),
            "at": str(row["sold_at"] or ""),
        }
        for row in rows
    ]


def _trade_records(limit: int) -> list[dict[str, Any]]:
    rows = repo.list_trades(limit=limit)
    return [
        {
            "trade_id": int(row["id"]),
            "opportunity_id": int(row["opportunity_id"]),
            "status": str(row["status"] or ""),
            "title": str(row["title"] or ""),
            "approved_buy_price": float(row["approved_buy_price"]),
            "target_sell_price": float(row["target_sell_price"]),
            "sold_price": float(row["sold_price"]) if row["sold_price"] is not None else None,
            "updated_at": str(row["updated_at"] or ""),
        }
        for row in rows
    ]


def _market_snapshot() -> dict[str, Any]:
    metrics = repo.get_dashboard_metrics()
    normalized_market_preview = repo.get_normalized_market_snapshots(limit=5, scope="full")
    tradable_market_preview = repo.get_normalized_market_snapshots(limit=5, scope="tradable")
    normalized_market_count = len(repo.get_normalized_market_snapshots(limit=200, scope="full"))
    tradable_market_count = len(repo.get_normalized_market_snapshots(limit=200, scope="tradable"))
    with get_conn() as conn:
        open_listing_row = conn.execute(
            """
            SELECT COUNT(*) AS c, COALESCE(AVG(list_price), 0) AS avg_price
            FROM listings_raw
            WHERE status = 'open'
            """
        ).fetchone()
        last_sale_row = conn.execute(
            """
            SELECT sold_price, sold_at
            FROM sales_raw
            ORDER BY sold_at DESC
            LIMIT 1
            """
        ).fetchone()
    return {
        "pending_review_count": int(metrics["pending_review_count"]),
        "active_trades_count": int(metrics["active_trades_count"]),
        "sold_count": int(metrics["sold_count"]),
        "gross_profit": float(metrics["gross_profit"]),
        "open_listing_count": int(open_listing_row["c"]) if open_listing_row else 0,
        "open_listing_avg_price": round(float(open_listing_row["avg_price"]), 2) if open_listing_row else 0.0,
        "last_sale_price": float(last_sale_row["sold_price"]) if last_sale_row else None,
        "last_sale_at": str(last_sale_row["sold_at"]) if last_sale_row else "",
        "normalized_market_preview": normalized_market_preview,
        "normalized_market_count": normalized_market_count,
        "tradable_market_preview": tradable_market_preview,
        "tradable_market_count": tradable_market_count,
        "strategy_market_count": tradable_market_count,
    }


def _arbitrage_snapshot(limit: int) -> dict[str, Any]:
    return build_arbitrage_opportunities(
        limit=limit,
        window_hours=48,
        min_platforms=2,
        buy_fee_rate=0.0,
        sell_fee_rate=float(settings.platform_fee_rate or 0.0),
        shipping_cost=float(settings.default_shipping_cost or 0.0),
        min_net_profit=0.0,
        min_roi=0.0,
    )


def _trend_analysis(prices: list[float]) -> dict[str, Any]:
    if len(prices) < 2:
        return {"direction": "flat", "change_pct": 0.0}
    first = prices[0]
    last = prices[-1]
    if first <= 0:
        return {"direction": "flat", "change_pct": 0.0}
    change_pct = round(((last - first) / first) * 100, 2)
    direction = "up" if change_pct > 1 else "down" if change_pct < -1 else "flat"
    return {"direction": direction, "change_pct": change_pct}


def _volatility(prices: list[float]) -> dict[str, Any]:
    clean = [p for p in prices if p > 0]
    if len(clean) < 2:
        return {"stddev": 0.0, "coefficient_of_variation": 0.0}
    stddev = stdev(clean)
    avg_price = mean(clean)
    cov = stddev / avg_price if avg_price > 0 else 0.0
    return {
        "stddev": round(float(stddev), 4),
        "coefficient_of_variation": round(float(cov), 4),
    }


def _risk_assessment() -> dict[str, Any]:
    rows = repo.list_opportunities(limit=200)
    scores = [_parse_risk_score(str(row["review_note"] or "")) for row in rows]
    parsed = [s for s in scores if s is not None]
    blocked = sum(1 for row in rows if str(row["status"] or "") == "blocked_risk")
    avg_risk = round(mean(parsed), 2) if parsed else 0.0
    return {
        "average_risk_score": avg_risk,
        "blocked_count": blocked,
        "total_scanned": len(rows),
    }


def _opportunity_identification(limit: int) -> list[dict[str, Any]]:
    rows = repo.list_opportunities(status="pending_review", limit=limit)
    return [
        {
            "opportunity_id": int(row["id"]),
            "title": str(row["title"] or ""),
            "score": float(row["score"]),
            "expected_profit": float(row["expected_profit"]),
            "roi": float(row["roi"]),
        }
        for row in rows
    ]


def _calculation_overview(limit: int) -> dict[str, Any]:
    history = _price_history(limit=limit)
    prices = [float(item["price"]) for item in reversed(history)]
    opportunities = _opportunity_identification(limit=limit)
    return {
        "trend_analysis": _trend_analysis(prices),
        "volatility": _volatility(prices),
        "risk_assessment": _risk_assessment(),
        "opportunity_identification": opportunities,
    }


def _advanced_metrics(limit: int) -> dict[str, Any]:
    history = _price_history(limit=limit)
    prices = [float(item["price"]) for item in reversed(history) if float(item["price"]) > 0]
    if len(prices) < 2:
        return {
            "momentum": {"short_term_pct": 0.0, "long_term_pct": 0.0},
            "liquidity": {"trade_count": len(_trade_records(limit=limit)), "sales_count": len(prices)},
            "anomaly_detection": {"spike_count": 0, "spike_ratio": 0.0},
        }

    short_window = prices[-min(3, len(prices)) :]
    long_window = prices[-min(10, len(prices)) :]
    short_avg = mean(short_window)
    long_avg = mean(long_window)
    base = long_avg if long_avg > 0 else short_avg
    short_term_pct = round(((short_avg - base) / base) * 100, 2) if base > 0 else 0.0

    first = prices[0]
    long_term_pct = round(((prices[-1] - first) / first) * 100, 2) if first > 0 else 0.0

    vol = _volatility(prices)
    stddev = float(vol["stddev"])
    price_avg = mean(prices)
    threshold = (2 * stddev) if stddev > 0 else 0.0
    spikes = 0
    if threshold > 0:
        spikes = sum(1 for price in prices if abs(price - price_avg) > threshold)

    return {
        "momentum": {"short_term_pct": short_term_pct, "long_term_pct": long_term_pct},
        "liquidity": {"trade_count": len(_trade_records(limit=limit)), "sales_count": len(prices)},
        "anomaly_detection": {
            "spike_count": spikes,
            "spike_ratio": round((spikes / len(prices)) if prices else 0.0, 4),
        },
    }


def _automation_recommendation(limit: int) -> dict[str, Any]:
    calc = _calculation_overview(limit=limit)
    advanced = _advanced_metrics(limit=limit)
    autotrade = auto_trade_service.status()
    allow_run_once = bool(autotrade.get("enabled")) and not bool(autotrade.get("busy"))
    recommended_autotrade_limit = max(
        1,
        min(RECOMMENDATION_AUTOTRADE_CAP, len(calc["opportunity_identification"])),
    )

    risk = calc["risk_assessment"]
    momentum = advanced["momentum"]
    # Keep the recommendation conservative under elevated risk or downtrend momentum.
    suggested_min_score = DEFAULT_SUGGESTED_MIN_SCORE
    if float(risk["average_risk_score"]) > HIGH_RISK_AVG_THRESHOLD:
        suggested_min_score = HIGH_RISK_SUGGESTED_MIN_SCORE
    if float(momentum["short_term_pct"]) < NEGATIVE_MOMENTUM_THRESHOLD:
        suggested_min_score = max(suggested_min_score, NEGATIVE_MOMENTUM_SUGGESTED_MIN_SCORE)

    return {
        "allow_run_once": allow_run_once,
        "suggested_autotrade_limit": recommended_autotrade_limit,
        "suggested_min_score": suggested_min_score,
        "risk_summary": risk,
        "momentum": momentum,
        "autotrade_status": autotrade,
    }


def _decision_overview(limit: int) -> dict[str, Any]:
    rows = repo.list_opportunities(limit=limit)
    signals: list[dict[str, Any]] = []
    pricing: list[dict[str, Any]] = []
    alerts: list[dict[str, Any]] = []
    for row in rows:
        score = float(row["score"])
        status = str(row["status"] or "")
        risk_score = _parse_risk_score(str(row["review_note"] or "")) or 0.0
        signal = "buy" if status == "pending_review" and score >= 60 else "hold"
        signals.append(
            {
                "opportunity_id": int(row["id"]),
                "title": str(row["title"] or ""),
                "signal": signal,
                "score": score,
            }
        )
        pricing.append(
            {
                "opportunity_id": int(row["id"]),
                "title": str(row["title"] or ""),
                "suggested_list_price": float(row["suggested_list_price"]),
                "expected_sale_price": float(row["expected_sale_price"]),
            }
        )
        if status == "blocked_risk" or risk_score >= 70:
            alerts.append(
                {
                    "opportunity_id": int(row["id"]),
                    "title": str(row["title"] or ""),
                    "risk_score": risk_score,
                    "status": status,
                }
            )
    return {
        "buy_sell_signals": signals,
        "pricing_suggestions": pricing,
        "risk_alerts": alerts,
    }


@router.get("/data/price-history")
def get_price_history(limit: int = Query(default=100, ge=1, le=MAX_ANALYSIS_LIMIT)) -> dict[str, Any]:
    items = _price_history(limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/data/trade-records")
def get_trade_records(limit: int = Query(default=100, ge=1, le=MAX_ANALYSIS_LIMIT)) -> dict[str, Any]:
    items = _trade_records(limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/arbitrage/opportunities")
def get_arbitrage_opportunities(
    limit: int = Query(default=20, ge=1, le=100),
    window_hours: int = Query(default=48, ge=1, le=24 * 30),
    keyword: str = "",
    sources: str = "",
    min_platforms: int = Query(default=2, ge=2, le=10),
    buy_fee_rate: float = Query(default=0.0, ge=0.0, le=1.0),
    sell_fee_rate: float = Query(default=float(settings.platform_fee_rate or 0.0), ge=0.0, le=1.0),
    shipping_cost: float = Query(default=float(settings.default_shipping_cost or 0.0), ge=0.0, le=999999.0),
    min_net_profit: float = Query(default=0.0, ge=0.0, le=999999.0),
    min_roi: float = Query(default=0.0, ge=0.0, le=100.0),
) -> dict[str, Any]:
    parsed_sources = [item.strip() for item in str(sources or "").split(",") if item.strip()]
    return build_arbitrage_opportunities(
        limit=limit,
        window_hours=window_hours,
        keyword=keyword,
        sources=parsed_sources,
        min_platforms=min_platforms,
        buy_fee_rate=buy_fee_rate,
        sell_fee_rate=sell_fee_rate,
        shipping_cost=shipping_cost,
        min_net_profit=min_net_profit,
        min_roi=min_roi,
    )


@router.get("/arbitrage/matching-preview")
def get_arbitrage_matching_preview(
    limit: int = Query(default=20, ge=1, le=100),
    window_hours: int = Query(default=72, ge=1, le=24 * 30),
    keyword: str = "",
    sources: str = "",
    buy_fee_rate: float = Query(default=0.0, ge=0.0, le=1.0),
    sell_fee_rate: float = Query(default=float(settings.platform_fee_rate or 0.0), ge=0.0, le=1.0),
    shipping_cost: float = Query(default=float(settings.default_shipping_cost or 0.0), ge=0.0, le=999999.0),
) -> dict[str, Any]:
    parsed_sources = [item.strip() for item in str(sources or "").split(",") if item.strip()]
    return build_arbitrage_matching_preview(
        limit=limit,
        listing_hours=window_hours,
        include_sources=tuple(parsed_sources),
        keyword=keyword,
        buy_fee_rate=buy_fee_rate,
        sell_fee_rate=sell_fee_rate,
        shipping_cost=shipping_cost,
    )


@router.post("/arbitrage/validate-match")
def validate_arbitrage_match(payload: ArbitrageMatchValidateIn) -> dict[str, Any]:
    return explain_marketplace_match(
        left_title=payload.left_title,
        right_title=payload.right_title,
        left_key=payload.left_key,
        right_key=payload.right_key,
    )


@router.post("/arbitrage/validate-batch")
def validate_arbitrage_match_batch(
    payload: list[ArbitrageMatchBatchItemIn],
) -> dict[str, Any]:
    items = [
        {
            "input": item.model_dump(),
            "result": explain_marketplace_match(
                left_title=item.left_title,
                right_title=item.right_title,
                left_key=item.left_key,
                right_key=item.right_key,
            ),
        }
        for item in payload
    ]
    return {"items": items, "count": len(items)}


@router.post("/arbitrage/match-samples", dependencies=[Depends(require_cardflip_operate)])
def create_arbitrage_match_sample(payload: ArbitrageMatchSampleIn) -> dict[str, Any]:
    result = explain_marketplace_match(
        left_title=payload.left_title,
        right_title=payload.right_title,
        left_key=payload.left_key,
        right_key=payload.right_key,
    )
    return repo.create_matching_lab_sample(
        left_title=payload.left_title,
        right_title=payload.right_title,
        left_key=payload.left_key,
        right_key=payload.right_key,
        expected_verdict=payload.expected_verdict,
        note=payload.note,
        result=result,
    )


@router.get("/arbitrage/match-samples")
def get_arbitrage_match_samples(
    limit: int = Query(default=100, ge=1, le=500),
) -> dict[str, Any]:
    items = repo.list_matching_lab_samples(limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/arbitrage/match-samples/report")
def get_arbitrage_match_sample_report(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=2000, ge=1, le=10000),
    accuracy_threshold: float = Query(default=0.8, ge=0.0, le=1.0),
    min_scored_samples: int = Query(default=10, ge=1, le=10000),
) -> dict[str, Any]:
    return repo.build_matching_lab_report(
        days=days,
        limit=limit,
        accuracy_threshold=accuracy_threshold,
        min_scored_samples=min_scored_samples,
    )


@router.get("/arbitrage/review-queue")
def get_arbitrage_review_queue(
    limit: int = Query(default=20, ge=1, le=100),
    listing_hours: int = Query(default=24 * 30, ge=1, le=24 * 30),
    candidate_pool: int = Query(default=300, ge=20, le=1000),
    min_token_overlap: float = Query(default=0.35, ge=0.0, le=1.0),
) -> dict[str, Any]:
    return repo.build_matching_review_queue(
        limit=limit,
        listing_hours=listing_hours,
        candidate_pool=candidate_pool,
        min_token_overlap=min_token_overlap,
    )


@router.post("/arbitrage/review-queue/{review_id}/label", dependencies=[Depends(require_cardflip_operate)])
def label_arbitrage_review_queue_item(
    review_id: str,
    payload: ArbitrageReviewQueueLabelIn,
    listing_hours: int = Query(default=24 * 30, ge=1, le=24 * 30),
    candidate_pool: int = Query(default=300, ge=20, le=1000),
    min_token_overlap: float = Query(default=0.35, ge=0.0, le=1.0),
) -> dict[str, Any]:
    try:
        return repo.label_matching_review_queue_item(
            review_id=review_id,
            expected_verdict=payload.expected_verdict,
            note=payload.note,
            listing_hours=listing_hours,
            candidate_pool=candidate_pool,
            min_token_overlap=min_token_overlap,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"review queue item not found: {exc}") from exc


@router.get("/data/market-snapshot")
def get_market_snapshot() -> dict[str, Any]:
    return _market_snapshot()


@router.get("/data/normalized-market")
def get_normalized_market(
    limit: int = Query(default=20, ge=1, le=200),
    listing_hours: int = Query(default=24, ge=1, le=24 * 30),
    sales_days: int = Query(default=7, ge=1, le=90),
    scope: Literal["full", "tradable"] = Query(default="full"),
) -> dict[str, Any]:
    items = repo.get_normalized_market_snapshots(
        limit=limit,
        listing_hours=listing_hours,
        sales_days=sales_days,
        scope=scope,
    )
    return {
        "items": items,
        "count": len(items),
        "listing_hours": listing_hours,
        "sales_days": sales_days,
        "scope": scope,
    }


@router.get("/data/tradable-market")
def get_tradable_market(
    limit: int = Query(default=20, ge=1, le=200),
    listing_hours: int = Query(default=24, ge=1, le=24 * 30),
    sales_days: int = Query(default=7, ge=1, le=90),
) -> dict[str, Any]:
    return get_normalized_market(
        limit=limit,
        listing_hours=listing_hours,
        sales_days=sales_days,
        scope="tradable",
    )


@router.get("/calculation/overview")
def get_calculation_overview(limit: int = Query(default=100, ge=1, le=MAX_ANALYSIS_LIMIT)) -> dict[str, Any]:
    return _calculation_overview(limit=limit)


@router.get("/calculation/advanced")
def get_advanced_calculation(limit: int = Query(default=100, ge=1, le=MAX_ANALYSIS_LIMIT)) -> dict[str, Any]:
    return _advanced_metrics(limit=limit)


@router.get("/decision/overview")
def get_decision_overview(limit: int = Query(default=100, ge=1, le=MAX_ANALYSIS_LIMIT)) -> dict[str, Any]:
    return _decision_overview(limit=limit)


@router.get("/decision/market-docs")
def get_market_docs(
    limit: int = Query(default=20, ge=1, le=200),
    listing_hours: int = Query(default=24, ge=1, le=24 * 30),
    sales_days: int = Query(default=7, ge=1, le=90),
    scope: Literal["full", "tradable"] = Query(default="tradable"),
) -> dict[str, Any]:
    items = build_market_snapshot_documents(
        limit=limit,
        listing_hours=listing_hours,
        sales_days=sales_days,
        scope=scope,
    )
    return {
        "items": items,
        "count": len(items),
        "scope": scope,
    }


@router.get("/decision/strategy-proposal")
def get_market_strategy_proposal(
    limit: int = Query(default=12, ge=1, le=50),
    listing_hours: int = Query(default=24, ge=1, le=24 * 30),
    sales_days: int = Query(default=7, ge=1, le=90),
    include_reference: bool = True,
) -> dict[str, Any]:
    return get_strategy_proposal(
        limit=limit,
        listing_hours=listing_hours,
        sales_days=sales_days,
        include_reference=include_reference,
    )


@router.get("/automation/recommendation")
def get_automation_recommendation(
    limit: int = Query(default=100, ge=1, le=MAX_ANALYSIS_LIMIT)
) -> dict[str, Any]:
    return _automation_recommendation(limit=limit)


@router.get("/strategy/proposal")
def get_strategy_proposal_view(
    limit: int = Query(default=12, ge=1, le=100),
    listing_hours: int = Query(default=24, ge=1, le=24 * 30),
    sales_days: int = Query(default=7, ge=1, le=90),
    include_reference: bool = True,
) -> dict[str, Any]:
    return get_strategy_proposal(
        limit=limit,
        listing_hours=listing_hours,
        sales_days=sales_days,
        include_reference=include_reference,
    )


@router.post("/automation/run-once", dependencies=[Depends(require_cardflip_operate)])
def run_automation_once_from_analysis(
    force: bool = False,
    include_monitor: bool = False,
    include_scan: bool = False,
    include_execution_retry: bool = False,
    include_supabase_sync: bool = False,
    limit: int = Query(default=0, ge=0, le=MAX_ANALYSIS_LIMIT),
) -> dict[str, Any]:
    recommendation = _automation_recommendation(limit=max(1, limit or 100))
    suggested_limit = int(recommendation["suggested_autotrade_limit"])
    effective_limit = max(1, min(MAX_ANALYSIS_LIMIT, limit or suggested_limit))
    result = automation_service.run_once(
        include_monitor=include_monitor,
        include_scan=include_scan,
        include_autotrade=True,
        include_execution_retry=include_execution_retry,
        include_supabase_sync=include_supabase_sync,
        autotrade_limit=effective_limit,
        force=force,
    )
    return {
        "recommendation": recommendation,
        "autotrade_limit_used": effective_limit,
        "result": result,
    }


@router.get("/admin-overview")
def get_admin_overview(request: Request) -> dict[str, Any]:
    viewer = _require_admin_profile(request)
    return _admin_overview_payload(viewer=viewer)


@router.get("/admin-overview/stream")
async def stream_admin_overview(
    request: Request,
    interval_seconds: float = Query(default=5.0, ge=0.0, le=30.0),
    max_events: int = Query(default=0, ge=0, le=50),
) -> StreamingResponse:
    viewer = _require_admin_profile(request)

    async def event_gen():
        emitted = 0
        last_payload = ""
        while max_events <= 0 or emitted < max_events:
            payload = _admin_overview_payload(viewer=viewer)
            encoded = json.dumps(payload, ensure_ascii=False)
            if encoded != last_payload:
                yield f"event: overview\ndata: {encoded}\n\n"
                last_payload = encoded
            else:
                heartbeat = json.dumps(
                    {
                        "generated_at": payload.get("generated_at"),
                        "status": "alive",
                    },
                    ensure_ascii=False,
                )
                yield f"event: heartbeat\ndata: {heartbeat}\n\n"
            emitted += 1
            if max_events > 0 and emitted >= max_events:
                break
            if interval_seconds > 0:
                await asyncio.sleep(interval_seconds)

    return StreamingResponse(
        event_gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/report")
def generate_report(limit: int = Query(default=100, ge=1, le=MAX_ANALYSIS_LIMIT)) -> dict[str, Any]:
    data_layer = {
        "price_history": _price_history(limit=limit),
        "trade_records": _trade_records(limit=limit),
        "market_snapshot": _market_snapshot(),
        "normalized_market_full": repo.get_normalized_market_snapshots(limit=min(20, limit), scope="full"),
        "normalized_market_tradable": repo.get_normalized_market_snapshots(limit=min(20, limit), scope="tradable"),
    }
    calculation_layer = _calculation_overview(limit=limit)
    advanced_calculation = _advanced_metrics(limit=limit)
    decision_layer = _decision_overview(limit=limit)
    automation_layer = _automation_recommendation(limit=limit)
    report_text = "\n".join(
        [
            "# Analysis Report",
            f"- price points: {len(data_layer['price_history'])}",
            f"- trade records: {len(data_layer['trade_records'])}",
            f"- trend: {calculation_layer['trend_analysis']['direction']}",
            f"- avg risk score: {calculation_layer['risk_assessment']['average_risk_score']}",
            f"- risk alerts: {len(decision_layer['risk_alerts'])}",
            f"- suggested autotrade limit: {automation_layer['suggested_autotrade_limit']}",
        ]
    )
    return {
        "data_layer": data_layer,
        "calculation_layer": calculation_layer,
        "advanced_calculation_layer": advanced_calculation,
        "decision_layer": decision_layer,
        "automation_layer": automation_layer,
        "report_text": report_text,
    }


@router.get("/stream")
async def realtime_stream(
    interval_seconds: float = Query(default=1.0, ge=0.0, le=30.0),
    max_events: int = Query(default=3, ge=1, le=20),
) -> StreamingResponse:
    async def event_gen():
        for _ in range(max_events):
            payload = {
                "market_snapshot": _market_snapshot(),
                "calculation_layer": _calculation_overview(limit=50),
                "advanced_calculation_layer": _advanced_metrics(limit=50),
                "decision_layer": _decision_overview(limit=50),
                "automation_layer": _automation_recommendation(limit=50),
            }
            try:
                encoded = json.dumps(payload, ensure_ascii=False)
            except (TypeError, ValueError) as exc:
                yield f"event: error\ndata: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"
                break
            yield f"data: {encoded}\n\n"
            if interval_seconds > 0:
                await asyncio.sleep(interval_seconds)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
