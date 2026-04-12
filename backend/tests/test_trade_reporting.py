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


def test_execution_list_respects_blocked_source_action_lane(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade_id = _seed_trade(90, sold_price=None)

    monkeypatch.setattr(
        repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "source_leaderboard_7d": [
                    {
                        "source": "pytest",
                        "list_action_lane": "blocked",
                        "allow_auto_list": False,
                    }
                ]
            }
        },
    )

    service = ExecutionService()
    result = service.execute_list(trade_id=trade_id, dry_run=True, force=False)

    assert result["success"] is False
    assert result["blocked"] is True
    assert "source_action_blocked:pytest:list:blocked" in str(result["error"])


def test_execution_sell_respects_blocked_source_action_lane(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade_id = _seed_trade(91, sold_price=None)

    monkeypatch.setattr(
        repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "source_leaderboard_7d": [
                    {
                        "source": "pytest",
                        "sell_action_lane": "blocked",
                        "allow_auto_sell": False,
                    }
                ]
            }
        },
    )

    service = ExecutionService()
    result = service.execute_sell(trade_id=trade_id, dry_run=True, force=False, sold_price=150.0)

    assert result["success"] is False
    assert result["blocked"] is True
    assert "source_action_blocked:pytest:sell:blocked" in str(result["error"])


def test_retry_failed_treats_blocked_source_action_as_blocked_not_failure(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade_id = _seed_trade(92, sold_price=None)
    repo.create_execution_log(
        trade_id=trade_id,
        action="list",
        provider="pytest",
        dry_run=False,
        request_payload={"requested_listing_url": ""},
        response_payload={"error": "http 500"},
        success=False,
        error="http 500",
    )

    monkeypatch.setattr(
        repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "source_leaderboard_7d": [
                    {
                        "source": "pytest",
                        "list_action_lane": "blocked",
                        "allow_auto_list": False,
                    }
                ]
            }
        },
    )

    service = ExecutionService()
    result = service.retry_failed(action="list", limit=1, dry_run=True, force=False)

    assert result["retried"] == 1
    assert result["succeeded"] == 0
    assert result["failed"] == 0
    assert result["blocked"] == 1
    assert result["items"][0]["blocked"] is True
    assert "source_action_blocked:pytest:list:blocked" in str(result["items"][0]["error"])


def test_retry_failed_limits_sell_action_for_observe_lane(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade_one = _seed_trade(93, sold_price=None)
    trade_two = _seed_trade(94, sold_price=None)
    repo.create_execution_log(
        trade_id=trade_one,
        action="sell",
        provider="pytest",
        dry_run=False,
        request_payload={"requested_sold_price": 150.0},
        response_payload={"error": "http 500"},
        success=False,
        error="http 500",
    )
    repo.create_execution_log(
        trade_id=trade_two,
        action="sell",
        provider="pytest",
        dry_run=False,
        request_payload={"requested_sold_price": 151.0},
        response_payload={"error": "http 500"},
        success=False,
        error="http 500",
    )

    monkeypatch.setattr(
        repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "source_leaderboard_7d": [
                    {
                        "source": "pytest",
                        "sell_action_lane": "observe",
                        "allow_auto_sell": True,
                    }
                ]
            }
        },
    )

    service = ExecutionService()
    sell_calls: list[int] = []

    def _execute_sell(**kwargs):
        sell_calls.append(int(kwargs["trade_id"]))
        return {
            "success": True,
            "blocked": False,
            "log_id": 1000 + int(kwargs["trade_id"]),
            "business_ban_code": "",
            "error": "",
        }

    monkeypatch.setattr(service, "execute_sell", _execute_sell)

    result = service.retry_failed(action="sell", limit=2, dry_run=True, force=False)

    assert result["retried"] == 2
    assert result["succeeded"] == 1
    assert result["failed"] == 0
    assert result["blocked"] == 0
    assert result["skipped_source_action_cap"] == 1
    assert len(sell_calls) == 1
    assert result["items"][1]["skipped"] is True
    assert "source_action_cap_reached:pytest:sell:observe" in str(result["items"][1]["error"])


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


def test_autotrade_cockpit_exposes_delivery_surface(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade_id = _seed_trade(13, sold_price=None)
    _set_trade_window(trade_id, holding_days=2)

    old_limit = settings.auto_approve_portfolio_max_deployed_capital
    object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 500.0)

    try:
        with TestClient(create_app()) as client:
            response = client.get("/autotrade/cockpit")
    finally:
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_limit)

    assert response.status_code == 200
    payload = response.json()
    assert "ready" in payload
    assert "blocking_reasons" in payload
    assert "execution_readiness" in payload
    assert "operating_state" in payload
    assert "portfolio" in payload
    assert "autotrade" in payload
    assert "profit_cockpit" in payload
    assert payload["portfolio"]["capital_limit"] == 500.0
    assert "source_position_controls" in payload["autotrade"]
    assert "cluster_position_controls" in payload["autotrade"]


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


def test_source_leaderboard_tightens_when_live_execution_quality_degrades(
    isolated_reporting_sqlite: Path,
) -> None:
    trade_one = _seed_trade(31, sold_price=160.0)
    trade_two = _seed_trade(32, sold_price=155.0)
    _set_trade_window(trade_one, holding_days=1)
    _set_trade_window(trade_two, holding_days=1)

    with get_conn() as conn:
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-31",))
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-32",))
        conn.execute(
            "UPDATE trades SET updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), trade_one),
        )
        conn.execute(
            "UPDATE trades SET updated_at = ? WHERE id = ?",
            (datetime.now(timezone.utc).isoformat(), trade_two),
        )

    for idx in range(6):
        repo.create_execution_log(
            trade_id=trade_one if idx % 2 == 0 else trade_two,
            action="buy",
            provider="pytest",
            dry_run=False,
            request_payload={"idx": idx},
            response_payload={"error": "business ban"} if idx < 3 else {"error": "http 500"},
            success=False,
            error="business ban" if idx < 3 else "http 500",
        )

    report = repo.get_trade_performance_report()
    alpha = next(item for item in report["profit_cockpit"]["source_leaderboard_7d"] if item["source"] == "alpha")

    assert alpha["execution_live_sample_size"] == 6
    assert alpha["execution_live_failure_rate"] == 1.0
    assert alpha["execution_live_business_ban_count"] == 3
    assert alpha["execution_buy_state"] == "recovery"
    assert alpha["source_lane"] == "blocked"
    assert alpha["block_new_approvals"] is True
    assert alpha["strategy_mode"] == "tighten"
    assert alpha["intake_multiplier"] == 0.0


def test_source_leaderboard_moves_blocked_buy_source_into_observe_on_success_streak(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade_one = _seed_trade(41, sold_price=160.0)
    trade_two = _seed_trade(42, sold_price=155.0)
    _set_trade_window(trade_one, holding_days=1)
    _set_trade_window(trade_two, holding_days=1)

    with get_conn() as conn:
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-41",))
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-42",))

    execution_ids: list[int] = []
    for idx in range(4):
        execution_ids.append(
            repo.create_execution_log(
                trade_id=trade_one if idx % 2 == 0 else trade_two,
                action="buy",
                provider="pytest",
                dry_run=False,
                request_payload={"idx": idx},
                response_payload={"error": "business ban"},
                success=False,
                error="business ban",
            )
        )
    for idx in range(2):
        execution_ids.append(
            repo.create_execution_log(
                trade_id=trade_one if idx % 2 == 0 else trade_two,
                action="buy",
                provider="pytest",
                dry_run=False,
                request_payload={"idx": 100 + idx},
                response_payload={"ok": True},
                success=True,
                error="",
            )
        )

        with get_conn() as conn:
            base = datetime(2026, 3, 20, 10, tzinfo=timezone.utc)
            for index, execution_id in enumerate(execution_ids):
                conn.execute(
                    "UPDATE execution_logs SET created_at = ? WHERE id = ?",
                    ((base + timedelta(minutes=index)).isoformat(), execution_id),
                )

    fixed_now = datetime(2026, 3, 20, 12, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(repo, "datetime", _FixedDateTime)

    report = repo.get_trade_performance_report()
    alpha = next(item for item in report["profit_cockpit"]["source_leaderboard_7d"] if item["source"] == "alpha")

    assert alpha["execution_buy_state"] == "recovery"
    assert alpha["buy_positive_streak"] == 2
    assert alpha["source_lane"] == "observe"
    assert alpha["block_new_approvals"] is False
    assert 0.2 < alpha["intake_multiplier"] < 0.6


def test_source_leaderboard_reopens_in_observe_mode_after_live_buy_recovery_streak(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade_one = _seed_trade(41, sold_price=160.0)
    trade_two = _seed_trade(42, sold_price=158.0)
    _set_trade_window(trade_one, holding_days=1)
    _set_trade_window(trade_two, holding_days=1)

    with get_conn() as conn:
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-41",))
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-42",))

    log_ids: list[int] = []
    for idx in range(6):
        log_ids.append(
            repo.create_execution_log(
                trade_id=trade_one if idx % 2 == 0 else trade_two,
                action="buy",
                provider="pytest",
                dry_run=False,
                request_payload={"idx": idx},
                response_payload={"error": "business ban"} if idx < 3 else {"error": "http 500"},
                success=False,
                error="business ban" if idx < 3 else "http 500",
            )
        )
    for idx in range(2):
        log_ids.append(
            repo.create_execution_log(
                trade_id=trade_one if idx % 2 == 0 else trade_two,
                action="buy",
                provider="pytest",
                dry_run=False,
                request_payload={"idx": 100 + idx},
                response_payload={"ok": True},
                success=True,
                error="",
            )
        )

    base = datetime(2026, 3, 20, 12, tzinfo=timezone.utc)
    with get_conn() as conn:
        for idx, log_id in enumerate(log_ids):
            conn.execute(
                "UPDATE execution_logs SET created_at = ? WHERE id = ?",
                ((base.replace(minute=idx)).isoformat(), log_id),
            )

    fixed_now = datetime(2026, 3, 20, 13, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(repo, "datetime", _FixedDateTime)

    report = repo.get_trade_performance_report()
    alpha = next(item for item in report["profit_cockpit"]["source_leaderboard_7d"] if item["source"] == "alpha")

    assert alpha["execution_buy_state"] == "recovery"
    assert alpha["buy_positive_streak"] == 2
    assert alpha["source_lane"] == "observe"
    assert alpha["block_new_approvals"] is False
    assert alpha["source_recovery_progress"] > 0.6
    assert alpha["intake_multiplier"] > 0.2
    assert alpha["intake_multiplier"] < 0.6


def test_source_leaderboard_expands_after_recovery_and_profit_validation(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade_one = _seed_trade(51, sold_price=170.0)
    trade_two = _seed_trade(52, sold_price=168.0)
    _set_trade_window(trade_one, holding_days=1)
    _set_trade_window(trade_two, holding_days=1)

    with get_conn() as conn:
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-51",))
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-52",))

    log_ids: list[int] = []
    for idx in range(3):
        log_ids.append(
            repo.create_execution_log(
                trade_id=trade_one if idx % 2 == 0 else trade_two,
                action="buy",
                provider="pytest",
                dry_run=False,
                request_payload={"idx": idx},
                response_payload={"error": "http 500"},
                success=False,
                error="http 500",
            )
        )
    for idx in range(6):
        log_ids.append(
            repo.create_execution_log(
                trade_id=trade_one if idx % 2 == 0 else trade_two,
                action="buy",
                provider="pytest",
                dry_run=False,
                request_payload={"idx": 100 + idx},
                response_payload={"ok": True},
                success=True,
                error="",
            )
        )

    base = datetime(2026, 3, 20, 14, tzinfo=timezone.utc)
    with get_conn() as conn:
        for idx, log_id in enumerate(log_ids):
            conn.execute(
                "UPDATE execution_logs SET created_at = ? WHERE id = ?",
                ((base.replace(minute=idx)).isoformat(), log_id),
            )

    fixed_now = datetime(2026, 3, 20, 16, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(repo, "datetime", _FixedDateTime)

    report = repo.get_trade_performance_report()
    alpha = next(item for item in report["profit_cockpit"]["source_leaderboard_7d"] if item["source"] == "alpha")

    assert alpha["execution_buy_state"] == "normal"
    assert alpha["buy_positive_streak"] >= 3
    assert alpha["recovery_profit_validated"] is True
    assert alpha["source_lane"] == "expand"
    assert alpha["block_new_approvals"] is False
    assert alpha["intake_multiplier"] >= 1.0


def test_source_leaderboard_moves_list_action_into_observe_on_success_streak(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade_one = _seed_trade(61, sold_price=170.0)
    trade_two = _seed_trade(62, sold_price=168.0)
    _set_trade_window(trade_one, holding_days=1)
    _set_trade_window(trade_two, holding_days=1)

    with get_conn() as conn:
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-61",))
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-62",))

    log_ids: list[int] = []
    for idx in range(4):
        log_ids.append(
            repo.create_execution_log(
                trade_id=trade_one if idx % 2 == 0 else trade_two,
                action="list",
                provider="pytest",
                dry_run=False,
                request_payload={"idx": idx},
                response_payload={"error": "http 500"},
                success=False,
                error="http 500",
            )
        )
    for idx in range(2):
        log_ids.append(
            repo.create_execution_log(
                trade_id=trade_one if idx % 2 == 0 else trade_two,
                action="list",
                provider="pytest",
                dry_run=False,
                request_payload={"idx": 100 + idx},
                response_payload={"ok": True},
                success=True,
                error="",
            )
        )

    base = datetime(2026, 3, 20, 18, tzinfo=timezone.utc)
    with get_conn() as conn:
        for idx, log_id in enumerate(log_ids):
            conn.execute(
                "UPDATE execution_logs SET created_at = ? WHERE id = ?",
                ((base.replace(minute=idx)).isoformat(), log_id),
            )

    fixed_now = datetime(2026, 3, 20, 19, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(repo, "datetime", _FixedDateTime)

    report = repo.get_trade_performance_report()
    alpha = next(item for item in report["profit_cockpit"]["source_leaderboard_7d"] if item["source"] == "alpha")

    assert alpha["execution_list_state"] == "recovery"
    assert alpha["list_positive_streak"] == 2
    assert alpha["list_action_lane"] == "observe"
    assert alpha["allow_auto_list"] is True


def test_source_leaderboard_expands_sell_action_when_cashout_quality_is_strong(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade_one = _seed_trade(71, sold_price=170.0)
    trade_two = _seed_trade(72, sold_price=169.0)
    _set_trade_window(trade_one, holding_days=1)
    _set_trade_window(trade_two, holding_days=1)

    with get_conn() as conn:
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-71",))
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-72",))

    log_ids: list[int] = []
    for idx in range(3):
        log_ids.append(
            repo.create_execution_log(
                trade_id=trade_one if idx % 2 == 0 else trade_two,
                action="sell",
                provider="pytest",
                dry_run=False,
                request_payload={"requested_sold_price": 170.0},
                response_payload={"ok": True},
                success=True,
                error="",
            )
        )

    base = datetime(2026, 3, 20, 20, tzinfo=timezone.utc)
    with get_conn() as conn:
        for idx, log_id in enumerate(log_ids):
            conn.execute(
                "UPDATE execution_logs SET created_at = ? WHERE id = ?",
                ((base.replace(minute=idx)).isoformat(), log_id),
            )

    fixed_now = datetime(2026, 3, 20, 21, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(repo, "datetime", _FixedDateTime)

    report = repo.get_trade_performance_report()
    alpha = next(item for item in report["profit_cockpit"]["source_leaderboard_7d"] if item["source"] == "alpha")

    assert alpha["sell_positive_streak"] >= 3
    assert alpha["avg_holding_days"] <= 5.0
    assert alpha["cashout_quality_validated"] is True
    assert alpha["sell_action_lane"] == "expand"
    assert alpha["allow_auto_sell"] is True
    assert alpha["capital_multiplier"] >= 1.3


def test_source_leaderboard_keeps_sell_action_in_observe_when_cashout_is_slow(
    isolated_reporting_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trade_one = _seed_trade(73, sold_price=170.0)
    trade_two = _seed_trade(74, sold_price=169.0)
    _set_trade_window(trade_one, holding_days=9)
    _set_trade_window(trade_two, holding_days=8)

    with get_conn() as conn:
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-73",))
        conn.execute("UPDATE listings_raw SET source = 'alpha' WHERE listing_id = ?", ("report-listing-74",))

    log_ids: list[int] = []
    for idx in range(3):
        log_ids.append(
            repo.create_execution_log(
                trade_id=trade_one if idx % 2 == 0 else trade_two,
                action="sell",
                provider="pytest",
                dry_run=False,
                request_payload={"requested_sold_price": 170.0},
                response_payload={"ok": True},
                success=True,
                error="",
            )
        )

    base = datetime(2026, 3, 20, 22, tzinfo=timezone.utc)
    with get_conn() as conn:
        for idx, log_id in enumerate(log_ids):
            conn.execute(
                "UPDATE execution_logs SET created_at = ? WHERE id = ?",
                ((base.replace(minute=idx)).isoformat(), log_id),
            )

    fixed_now = datetime(2026, 3, 20, 23, tzinfo=timezone.utc)

    class _FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                return fixed_now.replace(tzinfo=None)
            return fixed_now.astimezone(tz)

    monkeypatch.setattr(repo, "datetime", _FixedDateTime)

    report = repo.get_trade_performance_report()
    alpha = next(item for item in report["profit_cockpit"]["source_leaderboard_7d"] if item["source"] == "alpha")

    assert alpha["sell_positive_streak"] >= 3
    assert alpha["avg_holding_days"] > 5.0
    assert alpha["cashout_quality_validated"] is False
    assert alpha["sell_action_lane"] == "observe"
    assert alpha["capital_multiplier"] <= 0.8
