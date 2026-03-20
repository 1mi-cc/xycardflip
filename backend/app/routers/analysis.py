from __future__ import annotations

import asyncio
import json
from statistics import mean, stdev
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from .. import repositories as repo
from ..database import get_conn

router = APIRouter(prefix="/analysis", tags=["analysis"])


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
    }


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
def get_price_history(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    items = _price_history(limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/data/trade-records")
def get_trade_records(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    items = _trade_records(limit=limit)
    return {"items": items, "count": len(items)}


@router.get("/data/market-snapshot")
def get_market_snapshot() -> dict[str, Any]:
    return _market_snapshot()


@router.get("/calculation/overview")
def get_calculation_overview(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return _calculation_overview(limit=limit)


@router.get("/decision/overview")
def get_decision_overview(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    return _decision_overview(limit=limit)


@router.get("/report")
def generate_report(limit: int = Query(default=100, ge=1, le=500)) -> dict[str, Any]:
    data_layer = {
        "price_history": _price_history(limit=limit),
        "trade_records": _trade_records(limit=limit),
        "market_snapshot": _market_snapshot(),
    }
    calculation_layer = _calculation_overview(limit=limit)
    decision_layer = _decision_overview(limit=limit)
    report_text = "\n".join(
        [
            "# Analysis Report",
            f"- price points: {len(data_layer['price_history'])}",
            f"- trade records: {len(data_layer['trade_records'])}",
            f"- trend: {calculation_layer['trend_analysis']['direction']}",
            f"- avg risk score: {calculation_layer['risk_assessment']['average_risk_score']}",
            f"- risk alerts: {len(decision_layer['risk_alerts'])}",
        ]
    )
    return {
        "data_layer": data_layer,
        "calculation_layer": calculation_layer,
        "decision_layer": decision_layer,
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
                "decision_layer": _decision_overview(limit=50),
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
