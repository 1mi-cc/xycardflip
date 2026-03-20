from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import repositories as repo
from app.config import settings
from app.database import get_conn
from app.database import get_data_integrity_status
from app.database import init_db
from app.errors import BusyStateError
from app.main import create_app
from app.schemas import ListingIn, ValuationOut
from app.services.automation import automation_service
from app.services.autotrade import auto_trade_service
from app.services.execution import execution_service
from app.services.execution_retry import execution_retry_service
from app.services.market_monitor import monitor_service
from app.services.operating_state import operating_state_service
import app.services.automation as automation_module


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


def test_health_route_exposes_integrity_and_guard_status(isolated_sqlite: Path) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert "data_integrity" in payload
    assert "operating_state" in payload
    assert "automation_guards" in payload
    assert "automation" in payload["automation_guards"]
    assert "execution_retry_replay" in payload["automation_guards"]


def test_monitor_status_includes_virtual_goods_channels() -> None:
    old_include = settings.monitor_include_virtual_goods_channels
    old_keywords = settings.monitor_keywords
    old_channels = settings.monitor_virtual_goods_channels
    try:
        object.__setattr__(settings, "monitor_include_virtual_goods_channels", True)
        object.__setattr__(settings, "monitor_keywords", ("咸鱼之王功法",))
        object.__setattr__(settings, "monitor_virtual_goods_channels", ("拼多多特价", "京东秒杀"))
        status = monitor_service.status()
        assert "拼多多特价" in status["keywords"]
        assert "京东秒杀" in status["keywords"]
        assert status["channel_keywords"] == ["拼多多特价", "京东秒杀"]
    finally:
        object.__setattr__(settings, "monitor_include_virtual_goods_channels", old_include)
        object.__setattr__(settings, "monitor_keywords", old_keywords)
        object.__setattr__(settings, "monitor_virtual_goods_channels", old_channels)


def test_autotrade_can_auto_list_discount_and_auto_sell(
    isolated_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opportunity_id = _seed_pending_opportunity(index=4)
    calls: dict[str, list[dict[str, object]]] = {"buy": [], "list": [], "sell": []}

    def fake_buy(*, trade_id: int, dry_run: bool = True, force: bool = False, confirm_token: str | None = None):
        calls["buy"].append({"trade_id": trade_id, "dry_run": dry_run})
        return {"success": True}

    def fake_list(
        *,
        trade_id: int,
        dry_run: bool = True,
        force: bool = False,
        confirm_token: str | None = None,
        listing_url: str = "",
        note: str = "",
        update_trade_state: bool = True,
    ):
        calls["list"].append({"trade_id": trade_id, "dry_run": dry_run, "note": note})
        return {"success": True}

    def fake_sell(
        *,
        trade_id: int,
        dry_run: bool = True,
        force: bool = False,
        confirm_token: str | None = None,
        sold_price: float | None = None,
        note: str = "",
        update_trade_state: bool = True,
    ):
        calls["sell"].append({"trade_id": trade_id, "dry_run": dry_run, "sold_price": sold_price, "note": note})
        return {"success": True}

    monkeypatch.setattr(execution_service, "execute_buy", fake_buy)
    monkeypatch.setattr(execution_service, "execute_list", fake_list)
    monkeypatch.setattr(execution_service, "execute_sell", fake_sell)
    monkeypatch.setattr("app.services.autotrade.random.uniform", lambda a, b: 2.0)

    old_state = auto_trade_service.status()
    auto_trade_service.update_config(
        batch_size=1,
        min_score=50,
        min_roi=0.01,
        require_risk_score=False,
        auto_execute_buy_on_approve=True,
        auto_execute_buy_dry_run=True,
        auto_execute_list_on_buy_success=True,
        auto_execute_list_dry_run=True,
        auto_execute_list_discount_min_pct=1.0,
        auto_execute_list_discount_max_pct=3.0,
        auto_execute_sell_on_list_success=True,
        auto_execute_sell_dry_run=True,
        auto_execute_sell_price_multiplier=1.0,
    )
    try:
        result = auto_trade_service.run_once(force=True, limit=1)
    finally:
        auto_trade_service.update_config(
            batch_size=int(old_state["batch_size"]),
            min_score=float(old_state["min_score"]),
            min_roi=float(old_state["min_roi"]),
            require_risk_score=bool(old_state["require_risk_score"]),
            auto_execute_buy_on_approve=bool(old_state["auto_execute_buy_on_approve"]),
            auto_execute_buy_dry_run=bool(old_state["auto_execute_buy_dry_run"]),
            auto_execute_list_on_buy_success=bool(old_state["auto_execute_list_on_buy_success"]),
            auto_execute_list_dry_run=bool(old_state["auto_execute_list_dry_run"]),
            auto_execute_list_discount_min_pct=float(old_state.get("auto_execute_list_discount_min_pct", 1.0)),
            auto_execute_list_discount_max_pct=float(old_state.get("auto_execute_list_discount_max_pct", 3.0)),
            auto_execute_sell_on_list_success=bool(old_state.get("auto_execute_sell_on_list_success", False)),
            auto_execute_sell_dry_run=bool(old_state.get("auto_execute_sell_dry_run", True)),
            auto_execute_sell_price_multiplier=float(old_state.get("auto_execute_sell_price_multiplier", 1.0)),
        )

    assert result["approved"] == 1
    assert result["buy_exec_succeeded"] == 1
    assert result["list_exec_succeeded"] == 1
    assert result["sell_exec_succeeded"] == 1
    assert len(calls["buy"]) == 1
    assert len(calls["list"]) == 1
    assert len(calls["sell"]) == 1

    trades = repo.list_trades(limit=10)
    trade = next(row for row in trades if int(row["opportunity_id"]) == opportunity_id)
    assert float(trade["target_sell_price"]) == pytest.approx(176.4, rel=0, abs=1e-6)
    assert float(calls["sell"][0]["sold_price"]) == pytest.approx(176.4, rel=0, abs=1e-6)
