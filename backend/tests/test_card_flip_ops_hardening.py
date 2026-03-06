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
    assert "automation_guards" in payload
    assert "automation" in payload["automation_guards"]
    assert "execution_retry_replay" in payload["automation_guards"]
