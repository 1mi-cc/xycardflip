from __future__ import annotations

import hashlib
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import HTTPException
from fastapi import Request

from .config import settings

VALID_ROLES: tuple[str, ...] = ("admin", "ops", "viewer", "user")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def utcnow_iso() -> str:
    return utcnow().isoformat()


def normalize_strings(values: list[str] | tuple[str, ...]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for raw in values:
        text = str(raw or "").strip()
        if not text:
            continue
        lowered = text.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        normalized.append(text)
    return normalized


def normalize_role(role: str | None) -> str:
    text = str(role or "").strip().lower()
    if text in VALID_ROLES:
        return text
    if text in {"operator", "operation", "ops-user"}:
        return "ops"
    if text in {"read", "readonly", "guest"}:
        return "viewer"
    if text in {"member", "customer", "reporter"}:
        return "user"
    return "user"


def role_permission_map() -> dict[str, list[str]]:
    return {
        "admin": normalize_strings(
            [
                *settings.ui_role_permissions_admin,
                "support:ticket:view",
                "support:ticket:create",
                "support:ticket:manage",
            ]
        ),
        "ops": normalize_strings(
            [
                *settings.ui_role_permissions_ops,
                "support:ticket:view",
            ]
        ),
        "viewer": normalize_strings(
            [
                *settings.ui_role_permissions_viewer,
            ]
        ),
        "user": ["support:ticket:view", "support:ticket:create", "profile:view"],
    }


def resolve_permissions(role_keys: list[str]) -> list[str]:
    mapping = role_permission_map()
    merged: list[str] = []
    seen: set[str] = set()
    for role in role_keys:
        for permission in mapping.get(normalize_role(role), []):
            lowered = permission.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            merged.append(permission)
    return merged


def hash_password(password: str, *, salt: str | None = None) -> str:
    text = str(password or "")
    if not text:
        raise ValueError("password is required")
    actual_salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        text.encode("utf-8"),
        actual_salt.encode("utf-8"),
        120_000,
    )
    return f"pbkdf2_sha256${actual_salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        scheme, salt, expected = str(password_hash or "").split("$", 2)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256" or not salt or not expected:
        return False
    actual = hash_password(password, salt=salt)
    return secrets.compare_digest(actual, password_hash)


def issue_session_token() -> str:
    return f"cfas_{secrets.token_urlsafe(36)}"


def session_expires_at(hours: int | None = None) -> str:
    ttl_hours = max(1, int(hours or settings.ui_auth_session_hours))
    return (utcnow() + timedelta(hours=ttl_hours)).isoformat()


def parse_iso_datetime(value: str | None) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def extract_bearer_token(request: Request) -> str:
    auth_header = (request.headers.get("authorization") or "").strip()
    if not auth_header:
        return ""
    if auth_header.lower().startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def build_user_profile(user_row: Any) -> dict[str, Any]:
    role = normalize_role(getattr(user_row, "role", None) or user_row["role"])
    role_keys = [role]
    permissions = resolve_permissions(role_keys)
    username = str(getattr(user_row, "username", None) or user_row["username"]).strip()
    nickname = str(getattr(user_row, "nickname", None) or user_row["nickname"] or username).strip() or username
    roles = [
        {
            "key": role,
            "name": role,
            "permissions": permissions,
            "perms": permissions,
        }
    ]
    return {
        "id": f"user_{int(getattr(user_row, 'id', None) or user_row['id'])}",
        "userId": int(getattr(user_row, "id", None) or user_row["id"]),
        "username": username,
        "nickname": nickname,
        "email": str(getattr(user_row, "email", None) or user_row["email"] or "").strip(),
        "roles": roles,
        "roleKeys": role_keys,
        "permissions": permissions,
        "perms": permissions,
        "isAdmin": role == "admin",
    }


def success_response(data: dict[str, Any], message: str = "success") -> dict[str, Any]:
    return {
        "success": True,
        "message": message,
        "data": data,
    }


def auth_failed(message: str = "用户名或密码错误", *, status_code: int = 401) -> None:
    raise HTTPException(status_code=status_code, detail=message)


def fetch_user_by_session_token(
    conn: sqlite3.Connection,
    token: str,
    *,
    touch_session: bool = False,
) -> sqlite3.Row | None:
    text = str(token or "").strip()
    if not text:
        return None

    row = conn.execute(
        """
        SELECT u.*, s.id AS session_id, s.expires_at
        FROM auth_sessions AS s
        JOIN users AS u ON u.id = s.user_id
        WHERE s.token = ?
        LIMIT 1
        """,
        (text,),
    ).fetchone()
    if row is None:
        return None

    expires_at = parse_iso_datetime(row["expires_at"])
    if expires_at is None or expires_at <= utcnow():
        conn.execute("DELETE FROM auth_sessions WHERE id = ?", (int(row["session_id"]),))
        return None

    if touch_session:
        conn.execute(
            """
            UPDATE auth_sessions
            SET last_seen_at = ?, expires_at = ?
            WHERE id = ?
            """,
            (utcnow_iso(), session_expires_at(), int(row["session_id"])),
        )

    return row


def require_current_user(conn: sqlite3.Connection, request: Request) -> sqlite3.Row:
    token = extract_bearer_token(request)
    if not token:
        auth_failed("请先登录", status_code=401)
    row = fetch_user_by_session_token(conn, token, touch_session=True)
    if row is None:
        auth_failed("登录已失效，请重新登录", status_code=401)
    if int(row["is_active"] or 0) != 1:
        auth_failed("当前账号已被停用", status_code=403)
    return row
