from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

import app.config as config_module
import app.routers.setup as setup_router_module
from app.config import settings
from app.database import get_seed_admin_bootstrap_path
from app.database import init_db
from app.main import create_app


@pytest.fixture
def isolated_setup_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    old_sqlite_path = settings.sqlite_path
    old_username = settings.ui_auth_username
    old_password = settings.ui_auth_password
    old_nickname = settings.ui_auth_nickname
    old_gemini_key = settings.gemini_api_key
    old_gemini_source = settings.gemini_key_source_path
    old_auto_apply = settings.auto_tune_auto_apply_enabled
    old_cooldown = settings.auto_tune_cooldown_hours
    old_min_batches = settings.auto_tune_min_closed_batches
    old_latest_min_sold = settings.auto_tune_latest_min_sold_count
    old_previous_min_sold = settings.auto_tune_previous_min_sold_count
    env_path = tmp_path / "setup.env"

    monkeypatch.setattr(config_module, "_dotenv_path", env_path)
    object.__setattr__(settings, "sqlite_path", str(tmp_path / "setup.db"))
    object.__setattr__(settings, "ui_auth_username", "admin")
    object.__setattr__(settings, "ui_auth_password", "")
    object.__setattr__(settings, "ui_auth_nickname", "Bootstrap Admin")
    object.__setattr__(settings, "gemini_api_key", "")
    object.__setattr__(settings, "gemini_key_source_path", "")
    object.__setattr__(settings, "auto_tune_auto_apply_enabled", False)
    object.__setattr__(settings, "auto_tune_cooldown_hours", 24)
    object.__setattr__(settings, "auto_tune_min_closed_batches", 2)
    object.__setattr__(settings, "auto_tune_latest_min_sold_count", 5)
    object.__setattr__(settings, "auto_tune_previous_min_sold_count", 3)
    init_db()

    try:
        yield {
            "env_path": env_path,
            "bootstrap_path": get_seed_admin_bootstrap_path(),
        }
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
        object.__setattr__(settings, "ui_auth_username", old_username)
        object.__setattr__(settings, "ui_auth_password", old_password)
        object.__setattr__(settings, "ui_auth_nickname", old_nickname)
        object.__setattr__(settings, "gemini_api_key", old_gemini_key)
        object.__setattr__(settings, "gemini_key_source_path", old_gemini_source)
        object.__setattr__(settings, "auto_tune_auto_apply_enabled", old_auto_apply)
        object.__setattr__(settings, "auto_tune_cooldown_hours", old_cooldown)
        object.__setattr__(settings, "auto_tune_min_closed_batches", old_min_batches)
        object.__setattr__(settings, "auto_tune_latest_min_sold_count", old_latest_min_sold)
        object.__setattr__(settings, "auto_tune_previous_min_sold_count", old_previous_min_sold)


def test_setup_status_reports_bootstrap_mode(isolated_setup_env: dict[str, Path]) -> None:
    with TestClient(create_app()) as client:
        response = client.get("/setup/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["bootstrap_password_mode"] is True
    assert payload["setup_recommended"] is True
    assert payload["bootstrap_credentials_exists"] is True
    assert payload["values"]["gemini_runtime_status"]["source_type"] == "none"
    assert payload["values"]["gemini_runtime_status"]["key_count"] == 0


def test_setup_apply_updates_env_and_admin_password(isolated_setup_env: dict[str, Path]) -> None:
    env_path = isolated_setup_env["env_path"]
    bootstrap_payload = json.loads(
        isolated_setup_env["bootstrap_path"].read_text(encoding="utf-8"),
    )
    bootstrap_password = str(bootstrap_payload["password"])

    with TestClient(create_app()) as client:
        apply_response = client.post(
            "/setup/apply",
            json={
                "ui_auth_password": "new-admin-123",
                "ui_auth_nickname": "Local Boss",
                "auto_tune_auto_apply_enabled": True,
                "auto_tune_cooldown_hours": 12,
            },
        )
        assert apply_response.status_code == 200
        payload = apply_response.json()
        assert payload["saved"] is True
        assert "UI_AUTH_PASSWORD" in payload["applied_keys"]
        assert env_path.exists() is True
        env_text = env_path.read_text(encoding="utf-8")
        assert "UI_AUTH_PASSWORD=new-admin-123" in env_text
        assert "AUTO_TUNE_AUTO_APPLY_ENABLED=true" in env_text
        assert "AUTO_TUNE_COOLDOWN_HOURS=12" in env_text
        assert payload["audit"]["actor"] == "bootstrap_setup"
        assert "UI_AUTH_PASSWORD" in payload["audit"]["changed_keys"]

        old_login = client.post(
            "/auth/login",
            json={"username": "admin", "password": bootstrap_password},
        )
        new_login = client.post(
            "/auth/login",
            json={"username": "admin", "password": "new-admin-123"},
        )

    assert old_login.status_code == 401
    assert new_login.status_code == 200
    assert new_login.json()["data"]["user"]["nickname"] == "Local Boss"


def test_setup_audit_endpoint_returns_recent_changes(isolated_setup_env: dict[str, Path]) -> None:
    with TestClient(create_app()) as client:
        apply_response = client.post(
            "/setup/apply",
            json={
                "ui_auth_nickname": "Audit Admin",
                "auto_tune_auto_apply_enabled": True,
            },
        )
        assert apply_response.status_code == 200

        audit_response = client.get("/setup/audit", params={"limit": 10})
        assert audit_response.status_code == 200
        payload = audit_response.json()
        assert payload["count"] >= 1
        item = payload["items"][0]
        assert item["actor"] == "bootstrap_setup"
        assert "UI_AUTH_NICKNAME" in item["changed_keys"]


def test_setup_audit_rollback_restores_non_secret_values(isolated_setup_env: dict[str, Path]) -> None:
    with TestClient(create_app()) as client:
        first = client.post(
            "/setup/apply",
            json={
                "ui_auth_nickname": "Rollback Admin",
                "auto_tune_cooldown_hours": 12,
            },
        )
        assert first.status_code == 200
        audit_id = int(first.json()["audit"]["id"])

        second = client.post(
            "/setup/apply",
            json={
                "ui_auth_nickname": "Changed Again",
                "auto_tune_cooldown_hours": 30,
            },
        )
        assert second.status_code == 200

        rollback = client.post(f"/setup/audit/{audit_id}/rollback")
        assert rollback.status_code == 200
        payload = rollback.json()
        assert payload["status"]["values"]["ui_auth_nickname"] == "Bootstrap Admin"
        assert payload["status"]["values"]["auto_tune_cooldown_hours"] == 24


def test_setup_test_gemini_endpoint_uses_client_result(
    isolated_setup_env: dict[str, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_test_connection():
        return {
            "enabled": True,
            "success": True,
            "model": "gemini-test",
            "key_count": 1,
            "error": "",
        }

    monkeypatch.setattr(
        setup_router_module.GeminiClient,
        "test_connection",
        lambda self: _fake_test_connection(),
    )

    with TestClient(create_app()) as client:
        response = client.get("/setup/test-gemini")
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["model"] == "gemini-test"


def test_setup_apply_requires_admin_when_not_in_bootstrap_mode(
    isolated_setup_env: dict[str, Path],
) -> None:
    object.__setattr__(settings, "ui_auth_password", "configured-pass")
    with TestClient(create_app()) as client:
        response = client.post(
            "/setup/apply",
            json={"ui_auth_nickname": "Blocked"},
        )
    assert response.status_code == 401
