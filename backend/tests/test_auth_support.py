from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.database import init_db
from app.main import create_app


@pytest.fixture
def isolated_auth_sqlite(tmp_path: Path):
    old_sqlite_path = settings.sqlite_path
    old_username = settings.ui_auth_username
    old_password = settings.ui_auth_password
    old_nickname = settings.ui_auth_nickname
    old_allow_registration = settings.ui_auth_allow_registration

    object.__setattr__(settings, "sqlite_path", str(tmp_path / "auth_support.db"))
    object.__setattr__(settings, "ui_auth_username", "admin")
    object.__setattr__(settings, "ui_auth_password", "admin123456")
    object.__setattr__(settings, "ui_auth_nickname", "系统管理员")
    object.__setattr__(settings, "ui_auth_allow_registration", True)
    init_db()

    try:
        yield Path(settings.sqlite_path)
    finally:
        object.__setattr__(settings, "sqlite_path", old_sqlite_path)
        object.__setattr__(settings, "ui_auth_username", old_username)
        object.__setattr__(settings, "ui_auth_password", old_password)
        object.__setattr__(settings, "ui_auth_nickname", old_nickname)
        object.__setattr__(settings, "ui_auth_allow_registration", old_allow_registration)


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_seed_admin_can_login_and_fetch_profile(isolated_auth_sqlite: Path) -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/auth/login",
            json={"username": "admin", "password": "admin123456"},
        )

        assert response.status_code == 200
        payload = response.json()["data"]
        assert payload["user"]["username"] == "admin"
        assert payload["user"]["isAdmin"] is True
        assert "support:ticket:manage" in payload["permissions"]

        me = client.get("/auth/user", headers=_bearer(payload["token"]))
        assert me.status_code == 200
        assert me.json()["data"]["user"]["nickname"] == "系统管理员"


def test_user_ticket_flow_and_admin_management(isolated_auth_sqlite: Path) -> None:
    with TestClient(create_app()) as client:
        register = client.post(
            "/auth/register",
            json={
                "username": "farmer_user",
                "email": "farmer@example.com",
                "password": "secret123",
                "nickname": "农户甲",
            },
        )
        assert register.status_code == 200

        user_login = client.post(
            "/auth/login",
            json={"username": "farmer_user", "password": "secret123"},
        )
        assert user_login.status_code == 200
        user_token = user_login.json()["data"]["token"]

        create_ticket = client.post(
            "/support/tickets",
            headers=_bearer(user_token),
            json={
                "title": "模拟盘打不开",
                "category": "bug",
                "priority": "high",
                "description": "今天打开模拟盘一直转圈，想上报给管理员处理。",
            },
        )
        assert create_ticket.status_code == 200
        ticket_id = create_ticket.json()["data"]["ticket"]["id"]

        user_list = client.get("/support/tickets", headers=_bearer(user_token))
        assert user_list.status_code == 200
        user_payload = user_list.json()["data"]
        assert user_payload["canManage"] is False
        assert len(user_payload["items"]) == 1

        admin_login = client.post(
            "/auth/login",
            json={"username": "admin", "password": "admin123456"},
        )
        assert admin_login.status_code == 200
        admin_token = admin_login.json()["data"]["token"]

        admin_list = client.get("/support/tickets", headers=_bearer(admin_token))
        assert admin_list.status_code == 200
        admin_payload = admin_list.json()["data"]
        assert admin_payload["canManage"] is True
        assert admin_payload["stats"]["total"] == 1

        update = client.patch(
            f"/support/tickets/{ticket_id}",
            headers=_bearer(admin_token),
            json={"status": "resolved", "priority": "urgent", "adminAssignee": "admin"},
        )
        assert update.status_code == 200
        assert update.json()["data"]["ticket"]["status"] == "resolved"

        reply = client.post(
            f"/support/tickets/{ticket_id}/reply",
            headers=_bearer(admin_token),
            json={"message": "已定位到前端缓存问题，请重启到最新版本。"},
        )
        assert reply.status_code == 200
        assert reply.json()["data"]["ticket"]["lastReplyBy"] == "admin"

        detail = client.get(f"/support/tickets/{ticket_id}", headers=_bearer(user_token))
        assert detail.status_code == 200
        messages = detail.json()["data"]["messages"]
        assert len(messages) == 2
        assert messages[-1]["message"].startswith("已定位到前端缓存问题")

        forbidden = client.patch(
            f"/support/tickets/{ticket_id}",
            headers=_bearer(user_token),
            json={"status": "closed"},
        )
        assert forbidden.status_code == 403
