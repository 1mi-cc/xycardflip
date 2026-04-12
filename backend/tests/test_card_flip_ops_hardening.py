from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import repositories as repo
from app.config import settings
from app.config import single_account_guardrail_status
from app.database import collect_database_diagnostics
from app.database import get_conn
from app.database import get_database_health_snapshot
from app.database import get_data_integrity_status
from app.database import init_db
from app.errors import BusyStateError
from app.main import create_app
from app.schemas import FeatureData
from app.schemas import ListingIn, ValuationOut
from app.services.automation import automation_service
from app.services.autotrade import auto_trade_service
from app.services.execution import execution_service
from app.services.execution_retry import execution_retry_service
from app.services.market_monitor import monitor_service
from app.services.operating_state import operating_state_service
from app.services.startup_diagnostics import startup_configuration_checks
import app.services.automation as automation_module
import app.routers.health as health_router_module


@pytest.fixture
def isolated_sqlite(tmp_path: Path):
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "card_flip_ops.db"))
    init_db()
    try:
        yield Path(settings.sqlite_path)
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def _seed_pending_opportunity(index: int = 1) -> int:
    listed_at = datetime(2026, 3, 6, tzinfo=timezone.utc)
    listing = ListingIn(
        source="pytest",
        listing_id=f"listing-{index}",
        seller_id=f"seller-{index}",
        title=f"pytest card #{index}",
        description="seed listing",
        list_price=100 + index,
        listed_at=listed_at,
        status="open",
        raw={"index": index},
    )
    listing_row_id, _ = repo.upsert_listing(listing)
    assert listing_row_id is not None

    valuation_id = repo.save_valuation(
        ValuationOut(
            listing_row_id=listing_row_id,
            expected_sale_price=168 + index,
            buy_limit=120 + index,
            suggested_list_price=176 + index,
            ci_low=150 + index,
            ci_high=182 + index,
            model_confidence=0.92,
            comparables_count=16,
            reasoning="pytest seed",
        )
    )
    return repo.upsert_opportunity(
        listing_row_id=listing_row_id,
        valuation_id=valuation_id,
        expected_profit=38.0,
        roi=0.32,
        score=88.0,
        status="pending_review",
        note="pytest_seed;risk_score=0;risk_level=low;reasons=none",
    )


def test_autotrade_run_once_busy_returns_conflict(isolated_sqlite: Path) -> None:
    acquired = auto_trade_service._run_lock.acquire(blocking=False)
    assert acquired is True
    try:
        with TestClient(create_app()) as client:
            response = client.post("/autotrade/run-once", params={"force": True})
        assert response.status_code == 409
        payload = response.json()
        assert payload["busy"] is True
        assert payload["service"] == "autotrade"
        assert payload["reason"] == "run_once_in_progress"
    finally:
        auto_trade_service._run_lock.release()


def test_monitor_run_once_route_returns_502_with_monitor_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom() -> dict[str, object]:
        raise RuntimeError("upstream xianyu failure")

    monkeypatch.setattr(monitor_service, "run_once", _boom)
    monkeypatch.setattr(
        monitor_service,
        "status",
        lambda: {
            "circuit_open": True,
            "circuit_reason": "proxy_exhausted",
            "last_error": "upstream xianyu failure",
        },
    )

    with TestClient(create_app()) as client:
        response = client.post("/monitor/run-once")

    assert response.status_code == 502
    payload = response.json()["detail"]
    assert payload["message"] == "monitor run failed"
    assert payload["error"] == "upstream xianyu failure"
    assert payload["circuit_open"] is True
    assert payload["circuit_reason"] == "proxy_exhausted"


def test_approve_opportunity_idempotent_creates_single_trade(isolated_sqlite: Path) -> None:
    opportunity_id = _seed_pending_opportunity()

    first = repo.approve_opportunity_idempotent(
        opportunity_id=opportunity_id,
        approved_buy_price=101.0,
        approved_by="pytest",
        note="first approval",
    )
    second = repo.approve_opportunity_idempotent(
        opportunity_id=opportunity_id,
        approved_buy_price=101.0,
        approved_by="pytest",
        note="second approval",
    )

    assert first["created"] is True
    assert first["idempotent"] is False
    assert second["created"] is False
    assert second["idempotent"] is True
    assert second["existing_trade_id"] == first["trade_id"]


def test_approve_opportunity_idempotent_concurrent_burst_creates_single_trade(
    isolated_sqlite: Path,
) -> None:
    opportunity_id = _seed_pending_opportunity(index=2)

    def _approve() -> dict[str, object]:
        return repo.approve_opportunity_idempotent(
            opportunity_id=opportunity_id,
            approved_buy_price=102.0,
            approved_by="pytest",
            note="burst approval",
        )

    with ThreadPoolExecutor(max_workers=10) as executor:
        results = list(executor.map(lambda _: _approve(), range(10)))

    assert sum(1 for item in results if item["created"]) == 1
    assert sum(1 for item in results if item["idempotent"]) == 9

    rows = repo.list_trades(limit=20)
    matching = [row for row in rows if int(row["opportunity_id"]) == opportunity_id]
    assert len(matching) == 1


def test_execution_retry_guard_blocks_parallel_entry_points(isolated_sqlite: Path) -> None:
    acquired = execution_service._retry_lock.acquire(blocking=False)
    assert acquired is True
    try:
        with pytest.raises(BusyStateError) as route_exc:
            execution_service.retry_failed(limit=1)
        assert route_exc.value.reason == "retry_failed_in_progress"

        with pytest.raises(BusyStateError) as service_exc:
            execution_retry_service.run_once(limit=1, service_force=True)
        assert service_exc.value.reason == "retry_failed_in_progress"

        guard = execution_retry_service.guard_status()
        assert guard["busy"] is False
        assert guard["last_busy_reason"] == "retry_failed_in_progress"
    finally:
        execution_service._retry_lock.release()


def test_automation_run_once_reports_partial_success(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(monitor_service, "run_once", lambda: {"processed": 3})
    monkeypatch.setattr(
        operating_state_service,
        "status",
        lambda: {
            "state": "normal",
            "reasons": ["healthy"],
            "recommendations": {
                "scan_limit_factor": 1.0,
                "autotrade_limit_factor": 1.0,
                "execution_retry_limit_factor": 1.0,
                "allow_autotrade": True,
                "allow_execution_retry": True,
                "require_manual_review": False,
            },
        },
    )

    async def fake_scan_open_listings(*, limit: int = 0):
        return {"processed": limit}

    def fake_autotrade_run_once(*args, **kwargs):
        raise BusyStateError(
            service="autotrade",
            reason="run_once_in_progress",
            message="autotrade run is already in progress",
        )

    def fake_execution_retry_run_once(*args, **kwargs):
        raise RuntimeError("retry stage failed")

    monkeypatch.setattr(automation_module, "scan_open_listings", fake_scan_open_listings)
    monkeypatch.setattr(auto_trade_service, "run_once", fake_autotrade_run_once)
    monkeypatch.setattr(execution_retry_service, "run_once", fake_execution_retry_run_once)

    result = automation_service.run_once(
        include_monitor=True,
        include_scan=True,
        include_autotrade=True,
        include_execution_retry=True,
        include_supabase_sync=False,
        force=True,
    )

    assert result["monitor"]["success"] is True
    assert result["scan"]["success"] is True
    assert result["autotrade"]["busy"] is True
    assert result["autotrade"]["status_code"] == 409
    assert result["execution_retry"]["success"] is False
    assert result["execution_retry"]["status_code"] == 500
    assert result["had_busy"] is True
    assert result["success"] is False


def test_automation_run_once_recovery_skips_risky_stages(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(monitor_service, "run_once", lambda: {"processed": 1})
    monkeypatch.setattr(
        operating_state_service,
        "status",
        lambda: {
            "state": "recovery",
            "reasons": ["monitor_circuit_open"],
            "recommendations": {
                "scan_limit_factor": 0.2,
                "autotrade_limit_factor": 0.2,
                "execution_retry_limit_factor": 0.2,
                "allow_autotrade": False,
                "allow_execution_retry": False,
                "require_manual_review": True,
            },
        },
    )

    async def fake_scan_open_listings(*, limit: int = 0):
        return {"processed": limit}

    called = {"autotrade": 0, "execution_retry": 0}

    def fake_autotrade_run_once(*args, **kwargs):
        called["autotrade"] += 1
        return {"approved": 1}

    def fake_execution_retry_run_once(*args, **kwargs):
        called["execution_retry"] += 1
        return {"retried": 1}

    monkeypatch.setattr(automation_module, "scan_open_listings", fake_scan_open_listings)
    monkeypatch.setattr(auto_trade_service, "run_once", fake_autotrade_run_once)
    monkeypatch.setattr(execution_retry_service, "run_once", fake_execution_retry_run_once)

    result = automation_service.run_once(
        include_monitor=True,
        include_scan=True,
        include_autotrade=True,
        include_execution_retry=True,
        include_supabase_sync=False,
        force=False,
        scan_limit=50,
    )

    assert result["operating_state"]["state"] == "recovery"
    assert result["applied_limits"]["scan"]["effective"] == 10
    assert result["autotrade"]["skipped"] is True
    assert result["autotrade"]["reason"] == "operating_state_recovery"
    assert result["execution_retry"]["skipped"] is True
    assert result["execution_retry"]["reason"] == "operating_state_recovery"
    assert called["autotrade"] == 0
    assert called["execution_retry"] == 0


def test_automation_run_once_cautious_scales_limits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(monitor_service, "run_once", lambda: {"processed": 1})
    monkeypatch.setattr(
        operating_state_service,
        "status",
        lambda: {
            "state": "cautious",
            "reasons": ["execution_health_cautious"],
            "recommendations": {
                "scan_limit_factor": 0.5,
                "autotrade_limit_factor": 0.5,
                "execution_retry_limit_factor": 0.5,
                "allow_autotrade": True,
                "allow_execution_retry": True,
                "require_manual_review": True,
            },
        },
    )

    captured: dict[str, int] = {}

    async def fake_scan_open_listings(*, limit: int = 0):
        captured["scan_limit"] = limit
        return {"processed": limit}

    def fake_autotrade_run_once(*args, **kwargs):
        captured["autotrade_limit"] = int(kwargs.get("limit") or 0)
        return {"approved": 0}

    def fake_execution_retry_run_once(*args, **kwargs):
        captured["execution_retry_limit"] = int(kwargs.get("limit") or 0)
        return {"retried": 0}

    monkeypatch.setattr(automation_module, "scan_open_listings", fake_scan_open_listings)
    monkeypatch.setattr(auto_trade_service, "run_once", fake_autotrade_run_once)
    monkeypatch.setattr(execution_retry_service, "run_once", fake_execution_retry_run_once)

    result = automation_service.run_once(
        include_monitor=True,
        include_scan=True,
        include_autotrade=True,
        include_execution_retry=True,
        include_supabase_sync=False,
        force=False,
        scan_limit=40,
        autotrade_limit=10,
        execution_retry_limit=12,
    )

    assert result["operating_state"]["state"] == "cautious"
    assert captured["scan_limit"] == 20
    assert captured["autotrade_limit"] == 5
    assert captured["execution_retry_limit"] == 6
    assert result["applied_limits"]["autotrade"]["effective"] == 5
    assert result["applied_limits"]["execution_retry"]["effective"] == 6


def test_init_db_creates_trade_unique_index_when_clean(isolated_sqlite: Path) -> None:
    init_db()
    status = get_data_integrity_status()
    assert status["ok"] is True
    assert status["trade_opportunity_unique_index"] is True
    assert status["has_duplicate_trade_opportunities"] is False


def test_init_db_reports_duplicate_trades_when_unique_index_skipped(isolated_sqlite: Path) -> None:
    opportunity_id = _seed_pending_opportunity(index=3)
    with get_conn() as conn:
        conn.execute("DROP INDEX IF EXISTS ux_trades_opportunity_id")

    repo.create_trade(
        opportunity_id=opportunity_id,
        approved_buy_price=103.0,
        target_sell_price=183.0,
        approved_by="pytest",
        note="dup 1",
    )
    repo.create_trade(
        opportunity_id=opportunity_id,
        approved_buy_price=103.0,
        target_sell_price=183.0,
        approved_by="pytest",
        note="dup 2",
    )

    init_db()
    status = get_data_integrity_status()
    assert status["ok"] is False
    assert status["trade_opportunity_unique_index"] is False
    assert status["has_duplicate_trade_opportunities"] is True
    assert status["duplicate_trade_opportunity_count"] >= 1


def test_persist_scan_batch_writes_consistent_records(isolated_sqlite: Path) -> None:
    listed_at = datetime(2026, 3, 7, tzinfo=timezone.utc)
    listing = ListingIn(
        source="pytest",
        listing_id="batch-listing-1",
        seller_id="batch-seller-1",
        title="batch card",
        description="batch seed",
        list_price=110,
        listed_at=listed_at,
        status="open",
        raw={"batch": True},
    )
    listing_row_id, _ = repo.upsert_listing(listing)
    assert listing_row_id is not None

    feature = FeatureData(
        card_name="batch card",
        rarity="rare",
        edition="1st",
        card_condition="nm",
        confidence=0.88,
    )
    valuation = ValuationOut(
        listing_row_id=listing_row_id,
        expected_sale_price=176,
        buy_limit=132,
        suggested_list_price=182,
        ci_low=168,
        ci_high=188,
        model_confidence=0.9,
        comparables_count=12,
        reasoning="batch persist test",
    )

    result = repo.persist_scan_batch(
        [
            {
                "listing_row_id": listing_row_id,
                "feature": feature,
                "extracted_by": "pytest_batch",
                "valuation": valuation,
                "expected_profit": 42.0,
                "roi": 0.31,
                "score": 86.0,
                "status": "pending_review",
                "note": "batch_test",
            }
        ]
    )

    assert result["written"] == 1
    assert repo.get_features("listing", listing_row_id) is not None
    assert repo.get_latest_valuation_for_listing(listing_row_id) is not None
    opportunity = repo.get_opportunity_by_listing_row_id(listing_row_id)
    assert opportunity is not None
    assert str(opportunity["status"]) == "pending_review"

    diagnostics = collect_database_diagnostics(include_query_plans=False)
    batch_writes = diagnostics["batch_writes"]
    assert batch_writes["last_batch_size"] == 1
    assert batch_writes["last_batch_error"] == ""


def test_database_diagnostics_expose_runtime_and_target_indexes(isolated_sqlite: Path) -> None:
    opportunity_id = _seed_pending_opportunity(index=4)
    trade = repo.approve_opportunity_idempotent(
        opportunity_id=opportunity_id,
        approved_buy_price=104.0,
        approved_by="pytest",
        note="diag seed",
    )
    repo.create_execution_log(
        trade_id=int(trade["trade_id"]),
        action="buy",
        provider="pytest",
        dry_run=True,
        request_payload={"trade_id": trade["trade_id"]},
        response_payload={"ok": True},
        success=True,
    )

    diagnostics = collect_database_diagnostics()
    assert diagnostics["runtime"]["journal_mode"] == "WAL"
    assert diagnostics["runtime"]["synchronous"] == "NORMAL"
    assert diagnostics["runtime"]["busy_timeout_ms"] == settings.sqlite_busy_timeout_ms
    assert diagnostics["runtime"]["foreign_keys"] is True

    listings_indexes = {item["name"] for item in diagnostics["tables"]["listings_raw"]["indexes"]}
    opportunities_indexes = {item["name"] for item in diagnostics["tables"]["opportunities"]["indexes"]}
    trades_indexes = {item["name"] for item in diagnostics["tables"]["trades"]["indexes"]}
    valuation_indexes = {item["name"] for item in diagnostics["tables"]["valuation_records"]["indexes"]}
    execution_indexes = {item["name"] for item in diagnostics["tables"]["execution_logs"]["indexes"]}

    assert "idx_listings_status_listed_at" in listings_indexes
    assert "idx_listings_source_seller_status_price" in listings_indexes
    assert "idx_opportunities_status_score" in opportunities_indexes
    assert "idx_trades_status_updated" in trades_indexes
    assert "idx_valuation_records_listing_row_id_id" in valuation_indexes
    assert "idx_execution_logs_trade_action_id" in execution_indexes


def test_database_diagnostics_query_plans_use_targeted_indexes(isolated_sqlite: Path) -> None:
    opportunity_id = _seed_pending_opportunity(index=5)
    trade = repo.approve_opportunity_idempotent(
        opportunity_id=opportunity_id,
        approved_buy_price=105.0,
        approved_by="pytest",
        note="diag plan seed",
    )
    repo.create_execution_log(
        trade_id=int(trade["trade_id"]),
        action="buy",
        provider="pytest",
        dry_run=True,
        request_payload={"trade_id": trade["trade_id"]},
        response_payload={"ok": True},
        success=True,
    )

    diagnostics = collect_database_diagnostics()
    query_plans = diagnostics["query_plans"]

    def _plan_text(name: str) -> str:
        return " | ".join(str(row[-1]) for row in query_plans[name])

    open_plan = _plan_text("get_open_listings")
    assert (
        "idx_listings_status_listed_at" in open_plan
        or "idx_listings_normalized_key_status" in open_plan
    )
    assert "USE TEMP B-TREE" not in open_plan

    opportunity_plan = _plan_text("list_opportunities")
    assert "idx_opportunities_status_score" in opportunity_plan
    assert "USE TEMP B-TREE" not in opportunity_plan

    trade_plan = _plan_text("list_trades")
    assert "idx_trades_status_updated" in trade_plan
    assert "USE TEMP B-TREE" not in trade_plan

    valuation_plan = _plan_text("latest_valuation")
    assert "idx_valuation_records_listing_row_id_id" in valuation_plan
    assert "SCAN valuation_records" not in valuation_plan

    execution_plan = _plan_text("latest_execution_log")
    assert "idx_execution_logs_trade_action_id" in execution_plan


def test_health_route_exposes_integrity_and_guard_status(isolated_sqlite: Path) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert "database" in payload
    assert "gemini_runtime" in payload
    assert "data_integrity" in payload
    assert "operating_state" in payload
    assert "automation_guards" in payload
    assert "startup_checks" in payload
    assert "automation" in payload["automation_guards"]
    assert "execution_retry_replay" in payload["automation_guards"]
    assert "batch_writes" in payload["database"]
    assert "startup_services" not in payload
    assert "event_handlers" not in payload
    assert "runtime" not in payload["network_policy"]
    assert "proxy_pool_api" not in payload["network_policy"]
    assert "uptime_kuma_url" not in payload["monitoring"]


def test_operating_state_escalates_on_live_buy_failure_pattern(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        monitor_service,
        "status",
        lambda: {
            "circuit_open": False,
            "health": {
                "samples": 10,
                "success_rate": 1.0,
                "guard_triggered": False,
            },
        },
    )
    monkeypatch.setattr(auto_trade_service, "status", lambda: {"running": True})
    monkeypatch.setattr(
        execution_retry_service,
        "status",
        lambda: {"running": True, "last_error": ""},
    )

    def _execution_summary(*, dry_run=None, **kwargs):
        if dry_run is False:
            return {
                "sample_size": 8,
                "success_count": 6,
                "failure_count": 2,
                "success_rate": 0.75,
                "failure_rate": 0.25,
                "business_ban_count": 0,
                "last_failure_at": "2026-03-01T00:00:00+00:00",
                "by_action": {
                    "buy": {
                        "sample_size": 8,
                        "success_count": 2,
                        "failure_count": 6,
                        "success_rate": 0.25,
                        "failure_rate": 0.75,
                        "business_ban_count": 0,
                        "last_failure_at": "2026-03-01T00:00:00+00:00",
                    }
                },
            }
        return {
            "sample_size": 12,
            "success_count": 10,
            "failure_count": 2,
            "success_rate": 0.8333,
            "failure_rate": 0.1667,
            "business_ban_count": 0,
            "last_failure_at": "2026-03-01T00:00:00+00:00",
            "by_action": {},
        }

    monkeypatch.setattr(repo, "get_execution_log_summary", _execution_summary)

    status = operating_state_service.status()

    assert status["state"] == "recovery"
    assert any(str(reason).startswith("execution_action_recovery:buy") for reason in status["reasons"])
    assert status["signals"]["execution_by_action"]["buy"]["failure_rate"] == 0.75


def test_startup_checks_warn_when_gemini_pool_path_missing(
    isolated_sqlite: Path,
) -> None:
    old_source = settings.gemini_key_source_path
    old_local = settings.gemini_api_key
    object.__setattr__(settings, "gemini_key_source_path", str(isolated_sqlite.parent / "missing-pool"))
    object.__setattr__(settings, "gemini_api_key", "")
    try:
        checks = startup_configuration_checks()
    finally:
        object.__setattr__(settings, "gemini_key_source_path", old_source)
        object.__setattr__(settings, "gemini_api_key", old_local)

    codes = {item["code"] for item in checks["items"]}
    assert "gemini_external_source_missing" in codes


def test_startup_checks_warn_when_single_account_guardrails_drift(
    isolated_sqlite: Path,
) -> None:
    old_single_account_mode = settings.single_account_mode
    old_strategy_profile = settings.strategy_profile
    old_monitor_pages = settings.monitor_pages
    try:
        object.__setattr__(settings, "single_account_mode", True)
        object.__setattr__(settings, "strategy_profile", "balanced")
        object.__setattr__(settings, "monitor_pages", 2)
        checks = startup_configuration_checks()
    finally:
        object.__setattr__(settings, "single_account_mode", old_single_account_mode)
        object.__setattr__(settings, "strategy_profile", old_strategy_profile)
        object.__setattr__(settings, "monitor_pages", old_monitor_pages)

    codes = {item["code"] for item in checks["items"]}
    assert "single_account_guardrails_drift" in codes


def test_single_account_guardrails_align_with_defensive_local_profile(
    isolated_sqlite: Path,
) -> None:
    old_single_account_mode = settings.single_account_mode
    old_strategy_profile = settings.strategy_profile
    old_monitor_pages = settings.monitor_pages
    old_day_delay_min = settings.monitor_day_delay_min
    old_peak_delay_min = settings.monitor_peak_delay_min
    old_night_delay_min = settings.monitor_night_delay_min
    old_rest_probability = settings.monitor_long_rest_probability
    old_monitor_min_delay = settings.monitor_min_delay_sec
    old_monitor_max_delay = settings.monitor_max_delay_sec
    old_monitor_circuit_errors = settings.monitor_circuit_max_errors
    old_monitor_403_threshold = settings.monitor_circuit_403_threshold
    old_monitor_cooldown = settings.monitor_circuit_cooldown_sec
    old_auto_start_monitor = settings.auto_start_monitor
    old_auto_start_autotrade = settings.auto_start_autotrade
    old_auto_start_retry = settings.auto_start_execution_retry
    old_default_monitor = settings.automation_default_include_monitor
    old_default_scan = settings.automation_default_include_scan
    old_default_autotrade = settings.automation_default_include_autotrade
    old_default_retry = settings.automation_default_include_execution_retry
    old_provider = settings.execution_provider
    old_live = settings.execution_live_enabled
    old_proxy_pool = settings.monitor_use_proxy_pool
    old_force_proxy_url = settings.network_force_proxy_url
    old_rotate_proxy = settings.execution_auto_rotate_proxy_on_ban
    old_scan_limit = settings.automation_default_scan_limit
    old_portfolio_cap = settings.auto_approve_portfolio_max_deployed_capital
    old_source_share = settings.auto_approve_max_source_capital_share
    old_cluster_batch = settings.auto_approve_max_cluster_batch_share
    old_cluster_capital = settings.auto_approve_max_cluster_capital_share
    try:
        object.__setattr__(settings, "single_account_mode", True)
        object.__setattr__(settings, "strategy_profile", "conservative")
        object.__setattr__(settings, "monitor_pages", 1)
        object.__setattr__(settings, "monitor_day_delay_min", 20.0)
        object.__setattr__(settings, "monitor_peak_delay_min", 12.0)
        object.__setattr__(settings, "monitor_night_delay_min", 35.0)
        object.__setattr__(settings, "monitor_long_rest_probability", 0.12)
        object.__setattr__(settings, "monitor_min_delay_sec", 3.0)
        object.__setattr__(settings, "monitor_max_delay_sec", 8.0)
        object.__setattr__(settings, "monitor_circuit_max_errors", 2)
        object.__setattr__(settings, "monitor_circuit_403_threshold", 1)
        object.__setattr__(settings, "monitor_circuit_cooldown_sec", 1800.0)
        object.__setattr__(settings, "auto_start_monitor", False)
        object.__setattr__(settings, "auto_start_autotrade", False)
        object.__setattr__(settings, "auto_start_execution_retry", False)
        object.__setattr__(settings, "automation_default_include_monitor", False)
        object.__setattr__(settings, "automation_default_include_scan", True)
        object.__setattr__(settings, "automation_default_include_autotrade", False)
        object.__setattr__(settings, "automation_default_include_execution_retry", False)
        object.__setattr__(settings, "execution_provider", "mock")
        object.__setattr__(settings, "execution_live_enabled", False)
        object.__setattr__(settings, "monitor_use_proxy_pool", False)
        object.__setattr__(settings, "network_force_proxy_url", "")
        object.__setattr__(settings, "execution_auto_rotate_proxy_on_ban", False)
        object.__setattr__(settings, "automation_default_scan_limit", 40)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 500.0)
        object.__setattr__(settings, "auto_approve_max_source_capital_share", 0.35)
        object.__setattr__(settings, "auto_approve_max_cluster_batch_share", 0.25)
        object.__setattr__(settings, "auto_approve_max_cluster_capital_share", 0.25)

        status = single_account_guardrail_status()
    finally:
        object.__setattr__(settings, "single_account_mode", old_single_account_mode)
        object.__setattr__(settings, "strategy_profile", old_strategy_profile)
        object.__setattr__(settings, "monitor_pages", old_monitor_pages)
        object.__setattr__(settings, "monitor_day_delay_min", old_day_delay_min)
        object.__setattr__(settings, "monitor_peak_delay_min", old_peak_delay_min)
        object.__setattr__(settings, "monitor_night_delay_min", old_night_delay_min)
        object.__setattr__(settings, "monitor_long_rest_probability", old_rest_probability)
        object.__setattr__(settings, "monitor_min_delay_sec", old_monitor_min_delay)
        object.__setattr__(settings, "monitor_max_delay_sec", old_monitor_max_delay)
        object.__setattr__(settings, "monitor_circuit_max_errors", old_monitor_circuit_errors)
        object.__setattr__(settings, "monitor_circuit_403_threshold", old_monitor_403_threshold)
        object.__setattr__(settings, "monitor_circuit_cooldown_sec", old_monitor_cooldown)
        object.__setattr__(settings, "auto_start_monitor", old_auto_start_monitor)
        object.__setattr__(settings, "auto_start_autotrade", old_auto_start_autotrade)
        object.__setattr__(settings, "auto_start_execution_retry", old_auto_start_retry)
        object.__setattr__(settings, "automation_default_include_monitor", old_default_monitor)
        object.__setattr__(settings, "automation_default_include_scan", old_default_scan)
        object.__setattr__(settings, "automation_default_include_autotrade", old_default_autotrade)
        object.__setattr__(settings, "automation_default_include_execution_retry", old_default_retry)
        object.__setattr__(settings, "execution_provider", old_provider)
        object.__setattr__(settings, "execution_live_enabled", old_live)
        object.__setattr__(settings, "monitor_use_proxy_pool", old_proxy_pool)
        object.__setattr__(settings, "network_force_proxy_url", old_force_proxy_url)
        object.__setattr__(settings, "execution_auto_rotate_proxy_on_ban", old_rotate_proxy)
        object.__setattr__(settings, "automation_default_scan_limit", old_scan_limit)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_cap)
        object.__setattr__(settings, "auto_approve_max_source_capital_share", old_source_share)
        object.__setattr__(settings, "auto_approve_max_cluster_batch_share", old_cluster_batch)
        object.__setattr__(settings, "auto_approve_max_cluster_capital_share", old_cluster_capital)

    assert status["enabled"] is True
    assert status["aligned"] is True
    assert status["failing_codes"] == []


def test_database_health_snapshot_handles_unopenable_path(tmp_path: Path) -> None:
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path))
    try:
        snapshot = get_database_health_snapshot()
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)

    assert snapshot["available"] is False
    assert "database_open_failed" in snapshot["degraded_reasons"]
    assert snapshot["batch_writes"]["last_batch_size"] >= 0


def test_health_ready_route_reports_ready_and_degraded(
    isolated_sqlite: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health/ready")
    assert response.status_code == 200
    payload = response.json()
    assert payload["ready"] is True
    assert payload["reasons"] == []

    monkeypatch.setattr(
        health_router_module,
        "get_database_health_snapshot",
        lambda: {"journal_mode": "DELETE", "degraded_reasons": ["journal_mode:delete"]},
    )
    monkeypatch.setattr(
        health_router_module,
        "get_data_integrity_status",
        lambda: {"ok": True, "message": "ok"},
    )
    monkeypatch.setattr(
        health_router_module.operating_state_service,
        "status",
        lambda: {"state": "recovery", "reasons": ["manual"]},
    )

    with TestClient(create_app()) as client:
        degraded = client.get("/health/ready")
    assert degraded.status_code == 503
    degraded_payload = degraded.json()
    assert degraded_payload["ready"] is False
    assert "database:journal_mode:delete" in degraded_payload["reasons"]
    assert "operating_state:recovery" in degraded_payload["reasons"]


def test_operating_state_ignores_dry_run_execution_failures_for_live_degrade(
    isolated_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opportunity_id = _seed_pending_opportunity(index=6)
    trade = repo.approve_opportunity_idempotent(
        opportunity_id=opportunity_id,
        approved_buy_price=106.0,
        approved_by="pytest",
        note="operating state seed",
    )
    trade_id = int(trade["trade_id"])

    for idx in range(6):
        repo.create_execution_log(
            trade_id=trade_id,
            action="buy",
            provider="pytest",
            dry_run=True,
            request_payload={"idx": idx},
            response_payload={"error": "dry run failed"},
            success=False,
            error="dry_run_failure",
        )

    monkeypatch.setattr(
        health_router_module.monitor_service,
        "status",
        lambda: {
            "circuit_open": False,
            "health": {
                "samples": 10,
                "success_rate": 1.0,
                "guard_triggered": False,
            },
        },
    )
    monkeypatch.setattr(
        health_router_module.auto_trade_service,
        "status",
        lambda: {"running": False},
    )
    monkeypatch.setattr(
        health_router_module.execution_retry_service,
        "status",
        lambda: {"running": False, "last_error": ""},
    )

    status = health_router_module.operating_state_service.status()

    assert status["state"] == "normal"
    assert status["signals"]["execution_signal_scope"] == "live_only"
    assert status["signals"]["execution_all_sample_size"] >= 6
    assert status["signals"]["execution_live_sample_size"] == 0
