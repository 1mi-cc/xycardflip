from __future__ import annotations

from typing import Any

from fastapi import HTTPException
from fastapi import Request

from .auth_utils import build_user_profile
from .auth_utils import normalize_role
from .auth_utils import require_current_user
from .config import settings
from .database import get_conn


def _bypass_profile() -> dict[str, Any]:
    return {
        "id": "user_test_bypass",
        "userId": 0,
        "username": "test-bypass",
        "nickname": "test-bypass",
        "email": "",
        "roles": [
            {
                "key": "admin",
                "name": "admin",
                "permissions": ["*"],
                "perms": ["*"],
            }
        ],
        "roleKeys": ["admin"],
        "permissions": ["*"],
        "perms": ["*"],
        "isAdmin": True,
    }


def resolve_request_profile(request: Request) -> dict[str, Any]:
    if not bool(settings.ui_auth_enforce_permissions):
        return _bypass_profile()
    with get_conn() as conn:
        user_row = require_current_user(conn, request)
        return build_user_profile(user_row)


def require_any_permission(*permissions: str):
    normalized_permissions = [
        str(permission or "").strip().lower()
        for permission in permissions
        if str(permission or "").strip()
    ]

    def _dependency(request: Request) -> dict[str, Any]:
        profile = resolve_request_profile(request)
        if not bool(settings.ui_auth_enforce_permissions):
            return profile
        granted = {
            str(permission or "").strip().lower()
            for permission in list(profile.get("permissions") or []) + list(profile.get("perms") or [])
            if str(permission or "").strip()
        }
        if any(permission in granted for permission in normalized_permissions):
            return profile
        raise HTTPException(
            status_code=403,
            detail=f"requires permission: {', '.join(normalized_permissions)}",
        )

    return _dependency


def require_any_role(*roles: str):
    normalized_roles = {
        normalize_role(role)
        for role in roles
        if str(role or "").strip()
    }

    def _dependency(request: Request) -> dict[str, Any]:
        profile = resolve_request_profile(request)
        if not bool(settings.ui_auth_enforce_permissions):
            return profile
        current_roles = {
            normalize_role(role)
            for role in list(profile.get("roleKeys") or [])
        }
        if not current_roles and profile.get("isAdmin"):
            current_roles.add("admin")
        if current_roles & normalized_roles:
            return profile
        raise HTTPException(
            status_code=403,
            detail=f"requires role: {', '.join(sorted(normalized_roles))}",
        )

    return _dependency


require_cardflip_view = require_any_permission("cardflip:view", "dashboard:view")
require_cardflip_operate = require_any_role("admin", "ops")
