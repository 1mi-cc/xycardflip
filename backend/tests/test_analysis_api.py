from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from app import repositories as repo
from app.config import settings
from app.database import init_db
from app.main import create_app
from app.schemas import ListingIn, SaleIn, ValuationOut


def _seed_data() -> None:
    sold_base = datetime(2026, 3, 10, tzinfo=timezone.utc)
    repo.insert_sales(
        [
            SaleIn(
                source="pytest",
                item_id="sale-1",
                title="Blue-Eyes White Dragon",
                description="sold",
                sold_price=100.0,
                sold_at=sold_base,
                raw={},
            ),
            SaleIn(
                source="pytest",
                item_id="sale-2",
                title="Blue-Eyes White Dragon",
                description="sold",
                sold_price=120.0,
                sold_at=sold_base.replace(day=11),
                raw={},
            ),
            SaleIn(
                source="pytest",
                item_id="sale-3",
                title="Blue-Eyes White Dragon",
                description="sold",
                sold_price=110.0,
                sold_at=sold_base.replace(day=12),
                raw={},
            ),
        ]
    )

    listing_a = ListingIn(
        source="pytest",
        listing_id="listing-a",
        seller_id="seller-a",
        title="Card A",
        description="desc",
        list_price=80.0,
        listed_at=sold_base,
        status="open",
        raw={},
    )
    listing_b = ListingIn(
        source="pytest",
        listing_id="listing-b",
        seller_id="seller-b",
        title="Card B",
        description="desc",
        list_price=140.0,
        listed_at=sold_base,
        status="open",
        raw={},
    )
    listing_a_id, _ = repo.upsert_listing(listing_a)
    listing_b_id, _ = repo.upsert_listing(listing_b)
    assert listing_a_id is not None and listing_b_id is not None

    valuation_a = repo.save_valuation(
        ValuationOut(
            listing_row_id=listing_a_id,
            expected_sale_price=130.0,
            buy_limit=90.0,
            suggested_list_price=135.0,
            ci_low=120.0,
            ci_high=140.0,
            model_confidence=0.9,
            comparables_count=12,
            reasoning="seed",
        )
    )
    valuation_b = repo.save_valuation(
        ValuationOut(
            listing_row_id=listing_b_id,
            expected_sale_price=150.0,
            buy_limit=95.0,
            suggested_list_price=155.0,
            ci_low=130.0,
            ci_high=170.0,
            model_confidence=0.7,
            comparables_count=8,
            reasoning="seed",
        )
    )
    opp_a = repo.upsert_opportunity(
        listing_row_id=listing_a_id,
        valuation_id=valuation_a,
        expected_profit=30.0,
        roi=0.375,
        score=75.0,
        status="pending_review",
        note="risk_score=20;risk_level=low;reasons=none",
    )
    repo.upsert_opportunity(
        listing_row_id=listing_b_id,
        valuation_id=valuation_b,
        expected_profit=5.0,
        roi=0.03,
        score=35.0,
        status="blocked_risk",
        note="risk_score=80;risk_level=high;reasons=list_price_above_buy_limit",
    )
    repo.approve_opportunity_idempotent(
        opportunity_id=opp_a,
        approved_buy_price=82.0,
        approved_by="pytest",
        note="seed trade",
    )


def test_analysis_endpoints(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "analysis_api.db"))
    try:
        init_db()
        _seed_data()
        with TestClient(create_app()) as client:
            price_history = client.get("/analysis/data/price-history", params={"limit": 5})
            assert price_history.status_code == 200
            history_payload = price_history.json()
            assert history_payload["count"] == 3

            trade_records = client.get("/analysis/data/trade-records")
            assert trade_records.status_code == 200
            assert trade_records.json()["count"] >= 1

            snapshot = client.get("/analysis/data/market-snapshot")
            assert snapshot.status_code == 200
            assert "open_listing_count" in snapshot.json()

            calc = client.get("/analysis/calculation/overview")
            assert calc.status_code == 200
            calc_payload = calc.json()
            assert "trend_analysis" in calc_payload
            assert "volatility" in calc_payload
            assert "risk_assessment" in calc_payload
            assert "opportunity_identification" in calc_payload

            advanced_calc = client.get("/analysis/calculation/advanced")
            assert advanced_calc.status_code == 200
            advanced_payload = advanced_calc.json()
            assert "momentum" in advanced_payload
            assert "liquidity" in advanced_payload
            assert "anomaly_detection" in advanced_payload

            decision = client.get("/analysis/decision/overview")
            assert decision.status_code == 200
            decision_payload = decision.json()
            assert "buy_sell_signals" in decision_payload
            assert "pricing_suggestions" in decision_payload
            assert "risk_alerts" in decision_payload
            assert len(decision_payload["risk_alerts"]) >= 1

            auto_reco = client.get("/analysis/automation/recommendation")
            assert auto_reco.status_code == 200
            auto_reco_payload = auto_reco.json()
            assert "allow_run_once" in auto_reco_payload
            assert "suggested_autotrade_limit" in auto_reco_payload
            assert "autotrade_status" in auto_reco_payload

            auto_run = client.post(
                "/analysis/automation/run-once",
                params={"force": True, "limit": 5},
            )
            assert auto_run.status_code == 200
            auto_run_payload = auto_run.json()
            assert "recommendation" in auto_run_payload
            assert "result" in auto_run_payload

            report = client.get("/analysis/report")
            assert report.status_code == 200
            report_payload = report.json()
            assert "data_layer" in report_payload
            assert "calculation_layer" in report_payload
            assert "advanced_calculation_layer" in report_payload
            assert "decision_layer" in report_payload
            assert "automation_layer" in report_payload
            assert "report_text" in report_payload

            stream = client.get(
                "/analysis/stream",
                params={"interval_seconds": 0, "max_events": 2},
                headers={"accept": "text/event-stream"},
            )
            assert stream.status_code == 200
            assert "text/event-stream" in stream.headers.get("content-type", "")
            assert "data:" in stream.text
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
