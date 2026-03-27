from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import init_db
from app import repositories as repo
from app.main import create_app
from app.services.seller_controls import seller_controls_service
from app.services.autotrade import auto_trade_service


@pytest.fixture
def isolated_seller_controls_sqlite(tmp_path: Path):
    old_sqlite_path = settings.sqlite_path
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "seller_controls.db"))
    init_db()
    try:
        yield Path(settings.sqlite_path)
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)


def test_sync_from_metrics_freezes_and_unfreezes_seller(
    isolated_seller_controls_sqlite: Path,
) -> None:
    blacklist_metrics = {
        "profit_cockpit": {
            "seller_leaderboard_7d": [
                {
                    "source": "alpha",
                    "seller_id": "seller-bad",
                    "seller_lane": "blacklist",
                    "sold_count": 3,
                    "lane_summary": "seller is underperforming",
                },
            ],
        },
    }

    freeze_result = seller_controls_service.sync_from_metrics(metrics=blacklist_metrics)
    assert len(freeze_result["frozen"]) == 1
    assert seller_controls_service.is_seller_frozen(source="alpha", seller_id="seller-bad") is True

    recovery_metrics = {
        "profit_cockpit": {
            "seller_leaderboard_7d": [
                {
                    "source": "alpha",
                    "seller_id": "seller-bad",
                    "seller_lane": "neutral",
                    "sold_count": 3,
                    "lane_summary": "seller recovered",
                },
            ],
        },
    }

    unfreeze_result = seller_controls_service.sync_from_metrics(metrics=recovery_metrics)
    assert len(unfreeze_result["unfrozen"]) == 1
    assert seller_controls_service.is_seller_frozen(source="alpha", seller_id="seller-bad") is False
    assert seller_controls_service.runtime_control(source="alpha", seller_id="seller-bad")["state"] == "observe"


def test_observe_state_returns_to_normal_after_observe_window(
    isolated_seller_controls_sqlite: Path,
) -> None:
    repo.upsert_seller_control_state(
        source="alpha",
        seller_id="seller-watch",
        state="observe",
        reason="manual observe seed",
        frozen_until=(datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
        metadata={"seller_lane": "observe"},
    )

    result = seller_controls_service.sync_from_metrics(
        metrics={
            "profit_cockpit": {
                "seller_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "seller_id": "seller-watch",
                        "seller_lane": "neutral",
                        "sold_count": 3,
                        "lane_summary": "observe completed",
                    },
                ],
            },
        },
    )

    assert len(result["unfrozen"]) == 1
    assert seller_controls_service.runtime_control(source="alpha", seller_id="seller-watch")["state"] == "normal"


def test_runtime_control_scales_observe_multiplier_with_positive_streak(
    isolated_seller_controls_sqlite: Path,
) -> None:
    repo.upsert_seller_control_state(
        source="alpha",
        seller_id="seller-ramp",
        state="observe",
        reason="observe seed",
        frozen_until=(datetime.now(timezone.utc) + timedelta(hours=12)).isoformat(),
        metadata={"positive_streak": 2},
    )

    runtime = seller_controls_service.runtime_control(source="alpha", seller_id="seller-ramp")

    assert runtime["state"] == "observe"
    assert runtime["positive_streak"] == 2
    assert runtime["recovery_progress"] == pytest.approx(2 / 3, rel=1e-3)
    assert runtime["intake_multiplier"] > 0.6
    assert runtime["intake_multiplier"] < 1.0


def test_observe_state_graduates_early_when_positive_streak_hits_threshold(
    isolated_seller_controls_sqlite: Path,
) -> None:
    repo.upsert_seller_control_state(
        source="alpha",
        seller_id="seller-grad",
        state="observe",
        reason="observe seed",
        frozen_until=(datetime.now(timezone.utc) + timedelta(hours=48)).isoformat(),
        metadata={"positive_streak": 2},
    )

    result = seller_controls_service.sync_from_metrics(
        metrics={
            "profit_cockpit": {
                "seller_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "seller_id": "seller-grad",
                        "seller_lane": "whitelist",
                        "positive_streak": 3,
                        "sold_count": 4,
                        "lane_summary": "seller regained trust",
                    },
                ],
            },
        },
    )

    assert len(result["unfrozen"]) == 1
    assert seller_controls_service.runtime_control(source="alpha", seller_id="seller-grad")["state"] == "normal"


def test_status_summary_includes_recent_events_and_daily_report(
    isolated_seller_controls_sqlite: Path,
) -> None:
    seller_controls_service.sync_from_metrics(
        metrics={
            "profit_cockpit": {
                "seller_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "seller_id": "seller-a",
                        "seller_lane": "blacklist",
                        "sold_count": 3,
                        "lane_summary": "seller slipped",
                    },
                ],
            },
        },
    )
    seller_controls_service.sync_from_metrics(
        metrics={
            "profit_cockpit": {
                "seller_leaderboard_7d": [
                    {
                        "source": "alpha",
                        "seller_id": "seller-a",
                        "seller_lane": "neutral",
                        "sold_count": 3,
                        "lane_summary": "seller recovered",
                    },
                ],
            },
        },
    )

    summary = seller_controls_service.status_summary(limit=5)

    assert summary["daily_report"]["event_count"] >= 2
    assert summary["daily_report"]["counts_by_type"]["auto_freeze"] >= 1
    assert summary["daily_report"]["counts_by_type"]["auto_observe"] >= 1
    assert len(summary["recent_events"]) >= 2


def test_manual_action_updates_state_and_creates_events(
    isolated_seller_controls_sqlite: Path,
) -> None:
    freeze_result = seller_controls_service.apply_manual_action(
        source="alpha",
        seller_id="seller-manual",
        action="freeze",
        reason="manual risk override",
        actor="ops",
        duration_hours=12,
    )
    assert freeze_result["state"]["state"] == "frozen"
    assert freeze_result["event"]["event_type"] == "manual_freeze"
    assert freeze_result["state"]["metadata"]["manual_actor"] == "ops"
    assert freeze_result["event"]["next_state"]["metadata"]["manual_actor"] == "ops"
    assert "T" in str(freeze_result["state"]["frozen_until"] or "")

    observe_result = seller_controls_service.apply_manual_action(
        source="alpha",
        seller_id="seller-manual",
        action="observe",
        reason="manual probation",
        actor="ops",
        duration_hours=24,
    )
    assert observe_result["state"]["state"] == "observe"
    assert observe_result["event"]["event_type"] == "manual_observe"
    assert observe_result["state"]["metadata"]["manual_actor"] == "ops"

    restore_result = seller_controls_service.apply_manual_action(
        source="alpha",
        seller_id="seller-manual",
        action="normal",
        reason="manual release",
        actor="ops",
    )
    assert restore_result["state"]["state"] == "normal"
    assert restore_result["event"]["event_type"] == "manual_restore"

    events = repo.list_seller_control_events_for_seller(source="alpha", seller_id="seller-manual", limit=5)
    assert events[0]["event_type"] == "manual_restore"
    assert events[1]["event_type"] == "manual_observe"
    assert events[2]["event_type"] == "manual_freeze"


def test_manual_batch_action_applies_to_multiple_sellers(
    isolated_seller_controls_sqlite: Path,
) -> None:
    result = seller_controls_service.apply_manual_action_batch(
        items=[
            {"source": "alpha", "seller_id": "seller-a"},
            {"source": "alpha", "seller_id": "seller-b"},
            {"source": "alpha", "seller_id": "seller-a"},
        ],
        action="observe",
        reason="batch probation",
        actor="ops",
        duration_hours=24,
    )

    assert result["processed"] == 2
    assert repo.get_seller_control_state("alpha", "seller-a")["state"] == "observe"
    assert repo.get_seller_control_state("alpha", "seller-b")["state"] == "observe"


def test_seller_control_presets_can_be_saved_listed_and_deleted(
    isolated_seller_controls_sqlite: Path,
) -> None:
    preset = repo.upsert_seller_control_preset(
        name="alpha_losers",
        base_preset="losing",
        source_filter="alpha",
        action="observe",
        reason="alpha source losers",
        duration_hours=72,
        actor="ops",
    )
    assert preset["name"] == "alpha_losers"
    assert preset["base_preset"] == "losing"
    assert preset["source_filter"] == "alpha"

    status = auto_trade_service.status()
    assert status["seller_control_presets"][0]["name"] == "alpha_losers"

    updated = repo.record_seller_control_preset_run(
        preset_id=preset["id"],
        action="observe",
        actor="ops",
        reason="alpha source losers",
        duration_hours=72,
        matched_count=3,
        processed_count=2,
        matched_items=[
            {"source": "alpha", "seller_id": "seller-a"},
            {"source": "alpha", "seller_id": "seller-b"},
            {"source": "beta", "seller_id": "seller-c"},
        ],
    )
    assert updated["last_applied_action"] == "observe"
    assert updated["last_applied_by"] == "ops"
    assert updated["last_matched_count"] == 3
    assert updated["last_processed_count"] == 2
    assert updated["last_matched_items"][0]["seller_id"] == "seller-a"
    assert updated["last_matched_items"][2]["source"] == "beta"
    runs = repo.list_seller_control_preset_runs(preset_id=preset["id"], limit=5)
    assert runs[0]["reason"] == "alpha source losers"
    assert runs[0]["duration_hours"] == 72
    assert runs[0]["matched_items"][1]["seller_id"] == "seller-b"

    repo.record_seller_control_preset_run(
        preset_id=preset["id"],
        action="freeze",
        actor="ops",
        reason="second pass",
        duration_hours=48,
        matched_count=2,
        processed_count=1,
        matched_items=[
            {"source": "alpha", "seller_id": "seller-d"},
            {"source": "alpha", "seller_id": "seller-e"},
        ],
    )
    listed = repo.list_seller_control_presets(limit=10)
    assert listed[0]["recent_stats"]["run_count"] == 2
    assert listed[0]["recent_stats"]["avg_matched_count"] == 2.5
    assert listed[0]["recent_stats"]["avg_processed_count"] == 1.5
    assert listed[0]["recent_stats"]["avg_processed_rate"] == 0.6
    assert listed[0]["effectiveness_score"] > 0
    assert listed[0]["effectiveness_rank"] == 1

    deleted = repo.delete_seller_control_preset(preset["id"])
    assert deleted["id"] == preset["id"]
    assert repo.list_seller_control_presets(limit=10) == []


def test_seller_control_preset_runs_route_returns_history(
    isolated_seller_controls_sqlite: Path,
) -> None:
    preset = repo.upsert_seller_control_preset(
        name="alpha_history",
        base_preset="manual",
        source_filter="",
        action="freeze",
        reason="history preset",
        duration_hours=48,
        actor="ops",
    )
    repo.record_seller_control_preset_run(
        preset_id=preset["id"],
        action="freeze",
        actor="ops",
        reason="history preset",
        duration_hours=48,
        matched_count=2,
        processed_count=1,
        matched_items=[
            {"source": "alpha", "seller_id": "seller-x"},
            {"source": "alpha", "seller_id": "seller-y"},
        ],
    )

    with TestClient(create_app()) as client:
        response = client.get(f"/autotrade/seller-controls/presets/{preset['id']}/runs")

    assert response.status_code == 200
    payload = response.json()
    assert payload["preset"]["id"] == preset["id"]
    assert payload["items"][0]["reason"] == "history preset"
    assert payload["items"][0]["matched_items"][0]["seller_id"] == "seller-x"
