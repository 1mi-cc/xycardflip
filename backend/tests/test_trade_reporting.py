from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import repositories as repo
from app.config import settings
from app.database import get_conn
from app.database import init_db
from app.main import create_app
from app.schemas import ListingIn
from app.schemas import ValuationOut
from app.services.execution import ExecutionService


@pytest.fixture
def isolated_reporting_sqlite(tmp_path: Path):
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "trade_reporting.db"))
    init_db()
    try:
        yield Path(settings.sqlite_path)
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def _seed_trade(index: int, sold_price: float | None = None) -> int:
    listed_at = datetime(2026, 3, 10, tzinfo=timezone.utc)
    listing = ListingIn(
        source="pytest",
        listing_id=f"report-listing-{index}",
        seller_id=f"report-seller-{index}",
        title=f"report card #{index}",
        description="report seed",
        list_price=100.0,
        listed_at=listed_at,
        status="open",
        raw={"index": index},
    )
    listing_row_id, _ = repo.upsert_listing(listing)
    assert listing_row_id is not None

    valuation_id = repo.save_valuation(
        ValuationOut(
            listing_row_id=listing_row_id,
            expected_sale_price=150.0,
            buy_limit=120.0,
            suggested_list_price=160.0,
            ci_low=140.0,
            ci_high=170.0,
            model_confidence=0.92,
            comparables_count=12,
            reasoning="report seed",
        )
    )
    opportunity_id = repo.upsert_opportunity(
        listing_row_id=listing_row_id,
        valuation_id=valuation_id,
        expected_profit=30.0,
        roi=0.3,
        score=88.0,
        status="pending_review",
        note="pytest_seed;risk_score=10;risk_level=low;reasons=none",
    )
    approval = repo.approve_opportunity_idempotent(
        opportunity_id=opportunity_id,
        approved_buy_price=100.0,
        approved_by="pytest",
        note="report approval",
    )
    trade_id = int(approval["trade_id"])
    if sold_price is not None:
        repo.update_trade_listed(trade_id, f"https://example.test/{trade_id}", "listed")
        repo.update_trade_sold(trade_id, sold_price, "sold")
    return trade_id


def _set_trade_window(trade_id: int, *, holding_days: int) -> None:
    ended_at = datetime(2026, 3, 20, tzinfo=timezone.utc)
    started_at = ended_at - timedelta(days=holding_days)
    with get_conn() as conn:
        conn.execute(
            "UPDATE trades SET created_at = ?, updated_at = ? WHERE id = ?",
            (started_at.isoformat(), ended_at.isoformat(), trade_id),
        )


def test_execution_webhook_readiness_reports_missing_urls() -> None:
    old_buy = settings.execution_webhook_buy_url
    old_list = settings.execution_webhook_list_url
    old_sell = settings.execution_webhook_sell_url
    old_live_enabled = settings.execution_live_enabled
    try:
        object.__setattr__(settings, "execution_webhook_buy_url", "")
        object.__setattr__(settings, "execution_webhook_list_url", "")
        object.__setattr__(settings, "execution_webhook_sell_url", "")
        object.__setattr__(settings, "execution_live_enabled", True)

        service = ExecutionService()
        service.update_config(provider="webhook", live_enabled=True)
        readiness = service.webhook_readiness()

        assert readiness["provider"] == "webhook"
        assert readiness["webhook_provider"] is True
        assert readiness["live_ready"] is False
        assert "EXECUTION_WEBHOOK_BUY_URL" in readiness["missing"]
        assert "EXECUTION_WEBHOOK_LIST_URL" in readiness["missing"]
        assert "EXECUTION_WEBHOOK_SELL_URL" in readiness["missing"]
    finally:
        object.__setattr__(settings, "execution_webhook_buy_url", old_buy)
        object.__setattr__(settings, "execution_webhook_list_url", old_list)
        object.__setattr__(settings, "execution_webhook_sell_url", old_sell)
        object.__setattr__(settings, "execution_live_enabled", old_live_enabled)


def test_forward_validation_batch_auto_enrolls_and_closes(isolated_reporting_sqlite: Path) -> None:
    batch = repo.create_forward_validation_batch(
        name="wave-1",
        target_sample_size=2,
        note="pytest validation batch",
    )

    trade_one = _seed_trade(1)
    trade_two = _seed_trade(2)

    batches = repo.list_forward_validation_batches(limit=5)
    latest = batches[0]
    assert latest["id"] == batch["id"]
    assert latest["status"] == "closed"
    assert latest["enrolled_count"] == 2

    report = repo.get_trade_performance_report()
    active_batch = report["forward_validation"]["active_batch"]
    assert active_batch is None
    recent = report["forward_validation"]["recent_batches"][0]
    enrolled_ids = {item["trade_id"] for item in recent["items"]}
    assert enrolled_ids == {trade_one, trade_two}


def test_metrics_summary_exposes_profit_hit_rate_and_turnover(isolated_reporting_sqlite: Path) -> None:
    repo.create_forward_validation_batch(
        name="wave-metrics",
        target_sample_size=10,
        note="metrics batch",
    )
    profitable = _seed_trade(10, sold_price=150.0)
    losing = _seed_trade(11, sold_price=90.0)
    active = _seed_trade(12, sold_price=None)
    _set_trade_window(profitable, holding_days=5)
    _set_trade_window(losing, holding_days=1)
    _set_trade_window(active, holding_days=2)

    with TestClient(create_app()) as client:
        response = client.get("/trades/metrics-summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["active_trades_count"] == 1
    assert payload["sold_count"] == 2
    assert payload["gross_profit"] == 40.0
    assert payload["profit_hit_rate"] == 0.5
    assert payload["avg_holding_days"] == 3.0
    assert payload["median_holding_days"] == 3.0
    assert payload["execution_readiness"]["provider"] in {"mock", "disabled", "none", "webhook"}
    assert payload["profit_cockpit"]["inventory"]["active_trade_count"] == 1
    assert payload["profit_cockpit"]["inventory"]["deployed_capital"] == 100.0
    active_batch = payload["forward_validation"]["active_batch"]
    assert active_batch is not None
    assert active_batch["enrolled_count"] == 3
    assert active_batch["sold_count"] == 2


def test_metrics_summary_exposes_profit_cockpit_windows_and_sources(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    profitable = _seed_trade(21, sold_price=150.0)
    losing = _seed_trade(22, sold_price=80.0)
    stale = _seed_trade(23, sold_price=160.0)
    _set_trade_window(profitable, holding_days=1)
    _set_trade_window(losing, holding_days=1)
    _set_trade_window(stale, holding_days=9)

    with get_conn() as conn:
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-21",))
        conn.execute("UPDATE listings_raw SET source = 'beta' WHERE listing_id = ?", ("report-listing-22",))
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-23",))
        conn.execute(
            "UPDATE trades SET updated_at = ? WHERE id = ?",
            (datetime(2026, 3, 20, 13, tzinfo=timezone.utc).isoformat(), profitable),
        )
        conn.execute(
            "UPDATE trades SET updated_at = ? WHERE id = ?",
            (datetime(2026, 3, 20, 12, tzinfo=timezone.utc).isoformat(), losing),
        )
        conn.execute(
            "UPDATE trades SET updated_at = ? WHERE id = ?",
            (datetime(2026, 3, 11, tzinfo=timezone.utc).isoformat(), stale),
        )

    previous_state = repo.upsert_seller_control_state(
        source="alpha",
        seller_id="report-seller-23",
        state="frozen",
        reason="seller slipped",
        frozen_until=datetime(2026, 3, 21, tzinfo=timezone.utc).isoformat(),
        metadata={"seller_lane": "blacklist"},
    )
    next_state = repo.upsert_seller_control_state(
        source="alpha",
        seller_id="report-seller-23",
        state="observe",
        reason="seller recovered",
        frozen_until=datetime(2026, 3, 22, tzinfo=timezone.utc).isoformat(),
        metadata={"seller_lane": "observe", "positive_streak": 1},
    )
    repo.create_seller_control_event(
        source="alpha",
        seller_id="report-seller-23",
        event_type="auto_observe",
        reason="seller recovered",
        previous_state=previous_state,
        next_state=next_state,
    )

    fixed_now = datetime(2026, 3, 20, 12, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(repo, "datetime", _FixedDateTime)

    with TestClient(create_app()) as client:
        response = client.get("/trades/metrics-summary")

    assert response.status_code == 200
    payload = response.json()
    cockpit = payload["profit_cockpit"]
    assert cockpit["today"]["sold_count"] == 2
    assert cockpit["today"]["realized_net_profit"] == 0.2
    assert cockpit["last_7d"]["sold_count"] == 2
    assert cockpit["loss_streak"]["current_consecutive_losses"] == 0
    assert cockpit["best_source_7d"]["source"] == "alpha"
    assert cockpit["weakest_source_7d"]["source"] == "beta"
    assert cockpit["best_source_7d"]["strategy_mode"] == "hold"
    assert cockpit["weakest_source_7d"]["strategy_mode"] == "hold"
    assert cockpit["seller_leaderboard_7d"][0]["seller_id"] == "report-seller-21"
    assert cockpit["best_seller_all_time"]["seller_id"] == "report-seller-23"
    assert cockpit["seller_attribution_all_time"][0]["seller_id"] == "report-seller-23"
    assert cockpit["seller_attribution_all_time"][0]["recent_trades"][0]["trade_id"] == stale
    assert cockpit["seller_attribution_all_time"][0]["recent_trades"][0]["title"] == "report card #23"
    assert cockpit["seller_attribution_all_time"][0]["current_control"]["state"] == "observe"
    assert cockpit["seller_attribution_all_time"][0]["recent_control_events"][0]["event_type"] == "auto_observe"
