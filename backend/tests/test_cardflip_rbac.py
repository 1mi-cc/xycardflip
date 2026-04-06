from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import get_conn
from app.database import init_db
from app.main import create_app


@pytest.fixture
def secured_cardflip_auth_sqlite(tmp_path: Path):
    old_sqlite_path = settings.sqlite_path
    old_username = settings.ui_auth_username
    old_password = settings.ui_auth_password
    old_nickname = settings.ui_auth_nickname
    old_allow_registration = settings.ui_auth_allow_registration
    old_enforce = settings.ui_auth_enforce_permissions

    object.__setattr__(settings, "sqlite_path", str(tmp_path / "cardflip_rbac.db"))
    object.__setattr__(settings, "ui_auth_username", "admin")
    object.__setattr__(settings, "ui_auth_password", "admin123456")
    object.__setattr__(settings, "ui_auth_nickname", "System Admin")
    object.__setattr__(settings, "ui_auth_allow_registration", True)
    object.__setattr__(settings, "ui_auth_enforce_permissions", True)
    init_db()

    try:
        yield Path(settings.sqlite_path)
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
        object.__setattr__(settings, "ui_auth_username", old_username)
        object.__setattr__(settings, "ui_auth_password", old_password)
        object.__setattr__(settings, "ui_auth_nickname", old_nickname)
        object.__setattr__(settings, "ui_auth_allow_registration", old_allow_registration)
        object.__setattr__(settings, "ui_auth_enforce_permissions", old_enforce)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _set_user_role(username: str, role: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE users SET role = ? WHERE lower(username) = lower(?)",
            (role, username),
        )


def _login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200
    return str(response.json()["data"]["token"])


def test_cardflip_management_requires_auth_and_allows_viewer_read_only(
    secured_cardflip_auth_sqlite: Path,
) -> None:
    with TestClient(create_app()) as client:
        anonymous = client.get("/autotrade/status")
        assert anonymous.status_code == 401

        register = client.post(
            "/auth/register",
            json={
                "username": "viewer_user",
                "email": "viewer@example.com",
                "password": "secret123",
                "nickname": "Viewer User",
            },
        )
        assert register.status_code == 200
        _set_user_role("viewer_user", "viewer")

        viewer_token = _login(client, "viewer_user", "secret123")

        viewer_status = client.get("/autotrade/status", headers=_bearer(viewer_token))
        viewer_metrics = client.get("/trades/metrics-summary", headers=_bearer(viewer_token))
        viewer_analysis = client.get("/analysis/data/price-history", headers=_bearer(viewer_token))
        viewer_ragflow_status = client.get("/ragflow/status", headers=_bearer(viewer_token))
        viewer_mutation = client.post("/automation/start", headers=_bearer(viewer_token))
        viewer_analysis_mutation = client.post("/analysis/automation/run-once", headers=_bearer(viewer_token))
        viewer_ragflow_mutation = client.post(
            "/ragflow/chat",
            headers=_bearer(viewer_token),
            json={"question": "hello"},
        )

        assert viewer_status.status_code == 200
        assert viewer_metrics.status_code == 200
        assert viewer_analysis.status_code == 200
        assert viewer_ragflow_status.status_code == 200
        assert viewer_mutation.status_code == 403
        assert viewer_analysis_mutation.status_code == 403
        assert viewer_ragflow_mutation.status_code == 403


def test_cardflip_management_allows_ops_mutation(
    secured_cardflip_auth_sqlite: Path,
) -> None:
    with TestClient(create_app()) as client:
        register = client.post(
            "/auth/register",
            json={
                "username": "ops_user",
                "email": "ops@example.com",
                "password": "secret123",
                "nickname": "Ops User",
            },
        )
        assert register.status_code == 200
        _set_user_role("ops_user", "ops")

        ops_token = _login(client, "ops_user", "secret123")

        automation_start = client.post("/automation/start", headers=_bearer(ops_token))
        monitor_reset = client.post(
            "/monitor/reset-circuit",
            headers=_bearer(ops_token),
            params={"reason": "rbac test"},
        )
        strategy = client.post(
            "/vnpy/strategy-profile",
            headers=_bearer(ops_token),
            params={"profile": "balanced"},
        )

        assert automation_start.status_code == 200
        assert monitor_reset.status_code == 200
        assert strategy.status_code == 200
