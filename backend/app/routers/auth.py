from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi import Request

from ..auth_utils import auth_failed
from ..auth_utils import build_user_profile
from ..auth_utils import extract_bearer_token
from ..auth_utils import fetch_user_by_session_token
from ..auth_utils import issue_session_token
from ..auth_utils import require_current_user
from ..auth_utils import session_expires_at
from ..auth_utils import success_response
from ..auth_utils import utcnow_iso
from ..auth_utils import verify_password
from ..database import get_conn

router = APIRouter(tags=["auth"])


def _normalize_body(payload: dict[str, Any] | None) -> dict[str, Any]:
    return payload if isinstance(payload, dict) else {}


def _serialize_auth_payload(user_row: Any, token: str) -> dict[str, Any]:
    profile = build_user_profile(user_row)
    return {
        "token": token,
        "user": profile,
        "roles": profile["roles"],
        "permissions": profile["permissions"],
        "perms": profile["perms"],
    }


def _lookup_user_for_login(conn, identity: str):
    return conn.execute(
        """
        SELECT *
        FROM users
        WHERE lower(username) = lower(?) OR lower(email) = lower(?)
        LIMIT 1
        """,
        (identity, identity),
    ).fetchone()


@router.get("/auth/user")
def get_auth_user(request: Request) -> dict[str, Any]:
    with get_conn() as conn:
        user_row = require_current_user(conn, request)
        token = extract_bearer_token(request)
        payload = _serialize_auth_payload(user_row, token)
    return success_response(payload)


@router.get("/auth/userinfo")
def get_auth_userinfo(request: Request) -> dict[str, Any]:
    return get_auth_user(request)


@router.get("/user/profile")
def get_user_profile(request: Request) -> dict[str, Any]:
    with get_conn() as conn:
        user_row = require_current_user(conn, request)
        profile = build_user_profile(user_row)
    return success_response(
        {
            "user": profile,
            "roles": profile["roles"],
            "permissions": profile["permissions"],
            "perms": profile["perms"],
        }
    )


@router.post("/auth/login")
def login(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = _normalize_body(body)
    identity = str(payload.get("username") or payload.get("email") or "").strip()
    password = str(payload.get("password") or "").strip()
    if not identity or not password:
        auth_failed("请输入用户名和密码", status_code=400)

    with get_conn() as conn:
        user_row = _lookup_user_for_login(conn, identity)
        if user_row is None or not verify_password(password, user_row["password_hash"]):
            auth_failed("用户名或密码错误", status_code=401)
        if int(user_row["is_active"] or 0) != 1:
            auth_failed("当前账号已被停用", status_code=403)

        token = issue_session_token()
        now = utcnow_iso()
        conn.execute("DELETE FROM auth_sessions WHERE user_id = ?", (int(user_row["id"]),))
        conn.execute(
            """
            INSERT INTO auth_sessions (user_id, token, expires_at, created_at, last_seen_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (int(user_row["id"]), token, session_expires_at(), now, now),
        )

        refreshed = conn.execute(
            "SELECT * FROM users WHERE id = ?",
            (int(user_row["id"]),),
        ).fetchone()
        response_payload = _serialize_auth_payload(refreshed, token)
    return success_response(response_payload, message="login_success")


@router.post("/auth/logout")
def logout(request: Request) -> dict[str, Any]:
    token = extract_bearer_token(request)
    if token:
        with get_conn() as conn:
            conn.execute("DELETE FROM auth_sessions WHERE token = ?", (token,))
    return success_response({"logout": True}, message="logout_success")


@router.post("/auth/refresh")
def refresh(request: Request) -> dict[str, Any]:
    token = extract_bearer_token(request)
    if not token:
        auth_failed("请先登录", status_code=401)

    with get_conn() as conn:
        user_row = fetch_user_by_session_token(conn, token, touch_session=True)
        if user_row is None:
            auth_failed("登录已失效，请重新登录", status_code=401)
        payload = _serialize_auth_payload(user_row, token)
    return success_response(payload, message="refresh_success")
