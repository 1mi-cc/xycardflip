from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import init_db
from app.main import create_app
from app.services.autotrade import auto_trade_service
import app.services.autotrade as autotrade_module


@pytest.fixture
def isolated_autotrade_tuning_sqlite(tmp_path: Path):
    old_sqlite_path = settings.sqlite_path
    old_snapshot = auto_trade_service.tuning_snapshot()
    old_policy = auto_trade_service.tuning_policy()
    old_max_consecutive_losses = auto_trade_service._max_consecutive_losses
    old_daily_loss_limit = auto_trade_service._daily_loss_limit
    old_loss_recovery_enabled = auto_trade_service._loss_recovery_enabled
    old_loss_recovery_cooldown_hours = auto_trade_service._loss_recovery_cooldown_hours
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "autotrade_tuning.db"))
    init_db()
    auto_trade_service.update_config(
        min_score=60.0,
        min_roi=0.18,
        max_risk_score=40.0,
        require_risk_score=True,
        max_consecutive_losses=3,
        daily_loss_limit=100.0,
        loss_recovery_enabled=True,
        loss_recovery_cooldown_hours=12,
        tuning_auto_apply_enabled=False,
        tuning_cooldown_hours=24,
        tuning_min_closed_batches=2,
        tuning_latest_min_sold_count=5,
        tuning_previous_min_sold_count=3,
    )
    try:
        yield Path(settings.sqlite_path)
    finally:
        auto_trade_service.update_config(
            min_score=old_snapshot["min_score"],
            min_roi=old_snapshot["min_roi"],
            max_risk_score=old_snapshot["max_risk_score"],
            require_risk_score=old_snapshot["require_risk_score"],
            max_consecutive_losses=old_max_consecutive_losses,
            daily_loss_limit=old_daily_loss_limit,
            loss_recovery_enabled=old_loss_recovery_enabled,
            loss_recovery_cooldown_hours=old_loss_recovery_cooldown_hours,
            tuning_auto_apply_enabled=old_policy["auto_apply_enabled"],
            tuning_cooldown_hours=old_policy["cooldown_hours"],
            tuning_min_closed_batches=old_policy["min_closed_batches"],
            tuning_latest_min_sold_count=old_policy["latest_min_sold_count"],
            tuning_previous_min_sold_count=old_policy["previous_min_sold_count"],
        )
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_apply_tuning_creates_history_event(isolated_autotrade_tuning_sqlite: Path) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/autotrade/tuning/apply",
            json={
                "source": "validation_auto_tune",
                "applied_by": "pytest_operator",
                "note": "tighten after weak batch",
                "min_score": 66,
                "min_roi": 0.20,
                "max_risk_score": 34,
                "require_risk_score": True,
            },
        )

        assert response.status_code == 200
        payload = response.json()
        assert payload["status"]["min_score"] == 66
        assert payload["status"]["min_roi"] == 0.20
        assert payload["status"]["max_risk_score"] == 34
        assert payload["event"]["source"] == "validation_auto_tune"
        assert payload["event"]["applied_by"] == "pytest_operator"
        assert payload["event"]["previous_config"]["min_score"] == 60.0
        assert payload["event"]["next_config"]["min_score"] == 66.0

        history = client.get("/autotrade/tuning-history", params={"limit": 10})
        assert history.status_code == 200
        items = history.json()["items"]
        assert len(items) == 1
        assert items[0]["delta"]["min_score"] == 6.0
        assert items[0]["rollback_of_event_id"] is None


def test_rollback_tuning_event_restores_previous_thresholds(
    isolated_autotrade_tuning_sqlite: Path,
) -> None:
    with TestClient(create_app()) as client:
        applied = client.post(
            "/autotrade/tuning/apply",
            json={
                "source": "validation_auto_tune",
                "applied_by": "pytest_operator",
                "note": "widen funnel",
                "min_score": 54,
                "min_roi": 0.15,
                "max_risk_score": 44,
                "require_risk_score": False,
            },
        )
        assert applied.status_code == 200
        event_id = int(applied.json()["event"]["id"])

        rollback = client.post(
            f"/autotrade/tuning-history/{event_id}/rollback",
            json={
                "source": "validation_rollback",
                "applied_by": "pytest_operator",
                "note": "restore previous gate",
            },
        )
        assert rollback.status_code == 200
        payload = rollback.json()
        assert payload["status"]["min_score"] == 60.0
        assert payload["status"]["min_roi"] == 0.18
        assert payload["status"]["max_risk_score"] == 40.0
        assert payload["status"]["require_risk_score"] is True
        assert payload["event"]["rollback_of_event_id"] == event_id
        assert payload["event"]["next_config"]["min_score"] == 60.0

        history = client.get("/autotrade/tuning-history", params={"limit": 10})
        assert history.status_code == 200
        items = history.json()["items"]
        assert len(items) == 2
        assert items[0]["rollback_of_event_id"] == event_id
        assert items[1]["id"] == event_id


def test_maybe_auto_apply_tuning_applies_when_guardrails_pass(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        tuning_auto_apply_enabled=True,
        tuning_cooldown_hours=0,
        tuning_min_closed_batches=2,
        tuning_latest_min_sold_count=5,
        tuning_previous_min_sold_count=3,
    )

    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "forward_validation": {
                "active_batch": None,
                "recent_batches": [
                    {
                        "id": 11,
                        "name": "batch-11",
                        "status": "closed",
                        "sold_count": 6,
                        "profit_hit_rate": 0.72,
                        "avg_realized_roi": 0.14,
                        "avg_holding_days": 4.0,
                        "realized_net_profit": 120.0,
                    },
                    {
                        "id": 10,
                        "name": "batch-10",
                        "status": "closed",
                        "sold_count": 4,
                        "profit_hit_rate": 0.68,
                        "avg_realized_roi": 0.11,
                        "avg_holding_days": 5.0,
                        "realized_net_profit": 88.0,
                    },
                ],
            },
        },
    )

    result = auto_trade_service.maybe_auto_apply_tuning(
        trigger_source="forward_validation_close:11",
        applied_by="pytest_autotune",
    )

    assert result["applied"] is True
    assert result["status"]["min_score"] == 56.0
    assert result["status"]["min_roi"] == 0.165
    assert result["status"]["max_risk_score"] == 44.0
    assert result["event"]["source"] == "forward_validation_close:11"


def test_maybe_auto_apply_tuning_blocks_when_cooldown_active(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        tuning_auto_apply_enabled=True,
        tuning_cooldown_hours=24,
        tuning_min_closed_batches=2,
        tuning_latest_min_sold_count=5,
        tuning_previous_min_sold_count=3,
    )

    auto_trade_service.apply_tuning(
        source="manual_tune",
        applied_by="pytest_operator",
        note="seed cooldown",
        min_score=58.0,
        min_roi=0.17,
        max_risk_score=42.0,
        require_risk_score=True,
    )

    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "forward_validation": {
                "active_batch": None,
                "recent_batches": [
                    {
                        "id": 21,
                        "name": "batch-21",
                        "status": "closed",
                        "sold_count": 6,
                        "profit_hit_rate": 0.72,
                        "avg_realized_roi": 0.14,
                        "avg_holding_days": 4.0,
                        "realized_net_profit": 120.0,
                    },
                    {
                        "id": 20,
                        "name": "batch-20",
                        "status": "closed",
                        "sold_count": 4,
                        "profit_hit_rate": 0.68,
                        "avg_realized_roi": 0.11,
                        "avg_holding_days": 5.0,
                        "realized_net_profit": 88.0,
                    },
                ],
            },
        },
    )

    result = auto_trade_service.maybe_auto_apply_tuning(
        trigger_source="forward_validation_close:21",
        applied_by="pytest_autotune",
    )

    assert result["applied"] is False
    assert result["reason"] == "guard_blocked"
    assert any("Cooldown active" in reason for reason in result["evaluation"]["guard"]["reasons"])


def test_tuning_activity_and_daily_report_capture_blocked_and_applied_events(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        tuning_auto_apply_enabled=False,
        tuning_cooldown_hours=0,
        tuning_min_closed_batches=2,
        tuning_latest_min_sold_count=5,
        tuning_previous_min_sold_count=3,
    )

    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "forward_validation": {
                "active_batch": None,
                "recent_batches": [
                    {
                        "id": 31,
                        "name": "batch-31",
                        "status": "closed",
                        "sold_count": 6,
                        "profit_hit_rate": 0.72,
                        "avg_realized_roi": 0.14,
                        "avg_holding_days": 4.0,
                        "realized_net_profit": 120.0,
                    },
                    {
                        "id": 30,
                        "name": "batch-30",
                        "status": "closed",
                        "sold_count": 4,
                        "profit_hit_rate": 0.68,
                        "avg_realized_roi": 0.11,
                        "avg_holding_days": 5.0,
                        "realized_net_profit": 88.0,
                    },
                ],
            },
        },
    )

    disabled = auto_trade_service.maybe_auto_apply_tuning(
        trigger_source="forward_validation_close:31",
        applied_by="pytest_autotune",
    )
    assert disabled["applied"] is False
    assert disabled["reason"] == "auto_apply_disabled"

    auto_trade_service.update_config(tuning_auto_apply_enabled=True, tuning_cooldown_hours=0)
    applied = auto_trade_service.maybe_auto_apply_tuning(
        trigger_source="forward_validation_close:31",
        applied_by="pytest_autotune",
    )
    assert applied["applied"] is True

    with TestClient(create_app()) as client:
        activity = client.get("/autotrade/tuning-activity", params={"limit": 10})
        assert activity.status_code == 200
        items = activity.json()["items"]
        assert len(items) >= 2
        assert items[0]["decision_type"] == "auto_tune_applied"
        assert items[1]["decision_type"] == "auto_tune_disabled"

        report = client.get("/autotrade/tuning-daily-report", params={"hours": 24})
        assert report.status_code == 200
        payload = report.json()
        assert payload["activity_count"] >= 2
        assert payload["counts_by_type"]["auto_tune_applied"] >= 1
        assert payload["counts_by_type"]["auto_tune_disabled"] >= 1
        assert payload["latest_activity"]["decision_type"] == "auto_tune_applied"


def test_run_once_blocks_when_loss_guard_trips(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        max_consecutive_losses=3,
        daily_loss_limit=100.0,
    )

    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "today": {
                    "realized_net_profit": -132.5,
                    "sold_count": 4,
                },
                "last_7d": {
                    "realized_net_profit": -88.0,
                    "sold_count": 7,
                },
                "loss_streak": {
                    "current_consecutive_losses": 3,
                    "current_loss_total": -132.5,
                },
                "best_source_7d": None,
                "weakest_source_7d": None,
            },
        },
    )

    def _should_not_scan(*args, **kwargs):
        raise AssertionError("opportunities should not be scanned when the loss guard is blocked")

    monkeypatch.setattr(autotrade_module.repo, "list_opportunities", _should_not_scan)

    result = auto_trade_service.run_once(force=True)

    assert result["blocked"] is True
    assert result["reason"] == "profit_guard_blocked"
    assert result["profit_guard"]["blocked"] is True
    assert any("Loss streak reached" in reason for reason in result["profit_guard"]["reasons"])
    assert any("Today's realized net profit dropped" in reason for reason in result["profit_guard"]["reasons"])


def test_run_once_applies_loss_recovery_tighten_when_guard_trips(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        min_score=60.0,
        min_roi=0.18,
        max_risk_score=40.0,
        max_consecutive_losses=3,
        daily_loss_limit=100.0,
        loss_recovery_enabled=True,
        loss_recovery_cooldown_hours=0,
    )

    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "today": {
                    "realized_net_profit": -140.0,
                    "sold_count": 3,
                },
                "last_7d": {
                    "realized_net_profit": -90.0,
                    "sold_count": 6,
                },
                "loss_streak": {
                    "current_consecutive_losses": 3,
                    "current_loss_total": -140.0,
                },
                "best_source_7d": None,
                "weakest_source_7d": None,
            },
        },
    )
    monkeypatch.setattr(
        autotrade_module.repo,
        "list_opportunities",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("guard should block before scan")),
    )

    result = auto_trade_service.run_once(force=True)

    assert result["blocked"] is True
    assert result["loss_recovery"]["applied"] is True
    assert result["loss_recovery"]["event"]["source"] == "loss_recovery_guard"
    assert result["loss_recovery"]["event"]["next_config"]["min_score"] == 64.0
    assert result["loss_recovery"]["event"]["next_config"]["min_roi"] == pytest.approx(0.2)
    assert result["loss_recovery"]["event"]["next_config"]["max_risk_score"] == 36.0


def test_run_once_respects_loss_recovery_cooldown(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        min_score=60.0,
        min_roi=0.18,
        max_risk_score=40.0,
        max_consecutive_losses=3,
        daily_loss_limit=100.0,
        loss_recovery_enabled=True,
        loss_recovery_cooldown_hours=24,
    )

    auto_trade_service.apply_tuning(
        source="loss_recovery_guard",
        applied_by="profit_guard_bot",
        note="seed recovery cooldown",
        decision_type="loss_recovery_tighten",
        min_score=64.0,
        min_roi=0.2,
        max_risk_score=36.0,
        require_risk_score=True,
    )

    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "today": {
                    "realized_net_profit": -140.0,
                    "sold_count": 3,
                },
                "last_7d": {
                    "realized_net_profit": -90.0,
                    "sold_count": 6,
                },
                "loss_streak": {
                    "current_consecutive_losses": 3,
                    "current_loss_total": -140.0,
                },
                "best_source_7d": None,
                "weakest_source_7d": None,
            },
        },
    )
    monkeypatch.setattr(
        autotrade_module.repo,
        "list_opportunities",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("guard should block before scan")),
    )

    result = auto_trade_service.run_once(force=True)

    assert result["blocked"] is True
    assert result["loss_recovery"]["applied"] is False
    assert result["loss_recovery"]["reason"] == "loss_recovery_cooldown"


def test_run_once_releases_loss_recovery_when_profit_recovers(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        min_score=60.0,
        min_roi=0.18,
        max_risk_score=40.0,
        max_consecutive_losses=3,
        daily_loss_limit=100.0,
        loss_recovery_enabled=True,
        loss_recovery_cooldown_hours=0,
    )
    auto_trade_service.apply_tuning(
        source="loss_recovery_guard",
        applied_by="profit_guard_bot",
        note="seed recovery mode",
        decision_type="loss_recovery_tighten",
        min_score=64.0,
        min_roi=0.2,
        max_risk_score=36.0,
        require_risk_score=True,
    )

    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "today": {
                    "realized_net_profit": 32.0,
                    "sold_count": 1,
                },
                "last_7d": {
                    "realized_net_profit": 74.0,
                    "sold_count": 4,
                },
                "loss_streak": {
                    "current_consecutive_losses": 0,
                    "current_loss_total": 0.0,
                },
                "best_source_7d": {"source": "alpha"},
                "weakest_source_7d": {"source": "beta"},
            },
        },
    )
    monkeypatch.setattr(autotrade_module.repo, "list_opportunities", lambda *args, **kwargs: [])

    result = auto_trade_service.run_once(force=True)

    assert result["blocked"] is not True
    assert result["loss_recovery"]["applied"] is True
    assert result["loss_recovery"]["event"]["source"] == "loss_recovery_release"
    assert result["loss_recovery"]["event"]["next_config"]["min_score"] == 60.0
    assert result["loss_recovery"]["event"]["next_config"]["min_roi"] == pytest.approx(0.18)
    assert result["loss_recovery"]["event"]["next_config"]["max_risk_score"] == 40.0
    assert auto_trade_service.status()["loss_recovery_state"]["active"] is False


def test_status_marks_loss_recovery_active_when_tighten_config_is_live(
    isolated_autotrade_tuning_sqlite: Path,
) -> None:
    auto_trade_service.update_config(
        min_score=60.0,
        min_roi=0.18,
        max_risk_score=40.0,
    )
    auto_trade_service.apply_tuning(
        source="loss_recovery_guard",
        applied_by="profit_guard_bot",
        note="seed recovery mode",
        decision_type="loss_recovery_tighten",
        min_score=64.0,
        min_roi=0.2,
        max_risk_score=36.0,
        require_risk_score=True,
    )

    status = auto_trade_service.status()

    assert status["loss_recovery_state"]["active"] is True
    assert status["loss_recovery_state"]["source"] == "loss_recovery_guard"


def test_run_once_applies_source_specific_threshold_adjustments(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        min_score=60.0,
        min_roi=0.18,
        max_risk_score=40.0,
        max_consecutive_losses=0,
        daily_loss_limit=0.0,
    )

    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "today": {
                    "realized_net_profit": 0.0,
                    "sold_count": 0,
                },
                "last_7d": {
                    "realized_net_profit": 0.0,
                    "sold_count": 0,
                },
                "loss_streak": {
                    "current_consecutive_losses": 0,
                    "current_loss_total": 0.0,
                },
                "source_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "strategy_mode": "tighten",
                        "threshold_delta": {
                            "min_score": 4.0,
                            "min_roi": 0.02,
                            "max_risk_score": -4.0,
                        },
                    },
                    {
                        "source": "gamma",
                        "strategy_mode": "widen",
                        "threshold_delta": {
                            "min_score": -2.0,
                            "min_roi": -0.005,
                            "max_risk_score": 2.0,
                        },
                    },
                ],
            },
        },
    )
    monkeypatch.setattr(
        autotrade_module.repo,
        "list_opportunities",
        lambda *args, **kwargs: [
            {
                "id": 1,
                "score": 62.0,
                "roi": 0.19,
                "source": "alpha",
                "list_price": 100.0,
                "review_note": "risk_score=20",
            },
            {
                "id": 2,
                "score": 59.0,
                "roi": 0.176,
                "source": "gamma",
                "list_price": 100.0,
                "review_note": "risk_score=20",
            },
        ],
    )

    approvals: list[dict[str, object]] = []

    def _approve(**kwargs):
        approvals.append(kwargs)
        return {
            "created": True,
            "idempotent": False,
            "trade_id": 1000 + int(kwargs["opportunity_id"]),
        }

    monkeypatch.setattr(autotrade_module.repo, "approve_opportunity_idempotent", _approve)

    result = auto_trade_service.run_once(force=True)

    assert result["approved"] == 1
    assert result["opportunity_ids"] == [2]
    assert approvals[0]["opportunity_id"] == 2
    assert "source_mode=widen" in str(approvals[0]["note"])
    assert result["source_strategies"][0]["source"] == "alpha"


def test_run_once_blocks_blacklisted_seller_and_allows_whitelisted_seller(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        min_score=60.0,
        min_roi=0.18,
        max_risk_score=40.0,
        max_consecutive_losses=0,
        daily_loss_limit=0.0,
    )

    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "today": {
                    "realized_net_profit": 0.0,
                    "sold_count": 0,
                },
                "last_7d": {
                    "realized_net_profit": 0.0,
                    "sold_count": 0,
                },
                "loss_streak": {
                    "current_consecutive_losses": 0,
                    "current_loss_total": 0.0,
                },
                "seller_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "seller_id": "seller-bad",
                        "seller_key": "alpha::seller-bad",
                        "seller_lane": "blacklist",
                        "threshold_delta": {
                            "min_score": 8.0,
                            "min_roi": 0.05,
                            "max_risk_score": -8.0,
                        },
                        "intake_multiplier": 0.0,
                    },
                    {
                        "source": "alpha",
                        "seller_id": "seller-good",
                        "seller_key": "alpha::seller-good",
                        "seller_lane": "whitelist",
                        "threshold_delta": {
                            "min_score": -3.0,
                            "min_roi": -0.01,
                            "max_risk_score": 3.0,
                        },
                        "intake_multiplier": 1.25,
                    },
                ],
                "source_leaderboard_7d": [],
            },
        },
    )
    monkeypatch.setattr(
        autotrade_module.repo,
        "list_opportunities",
        lambda *args, **kwargs: [
            {
                "id": 1,
                "score": 90.0,
                "roi": 0.4,
                "source": "alpha",
                "seller_id": "seller-bad",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
            {
                "id": 2,
                "score": 59.0,
                "roi": 0.175,
                "source": "alpha",
                "seller_id": "seller-good",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
        ],
    )

    approvals: list[dict[str, object]] = []

    def _approve(**kwargs):
        approvals.append(kwargs)
        return {
            "created": True,
            "idempotent": False,
            "trade_id": 2000 + int(kwargs["opportunity_id"]),
        }

    monkeypatch.setattr(autotrade_module.repo, "approve_opportunity_idempotent", _approve)

    result = auto_trade_service.run_once(force=True)

    assert result["approved"] == 1
    assert result["skipped_seller_blacklist"] == 1
    assert result["opportunity_ids"] == [2]
    assert approvals[0]["opportunity_id"] == 2
    assert "seller_lane=whitelist" in str(approvals[0]["note"])
    assert result["seller_position_controls"][0]["seller_id"] in {"seller-bad", "seller-good"}


def test_run_once_applies_observe_seller_runtime_control(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        min_score=60.0,
        min_roi=0.18,
        max_risk_score=40.0,
        max_consecutive_losses=0,
        daily_loss_limit=0.0,
    )

    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [],
            },
        },
    )
    monkeypatch.setattr(
        autotrade_module.repo,
        "list_opportunities",
        lambda *args, **kwargs: [
            {
                "id": 1,
                "score": 61.0,
                "roi": 0.185,
                "source": "alpha",
                "seller_id": "seller-watch",
                "list_price": 100.0,
                "review_note": "risk_score=20",
            },
        ],
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "sync_from_metrics",
        lambda **kwargs: {"status": {"active_freeze_count": 0, "active_observe_count": 1, "items": []}},
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "runtime_control",
        lambda **kwargs: {
            "state": "observe",
            "blocked": False,
            "threshold_delta": {"min_score": 2.0, "min_roi": 0.01, "max_risk_score": -2.0},
            "intake_multiplier": 0.6,
        },
    )

    approvals: list[dict[str, object]] = []

    def _approve(**kwargs):
        approvals.append(kwargs)
        return {"created": True, "idempotent": False, "trade_id": 3001}

    monkeypatch.setattr(autotrade_module.repo, "approve_opportunity_idempotent", _approve)

    result = auto_trade_service.run_once(force=True)

    assert result["approved"] == 0
    assert result["skipped_score"] == 1
    assert approvals == []
