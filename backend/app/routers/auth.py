from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter
from fastapi import Request

from ..config import settings

router = APIRouter(tags=["auth"])

VALID_ROLES: tuple[str, ...] = ("admin", "ops", "viewer")
TOKEN_USERNAME_RE = re.compile(r"^local_token_(?P<username>[A-Za-z0-9_.@-]+)$")


def _normalize_strings(values: list[str] | tuple[str, ...]) -> list[str]:
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


def _to_string_array(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return _normalize_strings([str(item) for item in value if isinstance(item, str)])


def _normalize_role(role: str | None) -> str:
    text = (role or "").strip().lower()
    if text in VALID_ROLES:
        return text
    if text in {"operator", "operation", "ops-user"}:
        return "ops"
    if text in {"read", "readonly", "guest"}:
        return "viewer"
    return settings.ui_auth_default_role if settings.ui_auth_default_role in VALID_ROLES else "admin"


def _role_permission_map() -> dict[str, list[str]]:
    return {
        "admin": _normalize_strings(list(settings.ui_role_permissions_admin)),
        "ops": _normalize_strings(list(settings.ui_role_permissions_ops)),
        "viewer": _normalize_strings(list(settings.ui_role_permissions_viewer)),
    }


def _parse_user_role_map(raw: str | None) -> dict[str, list[str]]:
    text = (raw or "").strip()
    if not text:
        return {}

    mapping: dict[str, list[str]] = {}
    segments = [part.strip() for part in re.split(r"[,;\n\r]+", text) if part.strip()]
    for segment in segments:
        if ":" not in segment:
            continue
        username, raw_roles = segment.split(":", 1)
        key = username.strip().lower()
        if not key:
            continue
        role_parts = [item.strip() for item in re.split(r"[|/]+", raw_roles) if item.strip()]
        normalized_roles = [_normalize_role(item) for item in role_parts]
        normalized_roles = _normalize_strings(normalized_roles)
        if not normalized_roles:
            normalized_roles = [_normalize_role(settings.ui_auth_default_role)]
        mapping[key] = normalized_roles
    return mapping


def _extract_bearer_token(request: Request) -> str:
    auth_header = (request.headers.get("authorization") or "").strip()
    if not auth_header:
        return ""
    lower = auth_header.lower()
    if lower.startswith("bearer "):
        return auth_header[7:].strip()
    return ""


def _username_from_token(token: str) -> str:
    if not token:
        return ""
    matched = TOKEN_USERNAME_RE.match(token)
    if not matched:
        return ""
    return matched.group("username").strip()


def _resolve_username(request: Request, payload: dict[str, Any] | None = None) -> str:
    body = payload or {}
    for key in ("username", "userName", "user"):
        value = str(body.get(key) or "").strip()
        if value:
            return value

    from_query = (request.query_params.get("username") or "").strip()
    if from_query:
        return from_query

    from_header = (request.headers.get("x-username") or "").strip()
    if from_header:
        return from_header

    from_token = _username_from_token(_extract_bearer_token(request))
    if from_token:
        return from_token

    return settings.ui_auth_username


def _resolve_role_keys(
    request: Request,
    username: str,
    payload: dict[str, Any] | None = None,
) -> list[str]:
    body = payload or {}

    if isinstance(body.get("role"), str):
        return [_normalize_role(body.get("role"))]

    incoming_roles = _to_string_array(body.get("roles"))
    if incoming_roles:
        return _normalize_strings([_normalize_role(role) for role in incoming_roles])

    user_role_map = _parse_user_role_map(settings.ui_user_roles)
    mapped = user_role_map.get(username.lower())
    if mapped:
        return mapped

    configured = _normalize_strings([_normalize_role(role) for role in settings.ui_menu_roles])
    if configured:
        return configured

    query_role = _normalize_role(request.query_params.get("role"))
    if query_role:
        return [query_role]

    return [_normalize_role(settings.ui_auth_default_role)]


def _resolve_permissions(role_keys: list[str]) -> list[str]:
    role_to_permissions = _role_permission_map()
    merged: list[str] = []
    seen: set[str] = set()

    for role in role_keys:
        permissions = role_to_permissions.get(role)
        if permissions is None:
            permissions = _normalize_strings(list(settings.ui_menu_permissions))
        for permission in permissions:
            lowered = permission.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            merged.append(permission)
    return merged


def _build_user_profile(request: Request, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    username = _resolve_username(request, payload)
    role_keys = _resolve_role_keys(request, username, payload)
    permissions = _resolve_permissions(role_keys)
    roles = [
        {
            "key": role,
            "name": role,
            "permissions": permissions,
            "perms": permissions,
        }
        for role in role_keys
    ]

    return {
        "id": f"user_{username}",
        "username": username,
        "nickname": settings.ui_auth_nickname or username,
        "roles": roles,
        "roleKeys": role_keys,
        "permissions": permissions,
        "perms": permissions,
    }


def _success(data: dict[str, Any], message: str = "success") -> dict[str, Any]:
    return {
        "success": True,
        "data": data,
        "message": message,
    }


@router.get("/auth/user")
def get_auth_user(request: Request) -> dict[str, Any]:
    profile = _build_user_profile(request)
    token = _extract_bearer_token(request)
    if token:
        profile["token"] = token
    return _success(profile)


@router.get("/auth/userinfo")
def get_auth_userinfo(request: Request) -> dict[str, Any]:
    return get_auth_user(request)


@router.get("/user/profile")
def get_user_profile(request: Request) -> dict[str, Any]:
    profile = _build_user_profile(request)
    payload = {
        "user": profile,
        "roles": profile["roles"],
        "permissions": profile["permissions"],
        "perms": profile["perms"],
    }
    return _success(payload)


@router.post("/auth/login")
def login(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body or {}
    profile = _build_user_profile(request, payload)
    username = profile["username"]
    token = f"local_token_{username}"
    return _success(
        {
            "token": token,
            "user": profile,
            "roles": profile["roles"],
            "permissions": profile["permissions"],
            "perms": profile["perms"],
        },
        message="login_success",
    )


@router.post("/auth/register")
def register(request: Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    payload = body or {}
    username = str(payload.get("username") or "").strip()
    role_keys = _resolve_role_keys(request, username or settings.ui_auth_username, payload)
    return _success(
        {
            "username": username,
            "registered": True,
            "roleKeys": role_keys,
        },
        message="register_success",
    )


@router.post("/auth/logout")
def logout() -> dict[str, Any]:
    return _success({"logout": True}, message="logout_success")


@router.post("/auth/refresh")
def refresh(request: Request) -> dict[str, Any]:
    profile = _build_user_profile(request)
    token = _extract_bearer_token(request) or f"local_token_{profile['username']}"
    return _success(
        {
            "token": token,
            "roles": profile["roles"],
            "permissions": profile["permissions"],
            "perms": profile["perms"],
        },
        message="refresh_success",
    )
