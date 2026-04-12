from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import repositories as repo
from app.config import settings
from app.database import get_conn, init_db
from app.main import create_app
from app.services.autotrade import auto_trade_service
import app.services.autotrade as autotrade_module
import app.services.autotrade_alerting as autotrade_alerting_module
import app.services.notifier as notifier_module
import app.routers.autotrade as autotrade_router_module


@pytest.fixture
def isolated_autotrade_tuning_sqlite(tmp_path: Path):
    old_sqlite_path = settings.sqlite_path
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    old_source_share = settings.auto_approve_max_source_capital_share
    old_cluster_batch_share = settings.auto_approve_max_cluster_batch_share
    old_cluster_capital_share = settings.auto_approve_max_cluster_capital_share
    old_source_observe_base_multiplier = settings.auto_approve_source_observe_base_multiplier
    old_source_observe_release_streak = settings.auto_approve_source_observe_release_streak
    old_source_cashout_max_holding_days = settings.auto_approve_source_cashout_max_holding_days
    old_alert_email_auto_enabled = settings.autotrade_alert_email_auto_enabled
    old_alert_email_cooldown_minutes = settings.autotrade_alert_email_cooldown_minutes
    old_alert_email_min_severity = settings.autotrade_alert_email_min_severity
    old_alert_webhook_auto_enabled = settings.autotrade_alert_webhook_auto_enabled
    old_alert_webhook_cooldown_minutes = settings.autotrade_alert_webhook_cooldown_minutes
    old_alert_webhook_min_severity = settings.autotrade_alert_webhook_min_severity
    old_alert_escalation_minutes = settings.autotrade_alert_escalation_minutes
    old_status = auto_trade_service.status()
    old_snapshot = auto_trade_service.tuning_snapshot()
    old_policy = auto_trade_service.tuning_policy()
    old_max_consecutive_losses = auto_trade_service._max_consecutive_losses
    old_daily_loss_limit = auto_trade_service._daily_loss_limit
    old_loss_recovery_enabled = auto_trade_service._loss_recovery_enabled
    old_loss_recovery_cooldown_hours = auto_trade_service._loss_recovery_cooldown_hours
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "autotrade_tuning.db"))
    object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 0.0)
    object.__setattr__(settings, "auto_approve_max_source_capital_share", 1.0)
    object.__setattr__(settings, "auto_approve_max_cluster_batch_share", 1.0)
    object.__setattr__(settings, "auto_approve_max_cluster_capital_share", 1.0)
    init_db()
    auto_trade_service.update_config(
        batch_size=10,
        min_score=60.0,
        min_roi=0.18,
        max_risk_score=40.0,
        require_risk_score=True,
        auto_execute_buy_on_approve=False,
        auto_execute_buy_dry_run=True,
        auto_execute_list_on_buy_success=False,
        auto_execute_list_dry_run=True,
        max_consecutive_losses=3,
        daily_loss_limit=100.0,
        loss_recovery_enabled=True,
        loss_recovery_cooldown_hours=12,
        tuning_auto_apply_enabled=False,
        tuning_cooldown_hours=24,
        tuning_min_closed_batches=2,
        tuning_latest_min_sold_count=5,
        tuning_previous_min_sold_count=3,
        alert_email_auto_enabled=False,
        alert_email_cooldown_minutes=30,
        alert_email_min_severity="warning",
        alert_webhook_auto_enabled=False,
        alert_webhook_cooldown_minutes=30,
        alert_webhook_min_severity="error",
        alert_escalation_minutes=60,
    )
    try:
        yield Path(settings.sqlite_path)
    finally:
        auto_trade_service.update_config(
            batch_size=old_status["batch_size"],
            min_score=old_snapshot["min_score"],
            min_roi=old_snapshot["min_roi"],
            max_risk_score=old_snapshot["max_risk_score"],
            require_risk_score=old_snapshot["require_risk_score"],
            auto_execute_buy_on_approve=old_status["auto_execute_buy_on_approve"],
            auto_execute_buy_dry_run=old_status["auto_execute_buy_dry_run"],
            auto_execute_list_on_buy_success=old_status["auto_execute_list_on_buy_success"],
            auto_execute_list_dry_run=old_status["auto_execute_list_dry_run"],
            max_consecutive_losses=old_max_consecutive_losses,
            daily_loss_limit=old_daily_loss_limit,
            loss_recovery_enabled=old_loss_recovery_enabled,
            loss_recovery_cooldown_hours=old_loss_recovery_cooldown_hours,
            tuning_auto_apply_enabled=old_policy["auto_apply_enabled"],
            tuning_cooldown_hours=old_policy["cooldown_hours"],
            tuning_min_closed_batches=old_policy["min_closed_batches"],
            tuning_latest_min_sold_count=old_policy["latest_min_sold_count"],
            tuning_previous_min_sold_count=old_policy["previous_min_sold_count"],
            alert_email_auto_enabled=old_alert_email_auto_enabled,
            alert_email_cooldown_minutes=old_alert_email_cooldown_minutes,
            alert_email_min_severity=old_alert_email_min_severity,
            alert_webhook_auto_enabled=old_alert_webhook_auto_enabled,
            alert_webhook_cooldown_minutes=old_alert_webhook_cooldown_minutes,
            alert_webhook_min_severity=old_alert_webhook_min_severity,
            alert_escalation_minutes=old_alert_escalation_minutes,
        )
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)
        object.__setattr__(settings, "auto_approve_max_source_capital_share", old_source_share)
        object.__setattr__(settings, "auto_approve_max_cluster_batch_share", old_cluster_batch_share)
        object.__setattr__(settings, "auto_approve_max_cluster_capital_share", old_cluster_capital_share)
        object.__setattr__(settings, "auto_approve_source_observe_base_multiplier", old_source_observe_base_multiplier)
        object.__setattr__(settings, "auto_approve_source_observe_release_streak", old_source_observe_release_streak)
        object.__setattr__(settings, "auto_approve_source_cashout_max_holding_days", old_source_cashout_max_holding_days)
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


def test_autotrade_config_updates_delivery_controls(isolated_autotrade_tuning_sqlite: Path) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/autotrade/config",
            json={
                "alert_email_auto_enabled": True,
                "alert_ack_timeout_minutes": 300,
                "alert_escalation_minutes": 90,
                "alert_renotify_minutes": 180,
                "alert_email_cooldown_minutes": 45,
                "alert_email_min_severity": "error",
                "alert_webhook_auto_enabled": True,
                "alert_webhook_cooldown_minutes": 90,
                "alert_webhook_min_severity": "error",
                "portfolio_max_deployed_capital": 500.0,
                "max_source_capital_share": 0.55,
                "max_cluster_batch_share": 0.45,
                "max_cluster_capital_share": 0.5,
                "source_cashout_max_holding_days": 4.0,
                "source_observe_release_streak": 4,
                "source_observe_base_multiplier": 0.3,
            },
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["alert_email_auto_enabled"] is True
    assert payload["alert_ack_timeout_minutes"] == 300
    assert payload["alert_escalation_minutes"] == 90
    assert payload["alert_renotify_minutes"] == 180
    assert payload["alert_email_cooldown_minutes"] == 45
    assert payload["alert_email_min_severity"] == "error"
    assert payload["alert_webhook_auto_enabled"] is True
    assert payload["alert_webhook_cooldown_minutes"] == 90
    assert payload["alert_webhook_min_severity"] == "error"
    assert payload["portfolio_max_deployed_capital"] == 500.0
    assert payload["max_source_capital_share"] == 0.55
    assert payload["max_cluster_batch_share"] == 0.45
    assert payload["max_cluster_capital_share"] == 0.5
    assert payload["source_cashout_max_holding_days"] == 4.0
    assert payload["source_observe_release_streak"] == 4
    assert payload["source_observe_base_multiplier"] == 0.3


def test_source_and_cluster_manual_override_apis_and_cockpit(
    isolated_autotrade_tuning_sqlite: Path,
) -> None:
    with TestClient(create_app()) as client:
        source_action = client.post(
            "/autotrade/source-controls/manual-action",
            json={
                "source": "alpha",
                "action": "freeze",
                "reason": "ops hold",
                "actor": "ops",
                "duration_hours": 12,
            },
        )
        cluster_action = client.post(
            "/autotrade/cluster-controls/manual-action",
            json={
                "risk_cluster": "manual_card:Same",
                "action": "observe",
                "reason": "cluster watch",
                "actor": "ops",
                "duration_hours": 6,
            },
        )
        cockpit = client.get("/autotrade/cockpit")
        source_events = client.get("/autotrade/source-controls/events", params={"limit": 10})
        cluster_events = client.get("/autotrade/cluster-controls/events", params={"limit": 10})

    assert source_action.status_code == 200
    assert cluster_action.status_code == 200
    assert cockpit.status_code == 200
    cockpit_payload = cockpit.json()
    assert cockpit_payload["source_overrides"]["active_freeze_count"] >= 1
    assert cockpit_payload["cluster_overrides"]["active_observe_count"] >= 1
    assert source_events.status_code == 200
    assert cluster_events.status_code == 200
    assert source_events.json()["count"] >= 1
    assert cluster_events.json()["count"] >= 1


def test_cockpit_surfaces_operator_alerts_for_low_capital_and_expiring_overrides(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
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
                "inventory": {
                    "deployed_capital": 90.0,
                    "active_trade_count": 1,
                    "listed_trade_count": 1,
                    "approved_trade_count": 1,
                    "expected_exit_spread": 5.0,
                },
            },
            "forward_validation": {},
        },
    )

    with TestClient(create_app()) as client:
        source_action = client.post(
            "/autotrade/source-controls/manual-action",
            json={
                "source": "alpha",
                "action": "freeze",
                "reason": "ops hold",
                "actor": "ops",
                "duration_hours": 4,
            },
        )
        cluster_action = client.post(
            "/autotrade/cluster-controls/manual-action",
            json={
                "risk_cluster": "manual_card:Same",
                "action": "observe",
                "reason": "cluster watch",
                "actor": "ops",
                "duration_hours": 3,
            },
        )
        cockpit = client.get("/autotrade/cockpit")

    assert source_action.status_code == 200
    assert cluster_action.status_code == 200
    assert cockpit.status_code == 200
    payload = cockpit.json()
    codes = {str(item["code"]) for item in payload["alerts"]}
    assert "portfolio_capital_low" in codes
    assert "source_override_release_soon" in codes
    assert "cluster_override_release_soon" in codes
    assert payload["source_overrides"]["expiring_soon_count"] >= 1
    assert payload["cluster_overrides"]["expiring_soon_count"] >= 1
    assert payload["alert_summary"]["count"] >= 3


def test_expired_source_and_cluster_overrides_auto_restore_on_cockpit_load(
    isolated_autotrade_tuning_sqlite: Path,
) -> None:
    repo.upsert_source_control_state(
        source="expired-source",
        state="frozen",
        reason="manual freeze",
        frozen_until="2000-01-01T00:00:00+00:00",
        metadata={"manual_actor": "ops"},
    )
    repo.upsert_cluster_control_state(
        risk_cluster="manual_card:Expired",
        state="observe",
        reason="manual observe",
        frozen_until="2000-01-01T00:00:00+00:00",
        metadata={"manual_actor": "ops"},
    )

    with TestClient(create_app()) as client:
        cockpit = client.get("/autotrade/cockpit")

    assert cockpit.status_code == 200
    source_state = repo.get_source_control_state("expired-source")
    cluster_state = repo.get_cluster_control_state("manual_card:Expired")
    assert source_state is not None
    assert cluster_state is not None
    assert source_state["state"] == "normal"
    assert cluster_state["state"] == "normal"

    source_events = repo.list_source_control_events(limit=10)
    cluster_events = repo.list_cluster_control_events(limit=10)
    assert any(str(item["event_type"]) == "auto_restore" for item in source_events)
    assert any(str(item["event_type"]) == "auto_restore" for item in cluster_events)


def test_cockpit_surfaces_validation_baseline_scale_alert_in_single_account_mode(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_single_account_mode = settings.single_account_mode
    object.__setattr__(settings, "single_account_mode", True)
    try:
        dashboard = {
            "profit_cockpit": {
                "today": {"sold_count": 1, "realized_net_profit": 18.0},
                "last_7d": {
                    "sold_count": 8,
                    "profit_hit_rate": 0.625,
                    "avg_realized_roi": 0.1,
                    "realized_net_profit": 96.0,
                },
                "inventory": {"deployed_capital": 0.0},
                "source_leaderboard_7d": [
                    {"source": "alpha", "sold_count": 5, "realized_net_profit": 66.0},
                    {"source": "beta", "sold_count": 3, "realized_net_profit": 30.0},
                ],
                "seller_leaderboard_7d": [],
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
            },
            "forward_validation": {
                "active_batch": None,
                "recent_batches": [
                    {
                        "id": 71,
                        "name": "batch-71",
                        "status": "closed",
                        "sold_count": 6,
                        "profit_hit_rate": 0.72,
                        "avg_realized_roi": 0.14,
                        "avg_holding_days": 4.0,
                        "realized_net_profit": 120.0,
                    },
                    {
                        "id": 70,
                        "name": "batch-70",
                        "status": "closed",
                        "sold_count": 4,
                        "profit_hit_rate": 0.68,
                        "avg_realized_roi": 0.11,
                        "avg_holding_days": 5.0,
                        "realized_net_profit": 88.0,
                    },
                ],
            },
        }
        monkeypatch.setattr(autotrade_module.repo, "get_dashboard_metrics", lambda: dashboard)
        monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)
        monkeypatch.setattr(
            autotrade_module.repo,
            "get_execution_log_summary",
            lambda limit=24, dry_run=None: {
                "sample_size": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "business_ban_count": 0,
                "last_failure_at": "",
                "by_action": {},
            },
        )
        monkeypatch.setattr(
            autotrade_module.monitor_service,
            "status",
            lambda: {
                "circuit_open": False,
                "health": {
                    "samples": 12,
                    "success_rate": 0.9,
                    "guard_triggered": False,
                },
            },
        )
        monkeypatch.setattr(
            autotrade_module.risk_overrides_service,
            "source_status_summary",
            lambda limit=200: {"active_freeze_count": 0, "items": []},
        )
        monkeypatch.setattr(
            autotrade_module.risk_overrides_service,
            "cluster_status_summary",
            lambda limit=200: {"active_freeze_count": 0, "items": []},
        )

        with TestClient(create_app()) as client:
            cockpit = client.get("/autotrade/cockpit")
    finally:
        object.__setattr__(settings, "single_account_mode", old_single_account_mode)

    assert cockpit.status_code == 200
    payload = cockpit.json()
    codes = {str(item["code"]) for item in payload["alerts"]}
    assert "validation_baseline_scale_blocked" in codes
    scale_alert = next(
        item for item in payload["alerts"]
        if str(item["code"]) == "validation_baseline_scale_blocked"
    )
    assert "internal_auto_response_plan" not in scale_alert
    assert payload["autotrade"]["validation_baseline"]["ready_for_tune"] is True
    assert payload["autotrade"]["validation_baseline"]["ready_for_scale"] is False


def test_cockpit_surfaces_validation_baseline_regression_alert(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_single_account_mode = settings.single_account_mode
    object.__setattr__(settings, "single_account_mode", True)
    try:
        previous_hour = (datetime.now(timezone.utc) - timedelta(hours=1)).replace(
            minute=0,
            second=0,
            microsecond=0,
        )
        repo.upsert_validation_baseline_snapshot(
            bucket_type="hour",
            bucket_key=previous_hour.isoformat(),
            status="ready",
            ready=True,
            ready_for_tune=True,
            ready_for_scale=True,
            direction="improving",
            summary="Baseline looked healthy.",
            blocking_codes=[],
            snapshot={
                "health_score": 92.0,
                "tune_health_score": 100.0,
                "scale_health_score": 100.0,
            },
            captured_at=previous_hour.isoformat(),
        )

        dashboard = {
            "profit_cockpit": {
                "today": {"sold_count": 1, "realized_net_profit": 6.0},
                "last_7d": {
                    "sold_count": 6,
                    "profit_hit_rate": 0.55,
                    "avg_realized_roi": 0.08,
                    "realized_net_profit": 44.0,
                },
                "inventory": {"deployed_capital": 0.0},
                "source_leaderboard_7d": [
                    {"source": "alpha", "sold_count": 4, "realized_net_profit": 30.0},
                    {"source": "beta", "sold_count": 2, "realized_net_profit": 14.0},
                ],
                "seller_leaderboard_7d": [],
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
            },
            "forward_validation": {
                "active_batch": None,
                "recent_batches": [
                    {
                        "id": 91,
                        "name": "batch-91",
                        "status": "closed",
                        "sold_count": 5,
                        "profit_hit_rate": 0.56,
                        "avg_realized_roi": 0.085,
                        "avg_holding_days": 7.0,
                        "realized_net_profit": 50.0,
                    },
                    {
                        "id": 90,
                        "name": "batch-90",
                        "status": "closed",
                        "sold_count": 4,
                        "profit_hit_rate": 0.6,
                        "avg_realized_roi": 0.09,
                        "avg_holding_days": 6.0,
                        "realized_net_profit": 40.0,
                    },
                ],
            },
        }
        monkeypatch.setattr(autotrade_module.repo, "get_dashboard_metrics", lambda: dashboard)
        monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)
        monkeypatch.setattr(
            autotrade_module.repo,
            "get_execution_log_summary",
            lambda limit=24, dry_run=None: {
                "sample_size": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "business_ban_count": 0,
                "last_failure_at": "",
                "by_action": {},
            },
        )
        monkeypatch.setattr(
            autotrade_module.monitor_service,
            "status",
            lambda: {
                "circuit_open": False,
                "health": {
                    "samples": 12,
                    "success_rate": 0.9,
                    "guard_triggered": False,
                },
            },
        )
        monkeypatch.setattr(
            autotrade_module.risk_overrides_service,
            "source_status_summary",
            lambda limit=200: {"active_freeze_count": 0, "items": []},
        )
        monkeypatch.setattr(
            autotrade_module.risk_overrides_service,
            "cluster_status_summary",
            lambda limit=200: {"active_freeze_count": 0, "items": []},
        )

        with TestClient(create_app()) as client:
            cockpit = client.get("/autotrade/cockpit")
    finally:
        object.__setattr__(settings, "single_account_mode", old_single_account_mode)

    assert cockpit.status_code == 200
    payload = cockpit.json()
    codes = {str(item["code"]) for item in payload["alerts"]}
    assert "validation_baseline_regressed" in codes
    regression_alert = next(
        item for item in payload["alerts"]
        if str(item["code"]) == "validation_baseline_regressed"
    )
    assert regression_alert["incident_priority"] == "high"
    assert "health delta" in str(regression_alert["message"])
    assert "internal_auto_response_plan" not in regression_alert
    assert payload["autotrade"]["validation_baseline"]["trajectory"]["available"] is True
    assert payload["autotrade"]["validation_baseline"]["trajectory"]["scale_regressed"] is True


def test_cockpit_surfaces_validation_baseline_drawdown_with_critical_priority(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_single_account_mode = settings.single_account_mode
    object.__setattr__(settings, "single_account_mode", True)
    try:
        payload = autotrade_alerting_module.build_alert_payload(
            enabled=False,
            profit_guard={"blocked": False, "reasons": []},
            dashboard_metrics={
                "profit_cockpit": {
                    "inventory": {"deployed_capital": 0.0},
                },
            },
            operating_state={"state": "normal"},
            execution_readiness={"webhook_provider": False, "live_ready": False},
            validation_baseline={
                "ready": False,
                "ready_for_tune": False,
                "ready_for_scale": False,
                "blocking_codes": ["recent_sold_count"],
                "trajectory": {
                    "available": True,
                    "alert_level": "error",
                    "direction": "drawdown",
                    "summary": "Observation baseline regressed sharply and needs immediate review.",
                    "health_delta": -24.0,
                    "blocked_streak": 3,
                    "worsening_streak": 3,
                    "scale_regressed": False,
                    "tune_regressed": False,
                },
            },
        )
    finally:
        object.__setattr__(settings, "single_account_mode", old_single_account_mode)

    drawdown_alert = next(
        item for item in payload["alerts"]
        if str(item["code"]) == "validation_baseline_drawdown"
    )
    assert drawdown_alert["incident_priority"] in {"critical", "high"}
    assert drawdown_alert["severity"] == "error"
    assert "health delta -24.0" in str(drawdown_alert["message"])
    assert drawdown_alert["internal_auto_response_plan"]
    assert any(
        str(item["code"]) == "manual_mode_hold"
        for item in drawdown_alert["internal_auto_response_plan"]
    )


def test_cockpit_alert_email_hides_internal_auto_response_plan() -> None:
    subject, body = notifier_module.format_cockpit_alert_email(
        cockpit={
            "ready": False,
            "blocking_reasons": ["single_account_validation_scale_not_ready"],
            "alert_summary": {"count": 1},
            "portfolio": {"remaining_capital": 0.0, "deployed_capital": 0.0, "capital_limit": 0.0},
            "alerts": [
                {
                    "severity": "warning",
                    "incident_priority": "high",
                    "title": "Observation baseline regressed",
                    "message": "health delta -12.0",
                    "internal_auto_response_plan": [
                        {"code": "pause_widening"},
                        {"code": "review_validation_state"},
                    ],
                },
            ],
        },
    )

    assert "WARNING" in subject
    assert "actions:" not in body


def test_cockpit_alert_email_dispatch_endpoint(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_enabled = settings.alert_email_enabled
    old_to = settings.alert_email_to
    old_host = settings.smtp_host
    old_user = settings.smtp_user
    try:
        object.__setattr__(settings, "alert_email_enabled", True)
        object.__setattr__(settings, "alert_email_to", "ops@example.com")
        object.__setattr__(settings, "smtp_host", "smtp.example.com")
        object.__setattr__(settings, "smtp_user", "bot@example.com")
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )

        sent_payloads: list[tuple[str, str]] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_email",
            lambda subject, body: sent_payloads.append((subject, body)) or True,
        )

        with TestClient(create_app()) as client:
            client.post(
                "/autotrade/source-controls/manual-action",
                json={
                    "source": "alpha",
                    "action": "freeze",
                    "reason": "ops hold",
                    "actor": "ops",
                    "duration_hours": 4,
                },
            )
            response = client.post("/autotrade/alerts/email")

        assert response.status_code == 200
        payload = response.json()
        assert payload["sent"] is True
        assert payload["email_ready"] is True
        assert payload["alert_count"] >= 1
        assert sent_payloads
        assert "active alerts" in sent_payloads[0][0]
        assert "Alerts:" in sent_payloads[0][1]
    finally:
        object.__setattr__(settings, "alert_email_enabled", old_enabled)
        object.__setattr__(settings, "alert_email_to", old_to)
        object.__setattr__(settings, "smtp_host", old_host)
        object.__setattr__(settings, "smtp_user", old_user)


def test_cockpit_alert_webhook_dispatch_endpoint(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_enabled = settings.alert_webhook_enabled
    old_url = settings.alert_webhook_url
    try:
        object.__setattr__(settings, "alert_webhook_enabled", True)
        object.__setattr__(settings, "alert_webhook_url", "https://ops.example.com/hook")
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )

        sent_payloads: list[dict[str, object]] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_webhook",
            lambda payload: sent_payloads.append(payload) or True,
        )

        with TestClient(create_app()) as client:
            client.post(
                "/autotrade/source-controls/manual-action",
                json={
                    "source": "alpha",
                    "action": "freeze",
                    "reason": "ops hold",
                    "actor": "ops",
                    "duration_hours": 1,
                },
            )
            response = client.post("/autotrade/alerts/webhook", params={"force": True})

        assert response.status_code == 200
        payload = response.json()
        assert payload["sent"] is True
        assert payload["webhook_ready"] is True
        assert payload["alert_count"] >= 1
        assert sent_payloads
        assert sent_payloads[0]["kind"] == "autotrade_alert_escalation"
    finally:
        object.__setattr__(settings, "alert_webhook_enabled", old_enabled)
        object.__setattr__(settings, "alert_webhook_url", old_url)


def test_send_alert_webhook_uses_slack_payload_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    old_enabled = settings.alert_webhook_enabled
    old_provider = settings.alert_webhook_provider
    old_url = settings.alert_webhook_url
    captured: dict[str, object] = {}

    class _Response:
        status_code = 200

    def _fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response()

    try:
        object.__setattr__(settings, "alert_webhook_enabled", True)
        object.__setattr__(settings, "alert_webhook_provider", "slack")
        object.__setattr__(settings, "alert_webhook_url", "https://hooks.slack.com/services/T000/B000/XXX")
        monkeypatch.setattr(notifier_module.requests, "post", _fake_post)

        ok = notifier_module.send_alert_webhook({"text": "hello slack", "alerts": [{"code": "x"}]})

        assert ok is True
        assert captured["url"] == "https://hooks.slack.com/services/T000/B000/XXX"
        assert captured["json"] == {"text": "hello slack"}
    finally:
        object.__setattr__(settings, "alert_webhook_enabled", old_enabled)
        object.__setattr__(settings, "alert_webhook_provider", old_provider)
        object.__setattr__(settings, "alert_webhook_url", old_url)


def test_send_alert_webhook_uses_telegram_payload_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    old_enabled = settings.alert_webhook_enabled
    old_provider = settings.alert_webhook_provider
    old_token = settings.alert_telegram_bot_token
    old_chat_id = settings.alert_telegram_chat_id
    captured: dict[str, object] = {}

    class _Response:
        status_code = 200

    def _fake_post(url, json=None, headers=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        captured["timeout"] = timeout
        return _Response()

    try:
        object.__setattr__(settings, "alert_webhook_enabled", True)
        object.__setattr__(settings, "alert_webhook_provider", "telegram")
        object.__setattr__(settings, "alert_telegram_bot_token", "123:abc")
        object.__setattr__(settings, "alert_telegram_chat_id", "-100123")
        monkeypatch.setattr(notifier_module.requests, "post", _fake_post)

        ok = notifier_module.send_alert_webhook({"text": "hello tg", "alerts": [{"code": "x"}]})

        assert ok is True
        assert captured["url"] == "https://api.telegram.org/bot123:abc/sendMessage"
        assert captured["json"]["chat_id"] == "-100123"
        assert captured["json"]["text"] == "hello tg"
    finally:
        object.__setattr__(settings, "alert_webhook_enabled", old_enabled)
        object.__setattr__(settings, "alert_webhook_provider", old_provider)
        object.__setattr__(settings, "alert_telegram_bot_token", old_token)
        object.__setattr__(settings, "alert_telegram_chat_id", old_chat_id)


def test_alert_acknowledge_and_resume_endpoints_update_cockpit_state(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard = {
        "profit_cockpit": {
            "today": {"realized_net_profit": 0.0, "sold_count": 0},
            "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
            "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
            "seller_leaderboard_7d": [],
            "source_leaderboard_7d": [],
            "inventory": {
                "deployed_capital": 95.0,
                "active_trade_count": 1,
                "listed_trade_count": 1,
                "approved_trade_count": 1,
                "expected_exit_spread": 5.0,
            },
        },
        "forward_validation": {},
    }
    monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)

    with TestClient(create_app()) as client:
        cockpit = client.get("/autotrade/cockpit")
        assert cockpit.status_code == 200
        alert = cockpit.json()["alerts"][0]
        alert_key = str(alert["alert_key"])

        ack = client.post(f"/autotrade/alerts/{alert_key}/ack", json={"actor": "ops"})
        assert ack.status_code == 200
        ack_alert = ack.json()["cockpit"]["alerts"][0]
        assert ack_alert["acknowledged"] is True
        assert ack_alert["acked_by"] == "ops"

        resume = client.post(f"/autotrade/alerts/{alert_key}/resume", params={"actor": "ops"})
        assert resume.status_code == 200
        resumed_alert = resume.json()["cockpit"]["alerts"][0]
        assert resumed_alert["acknowledged"] is False
        assert resumed_alert["snoozed"] is False

        events = client.get("/autotrade/alerts/events", params={"limit": 10})
        assert events.status_code == 200
        actions = [str(item["action"]) for item in events.json()["items"]]
        assert "ack" in actions
        assert "resume" in actions

        filtered = client.get(
            "/autotrade/alerts/events",
            params={"limit": 10, "alert_key": alert_key},
        )
        assert filtered.status_code == 200
        assert filtered.json()["count"] >= 2
        assert all(str(item["alert_key"]) == alert_key for item in filtered.json()["items"])


def test_snoozed_alert_suppresses_auto_email_dispatch(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_enabled = settings.alert_email_enabled
    old_to = settings.alert_email_to
    old_host = settings.smtp_host
    old_user = settings.smtp_user
    old_auto_enabled = settings.autotrade_alert_email_auto_enabled
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "alert_email_enabled", True)
        object.__setattr__(settings, "alert_email_to", "ops@example.com")
        object.__setattr__(settings, "smtp_host", "smtp.example.com")
        object.__setattr__(settings, "smtp_user", "bot@example.com")
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", True)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
        dashboard = {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [],
                "inventory": {
                    "deployed_capital": 95.0,
                    "active_trade_count": 1,
                    "listed_trade_count": 1,
                    "approved_trade_count": 1,
                    "expected_exit_spread": 5.0,
                },
            },
            "forward_validation": {},
        }
        monkeypatch.setattr(autotrade_module.repo, "get_dashboard_metrics", lambda: dashboard)
        monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)
        monkeypatch.setattr(autotrade_module.repo, "list_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "sync_from_metrics",
            lambda **kwargs: {"status": {}},
        )
        sent_payloads: list[tuple[str, str]] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_email",
            lambda subject, body: sent_payloads.append((subject, body)) or True,
        )

        with TestClient(create_app()) as client:
            cockpit = client.get("/autotrade/cockpit")
            alert_keys = [
                str(item["alert_key"])
                for item in cockpit.json()["alerts"]
            ]
            for alert_key in alert_keys:
                snooze = client.post(
                    f"/autotrade/alerts/{alert_key}/snooze",
                    json={"actor": "ops", "minutes": 60, "reason": "review later"},
                )
                assert snooze.status_code == 200

        result = auto_trade_service.run_once(force=True)

        assert result["alert_dispatch"]["sent"] is False
        assert result["alert_dispatch"]["reason"] == "no_active_alerts"
        assert sent_payloads == []
    finally:
        object.__setattr__(settings, "alert_email_enabled", old_enabled)
        object.__setattr__(settings, "alert_email_to", old_to)
        object.__setattr__(settings, "smtp_host", old_host)
        object.__setattr__(settings, "smtp_user", old_user)
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", old_auto_enabled)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_expired_snooze_auto_resumes_and_records_event(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard = {
        "profit_cockpit": {
            "today": {"realized_net_profit": 0.0, "sold_count": 0},
            "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
            "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
            "seller_leaderboard_7d": [],
            "source_leaderboard_7d": [],
            "inventory": {
                "deployed_capital": 95.0,
                "active_trade_count": 1,
                "listed_trade_count": 1,
                "approved_trade_count": 1,
                "expected_exit_spread": 5.0,
            },
        },
        "forward_validation": {},
    }
    monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)

    with TestClient(create_app()) as client:
        cockpit = client.get("/autotrade/cockpit")
        alert_key = str(cockpit.json()["alerts"][0]["alert_key"])
        snooze = client.post(
            f"/autotrade/alerts/{alert_key}/snooze",
            json={"actor": "ops", "minutes": 60, "reason": "review later"},
        )
        assert snooze.status_code == 200

        repo.override_alert_signal_state_timestamps(
            alert_key=alert_key,
            last_seen_at="2000-01-01T00:00:00+00:00",
        )
        with repo.get_conn() as conn:
            conn.execute(
                """
                UPDATE alert_signal_states
                SET snoozed_until = '2000-01-01T00:00:00+00:00'
                WHERE alert_key = ?
                """,
                (alert_key,),
            )

        refreshed = client.get("/autotrade/cockpit")
        refreshed_alert = next(
            item for item in refreshed.json()["alerts"]
            if str(item["alert_key"]) == alert_key
        )
        assert refreshed_alert["snoozed"] is False

        events = client.get("/autotrade/alerts/events", params={"limit": 10})
        actions = [str(item["action"]) for item in events.json()["items"]]
        assert "snooze_expired" in actions


def test_expired_ack_auto_resumes_and_records_event(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard = {
        "profit_cockpit": {
            "today": {"realized_net_profit": 0.0, "sold_count": 0},
            "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
            "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
            "seller_leaderboard_7d": [],
            "source_leaderboard_7d": [],
            "inventory": {
                "deployed_capital": 95.0,
                "active_trade_count": 1,
                "listed_trade_count": 1,
                "approved_trade_count": 1,
                "expected_exit_spread": 5.0,
            },
        },
        "forward_validation": {},
    }
    monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)
    old_ack_timeout = settings.autotrade_alert_ack_timeout_minutes
    try:
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", 60)
        with TestClient(create_app()) as client:
            cockpit = client.get("/autotrade/cockpit")
            alert_key = str(cockpit.json()["alerts"][0]["alert_key"])
            ack = client.post(
                f"/autotrade/alerts/{alert_key}/ack",
                json={"actor": "ops"},
            )
            assert ack.status_code == 200

            repo.override_alert_signal_state_timestamps(
                alert_key=alert_key,
                first_seen_at="2000-01-01T00:00:00+00:00",
                last_seen_at="2000-01-01T00:00:00+00:00",
            )
            with repo.get_conn() as conn:
                conn.execute(
                    """
                    UPDATE alert_signal_states
                    SET acked_at = '2000-01-01T00:00:00+00:00'
                    WHERE alert_key = ?
                    """,
                    (alert_key,),
                )

            refreshed = client.get("/autotrade/cockpit")
            refreshed_alert = next(
                item for item in refreshed.json()["alerts"]
                if str(item["alert_key"]) == alert_key
            )
            assert refreshed_alert["acknowledged"] is False
            events = client.get("/autotrade/alerts/events", params={"limit": 10})
            actions = [str(item["action"]) for item in events.json()["items"]]
            assert "ack_expired" in actions
    finally:
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", old_ack_timeout)


def test_cockpit_alert_email_dispatch_respects_cooldown_and_records_history(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_enabled = settings.alert_email_enabled
    old_to = settings.alert_email_to
    old_host = settings.smtp_host
    old_user = settings.smtp_user
    old_cooldown = settings.autotrade_alert_email_cooldown_minutes
    try:
        object.__setattr__(settings, "alert_email_enabled", True)
        object.__setattr__(settings, "alert_email_to", "ops@example.com")
        object.__setattr__(settings, "smtp_host", "smtp.example.com")
        object.__setattr__(settings, "smtp_user", "bot@example.com")
        object.__setattr__(settings, "autotrade_alert_email_cooldown_minutes", 30)
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )

        sent_payloads: list[tuple[str, str]] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_email",
            lambda subject, body: sent_payloads.append((subject, body)) or True,
        )

        with TestClient(create_app()) as client:
            client.post(
                "/autotrade/source-controls/manual-action",
                json={
                    "source": "alpha",
                    "action": "freeze",
                    "reason": "ops hold",
                    "actor": "ops",
                    "duration_hours": 4,
                },
            )
            first = client.post("/autotrade/alerts/email")
            second = client.post("/autotrade/alerts/email")
            cockpit = client.get("/autotrade/cockpit")

        assert first.status_code == 200
        assert second.status_code == 200
        assert first.json()["sent"] is True
        assert second.json()["sent"] is False
        assert second.json()["reason"] == "cooldown_active"
        assert len(sent_payloads) == 1

        history = repo.list_alert_delivery_events(channel="email", limit=5)
        assert history[0]["reason"] == "cooldown_active"
        assert history[1]["success"] is True
        assert cockpit.status_code == 200
        assert cockpit.json()["alert_delivery"]["last_email_event"]["reason"] == "cooldown_active"
    finally:
        object.__setattr__(settings, "alert_email_enabled", old_enabled)
        object.__setattr__(settings, "alert_email_to", old_to)
        object.__setattr__(settings, "smtp_host", old_host)
        object.__setattr__(settings, "smtp_user", old_user)
        object.__setattr__(settings, "autotrade_alert_email_cooldown_minutes", old_cooldown)


def test_run_once_auto_dispatches_alert_email_with_cooldown(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_enabled = settings.alert_email_enabled
    old_to = settings.alert_email_to
    old_host = settings.smtp_host
    old_user = settings.smtp_user
    old_auto_enabled = settings.autotrade_alert_email_auto_enabled
    old_cooldown = settings.autotrade_alert_email_cooldown_minutes
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "alert_email_enabled", True)
        object.__setattr__(settings, "alert_email_to", "ops@example.com")
        object.__setattr__(settings, "smtp_host", "smtp.example.com")
        object.__setattr__(settings, "smtp_user", "bot@example.com")
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", True)
        object.__setattr__(settings, "autotrade_alert_email_cooldown_minutes", 30)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )
        monkeypatch.setattr(autotrade_module.repo, "list_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "sync_from_metrics",
            lambda **kwargs: {"status": {}},
        )

        sent_payloads: list[tuple[str, str]] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_email",
            lambda subject, body: sent_payloads.append((subject, body)) or True,
        )

        first = auto_trade_service.run_once(force=True)
        second = auto_trade_service.run_once(force=True)

        assert first["alert_dispatch"]["enabled"] is True
        assert first["alert_dispatch"]["sent"] is True
        assert second["alert_dispatch"]["sent"] is False
        assert second["alert_dispatch"]["reason"] == "cooldown_active"
        assert len(sent_payloads) == 1
    finally:
        object.__setattr__(settings, "alert_email_enabled", old_enabled)
        object.__setattr__(settings, "alert_email_to", old_to)
        object.__setattr__(settings, "smtp_host", old_host)
        object.__setattr__(settings, "smtp_user", old_user)
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", old_auto_enabled)
        object.__setattr__(settings, "autotrade_alert_email_cooldown_minutes", old_cooldown)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_run_once_re_dispatches_when_time_escalation_changes_effective_severity(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_enabled = settings.alert_email_enabled
    old_to = settings.alert_email_to
    old_host = settings.smtp_host
    old_user = settings.smtp_user
    old_auto_enabled = settings.autotrade_alert_email_auto_enabled
    old_cooldown = settings.autotrade_alert_email_cooldown_minutes
    old_escalation_minutes = settings.autotrade_alert_escalation_minutes
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "alert_email_enabled", True)
        object.__setattr__(settings, "alert_email_to", "ops@example.com")
        object.__setattr__(settings, "smtp_host", "smtp.example.com")
        object.__setattr__(settings, "smtp_user", "bot@example.com")
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", True)
        object.__setattr__(settings, "autotrade_alert_email_cooldown_minutes", 180)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )
        monkeypatch.setattr(autotrade_module.repo, "list_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "sync_from_metrics",
            lambda **kwargs: {"status": {}},
        )

        sent_payloads: list[tuple[str, str]] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_email",
            lambda subject, body: sent_payloads.append((subject, body)) or True,
        )

        first = auto_trade_service.run_once(force=True)
        active_states = repo.list_active_alert_signal_states(limit=10)
        assert active_states
        repo.override_alert_signal_state_timestamps(
            alert_key=str(active_states[0]["alert_key"]),
            first_seen_at="2000-01-01T00:00:00+00:00",
            last_seen_at="2000-01-01T00:00:00+00:00",
        )
        second = auto_trade_service.run_once(force=True)

        assert first["alert_dispatch"]["sent"] is True
        assert second["alert_dispatch"]["sent"] is True
        assert len(sent_payloads) == 2
    finally:
        object.__setattr__(settings, "alert_email_enabled", old_enabled)
        object.__setattr__(settings, "alert_email_to", old_to)
        object.__setattr__(settings, "smtp_host", old_host)
        object.__setattr__(settings, "smtp_user", old_user)
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", old_auto_enabled)
        object.__setattr__(settings, "autotrade_alert_email_cooldown_minutes", old_cooldown)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation_minutes)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_run_once_auto_alert_email_respects_min_severity_threshold(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_auto_enabled = settings.autotrade_alert_email_auto_enabled
    old_min_severity = settings.autotrade_alert_email_min_severity
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", True)
        object.__setattr__(settings, "autotrade_alert_email_min_severity", "error")
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )
        monkeypatch.setattr(autotrade_module.repo, "list_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "sync_from_metrics",
            lambda **kwargs: {"status": {}},
        )

        sent_payloads: list[tuple[str, str]] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_email",
            lambda subject, body: sent_payloads.append((subject, body)) or True,
        )

        result = auto_trade_service.run_once(force=True)

        assert result["alert_dispatch"]["enabled"] is True
        assert result["alert_dispatch"]["sent"] is False
        assert result["alert_dispatch"]["reason"] == "min_severity_not_met"
        assert result["alert_dispatch"]["min_severity"] == "error"
        assert result["alert_dispatch"]["highest_severity"] == "warning"
        assert sent_payloads == []
    finally:
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", old_auto_enabled)
        object.__setattr__(settings, "autotrade_alert_email_min_severity", old_min_severity)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_run_once_auto_alert_email_escalates_warning_after_age_threshold(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_auto_enabled = settings.autotrade_alert_email_auto_enabled
    old_min_severity = settings.autotrade_alert_email_min_severity
    old_escalation_minutes = settings.autotrade_alert_escalation_minutes
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", True)
        object.__setattr__(settings, "autotrade_alert_email_min_severity", "error")
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )
        monkeypatch.setattr(autotrade_module.repo, "list_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "sync_from_metrics",
            lambda **kwargs: {"status": {}},
        )

        alert_key = autotrade_alerting_module._build_alert_key(
            {
                "code": "portfolio_capital_low",
                "target": "",
            },
        )
        repo.upsert_alert_signal_state(
            alert_key=alert_key,
            code="portfolio_capital_low",
            scope="portfolio",
            target="",
            title="Portfolio capital running low",
            last_message="Only 5 capital remains.",
            last_severity="warning",
        )
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE alert_signal_states
                SET first_seen_at = datetime('now', '-90 minutes'),
                    last_seen_at = datetime('now', '-5 minutes')
                WHERE alert_key = ?
                """,
                (alert_key,),
            )

        sent_payloads: list[tuple[str, str]] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_email",
            lambda subject, body: sent_payloads.append((subject, body)) or True,
        )

        result = auto_trade_service.run_once(force=True)

        assert result["alert_dispatch"]["enabled"] is True
        assert result["alert_dispatch"]["sent"] is True
        assert sent_payloads
    finally:
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", old_auto_enabled)
        object.__setattr__(settings, "autotrade_alert_email_min_severity", old_min_severity)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation_minutes)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_run_once_auto_dispatches_webhook_only_after_escalation(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_enabled = settings.alert_webhook_enabled
    old_url = settings.alert_webhook_url
    old_auto_enabled = settings.autotrade_alert_webhook_auto_enabled
    old_cooldown = settings.autotrade_alert_webhook_cooldown_minutes
    old_min_severity = settings.autotrade_alert_webhook_min_severity
    old_escalation_minutes = settings.autotrade_alert_escalation_minutes
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "alert_webhook_enabled", True)
        object.__setattr__(settings, "alert_webhook_url", "https://ops.example.com/hook")
        object.__setattr__(settings, "autotrade_alert_webhook_auto_enabled", True)
        object.__setattr__(settings, "autotrade_alert_webhook_cooldown_minutes", 180)
        object.__setattr__(settings, "autotrade_alert_webhook_min_severity", "error")
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )
        monkeypatch.setattr(autotrade_module.repo, "list_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "sync_from_metrics",
            lambda **kwargs: {"status": {}},
        )

        sent_payloads: list[dict[str, object]] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_webhook",
            lambda payload: sent_payloads.append(payload) or True,
        )

        first = auto_trade_service.run_once(force=True)
        assert first["alert_webhook_dispatch"]["enabled"] is True
        assert first["alert_webhook_dispatch"]["sent"] is False
        assert first["alert_webhook_dispatch"]["reason"] == "no_escalated_alerts"

        active_states = repo.list_active_alert_signal_states(limit=10)
        assert active_states
        repo.override_alert_signal_state_timestamps(
            alert_key=str(active_states[0]["alert_key"]),
            first_seen_at="2000-01-01T00:00:00+00:00",
            last_seen_at="2000-01-01T00:00:00+00:00",
        )

        second = auto_trade_service.run_once(force=True)

        assert second["alert_webhook_dispatch"]["enabled"] is True
        assert second["alert_webhook_dispatch"]["sent"] is True
        assert len(sent_payloads) == 1
        assert sent_payloads[0]["kind"] == "autotrade_alert_escalation"
        assert sent_payloads[0]["alerts"]
    finally:
        object.__setattr__(settings, "alert_webhook_enabled", old_enabled)
        object.__setattr__(settings, "alert_webhook_url", old_url)
        object.__setattr__(settings, "autotrade_alert_webhook_auto_enabled", old_auto_enabled)
        object.__setattr__(settings, "autotrade_alert_webhook_cooldown_minutes", old_cooldown)
        object.__setattr__(settings, "autotrade_alert_webhook_min_severity", old_min_severity)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation_minutes)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_run_once_re_dispatches_webhook_when_renotify_stage_advances(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_enabled = settings.alert_webhook_enabled
    old_url = settings.alert_webhook_url
    old_auto_enabled = settings.autotrade_alert_webhook_auto_enabled
    old_cooldown = settings.autotrade_alert_webhook_cooldown_minutes
    old_min_severity = settings.autotrade_alert_webhook_min_severity
    old_escalation_minutes = settings.autotrade_alert_escalation_minutes
    old_renotify_minutes = settings.autotrade_alert_renotify_minutes
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "alert_webhook_enabled", True)
        object.__setattr__(settings, "alert_webhook_url", "https://ops.example.com/hook")
        object.__setattr__(settings, "autotrade_alert_webhook_auto_enabled", True)
        object.__setattr__(settings, "autotrade_alert_webhook_cooldown_minutes", 180)
        object.__setattr__(settings, "autotrade_alert_webhook_min_severity", "error")
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", 60)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )
        monkeypatch.setattr(autotrade_module.repo, "list_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "sync_from_metrics",
            lambda **kwargs: {"status": {}},
        )

        sent_payloads: list[dict[str, object]] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_webhook",
            lambda payload: sent_payloads.append(payload) or True,
        )

        alert_key = autotrade_alerting_module._build_alert_key(
            {
                "code": "portfolio_capital_low",
                "target": "",
            },
        )
        repo.upsert_alert_signal_state(
            alert_key=alert_key,
            code="portfolio_capital_low",
            scope="portfolio",
            target="",
            title="Portfolio capital running low",
            last_message="Only 5 capital remains.",
            last_severity="warning",
        )
        repo.override_alert_signal_state_timestamps(
            alert_key=alert_key,
            first_seen_at="2000-01-01T00:00:00+00:00",
            last_seen_at="2000-01-01T00:00:00+00:00",
        )

        first = auto_trade_service.run_once(force=True)
        second = auto_trade_service.run_once(force=True)

        assert first["alert_webhook_dispatch"]["sent"] is True
        assert second["alert_webhook_dispatch"]["sent"] is False

        repo.override_alert_signal_state_timestamps(
            alert_key=alert_key,
            first_seen_at="1999-12-31T22:00:00+00:00",
            last_seen_at="1999-12-31T22:00:00+00:00",
        )
        third = auto_trade_service.run_once(force=True)

        assert third["alert_webhook_dispatch"]["sent"] is True
        assert len(sent_payloads) == 2
    finally:
        object.__setattr__(settings, "alert_webhook_enabled", old_enabled)
        object.__setattr__(settings, "alert_webhook_url", old_url)
        object.__setattr__(settings, "autotrade_alert_webhook_auto_enabled", old_auto_enabled)
        object.__setattr__(settings, "autotrade_alert_webhook_cooldown_minutes", old_cooldown)
        object.__setattr__(settings, "autotrade_alert_webhook_min_severity", old_min_severity)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation_minutes)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", old_renotify_minutes)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_run_once_re_dispatches_after_ack_timeout_expires(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_enabled = settings.alert_email_enabled
    old_to = settings.alert_email_to
    old_host = settings.smtp_host
    old_user = settings.smtp_user
    old_auto_enabled = settings.autotrade_alert_email_auto_enabled
    old_ack_timeout = settings.autotrade_alert_ack_timeout_minutes
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "alert_email_enabled", True)
        object.__setattr__(settings, "alert_email_to", "ops@example.com")
        object.__setattr__(settings, "smtp_host", "smtp.example.com")
        object.__setattr__(settings, "smtp_user", "bot@example.com")
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", True)
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", 60)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )
        monkeypatch.setattr(autotrade_module.repo, "list_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "sync_from_metrics",
            lambda **kwargs: {"status": {}},
        )

        sent_payloads: list[tuple[str, str]] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_email",
            lambda subject, body: sent_payloads.append((subject, body)) or True,
        )

        first = auto_trade_service.run_once(force=True)
        assert first["alert_dispatch"]["sent"] is True

        active_states = repo.list_active_alert_signal_states(limit=10)
        assert active_states
        alert_keys = [str(item["alert_key"]) for item in active_states]
        for alert_key in alert_keys:
            repo.acknowledge_alert_signal_state(alert_key=alert_key, actor="ops")
        acked = auto_trade_service.run_once(force=True)
        assert acked["alert_dispatch"]["sent"] is False

        alert_key = alert_keys[0]
        repo.override_alert_signal_state_timestamps(
            alert_key=alert_key,
            first_seen_at="2000-01-01T00:00:00+00:00",
            last_seen_at="2000-01-01T00:00:00+00:00",
        )
        with repo.get_conn() as conn:
            conn.execute(
                """
                UPDATE alert_signal_states
                SET acked_at = '2000-01-01T00:00:00+00:00'
                WHERE alert_key = ?
                """,
                (alert_key,),
            )

        third = auto_trade_service.run_once(force=True)
        assert third["alert_dispatch"]["sent"] is True
        assert len(sent_payloads) == 2
    finally:
        object.__setattr__(settings, "alert_email_enabled", old_enabled)
        object.__setattr__(settings, "alert_email_to", old_to)
        object.__setattr__(settings, "smtp_host", old_host)
        object.__setattr__(settings, "smtp_user", old_user)
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", old_auto_enabled)
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", old_ack_timeout)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_alert_timeline_includes_signal_and_delivery_events(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_email_enabled = settings.alert_email_enabled
    old_email_to = settings.alert_email_to
    old_smtp_host = settings.smtp_host
    old_smtp_user = settings.smtp_user
    old_webhook_enabled = settings.alert_webhook_enabled
    old_webhook_url = settings.alert_webhook_url
    old_webhook_provider = settings.alert_webhook_provider
    old_ack_timeout = settings.autotrade_alert_ack_timeout_minutes
    old_escalation = settings.autotrade_alert_escalation_minutes
    old_renotify = settings.autotrade_alert_renotify_minutes
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "alert_email_enabled", True)
        object.__setattr__(settings, "alert_email_to", "ops@example.com")
        object.__setattr__(settings, "smtp_host", "smtp.example.com")
        object.__setattr__(settings, "smtp_user", "bot@example.com")
        object.__setattr__(settings, "alert_webhook_enabled", True)
        object.__setattr__(settings, "alert_webhook_url", "https://hooks.slack.test/services/ops")
        object.__setattr__(settings, "alert_webhook_provider", "slack")
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", 30)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
        dashboard = {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [],
                "inventory": {
                    "deployed_capital": 95.0,
                    "active_trade_count": 1,
                    "listed_trade_count": 1,
                    "approved_trade_count": 1,
                    "expected_exit_spread": 5.0,
                },
            },
            "forward_validation": {},
        }
        monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_email",
            lambda subject, body: True,
        )
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_webhook",
            lambda payload: True,
        )
        with TestClient(create_app()) as client:
            cockpit = client.get("/autotrade/cockpit")
            assert cockpit.status_code == 200
            alert_key = str(cockpit.json()["alerts"][0]["alert_key"])
            slack_stage_started_at = (
                datetime.now(timezone.utc) - timedelta(minutes=61)
            ).isoformat()

            repo.override_alert_signal_state_timestamps(
                alert_key=alert_key,
                first_seen_at=slack_stage_started_at,
                last_seen_at=slack_stage_started_at,
            )

            email = client.post("/autotrade/alerts/email")
            assert email.status_code == 200
            assert email.json()["sent"] is True

            ack = client.post(
                f"/autotrade/alerts/{alert_key}/ack",
                json={"actor": "ops"},
            )
            assert ack.status_code == 200

            resume = client.post(f"/autotrade/alerts/{alert_key}/resume", params={"actor": "ops"})
            assert resume.status_code == 200

            snooze = client.post(
                f"/autotrade/alerts/{alert_key}/snooze",
                json={"actor": "ops", "minutes": 60, "reason": "need time"},
            )
            assert snooze.status_code == 200

            with repo.get_conn() as conn:
                conn.execute(
                    """
                    UPDATE alert_signal_states
                    SET snoozed_until = '2000-01-01T00:00:00+00:00'
                    WHERE alert_key = ?
                    """,
                    (alert_key,),
                )
            refreshed = client.get("/autotrade/cockpit")
            assert refreshed.status_code == 200

            ack_again = client.post(
                f"/autotrade/alerts/{alert_key}/ack",
                json={"actor": "ops"},
            )
            assert ack_again.status_code == 200
            with repo.get_conn() as conn:
                conn.execute(
                    """
                    UPDATE alert_signal_states
                    SET acked_at = '2000-01-01T00:00:00+00:00'
                    WHERE alert_key = ?
                    """,
                    (alert_key,),
                )
            reactivated = client.get("/autotrade/cockpit")
            assert reactivated.status_code == 200

            reactivation_email = client.post("/autotrade/alerts/email")
            assert reactivation_email.status_code == 200
            assert reactivation_email.json()["sent"] is True

            slack = client.post("/autotrade/alerts/webhook")
            assert slack.status_code == 200
            assert slack.json()["sent"] is True

            timeline = client.get(
                "/autotrade/alerts/events",
                params={"limit": 40, "alert_key": alert_key},
            )
            assert timeline.status_code == 200
            items = timeline.json()["items"]
            actions = [str(item["action"]) for item in items]
            assert "ack" in actions
            assert "resume" in actions
            assert "snooze" in actions
            assert "snooze_expired" in actions
            assert "ack_expired" in actions
            assert "email_sent" in actions
            assert "slack_sent" in actions
            assert any(
                item.get("kind") == "delivery"
                and item.get("channel_label") == "Slack"
                and str(item.get("delivery_stage") or "") in {
                    "ack_timeout_external",
                    "ack_timeout_telegram",
                    "followup_telegram",
                }
                for item in items
            )
    finally:
        object.__setattr__(settings, "alert_email_enabled", old_email_enabled)
        object.__setattr__(settings, "alert_email_to", old_email_to)
        object.__setattr__(settings, "smtp_host", old_smtp_host)
        object.__setattr__(settings, "smtp_user", old_smtp_user)
        object.__setattr__(settings, "alert_webhook_enabled", old_webhook_enabled)
        object.__setattr__(settings, "alert_webhook_url", old_webhook_url)
        object.__setattr__(settings, "alert_webhook_provider", old_webhook_provider)
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", old_ack_timeout)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", old_renotify)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


@pytest.mark.parametrize(
    ("provider", "expected_action"),
    [
        ("slack", "slack_sent"),
        ("telegram", "telegram_sent"),
    ],
)
def test_run_once_layers_email_then_provider_after_ack_expiry(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
    provider: str,
    expected_action: str,
) -> None:
    old_email_enabled = settings.alert_email_enabled
    old_email_to = settings.alert_email_to
    old_smtp_host = settings.smtp_host
    old_smtp_user = settings.smtp_user
    old_email_auto = settings.autotrade_alert_email_auto_enabled
    old_webhook_enabled = settings.alert_webhook_enabled
    old_webhook_url = settings.alert_webhook_url
    old_webhook_provider = settings.alert_webhook_provider
    old_telegram_token = settings.alert_telegram_bot_token
    old_telegram_chat = settings.alert_telegram_chat_id
    old_webhook_auto = settings.autotrade_alert_webhook_auto_enabled
    old_webhook_min = settings.autotrade_alert_webhook_min_severity
    old_ack_timeout = settings.autotrade_alert_ack_timeout_minutes
    old_escalation = settings.autotrade_alert_escalation_minutes
    old_renotify = settings.autotrade_alert_renotify_minutes
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "alert_email_enabled", True)
        object.__setattr__(settings, "alert_email_to", "ops@example.com")
        object.__setattr__(settings, "smtp_host", "smtp.example.com")
        object.__setattr__(settings, "smtp_user", "bot@example.com")
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", True)
        object.__setattr__(settings, "alert_webhook_enabled", True)
        object.__setattr__(settings, "alert_webhook_provider", provider)
        object.__setattr__(settings, "alert_webhook_url", "https://hooks.example.com/autotrade")
        object.__setattr__(settings, "alert_telegram_bot_token", "bot-token" if provider == "telegram" else "")
        object.__setattr__(settings, "alert_telegram_chat_id", "chat-id" if provider == "telegram" else "")
        object.__setattr__(settings, "autotrade_alert_webhook_auto_enabled", True)
        object.__setattr__(settings, "autotrade_alert_webhook_min_severity", "error")
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", 30)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )
        monkeypatch.setattr(autotrade_module.repo, "list_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "sync_from_metrics",
            lambda **kwargs: {"status": {}},
        )
        email_payloads: list[tuple[str, str]] = []
        webhook_payloads: list[dict] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_email",
            lambda subject, body: email_payloads.append((subject, body)) or True,
        )
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_webhook",
            lambda payload: webhook_payloads.append(payload) or True,
        )

        first = auto_trade_service.run_once(force=True)
        assert first["alert_dispatch"]["sent"] is True
        assert first["alert_webhook_dispatch"]["sent"] is False

        active_states = repo.list_active_alert_signal_states(limit=10)
        assert active_states
        alert_key = str(active_states[0]["alert_key"])
        for item in active_states:
            repo.acknowledge_alert_signal_state(
                alert_key=str(item["alert_key"]),
                actor="ops",
            )

        suppressed = auto_trade_service.run_once(force=True)
        assert suppressed["alert_dispatch"]["sent"] is False
        assert suppressed["alert_webhook_dispatch"]["sent"] is False

        repo.override_alert_signal_state_timestamps(
            alert_key=alert_key,
            first_seen_at="2000-01-01T00:00:00+00:00",
            last_seen_at="2000-01-01T00:00:00+00:00",
        )
        with repo.get_conn() as conn:
            conn.execute(
                """
                UPDATE alert_signal_states
                SET acked_at = '2000-01-01T00:00:00+00:00'
                WHERE alert_key = ?
                """,
                (alert_key,),
            )

        reactivated = auto_trade_service.run_once(force=True)
        assert reactivated["alert_dispatch"]["sent"] is True
        assert reactivated["alert_webhook_dispatch"]["sent"] is True
        assert len(email_payloads) == 2
        assert len(webhook_payloads) == 1

        timeline = repo.list_alert_incident_timeline(alert_key=alert_key, limit=20)
        actions = [str(item["action"]) for item in timeline]
        assert "ack_expired" in actions
        assert "email_sent" in actions
        assert expected_action in actions
    finally:
        object.__setattr__(settings, "alert_email_enabled", old_email_enabled)
        object.__setattr__(settings, "alert_email_to", old_email_to)
        object.__setattr__(settings, "smtp_host", old_smtp_host)
        object.__setattr__(settings, "smtp_user", old_smtp_user)
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", old_email_auto)
        object.__setattr__(settings, "alert_webhook_enabled", old_webhook_enabled)
        object.__setattr__(settings, "alert_webhook_url", old_webhook_url)
        object.__setattr__(settings, "alert_webhook_provider", old_webhook_provider)
        object.__setattr__(settings, "alert_telegram_bot_token", old_telegram_token)
        object.__setattr__(settings, "alert_telegram_chat_id", old_telegram_chat)
        object.__setattr__(settings, "autotrade_alert_webhook_auto_enabled", old_webhook_auto)
        object.__setattr__(settings, "autotrade_alert_webhook_min_severity", old_webhook_min)
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", old_ack_timeout)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", old_renotify)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_manual_slack_and_telegram_routes_use_dedicated_channels(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_slack_enabled = settings.alert_slack_enabled
    old_slack_url = settings.alert_slack_webhook_url
    old_telegram_enabled = settings.alert_telegram_enabled
    old_telegram_token = settings.alert_telegram_bot_token
    old_telegram_chat = settings.alert_telegram_chat_id
    old_ack_timeout = settings.autotrade_alert_ack_timeout_minutes
    old_escalation = settings.autotrade_alert_escalation_minutes
    old_renotify = settings.autotrade_alert_renotify_minutes
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "alert_slack_enabled", True)
        object.__setattr__(settings, "alert_slack_webhook_url", "https://hooks.slack.test/services/ops")
        object.__setattr__(settings, "alert_telegram_enabled", True)
        object.__setattr__(settings, "alert_telegram_bot_token", "bot-token")
        object.__setattr__(settings, "alert_telegram_chat_id", "chat-id")
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", 100000)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
        monkeypatch.setattr(
            autotrade_router_module.repo,
            "get_dashboard_metrics",
            lambda: {
                "profit_cockpit": {
                    "today": {"realized_net_profit": 0.0, "sold_count": 0},
                    "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                    "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                    "seller_leaderboard_7d": [],
                    "source_leaderboard_7d": [],
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )
        slack_payloads: list[str] = []
        telegram_payloads: list[str] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_slack",
            lambda text: slack_payloads.append(text) or True,
        )
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_telegram",
            lambda text: telegram_payloads.append(text) or True,
        )

        with TestClient(create_app()) as client:
            cockpit = client.get("/autotrade/cockpit")
            assert cockpit.status_code == 200
            alert_key = str(cockpit.json()["alerts"][0]["alert_key"])
            slack_stage_started_at = (
                datetime.now(timezone.utc) - timedelta(minutes=61)
            ).isoformat()

            repo.override_alert_signal_state_timestamps(
                alert_key=alert_key,
                first_seen_at=slack_stage_started_at,
                last_seen_at=slack_stage_started_at,
            )
            refreshed = client.get("/autotrade/cockpit")
            assert refreshed.status_code == 200
            slack_alert = next(
                item
                for item in refreshed.json()["alerts"]
                if str(item.get("alert_key") or "") == alert_key
            )
            assert slack_alert["delivery_lane"] == "slack"

            slack = client.post("/autotrade/alerts/slack")
            assert slack.status_code == 200
            assert slack.json()["sent"] is True

            ack_again = client.post(
                f"/autotrade/alerts/{alert_key}/ack",
                json={"actor": "ops"},
            )
            assert ack_again.status_code == 200
            with repo.get_conn() as conn:
                conn.execute(
                    """
                    UPDATE alert_signal_states
                    SET acked_at = '2000-01-01T00:00:00+00:00'
                    WHERE alert_key = ?
                    """,
                    (alert_key,),
                )
            reactivated = client.get("/autotrade/cockpit")
            assert reactivated.status_code == 200
            telegram_alert = next(
                item
                for item in reactivated.json()["alerts"]
                if str(item.get("alert_key") or "") == alert_key
            )
            assert telegram_alert["delivery_lane"] == "telegram"

            telegram = client.post("/autotrade/alerts/telegram")
            assert telegram.status_code == 200
            assert telegram.json()["sent"] is True

            timeline = client.get(
                "/autotrade/alerts/events",
                params={"limit": 40, "alert_key": alert_key},
            )
            assert timeline.status_code == 200
            actions = [str(item["action"]) for item in timeline.json()["items"]]
            assert "slack_sent" in actions
            assert "telegram_sent" in actions

        assert slack_payloads
        assert telegram_payloads
    finally:
        object.__setattr__(settings, "alert_slack_enabled", old_slack_enabled)
        object.__setattr__(settings, "alert_slack_webhook_url", old_slack_url)
        object.__setattr__(settings, "alert_telegram_enabled", old_telegram_enabled)
        object.__setattr__(settings, "alert_telegram_bot_token", old_telegram_token)
        object.__setattr__(settings, "alert_telegram_chat_id", old_telegram_chat)
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", old_ack_timeout)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", old_renotify)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_alert_incident_case_actions_persist_and_emit_events(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard = {
        "profit_cockpit": {
            "today": {"realized_net_profit": 0.0, "sold_count": 0},
            "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
            "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
            "seller_leaderboard_7d": [],
            "source_leaderboard_7d": [],
            "inventory": {
                "deployed_capital": 95.0,
                "active_trade_count": 1,
                "listed_trade_count": 1,
                "approved_trade_count": 1,
                "expected_exit_spread": 5.0,
            },
        },
        "forward_validation": {},
    }
    monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)

    with TestClient(create_app()) as client:
        cockpit = client.get("/autotrade/cockpit")
        assert cockpit.status_code == 200
        alert_key = str(cockpit.json()["alerts"][0]["alert_key"])

        assign = client.post(
            f"/autotrade/alerts/{alert_key}/assign",
            json={"actor": "ops", "owner": "alice", "note": "triage owner"},
        )
        assert assign.status_code == 200
        assert assign.json()["state"]["incident_owner"] == "alice"
        assert assign.json()["state"]["incident_status"] == "assigned"

        note = client.post(
            f"/autotrade/alerts/{alert_key}/note",
            json={"actor": "alice", "note": "investigating source saturation"},
        )
        assert note.status_code == 200

        handoff = client.post(
            f"/autotrade/alerts/{alert_key}/handoff",
            json={"actor": "alice", "owner": "bob", "note": "handoff to APAC shift"},
        )
        assert handoff.status_code == 200
        assert handoff.json()["state"]["incident_owner"] == "bob"
        assert handoff.json()["state"]["incident_status"] == "handed_off"

        resolve = client.post(
            f"/autotrade/alerts/{alert_key}/resolve",
            json={"actor": "bob", "note": "issue mitigated"},
        )
        assert resolve.status_code == 200
        assert resolve.json()["state"]["incident_status"] == "resolved"
        assert resolve.json()["state"]["latest_case_note"] == "issue mitigated"

        refreshed = client.get("/autotrade/cockpit")
        assert refreshed.status_code == 200
        refreshed_alert = next(
            item for item in refreshed.json()["alerts"]
            if str(item["alert_key"]) == alert_key
        )
        assert refreshed_alert["incident_owner"] == "bob"
        assert refreshed_alert["incident_status"] == "open"
        assert refreshed_alert["latest_case_note"] == "issue mitigated"

        timeline = client.get(
            "/autotrade/alerts/events",
            params={"limit": 30, "alert_key": alert_key},
        )
        assert timeline.status_code == 200
        actions = [str(item["action"]) for item in timeline.json()["items"]]
        assert "assign" in actions
        assert "note" in actions
        assert "handoff" in actions
        assert "resolve" in actions
        assert "reopened" in actions


def test_cockpit_auto_assigns_owner_from_routing_policy(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    old_escalation = settings.autotrade_alert_escalation_minutes
    old_renotify = settings.autotrade_alert_renotify_minutes
    old_auto_assign = settings.autotrade_incident_auto_assign_enabled
    old_default_owner = settings.autotrade_incident_default_owner
    old_high_owner = settings.autotrade_incident_high_priority_owner
    old_critical_owner = settings.autotrade_incident_critical_priority_owner
    old_slack_owner = settings.autotrade_incident_slack_owner
    old_auto_sla_escalate = settings.autotrade_incident_auto_escalate_on_sla_breach
    try:
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", 30)
        object.__setattr__(settings, "autotrade_incident_auto_assign_enabled", True)
        object.__setattr__(settings, "autotrade_incident_default_owner", "ops_default")
        object.__setattr__(settings, "autotrade_incident_high_priority_owner", "ops_high")
        object.__setattr__(settings, "autotrade_incident_critical_priority_owner", "ops_critical")
        object.__setattr__(settings, "autotrade_incident_slack_owner", "ops_slack")
        object.__setattr__(settings, "autotrade_incident_auto_escalate_on_sla_breach", False)
        dashboard = {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [],
                "inventory": {
                    "deployed_capital": 95.0,
                    "active_trade_count": 1,
                    "listed_trade_count": 1,
                    "approved_trade_count": 1,
                    "expected_exit_spread": 5.0,
                },
            },
            "forward_validation": {},
        }
        monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)

        with TestClient(create_app()) as client:
            initial = client.get("/autotrade/cockpit")
            assert initial.status_code == 200
            alert = initial.json()["alerts"][0]
            alert_key = str(alert["alert_key"])

            aged_at = (datetime.now(timezone.utc) - timedelta(minutes=70)).replace(microsecond=0).isoformat()
            repo.override_alert_signal_state_timestamps(
                alert_key=alert_key,
                first_seen_at=aged_at,
                last_seen_at=aged_at,
            )

            routed = client.get("/autotrade/cockpit")
            assert routed.status_code == 200
            routed_alert = next(
                item for item in routed.json()["alerts"]
                if str(item["alert_key"]) == alert_key
            )
            assert routed_alert["incident_owner"] == "ops_slack"
            assert routed_alert["auto_routed_owner"] == "ops_slack"

            timeline = client.get(
                "/autotrade/alerts/events",
                params={"limit": 20, "alert_key": alert_key},
            )
            assert timeline.status_code == 200
            actions = [str(item["action"]) for item in timeline.json()["items"]]
            assert "auto_assign" in actions
    finally:
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", old_renotify)
        object.__setattr__(settings, "autotrade_incident_auto_assign_enabled", old_auto_assign)
        object.__setattr__(settings, "autotrade_incident_default_owner", old_default_owner)
        object.__setattr__(settings, "autotrade_incident_high_priority_owner", old_high_owner)
        object.__setattr__(settings, "autotrade_incident_critical_priority_owner", old_critical_owner)
        object.__setattr__(settings, "autotrade_incident_slack_owner", old_slack_owner)
        object.__setattr__(settings, "autotrade_incident_auto_escalate_on_sla_breach", old_auto_sla_escalate)


def test_cockpit_owner_routing_uses_rota_schedule_slots(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    old_escalation = settings.autotrade_alert_escalation_minutes
    old_renotify = settings.autotrade_alert_renotify_minutes
    old_auto_assign = settings.autotrade_incident_auto_assign_enabled
    old_slack_owner = settings.autotrade_incident_slack_owner
    old_rota_timezone = settings.autotrade_incident_rota_timezone
    old_slack_schedule = settings.autotrade_incident_slack_owner_schedule
    old_auto_sla_escalate = settings.autotrade_incident_auto_escalate_on_sla_breach
    try:
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", 30)
        object.__setattr__(settings, "autotrade_incident_auto_assign_enabled", True)
        object.__setattr__(settings, "autotrade_incident_slack_owner", "")
        object.__setattr__(settings, "autotrade_incident_rota_timezone", "UTC")
        object.__setattr__(settings, "autotrade_incident_slack_owner_schedule", "daily@00-12=ops_apac;daily@12-24=ops_us")
        object.__setattr__(settings, "autotrade_incident_auto_escalate_on_sla_breach", False)
        dashboard = {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [],
                "inventory": {
                    "deployed_capital": 95.0,
                    "active_trade_count": 1,
                    "listed_trade_count": 1,
                    "approved_trade_count": 1,
                    "expected_exit_spread": 5.0,
                },
            },
            "forward_validation": {},
        }
        monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)

        with TestClient(create_app()) as client:
            monkeypatch.setattr(
                autotrade_alerting_module,
                "_incident_rota_now",
                lambda: datetime(2026, 4, 5, 9, 0, tzinfo=timezone.utc),
            )
            initial = client.get("/autotrade/cockpit")
            assert initial.status_code == 200
            alert = initial.json()["alerts"][0]
            alert_key = str(alert["alert_key"])

            aged_at = (datetime.now(timezone.utc) - timedelta(minutes=70)).replace(microsecond=0).isoformat()
            repo.override_alert_signal_state_timestamps(
                alert_key=alert_key,
                first_seen_at=aged_at,
                last_seen_at=aged_at,
            )
            first_routed = client.get("/autotrade/cockpit")
            assert first_routed.status_code == 200
            first_alert = next(
                item for item in first_routed.json()["alerts"]
                if str(item["alert_key"]) == alert_key
            )
            assert first_alert["incident_owner"] == "ops_apac"

            monkeypatch.setattr(
                autotrade_alerting_module,
                "_incident_rota_now",
                lambda: datetime(2026, 4, 5, 18, 0, tzinfo=timezone.utc),
            )
            second_routed = client.get("/autotrade/cockpit")
            assert second_routed.status_code == 200
            second_alert = next(
                item for item in second_routed.json()["alerts"]
                if str(item["alert_key"]) == alert_key
            )
            assert second_alert["incident_owner"] == "ops_us"

            timeline = client.get(
                "/autotrade/alerts/events",
                params={"limit": 20, "alert_key": alert_key},
            )
            assert timeline.status_code == 200
            actions = [str(item["action"]) for item in timeline.json()["items"]]
            assert "auto_assign" in actions
            assert "auto_handoff" in actions
    finally:
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", old_renotify)
        object.__setattr__(settings, "autotrade_incident_auto_assign_enabled", old_auto_assign)
        object.__setattr__(settings, "autotrade_incident_slack_owner", old_slack_owner)
        object.__setattr__(settings, "autotrade_incident_rota_timezone", old_rota_timezone)
        object.__setattr__(settings, "autotrade_incident_slack_owner_schedule", old_slack_schedule)
        object.__setattr__(settings, "autotrade_incident_auto_escalate_on_sla_breach", old_auto_sla_escalate)


def test_sla_breach_auto_escalates_priority_and_handoffs_owner(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    old_escalation = settings.autotrade_alert_escalation_minutes
    old_renotify = settings.autotrade_alert_renotify_minutes
    old_auto_assign = settings.autotrade_incident_auto_assign_enabled
    old_auto_sla_escalate = settings.autotrade_incident_auto_escalate_on_sla_breach
    old_default_owner = settings.autotrade_incident_default_owner
    old_high_owner = settings.autotrade_incident_high_priority_owner
    old_critical_owner = settings.autotrade_incident_critical_priority_owner
    old_slack_owner = settings.autotrade_incident_slack_owner
    try:
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", 30)
        object.__setattr__(settings, "autotrade_incident_auto_assign_enabled", True)
        object.__setattr__(settings, "autotrade_incident_auto_escalate_on_sla_breach", True)
        object.__setattr__(settings, "autotrade_incident_default_owner", "ops_default")
        object.__setattr__(settings, "autotrade_incident_high_priority_owner", "ops_high")
        object.__setattr__(settings, "autotrade_incident_critical_priority_owner", "ops_critical")
        object.__setattr__(settings, "autotrade_incident_slack_owner", "ops_slack")
        dashboard = {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [],
                "inventory": {
                    "deployed_capital": 95.0,
                    "active_trade_count": 1,
                    "listed_trade_count": 1,
                    "approved_trade_count": 1,
                    "expected_exit_spread": 5.0,
                },
            },
            "forward_validation": {},
        }
        monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)

        with TestClient(create_app()) as client:
            initial = client.get("/autotrade/cockpit")
            assert initial.status_code == 200
            alert = initial.json()["alerts"][0]
            alert_key = str(alert["alert_key"])
            assert alert["incident_owner"] == "ops_default"

            aged_at = (datetime.now(timezone.utc) - timedelta(minutes=70)).replace(microsecond=0).isoformat()
            repo.override_alert_signal_state_timestamps(
                alert_key=alert_key,
                first_seen_at=aged_at,
                last_seen_at=aged_at,
            )

            breached = client.get("/autotrade/cockpit")
            assert breached.status_code == 200
            breached_alert = next(
                item for item in breached.json()["alerts"]
                if str(item["alert_key"]) == alert_key
            )
            assert breached_alert["incident_priority"] == "critical"
            assert breached_alert["incident_owner"] == "ops_critical"

            timeline = client.get(
                "/autotrade/alerts/events",
                params={"limit": 20, "alert_key": alert_key},
            )
            assert timeline.status_code == 200
            actions = [str(item["action"]) for item in timeline.json()["items"]]
            assert "sla_breached" in actions
            assert "auto_handoff" in actions
    finally:
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", old_renotify)
        object.__setattr__(settings, "autotrade_incident_auto_assign_enabled", old_auto_assign)
        object.__setattr__(settings, "autotrade_incident_auto_escalate_on_sla_breach", old_auto_sla_escalate)
        object.__setattr__(settings, "autotrade_incident_default_owner", old_default_owner)
        object.__setattr__(settings, "autotrade_incident_high_priority_owner", old_high_owner)
        object.__setattr__(settings, "autotrade_incident_critical_priority_owner", old_critical_owner)
        object.__setattr__(settings, "autotrade_incident_slack_owner", old_slack_owner)


def test_cleared_alert_auto_resolves_incident_without_manual_action(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_auto_approve_enabled = settings.auto_approve_enabled
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "auto_approve_enabled", True)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
        active_dashboard = {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [],
                "inventory": {
                    "deployed_capital": 95.0,
                    "active_trade_count": 1,
                    "listed_trade_count": 1,
                    "approved_trade_count": 1,
                    "expected_exit_spread": 5.0,
                },
            },
            "forward_validation": {},
        }
        cleared_dashboard = {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [],
                "inventory": {
                    "deployed_capital": 0.0,
                    "active_trade_count": 0,
                    "listed_trade_count": 0,
                    "approved_trade_count": 0,
                    "expected_exit_spread": 0.0,
                },
            },
            "forward_validation": {},
        }
        current_dashboard = {"value": active_dashboard}
        monkeypatch.setattr(
            autotrade_router_module.repo,
            "get_dashboard_metrics",
            lambda: current_dashboard["value"],
        )

        with TestClient(create_app()) as client:
            first = client.get("/autotrade/cockpit")
            assert first.status_code == 200
            alert_key = str(first.json()["alerts"][0]["alert_key"])

            current_dashboard["value"] = cleared_dashboard
            second = client.get("/autotrade/cockpit")
            assert second.status_code == 200
            assert second.json()["alerts"] == []

            state = repo.get_alert_signal_state(alert_key)
            assert state is not None
            assert state["incident_status"] == "resolved"
            assert state["resolved_at"]

            timeline = client.get(
                "/autotrade/alerts/events",
                params={"limit": 20, "alert_key": alert_key},
            )
            assert timeline.status_code == 200
            actions = [str(item["action"]) for item in timeline.json()["items"]]
            assert "cleared" in actions
    finally:
        object.__setattr__(settings, "auto_approve_enabled", old_auto_approve_enabled)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_resolved_incident_reopens_when_alert_stays_active(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard = {
        "profit_cockpit": {
            "today": {"realized_net_profit": 0.0, "sold_count": 0},
            "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
            "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
            "seller_leaderboard_7d": [],
            "source_leaderboard_7d": [],
            "inventory": {
                "deployed_capital": 95.0,
                "active_trade_count": 1,
                "listed_trade_count": 1,
                "approved_trade_count": 1,
                "expected_exit_spread": 5.0,
            },
        },
        "forward_validation": {},
    }
    monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)

    with TestClient(create_app()) as client:
        cockpit = client.get("/autotrade/cockpit")
        assert cockpit.status_code == 200
        alert_key = str(cockpit.json()["alerts"][0]["alert_key"])

        resolve = client.post(
            f"/autotrade/alerts/{alert_key}/resolve",
            json={"actor": "ops", "note": "resolved locally"},
        )
        assert resolve.status_code == 200
        assert resolve.json()["state"]["incident_status"] == "resolved"

        reopened = client.get("/autotrade/cockpit")
        assert reopened.status_code == 200
        reopened_alert = next(
            item for item in reopened.json()["alerts"]
            if str(item["alert_key"]) == alert_key
        )
        assert reopened_alert["incident_status"] == "open"

        timeline = client.get(
            "/autotrade/alerts/events",
            params={"limit": 20, "alert_key": alert_key},
        )
        assert timeline.status_code == 200
        actions = [str(item["action"]) for item in timeline.json()["items"]]
        assert "resolve" in actions
        assert "reopened" in actions


def test_alert_auto_resolves_when_condition_clears(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_auto_approve_enabled = settings.auto_approve_enabled
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    active_dashboard = {
        "profit_cockpit": {
            "today": {"realized_net_profit": 0.0, "sold_count": 0},
            "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
            "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
            "seller_leaderboard_7d": [],
            "source_leaderboard_7d": [],
            "inventory": {
                "deployed_capital": 95.0,
                "active_trade_count": 1,
                "listed_trade_count": 1,
                "approved_trade_count": 1,
                "expected_exit_spread": 5.0,
            },
        },
        "forward_validation": {},
    }
    cleared_dashboard = {
        "profit_cockpit": {
            "today": {"realized_net_profit": 0.0, "sold_count": 0},
            "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
            "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
            "seller_leaderboard_7d": [],
            "source_leaderboard_7d": [],
            "inventory": {
                "deployed_capital": 20.0,
                "active_trade_count": 0,
                "listed_trade_count": 0,
                "approved_trade_count": 0,
                "expected_exit_spread": 0.0,
            },
        },
        "forward_validation": {},
    }
    current_dashboard = {"value": active_dashboard}
    monkeypatch.setattr(
        autotrade_router_module.repo,
        "get_dashboard_metrics",
        lambda: current_dashboard["value"],
    )
    try:
        object.__setattr__(settings, "auto_approve_enabled", True)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)

        with TestClient(create_app()) as client:
            first = client.get("/autotrade/cockpit")
            assert first.status_code == 200
            alert_key = str(first.json()["alerts"][0]["alert_key"])

            current_dashboard["value"] = cleared_dashboard
            second = client.get("/autotrade/cockpit")
            assert second.status_code == 200
            assert second.json()["alerts"] == []

            state = repo.get_alert_signal_state(alert_key)
            assert state is not None
            assert state["incident_status"] == "resolved"
            assert state["resolved_at"]

            timeline = client.get(
                "/autotrade/alerts/events",
                params={"limit": 20, "alert_key": alert_key},
            )
            assert timeline.status_code == 200
            actions = [str(item["action"]) for item in timeline.json()["items"]]
            assert "cleared" in actions
    finally:
        object.__setattr__(settings, "auto_approve_enabled", old_auto_approve_enabled)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_alert_incident_priority_updates_sla_and_timeline(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dashboard = {
        "profit_cockpit": {
            "today": {"realized_net_profit": 0.0, "sold_count": 0},
            "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
            "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
            "seller_leaderboard_7d": [],
            "source_leaderboard_7d": [],
            "inventory": {
                "deployed_capital": 95.0,
                "active_trade_count": 1,
                "listed_trade_count": 1,
                "approved_trade_count": 1,
                "expected_exit_spread": 5.0,
            },
        },
        "forward_validation": {},
    }
    monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)

    with TestClient(create_app()) as client:
        cockpit = client.get("/autotrade/cockpit")
        assert cockpit.status_code == 200
        alert_key = str(cockpit.json()["alerts"][0]["alert_key"])

        priority = client.post(
            f"/autotrade/alerts/{alert_key}/priority",
            json={"actor": "ops", "priority": "critical", "note": "sev-1 customer impact"},
        )
        assert priority.status_code == 200
        state = priority.json()["state"]
        assert state["incident_priority"] == "critical"
        assert state["incident_sla_due_at"]

        refreshed = client.get("/autotrade/cockpit")
        assert refreshed.status_code == 200
        refreshed_alert = next(
            item for item in refreshed.json()["alerts"]
            if str(item["alert_key"]) == alert_key
        )
        assert refreshed_alert["incident_priority"] == "critical"
        assert refreshed_alert["sla_due_at"]

        timeline = client.get(
            "/autotrade/alerts/events",
            params={"limit": 20, "alert_key": alert_key},
        )
        assert timeline.status_code == 200
        actions = [str(item["action"]) for item in timeline.json()["items"]]
        assert "priority" in actions


def test_cockpit_alerts_include_incident_priority_and_sla_fields(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    old_escalation = settings.autotrade_alert_escalation_minutes
    old_renotify = settings.autotrade_alert_renotify_minutes
    old_auto_sla_escalate = settings.autotrade_incident_auto_escalate_on_sla_breach
    try:
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", 30)
        object.__setattr__(settings, "autotrade_incident_auto_escalate_on_sla_breach", False)
        dashboard = {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [],
                "inventory": {
                    "deployed_capital": 95.0,
                    "active_trade_count": 1,
                    "listed_trade_count": 1,
                    "approved_trade_count": 1,
                    "expected_exit_spread": 5.0,
                },
            },
            "forward_validation": {},
        }
        monkeypatch.setattr(autotrade_router_module.repo, "get_dashboard_metrics", lambda: dashboard)

        with TestClient(create_app()) as client:
            cockpit = client.get("/autotrade/cockpit")
            assert cockpit.status_code == 200
            payload = cockpit.json()
            alert = payload["alerts"][0]
            assert alert["incident_priority"] == "normal"
            assert alert["sla_minutes"] == 240
            assert alert["sla_due_at"]
            assert "incident_automation" in payload
            assert payload["incident_automation"]["auto_assign_enabled"] in {True, False}
            assert payload["incident_automation"]["auto_resolve_enabled"] in {True, False}
            assert payload["incident_automation"]["auto_escalate_on_sla_breach"] in {True, False}

            aged_at = (datetime.now(timezone.utc) - timedelta(minutes=70)).replace(microsecond=0).isoformat()
            repo.override_alert_signal_state_timestamps(
                alert_key=str(alert["alert_key"]),
                first_seen_at=aged_at,
                last_seen_at=aged_at,
            )

            escalated = client.get("/autotrade/cockpit")
            assert escalated.status_code == 200
            escalated_alert = next(
                item for item in escalated.json()["alerts"]
                if str(item["alert_key"]) == str(alert["alert_key"])
            )
            assert escalated_alert["incident_priority"] == "high"
            assert escalated_alert["sla_minutes"] == 60
            assert escalated_alert["sla_due_at"]
    finally:
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", old_renotify)
        object.__setattr__(settings, "autotrade_incident_auto_escalate_on_sla_breach", old_auto_sla_escalate)


def test_run_once_layers_dedicated_email_slack_then_telegram(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_email_enabled = settings.alert_email_enabled
    old_email_to = settings.alert_email_to
    old_smtp_host = settings.smtp_host
    old_smtp_user = settings.smtp_user
    old_email_auto = settings.autotrade_alert_email_auto_enabled
    old_slack_enabled = settings.alert_slack_enabled
    old_slack_url = settings.alert_slack_webhook_url
    old_slack_auto = settings.autotrade_alert_slack_auto_enabled
    old_slack_min = settings.autotrade_alert_slack_min_severity
    old_slack_cooldown = settings.autotrade_alert_slack_cooldown_minutes
    old_slack_stage = settings.autotrade_alert_slack_min_stage
    old_telegram_enabled = settings.alert_telegram_enabled
    old_telegram_token = settings.alert_telegram_bot_token
    old_telegram_chat = settings.alert_telegram_chat_id
    old_telegram_auto = settings.autotrade_alert_telegram_auto_enabled
    old_telegram_min = settings.autotrade_alert_telegram_min_severity
    old_telegram_cooldown = settings.autotrade_alert_telegram_cooldown_minutes
    old_telegram_stage = settings.autotrade_alert_telegram_min_stage
    old_webhook_auto = settings.autotrade_alert_webhook_auto_enabled
    old_ack_timeout = settings.autotrade_alert_ack_timeout_minutes
    old_escalation = settings.autotrade_alert_escalation_minutes
    old_renotify = settings.autotrade_alert_renotify_minutes
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    try:
        object.__setattr__(settings, "alert_email_enabled", True)
        object.__setattr__(settings, "alert_email_to", "ops@example.com")
        object.__setattr__(settings, "smtp_host", "smtp.example.com")
        object.__setattr__(settings, "smtp_user", "bot@example.com")
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", True)
        object.__setattr__(settings, "alert_slack_enabled", True)
        object.__setattr__(settings, "alert_slack_webhook_url", "https://hooks.slack.com/services/T000/B000/XXX")
        object.__setattr__(settings, "autotrade_alert_slack_auto_enabled", True)
        object.__setattr__(settings, "autotrade_alert_slack_min_severity", "error")
        object.__setattr__(settings, "autotrade_alert_slack_cooldown_minutes", 15)
        object.__setattr__(settings, "autotrade_alert_slack_min_stage", 1)
        object.__setattr__(settings, "alert_telegram_enabled", True)
        object.__setattr__(settings, "alert_telegram_bot_token", "123:abc")
        object.__setattr__(settings, "alert_telegram_chat_id", "-100123")
        object.__setattr__(settings, "autotrade_alert_telegram_auto_enabled", True)
        object.__setattr__(settings, "autotrade_alert_telegram_min_severity", "error")
        object.__setattr__(settings, "autotrade_alert_telegram_cooldown_minutes", 15)
        object.__setattr__(settings, "autotrade_alert_telegram_min_stage", 2)
        object.__setattr__(settings, "autotrade_alert_webhook_auto_enabled", False)
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", 60)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", 30)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 100.0)
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
                    "inventory": {
                        "deployed_capital": 95.0,
                        "active_trade_count": 1,
                        "listed_trade_count": 1,
                        "approved_trade_count": 1,
                        "expected_exit_spread": 5.0,
                    },
                },
                "forward_validation": {},
            },
        )
        monkeypatch.setattr(autotrade_module.repo, "list_opportunities", lambda *args, **kwargs: [])
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "sync_from_metrics",
            lambda **kwargs: {"status": {}},
        )

        email_payloads: list[tuple[str, str]] = []
        slack_payloads: list[str] = []
        telegram_payloads: list[str] = []
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_email",
            lambda subject, body: email_payloads.append((subject, body)) or True,
        )
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_slack",
            lambda text: slack_payloads.append(text) or True,
        )
        monkeypatch.setattr(
            autotrade_alerting_module,
            "send_alert_telegram",
            lambda text: telegram_payloads.append(text) or True,
        )

        first = auto_trade_service.run_once(force=True)
        assert first["alert_dispatch"]["sent"] is True
        assert first["alert_slack_dispatch"]["sent"] is False
        assert first["alert_telegram_dispatch"]["sent"] is False

        active_states = repo.list_active_alert_signal_states(limit=10)
        assert active_states
        alert_key = str(active_states[0]["alert_key"])

        stage_one_at = (datetime.now(timezone.utc) - timedelta(minutes=70)).replace(microsecond=0).isoformat()
        repo.override_alert_signal_state_timestamps(
            alert_key=alert_key,
            first_seen_at=stage_one_at,
            last_seen_at=stage_one_at,
        )
        second = auto_trade_service.run_once(force=True)
        assert second["alert_slack_dispatch"]["sent"] is True
        assert second["alert_telegram_dispatch"]["sent"] is False

        stage_two_at = (datetime.now(timezone.utc) - timedelta(minutes=100)).replace(microsecond=0).isoformat()
        repo.override_alert_signal_state_timestamps(
            alert_key=alert_key,
            first_seen_at=stage_two_at,
            last_seen_at=stage_two_at,
        )
        third = auto_trade_service.run_once(force=True)
        assert third["alert_telegram_dispatch"]["sent"] is True

        timeline = autotrade_alerting_module.list_alert_incident_timeline(
            alert_key=alert_key,
            limit=30,
        )
        actions = [str(item["action"]) for item in timeline["items"]]
        assert "email_sent" in actions
        assert "slack_sent" in actions
        assert "telegram_sent" in actions
        assert len(email_payloads) >= 1
        assert len(slack_payloads) == 1
        assert len(telegram_payloads) == 1
    finally:
        object.__setattr__(settings, "alert_email_enabled", old_email_enabled)
        object.__setattr__(settings, "alert_email_to", old_email_to)
        object.__setattr__(settings, "smtp_host", old_smtp_host)
        object.__setattr__(settings, "smtp_user", old_smtp_user)
        object.__setattr__(settings, "autotrade_alert_email_auto_enabled", old_email_auto)
        object.__setattr__(settings, "alert_slack_enabled", old_slack_enabled)
        object.__setattr__(settings, "alert_slack_webhook_url", old_slack_url)
        object.__setattr__(settings, "autotrade_alert_slack_auto_enabled", old_slack_auto)
        object.__setattr__(settings, "autotrade_alert_slack_min_severity", old_slack_min)
        object.__setattr__(settings, "autotrade_alert_slack_cooldown_minutes", old_slack_cooldown)
        object.__setattr__(settings, "autotrade_alert_slack_min_stage", old_slack_stage)
        object.__setattr__(settings, "alert_telegram_enabled", old_telegram_enabled)
        object.__setattr__(settings, "alert_telegram_bot_token", old_telegram_token)
        object.__setattr__(settings, "alert_telegram_chat_id", old_telegram_chat)
        object.__setattr__(settings, "autotrade_alert_telegram_auto_enabled", old_telegram_auto)
        object.__setattr__(settings, "autotrade_alert_telegram_min_severity", old_telegram_min)
        object.__setattr__(settings, "autotrade_alert_telegram_cooldown_minutes", old_telegram_cooldown)
        object.__setattr__(settings, "autotrade_alert_telegram_min_stage", old_telegram_stage)
        object.__setattr__(settings, "autotrade_alert_webhook_auto_enabled", old_webhook_auto)
        object.__setattr__(settings, "autotrade_alert_ack_timeout_minutes", old_ack_timeout)
        object.__setattr__(settings, "autotrade_alert_escalation_minutes", old_escalation)
        object.__setattr__(settings, "autotrade_alert_renotify_minutes", old_renotify)
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)


def test_manual_source_freeze_override_blocks_autotrade(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/autotrade/source-controls/manual-action",
            json={
                "source": "alpha",
                "action": "freeze",
                "reason": "manual hold",
                "actor": "ops",
                "duration_hours": 12,
            },
        )
    assert response.status_code == 200

    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "source_lane": "expand",
                        "block_new_approvals": False,
                        "strategy_mode": "widen",
                        "strategy_summary": "auto wants alpha",
                        "threshold_delta": {"min_score": 0.0, "min_roi": 0.0, "max_risk_score": 0.0},
                        "intake_multiplier": 1.0,
                        "capital_multiplier": 1.0,
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
                "score": 95.0,
                "roi": 0.4,
                "source": "alpha",
                "seller_id": "seller-a",
                "item_type": "manual_card",
                "normalized_key": "manual_card:Same",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
        ],
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "sync_from_metrics",
        lambda **kwargs: {"status": {}},
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "runtime_control",
        lambda **kwargs: {
            "state": "normal",
            "blocked": False,
            "threshold_delta": {},
            "intake_multiplier": 1.0,
        },
    )
    monkeypatch.setattr(
        autotrade_module.repo,
        "approve_opportunity_idempotent",
        lambda **kwargs: {"created": True, "idempotent": False, "trade_id": 9999},
    )

    result = auto_trade_service.run_once(force=True)

    assert result["approved"] == 0
    assert result["skipped_source_batch_cap"] == 1

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


def test_validation_baseline_can_be_tune_ready_before_scale_ready(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_single_account_mode = settings.single_account_mode
    object.__setattr__(settings, "single_account_mode", True)
    try:
        monkeypatch.setattr(
            autotrade_module.repo,
            "get_dashboard_metrics",
            lambda: {
                "profit_cockpit": {
                    "today": {"sold_count": 1, "realized_net_profit": 18.0},
                    "last_7d": {
                        "sold_count": 8,
                        "profit_hit_rate": 0.625,
                        "avg_realized_roi": 0.1,
                        "realized_net_profit": 96.0,
                    },
                    "inventory": {"deployed_capital": 0.0},
                    "source_leaderboard_7d": [
                        {"source": "alpha", "sold_count": 5, "realized_net_profit": 66.0},
                        {"source": "beta", "sold_count": 3, "realized_net_profit": 30.0},
                    ],
                },
                "forward_validation": {
                    "active_batch": None,
                    "recent_batches": [
                        {
                            "id": 51,
                            "name": "batch-51",
                            "status": "closed",
                            "sold_count": 6,
                            "profit_hit_rate": 0.72,
                            "avg_realized_roi": 0.14,
                            "avg_holding_days": 4.0,
                            "realized_net_profit": 120.0,
                        },
                        {
                            "id": 50,
                            "name": "batch-50",
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
        monkeypatch.setattr(
            autotrade_module.repo,
            "get_execution_log_summary",
            lambda limit=24, dry_run=None: {
                "sample_size": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "business_ban_count": 0,
                "last_failure_at": "",
                "by_action": {},
            },
        )
        monkeypatch.setattr(
            autotrade_module.monitor_service,
            "status",
            lambda: {
                "circuit_open": False,
                "health": {
                    "samples": 12,
                    "success_rate": 0.9,
                    "guard_triggered": False,
                },
            },
        )
        monkeypatch.setattr(
            autotrade_module.risk_overrides_service,
            "source_status_summary",
            lambda limit=200: {"active_freeze_count": 0, "items": []},
        )
        monkeypatch.setattr(
            autotrade_module.risk_overrides_service,
            "cluster_status_summary",
            lambda limit=200: {"active_freeze_count": 0, "items": []},
        )

        baseline = auto_trade_service._validation_baseline_snapshot()
    finally:
        object.__setattr__(settings, "single_account_mode", old_single_account_mode)

    assert baseline["ready_for_tune"] is True
    assert baseline["ready_for_scale"] is False
    assert baseline["ready"] is False
    assert baseline["status"] == "observe"
    assert "execution_live_readiness" in baseline["blocking_codes"]
    assert "execution_live_samples" in baseline["blocking_codes"]
    assert baseline["timeline"]["direction"] == "improving"
    assert len(baseline["timeline"]["points"]) == 2
    assert len(baseline["snapshot_history"]["hourly"]) >= 1
    assert len(baseline["snapshot_history"]["daily"]) >= 1


def test_validation_baseline_trend_detects_improving_batches(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_single_account_mode = settings.single_account_mode
    object.__setattr__(settings, "single_account_mode", True)
    try:
        monkeypatch.setattr(
            autotrade_module.repo,
            "get_dashboard_metrics",
            lambda: {
                "profit_cockpit": {
                    "today": {"sold_count": 1, "realized_net_profit": 18.0},
                    "last_7d": {
                        "sold_count": 8,
                        "profit_hit_rate": 0.625,
                        "avg_realized_roi": 0.1,
                        "realized_net_profit": 96.0,
                    },
                    "inventory": {"deployed_capital": 0.0},
                    "source_leaderboard_7d": [
                        {"source": "alpha", "sold_count": 5, "realized_net_profit": 66.0},
                        {"source": "beta", "sold_count": 3, "realized_net_profit": 30.0},
                    ],
                },
                "forward_validation": {
                    "active_batch": None,
                    "recent_batches": [
                        {
                            "id": 81,
                            "name": "batch-81",
                            "status": "closed",
                            "sold_count": 6,
                            "profit_hit_rate": 0.78,
                            "avg_realized_roi": 0.16,
                            "avg_holding_days": 3.0,
                            "realized_net_profit": 150.0,
                        },
                        {
                            "id": 80,
                            "name": "batch-80",
                            "status": "closed",
                            "sold_count": 3,
                            "profit_hit_rate": 0.34,
                            "avg_realized_roi": 0.02,
                            "avg_holding_days": 12.0,
                            "realized_net_profit": -12.0,
                        },
                    ],
                },
            },
        )
        monkeypatch.setattr(
            autotrade_module.repo,
            "get_execution_log_summary",
            lambda limit=24, dry_run=None: {
                "sample_size": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "business_ban_count": 0,
                "last_failure_at": "",
                "by_action": {},
            },
        )
        monkeypatch.setattr(
            autotrade_module.monitor_service,
            "status",
            lambda: {
                "circuit_open": False,
                "health": {
                    "samples": 12,
                    "success_rate": 0.9,
                    "guard_triggered": False,
                },
            },
        )
        monkeypatch.setattr(
            autotrade_module.risk_overrides_service,
            "source_status_summary",
            lambda limit=200: {"active_freeze_count": 0, "items": []},
        )
        monkeypatch.setattr(
            autotrade_module.risk_overrides_service,
            "cluster_status_summary",
            lambda limit=200: {"active_freeze_count": 0, "items": []},
        )

        baseline = auto_trade_service._validation_baseline_snapshot()
    finally:
        object.__setattr__(settings, "single_account_mode", old_single_account_mode)

    assert baseline["timeline"]["direction"] == "improving"
    assert baseline["timeline"]["delta_score"] > 0
    assert baseline["snapshot_history"]["hourly"][-1]["direction"] == "improving"


def test_maybe_auto_apply_tuning_uses_tune_baseline_in_single_account_mode(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_single_account_mode = settings.single_account_mode
    object.__setattr__(settings, "single_account_mode", True)
    auto_trade_service.update_config(
        tuning_auto_apply_enabled=True,
        tuning_cooldown_hours=0,
        tuning_min_closed_batches=2,
        tuning_latest_min_sold_count=5,
        tuning_previous_min_sold_count=3,
    )
    try:
        monkeypatch.setattr(
            autotrade_module.repo,
            "get_dashboard_metrics",
            lambda: {
                "profit_cockpit": {
                    "today": {"sold_count": 1, "realized_net_profit": 18.0},
                    "last_7d": {
                        "sold_count": 8,
                        "profit_hit_rate": 0.625,
                        "avg_realized_roi": 0.1,
                        "realized_net_profit": 96.0,
                    },
                    "inventory": {"deployed_capital": 0.0},
                    "source_leaderboard_7d": [
                        {"source": "alpha", "sold_count": 5, "realized_net_profit": 66.0},
                        {"source": "beta", "sold_count": 3, "realized_net_profit": 30.0},
                    ],
                },
                "forward_validation": {
                    "active_batch": None,
                    "recent_batches": [
                        {
                            "id": 61,
                            "name": "batch-61",
                            "status": "closed",
                            "sold_count": 6,
                            "profit_hit_rate": 0.72,
                            "avg_realized_roi": 0.14,
                            "avg_holding_days": 4.0,
                            "realized_net_profit": 120.0,
                        },
                        {
                            "id": 60,
                            "name": "batch-60",
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
        monkeypatch.setattr(
            autotrade_module.repo,
            "get_execution_log_summary",
            lambda limit=24, dry_run=None: {
                "sample_size": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "business_ban_count": 0,
                "last_failure_at": "",
                "by_action": {},
            },
        )
        monkeypatch.setattr(
            autotrade_module.monitor_service,
            "status",
            lambda: {
                "circuit_open": False,
                "health": {
                    "samples": 12,
                    "success_rate": 0.9,
                    "guard_triggered": False,
                },
            },
        )
        monkeypatch.setattr(
            autotrade_module.risk_overrides_service,
            "source_status_summary",
            lambda limit=200: {"active_freeze_count": 0, "items": []},
        )
        monkeypatch.setattr(
            autotrade_module.risk_overrides_service,
            "cluster_status_summary",
            lambda limit=200: {"active_freeze_count": 0, "items": []},
        )

        result = auto_trade_service.maybe_auto_apply_tuning(
            trigger_source="forward_validation_close:61",
            applied_by="pytest_autotune",
        )
    finally:
        object.__setattr__(settings, "single_account_mode", old_single_account_mode)

    assert result["applied"] is True
    assert result["evaluation"]["validation_baseline"]["ready_for_tune"] is True
    assert result["evaluation"]["validation_baseline"]["ready_for_scale"] is False
    assert result["status"]["min_score"] == 56.0
    assert result["status"]["min_roi"] == 0.165
    assert result["status"]["max_risk_score"] == 44.0


def test_run_once_blocks_when_single_account_validation_baseline_not_ready(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_single_account_mode = settings.single_account_mode
    object.__setattr__(settings, "single_account_mode", True)
    try:
        monkeypatch.setattr(
            autotrade_module.repo,
            "get_dashboard_metrics",
            lambda: {
                "profit_cockpit": {
                    "today": {"sold_count": 0, "realized_net_profit": 0.0},
                    "last_7d": {
                        "sold_count": 2,
                        "profit_hit_rate": 0.5,
                        "avg_realized_roi": 0.03,
                        "realized_net_profit": 12.0,
                    },
                    "inventory": {"deployed_capital": 0.0},
                    "source_leaderboard_7d": [
                        {
                            "source": "pytest-source",
                            "sold_count": 2,
                            "realized_net_profit": 12.0,
                            "profit_hit_rate": 0.5,
                            "avg_realized_roi": 0.03,
                        }
                    ],
                },
                "forward_validation": {
                    "active_batch": None,
                    "recent_batches": [],
                },
            },
        )
        monkeypatch.setattr(
            autotrade_module.repo,
            "get_execution_log_summary",
            lambda limit=24, dry_run=None: {
                "sample_size": 0,
                "success_count": 0,
                "failure_count": 0,
                "success_rate": 0.0,
                "failure_rate": 0.0,
                "business_ban_count": 0,
                "last_failure_at": "",
                "by_action": {},
            },
        )
        monkeypatch.setattr(
            autotrade_module.repo,
            "list_opportunities",
            lambda *args, **kwargs: pytest.fail("should not reach opportunity approval"),
        )

        result = auto_trade_service.run_once(force=True)
    finally:
        object.__setattr__(settings, "single_account_mode", old_single_account_mode)

    assert result["blocked"] is True
    assert result["reason"] == "single_account_validation_baseline_not_ready"
    assert result["validation_baseline"]["ready"] is False
    assert "recent_sold_count" in result["validation_baseline"]["blocking_codes"]
    assert "source_diversity" in result["validation_baseline"]["blocking_codes"]


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


def test_run_once_skips_non_tradable_item_types(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
                "score": 95.0,
                "roi": 0.4,
                "source": "alpha",
                "seller_id": "seller-noise",
                "item_type": "unknown",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
            {
                "id": 2,
                "score": 95.0,
                "roi": 0.4,
                "source": "alpha",
                "seller_id": "seller-good",
                "item_type": "manual_card",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
        ],
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "sync_from_metrics",
        lambda **kwargs: {"status": {}},
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "runtime_control",
        lambda **kwargs: {
            "state": "normal",
            "blocked": False,
            "threshold_delta": {},
            "intake_multiplier": 1.0,
        },
    )

    approvals: list[dict[str, object]] = []

    def _approve(**kwargs):
        approvals.append(kwargs)
        return {
            "created": True,
            "idempotent": False,
            "trade_id": 4000 + int(kwargs["opportunity_id"]),
        }

    monkeypatch.setattr(autotrade_module.repo, "approve_opportunity_idempotent", _approve)

    result = auto_trade_service.run_once(force=True)

    assert result["approved"] == 1
    assert result["skipped_non_tradable"] == 1
    assert result["opportunity_ids"] == [2]
    assert approvals[0]["opportunity_id"] == 2


def test_run_once_blocks_source_when_source_lane_is_blocked(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "source_lane": "blocked",
                        "block_new_approvals": True,
                        "strategy_mode": "tighten",
                        "strategy_summary": "blocked by live buy failures",
                        "threshold_delta": {
                            "min_score": 8.0,
                            "min_roi": 0.05,
                            "max_risk_score": -8.0,
                        },
                        "intake_multiplier": 0.0,
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
                "score": 95.0,
                "roi": 0.4,
                "source": "alpha",
                "seller_id": "seller-a",
                "item_type": "manual_card",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
        ],
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "sync_from_metrics",
        lambda **kwargs: {"status": {}},
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "runtime_control",
        lambda **kwargs: {
            "state": "normal",
            "blocked": False,
            "threshold_delta": {},
            "intake_multiplier": 1.0,
        },
    )

    approvals: list[dict[str, object]] = []

    def _approve(**kwargs):
        approvals.append(kwargs)
        return {
            "created": True,
            "idempotent": False,
            "trade_id": 5000 + int(kwargs["opportunity_id"]),
        }

    monkeypatch.setattr(autotrade_module.repo, "approve_opportunity_idempotent", _approve)

    result = auto_trade_service.run_once(force=True)

    assert result["approved"] == 0
    assert result["skipped_source_batch_cap"] == 1
    assert approvals == []
    assert result["source_position_controls"][0]["source_lane"] == "blocked"
    assert result["source_position_controls"][0]["batch_cap"] == 0


def test_run_once_allows_observe_source_with_small_flow(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "source_lane": "observe",
                        "block_new_approvals": False,
                        "strategy_mode": "tighten",
                        "strategy_summary": "buy recovery observe",
                        "threshold_delta": {
                            "min_score": 2.0,
                            "min_roi": 0.01,
                            "max_risk_score": -2.0,
                        },
                        "intake_multiplier": 0.4,
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
                "score": 95.0,
                "roi": 0.4,
                "source": "alpha",
                "seller_id": "seller-a",
                "item_type": "manual_card",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
        ],
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "sync_from_metrics",
        lambda **kwargs: {"status": {}},
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "runtime_control",
        lambda **kwargs: {
            "state": "normal",
            "blocked": False,
            "threshold_delta": {},
            "intake_multiplier": 1.0,
        },
    )

    approvals: list[dict[str, object]] = []

    def _approve(**kwargs):
        approvals.append(kwargs)
        return {
            "created": True,
            "idempotent": False,
            "trade_id": 6000 + int(kwargs["opportunity_id"]),
        }

    monkeypatch.setattr(autotrade_module.repo, "approve_opportunity_idempotent", _approve)

    result = auto_trade_service.run_once(force=True)

    assert result["approved"] == 1
    assert approvals[0]["opportunity_id"] == 1
    assert result["source_position_controls"][0]["source_lane"] == "observe"
    assert result["source_position_controls"][0]["batch_cap"] > 0


def test_run_once_allows_expand_source_at_normal_quota(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        autotrade_module.repo,
        "get_dashboard_metrics",
        lambda: {
            "profit_cockpit": {
                "today": {"realized_net_profit": 0.0, "sold_count": 0},
                "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                "seller_leaderboard_7d": [],
                "source_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "source_lane": "expand",
                        "block_new_approvals": False,
                        "strategy_mode": "widen",
                        "strategy_summary": "buy execution recovered and roi validated",
                        "threshold_delta": {
                            "min_score": 0.0,
                            "min_roi": 0.0,
                            "max_risk_score": 0.0,
                        },
                        "intake_multiplier": 1.0,
                        "capital_multiplier": 1.3,
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
                "score": 95.0,
                "roi": 0.4,
                "source": "alpha",
                "seller_id": "seller-a",
                "item_type": "manual_card",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
            {
                "id": 2,
                "score": 94.0,
                "roi": 0.39,
                "source": "alpha",
                "seller_id": "seller-b",
                "item_type": "manual_card",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
        ],
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "sync_from_metrics",
        lambda **kwargs: {"status": {}},
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "runtime_control",
        lambda **kwargs: {
            "state": "normal",
            "blocked": False,
            "threshold_delta": {},
            "intake_multiplier": 1.0,
        },
    )

    approvals: list[dict[str, object]] = []

    def _approve(**kwargs):
        approvals.append(kwargs)
        return {
            "created": True,
            "idempotent": False,
            "trade_id": 7000 + int(kwargs["opportunity_id"]),
        }

    monkeypatch.setattr(autotrade_module.repo, "approve_opportunity_idempotent", _approve)

    result = auto_trade_service.run_once(force=True)

    assert result["approved"] == 2
    assert len(approvals) == 2
    assert result["source_position_controls"][0]["source_lane"] == "expand"
    assert result["source_position_controls"][0]["batch_cap"] >= 2
    assert result["source_position_controls"][0]["capital_multiplier"] == 1.3
    assert result["source_position_controls"][0]["capital_cap"] >= 260.0


def test_source_position_controls_compete_globally_for_batch_and_capital() -> None:
    controls, items = auto_trade_service._build_source_position_controls(
        batch_limit=3,
        source_strategy_map={
            "alpha": {
                "source": "alpha",
                "source_lane": "expand",
                "block_new_approvals": False,
                "strategy_mode": "widen",
                "strategy_summary": "alpha strong",
                "intake_multiplier": 1.3,
                "capital_multiplier": 1.4,
                "realized_net_profit": 120.0,
            },
            "beta": {
                "source": "beta",
                "source_lane": "observe",
                "block_new_approvals": False,
                "strategy_mode": "tighten",
                "strategy_summary": "beta weaker",
                "intake_multiplier": 0.4,
                "capital_multiplier": 0.6,
                "realized_net_profit": 10.0,
            },
        },
        candidate_rows=[
            {"source": "alpha", "list_price": 100.0},
            {"source": "alpha", "list_price": 100.0},
            {"source": "alpha", "list_price": 100.0},
            {"source": "beta", "list_price": 100.0},
            {"source": "beta", "list_price": 100.0},
        ],
    )

    assert sum(int(item["batch_cap"]) for item in items) <= 3
    assert controls["alpha"]["batch_cap"] >= controls["beta"]["batch_cap"]
    assert controls["alpha"]["capital_cap"] > controls["beta"]["capital_cap"]


def test_source_position_controls_respect_remaining_portfolio_capital(monkeypatch: pytest.MonkeyPatch) -> None:
    old_portfolio_limit = settings.auto_approve_portfolio_max_deployed_capital
    old_source_share = settings.auto_approve_max_source_capital_share
    object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", 250.0)
    object.__setattr__(settings, "auto_approve_max_source_capital_share", 0.6)
    try:
        controls, items = auto_trade_service._build_source_position_controls(
            batch_limit=4,
            source_strategy_map={
                "alpha": {
                    "source": "alpha",
                    "source_lane": "expand",
                    "block_new_approvals": False,
                    "strategy_mode": "widen",
                    "strategy_summary": "alpha strong",
                    "intake_multiplier": 1.2,
                    "capital_multiplier": 1.3,
                    "realized_net_profit": 100.0,
                },
                "beta": {
                    "source": "beta",
                    "source_lane": "observe",
                    "block_new_approvals": False,
                    "strategy_mode": "tighten",
                    "strategy_summary": "beta weaker",
                    "intake_multiplier": 0.6,
                    "capital_multiplier": 0.7,
                    "realized_net_profit": 20.0,
                },
            },
            candidate_rows=[
                {"source": "alpha", "list_price": 20.0},
                {"source": "alpha", "list_price": 20.0},
                {"source": "alpha", "list_price": 20.0},
                {"source": "beta", "list_price": 20.0},
                {"source": "beta", "list_price": 20.0},
            ],
            metrics={"profit_cockpit": {"inventory": {"deployed_capital": 220.0}}},
        )
    finally:
        object.__setattr__(settings, "auto_approve_portfolio_max_deployed_capital", old_portfolio_limit)
        object.__setattr__(settings, "auto_approve_max_source_capital_share", old_source_share)

    assert round(sum(float(item["capital_cap"]) for item in items), 2) <= 30.0
    assert controls["alpha"]["remaining_portfolio_capital"] == 30.0


def test_source_position_controls_cap_single_source_capital_share(monkeypatch: pytest.MonkeyPatch) -> None:
    old_source_share = settings.auto_approve_max_source_capital_share
    object.__setattr__(settings, "auto_approve_max_source_capital_share", 0.5)
    try:
        controls, items = auto_trade_service._build_source_position_controls(
            batch_limit=3,
            source_strategy_map={
                "alpha": {
                    "source": "alpha",
                    "source_lane": "expand",
                    "block_new_approvals": False,
                    "strategy_mode": "widen",
                    "strategy_summary": "alpha strong",
                    "intake_multiplier": 1.3,
                    "capital_multiplier": 1.4,
                    "realized_net_profit": 120.0,
                },
                "beta": {
                    "source": "beta",
                    "source_lane": "expand",
                    "block_new_approvals": False,
                    "strategy_mode": "widen",
                    "strategy_summary": "beta solid",
                    "intake_multiplier": 0.8,
                    "capital_multiplier": 0.9,
                    "realized_net_profit": 40.0,
                },
            },
            candidate_rows=[
                {"source": "alpha", "list_price": 100.0},
                {"source": "alpha", "list_price": 100.0},
                {"source": "alpha", "list_price": 100.0},
                {"source": "beta", "list_price": 100.0},
                {"source": "beta", "list_price": 100.0},
            ],
        )
    finally:
        object.__setattr__(settings, "auto_approve_max_source_capital_share", old_source_share)

    assert controls["alpha"]["source_capital_share_limit_value"] > 0
    assert controls["alpha"]["capital_cap"] <= controls["alpha"]["source_capital_share_limit_value"]
    assert controls["alpha"]["capital_cap"] >= controls["beta"]["capital_cap"]


def test_cluster_position_controls_group_cross_source_same_normalized_key(monkeypatch: pytest.MonkeyPatch) -> None:
    old_cluster_batch_share = settings.auto_approve_max_cluster_batch_share
    old_cluster_capital_share = settings.auto_approve_max_cluster_capital_share
    object.__setattr__(settings, "auto_approve_max_cluster_batch_share", 0.5)
    object.__setattr__(settings, "auto_approve_max_cluster_capital_share", 0.5)
    try:
        controls, items = auto_trade_service._build_cluster_position_controls(
            batch_limit=4,
            candidate_rows=[
                {"source": "alpha", "normalized_key": "manual_card:Same", "item_type": "manual_card", "list_price": 100.0},
                {"source": "beta", "normalized_key": "manual_card:Same", "item_type": "manual_card", "list_price": 100.0},
                {"source": "gamma", "normalized_key": "manual_card:Other", "item_type": "manual_card", "list_price": 100.0},
            ],
        )
    finally:
        object.__setattr__(settings, "auto_approve_max_cluster_batch_share", old_cluster_batch_share)
        object.__setattr__(settings, "auto_approve_max_cluster_capital_share", old_cluster_capital_share)

    same_cluster = controls["manual_card:Same"]
    assert same_cluster["source_count"] == 2
    assert same_cluster["batch_cap"] <= 2
    assert len(items) == 2


def test_run_once_blocks_cross_source_same_cluster_concentration(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    old_cluster_batch_share = settings.auto_approve_max_cluster_batch_share
    object.__setattr__(settings, "auto_approve_max_cluster_batch_share", 0.5)
    try:
        monkeypatch.setattr(
            autotrade_module.repo,
            "get_dashboard_metrics",
            lambda: {
                "profit_cockpit": {
                    "today": {"realized_net_profit": 0.0, "sold_count": 0},
                    "last_7d": {"realized_net_profit": 0.0, "sold_count": 0},
                    "loss_streak": {"current_consecutive_losses": 0, "current_loss_total": 0.0},
                    "seller_leaderboard_7d": [],
                    "source_leaderboard_7d": [
                        {
                            "source": "alpha",
                            "source_lane": "expand",
                            "block_new_approvals": False,
                            "strategy_mode": "widen",
                            "strategy_summary": "alpha good",
                            "threshold_delta": {"min_score": 0.0, "min_roi": 0.0, "max_risk_score": 0.0},
                            "intake_multiplier": 1.2,
                            "capital_multiplier": 1.0,
                        },
                        {
                            "source": "beta",
                            "source_lane": "expand",
                            "block_new_approvals": False,
                            "strategy_mode": "widen",
                            "strategy_summary": "beta good",
                            "threshold_delta": {"min_score": 0.0, "min_roi": 0.0, "max_risk_score": 0.0},
                            "intake_multiplier": 1.1,
                            "capital_multiplier": 1.0,
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
                    "score": 95.0,
                    "roi": 0.4,
                    "source": "alpha",
                    "seller_id": "seller-a",
                    "item_type": "manual_card",
                    "normalized_key": "manual_card:Same",
                    "list_price": 100.0,
                    "review_note": "risk_score=10",
                },
                {
                    "id": 2,
                    "score": 94.0,
                    "roi": 0.39,
                    "source": "beta",
                    "seller_id": "seller-b",
                    "item_type": "manual_card",
                    "normalized_key": "manual_card:Same",
                    "list_price": 100.0,
                    "review_note": "risk_score=10",
                },
                {
                    "id": 3,
                    "score": 93.0,
                    "roi": 0.38,
                        "source": "gamma",
                        "seller_id": "seller-c",
                        "item_type": "manual_card",
                        "normalized_key": "manual_card:Other",
                        "list_price": 100.0,
                        "review_note": "risk_score=10",
                    },
                ],
            )
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "sync_from_metrics",
            lambda **kwargs: {"status": {}},
        )
        monkeypatch.setattr(
            autotrade_module.seller_controls_service,
            "runtime_control",
            lambda **kwargs: {
                "state": "normal",
                "blocked": False,
                "threshold_delta": {},
                "intake_multiplier": 1.0,
            },
        )
        approvals: list[dict[str, object]] = []

        def _approve(**kwargs):
            approvals.append(kwargs)
            return {
                "created": True,
                "idempotent": False,
                "trade_id": 10000 + int(kwargs["opportunity_id"]),
            }

        monkeypatch.setattr(autotrade_module.repo, "approve_opportunity_idempotent", _approve)
        result = auto_trade_service.run_once(limit=2, force=True)
    finally:
        object.__setattr__(settings, "auto_approve_max_cluster_batch_share", old_cluster_batch_share)

    assert result["approved"] == 1
    assert result["skipped_cluster_batch_cap"] == 1
    assert len(approvals) == 1
    assert result["cluster_position_controls"][0]["risk_cluster"] == "manual_card:Same"



def test_run_once_skips_auto_list_when_source_list_action_is_blocked(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        auto_execute_buy_on_approve=True,
        auto_execute_buy_dry_run=True,
        auto_execute_list_on_buy_success=True,
        auto_execute_list_dry_run=True,
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
                "source_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "source_lane": "expand",
                        "block_new_approvals": False,
                        "list_action_lane": "blocked",
                        "allow_auto_list": False,
                        "strategy_mode": "widen",
                        "strategy_summary": "buy ok, list blocked",
                        "threshold_delta": {
                            "min_score": 0.0,
                            "min_roi": 0.0,
                            "max_risk_score": 0.0,
                        },
                        "intake_multiplier": 1.0,
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
                "score": 95.0,
                "roi": 0.4,
                "source": "alpha",
                "seller_id": "seller-a",
                "item_type": "manual_card",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
        ],
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "sync_from_metrics",
        lambda **kwargs: {"status": {}},
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "runtime_control",
        lambda **kwargs: {
            "state": "normal",
            "blocked": False,
            "threshold_delta": {},
            "intake_multiplier": 1.0,
        },
    )

    monkeypatch.setattr(
        autotrade_module.execution_service,
        "execute_buy",
        lambda **kwargs: {"success": True, "log_id": 1},
    )

    list_calls: list[dict[str, object]] = []

    def _execute_list(**kwargs):
        list_calls.append(kwargs)
        return {"success": True, "log_id": 2}

    monkeypatch.setattr(autotrade_module.execution_service, "execute_list", _execute_list)
    monkeypatch.setattr(
        autotrade_module.repo,
        "approve_opportunity_idempotent",
        lambda **kwargs: {"created": True, "idempotent": False, "trade_id": 8001},
    )

    result = auto_trade_service.run_once(force=True)

    assert result["approved"] == 1
    assert result["buy_exec_succeeded"] == 1
    assert result["list_exec_skipped_source_action"] == 1
    assert result["list_exec_attempted"] == 0
    assert list_calls == []


def test_run_once_limits_auto_list_for_observe_source_action_lane(
    isolated_autotrade_tuning_sqlite: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    auto_trade_service.update_config(
        auto_execute_buy_on_approve=True,
        auto_execute_buy_dry_run=True,
        auto_execute_list_on_buy_success=True,
        auto_execute_list_dry_run=True,
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
                "source_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "source_lane": "expand",
                        "block_new_approvals": False,
                        "list_action_lane": "observe",
                        "allow_auto_list": True,
                        "strategy_mode": "tighten",
                        "strategy_summary": "list recovering",
                        "threshold_delta": {
                            "min_score": 0.0,
                            "min_roi": 0.0,
                            "max_risk_score": 0.0,
                        },
                        "intake_multiplier": 1.0,
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
                "score": 95.0,
                "roi": 0.4,
                "source": "alpha",
                "seller_id": "seller-a",
                "item_type": "manual_card",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
            {
                "id": 2,
                "score": 94.0,
                "roi": 0.39,
                "source": "alpha",
                "seller_id": "seller-b",
                "item_type": "manual_card",
                "list_price": 100.0,
                "review_note": "risk_score=10",
            },
        ],
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "sync_from_metrics",
        lambda **kwargs: {"status": {}},
    )
    monkeypatch.setattr(
        autotrade_module.seller_controls_service,
        "runtime_control",
        lambda **kwargs: {
            "state": "normal",
            "blocked": False,
            "threshold_delta": {},
            "intake_multiplier": 1.0,
        },
    )

    monkeypatch.setattr(
        autotrade_module.execution_service,
        "execute_buy",
        lambda **kwargs: {"success": True, "log_id": 1},
    )
    list_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        autotrade_module.execution_service,
        "execute_list",
        lambda **kwargs: list_calls.append(kwargs) or {"success": True, "log_id": 2},
    )
    monkeypatch.setattr(
        autotrade_module.repo,
        "approve_opportunity_idempotent",
        lambda **kwargs: {
            "created": True,
            "idempotent": False,
            "trade_id": 9000 + int(kwargs["opportunity_id"]),
        },
    )

    result = auto_trade_service.run_once(force=True)

    assert result["approved"] == 2
    assert result["buy_exec_succeeded"] == 2
    assert result["list_exec_attempted"] == 1
    assert result["list_exec_skipped_source_action_cap"] == 1
    assert len(list_calls) == 1


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
