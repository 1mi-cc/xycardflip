from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any

from ..auth_utils import hash_password
from ..config import resolved_dotenv_path
from ..config import settings
from ..database import get_conn
from ..database import get_seed_admin_bootstrap_path
from .gemini_client import GeminiClient
from .startup_diagnostics import startup_configuration_checks


_CONFIG_KEY_ORDER: tuple[str, ...] = (
    "UI_AUTH_PASSWORD",
    "UI_AUTH_NICKNAME",
    "GEMINI_API_KEY",
    "GEMINI_KEY_SOURCE_PATH",
    "AUTO_TUNE_AUTO_APPLY_ENABLED",
    "AUTO_TUNE_COOLDOWN_HOURS",
    "AUTO_TUNE_MIN_CLOSED_BATCHES",
    "AUTO_TUNE_LATEST_MIN_SOLD_COUNT",
    "AUTO_TUNE_PREVIOUS_MIN_SOLD_COUNT",
)

_SECRET_KEYS: set[str] = {"UI_AUTH_PASSWORD", "GEMINI_API_KEY"}

_ENV_TO_PAYLOAD_KEY: dict[str, str] = {
    "UI_AUTH_PASSWORD": "ui_auth_password",
    "UI_AUTH_NICKNAME": "ui_auth_nickname",
    "GEMINI_API_KEY": "gemini_api_key",
    "GEMINI_KEY_SOURCE_PATH": "gemini_key_source_path",
    "AUTO_TUNE_AUTO_APPLY_ENABLED": "auto_tune_auto_apply_enabled",
    "AUTO_TUNE_COOLDOWN_HOURS": "auto_tune_cooldown_hours",
    "AUTO_TUNE_MIN_CLOSED_BATCHES": "auto_tune_min_closed_batches",
    "AUTO_TUNE_LATEST_MIN_SOLD_COUNT": "auto_tune_latest_min_sold_count",
    "AUTO_TUNE_PREVIOUS_MIN_SOLD_COUNT": "auto_tune_previous_min_sold_count",
}


def _env_file_path() -> Path:
    path = resolved_dotenv_path().expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_env_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return []


def _upsert_env_lines(lines: list[str], updates: dict[str, str]) -> list[str]:
    result = list(lines)
    for key, value in updates.items():
        prefix = f"{key}="
        matched = False
        for idx, line in enumerate(result):
            if line.startswith(prefix):
                result[idx] = f"{key}={value}"
                matched = True
                break
        if not matched:
            result.append(f"{key}={value}")
    return result


def _write_env_updates(updates: dict[str, str]) -> Path:
    path = _env_file_path()
    lines = _read_env_lines(path)
    final_lines = _upsert_env_lines(lines, updates)
    path.write_text("\n".join(final_lines).rstrip() + "\n", encoding="utf-8")
    return path


def _set_runtime_value(key: str, value: Any) -> None:
    os.environ[key] = str(value)
    if key == "UI_AUTH_PASSWORD":
        object.__setattr__(settings, "ui_auth_password", str(value))
    elif key == "UI_AUTH_NICKNAME":
        object.__setattr__(settings, "ui_auth_nickname", str(value))
    elif key == "GEMINI_API_KEY":
        object.__setattr__(settings, "gemini_api_key", str(value))
    elif key == "GEMINI_KEY_SOURCE_PATH":
        object.__setattr__(settings, "gemini_key_source_path", str(value))
    elif key == "AUTO_TUNE_AUTO_APPLY_ENABLED":
        object.__setattr__(
            settings,
            "auto_tune_auto_apply_enabled",
            str(value).strip().lower() in {"1", "true", "yes", "on"},
        )
    elif key == "AUTO_TUNE_COOLDOWN_HOURS":
        object.__setattr__(settings, "auto_tune_cooldown_hours", int(value))
    elif key == "AUTO_TUNE_MIN_CLOSED_BATCHES":
        object.__setattr__(settings, "auto_tune_min_closed_batches", int(value))
    elif key == "AUTO_TUNE_LATEST_MIN_SOLD_COUNT":
        object.__setattr__(settings, "auto_tune_latest_min_sold_count", int(value))
    elif key == "AUTO_TUNE_PREVIOUS_MIN_SOLD_COUNT":
        object.__setattr__(settings, "auto_tune_previous_min_sold_count", int(value))


def _normalize_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _normalize_int(value: Any, default: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def _bootstrap_password_mode() -> bool:
    return not bool(str(settings.ui_auth_password or "").strip())


def _settings_snapshot() -> dict[str, Any]:
    return {
        "UI_AUTH_PASSWORD": str(settings.ui_auth_password or ""),
        "UI_AUTH_NICKNAME": str(settings.ui_auth_nickname or ""),
        "GEMINI_API_KEY": str(settings.gemini_api_key or ""),
        "GEMINI_KEY_SOURCE_PATH": str(settings.gemini_key_source_path or ""),
        "AUTO_TUNE_AUTO_APPLY_ENABLED": bool(settings.auto_tune_auto_apply_enabled),
        "AUTO_TUNE_COOLDOWN_HOURS": int(settings.auto_tune_cooldown_hours),
        "AUTO_TUNE_MIN_CLOSED_BATCHES": int(settings.auto_tune_min_closed_batches),
        "AUTO_TUNE_LATEST_MIN_SOLD_COUNT": int(settings.auto_tune_latest_min_sold_count),
        "AUTO_TUNE_PREVIOUS_MIN_SOLD_COUNT": int(settings.auto_tune_previous_min_sold_count),
    }


def _sanitize_audit_value(key: str, value: Any) -> Any:
    if key in {"UI_AUTH_PASSWORD", "GEMINI_API_KEY"}:
        text = str(value or "").strip()
        return {
            "kind": "secret",
            "set": bool(text),
            "length": len(text),
        }
    if key == "AUTO_TUNE_AUTO_APPLY_ENABLED":
        return bool(value)
    if key in {
        "AUTO_TUNE_COOLDOWN_HOURS",
        "AUTO_TUNE_MIN_CLOSED_BATCHES",
        "AUTO_TUNE_LATEST_MIN_SOLD_COUNT",
        "AUTO_TUNE_PREVIOUS_MIN_SOLD_COUNT",
    }:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0
    return str(value or "")


def _create_setting_audit_log(
    *,
    actor: str,
    source: str,
    changed_keys: list[str],
    previous_values: dict[str, Any],
    next_values: dict[str, Any],
) -> dict[str, Any]:
    details = {
        "previous": {
            key: _sanitize_audit_value(key, previous_values.get(key))
            for key in changed_keys
        },
        "next": {
            key: _sanitize_audit_value(key, next_values.get(key))
            for key in changed_keys
        },
    }
    summary = f"Changed {', '.join(changed_keys)}"
    with get_conn() as conn:
        cur = conn.execute(
            """
            INSERT INTO system_setting_audit_logs(
                actor,
                source,
                summary,
                changed_keys_json,
                details_json
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                str(actor or "").strip(),
                str(source or "").strip(),
                summary,
                json.dumps(changed_keys, ensure_ascii=True),
                json.dumps(details, ensure_ascii=True),
            ),
        )
        row = conn.execute(
            "SELECT * FROM system_setting_audit_logs WHERE id = ?",
            (int(cur.lastrowid),),
        ).fetchone()
    return _serialize_setting_audit_row(row)


def _serialize_setting_audit_row(row: Any) -> dict[str, Any]:
    return {
        "id": int(row["id"]),
        "actor": str(row["actor"] or ""),
        "source": str(row["source"] or ""),
        "summary": str(row["summary"] or ""),
        "changed_keys": json.loads(str(row["changed_keys_json"] or "[]")),
        "details": json.loads(str(row["details_json"] or "{}")),
        "created_at": row["created_at"],
    }


def list_setting_audit_logs(limit: int = 50) -> list[dict[str, Any]]:
    capped_limit = max(1, min(200, int(limit)))
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM system_setting_audit_logs
            ORDER BY id DESC
            LIMIT ?
            """,
            (capped_limit,),
        ).fetchall()
    return [_serialize_setting_audit_row(row) for row in rows]


def get_setting_audit_log(audit_id: int) -> dict[str, Any] | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM system_setting_audit_logs WHERE id = ? LIMIT 1",
            (audit_id,),
        ).fetchone()
    if not row:
        return None
    return _serialize_setting_audit_row(row)


def get_first_run_setup_status() -> dict[str, Any]:
    bootstrap_path = get_seed_admin_bootstrap_path()
    checks = startup_configuration_checks()
    gemini_runtime_status = GeminiClient().get_runtime_status()
    return {
        "config_path": str(_env_file_path()),
        "bootstrap_password_mode": _bootstrap_password_mode(),
        "bootstrap_credentials_path": str(bootstrap_path),
        "bootstrap_credentials_exists": bootstrap_path.exists(),
        "setup_recommended": _bootstrap_password_mode() or bool(checks["count"]),
        "startup_checks": checks,
        "values": {
            "ui_auth_username": settings.ui_auth_username,
            "ui_auth_nickname": settings.ui_auth_nickname,
            "ui_auth_password_set": bool(str(settings.ui_auth_password or "").strip()),
            "gemini_api_key_set": bool(str(settings.gemini_api_key or "").strip()),
            "gemini_key_source_path": str(settings.gemini_key_source_path or ""),
            "gemini_runtime_status": gemini_runtime_status,
            "auto_tune_auto_apply_enabled": settings.auto_tune_auto_apply_enabled,
            "auto_tune_cooldown_hours": settings.auto_tune_cooldown_hours,
            "auto_tune_min_closed_batches": settings.auto_tune_min_closed_batches,
            "auto_tune_latest_min_sold_count": settings.auto_tune_latest_min_sold_count,
            "auto_tune_previous_min_sold_count": settings.auto_tune_previous_min_sold_count,
        },
    }


def apply_first_run_setup(
    payload: dict[str, Any],
    *,
    actor: str = "operator",
    source: str = "system_settings",
) -> dict[str, Any]:
    previous_values = _settings_snapshot()
    updates: dict[str, str] = {}

    nickname = str(payload.get("ui_auth_nickname") or settings.ui_auth_nickname).strip()
    if nickname:
        updates["UI_AUTH_NICKNAME"] = nickname

    gemini_api_key = str(payload.get("gemini_api_key") or "").strip()
    if gemini_api_key:
        updates["GEMINI_API_KEY"] = gemini_api_key

    gemini_key_source_path = str(payload.get("gemini_key_source_path") or "").strip()
    if gemini_key_source_path:
        updates["GEMINI_KEY_SOURCE_PATH"] = gemini_key_source_path

    auto_apply = _normalize_bool(
        payload.get("auto_tune_auto_apply_enabled"),
        settings.auto_tune_auto_apply_enabled,
    )
    updates["AUTO_TUNE_AUTO_APPLY_ENABLED"] = "true" if auto_apply else "false"
    updates["AUTO_TUNE_COOLDOWN_HOURS"] = str(
        _normalize_int(
            payload.get("auto_tune_cooldown_hours"),
            settings.auto_tune_cooldown_hours,
            0,
            24 * 365,
        )
    )
    updates["AUTO_TUNE_MIN_CLOSED_BATCHES"] = str(
        _normalize_int(
            payload.get("auto_tune_min_closed_batches"),
            settings.auto_tune_min_closed_batches,
            1,
            10,
        )
    )
    updates["AUTO_TUNE_LATEST_MIN_SOLD_COUNT"] = str(
        _normalize_int(
            payload.get("auto_tune_latest_min_sold_count"),
            settings.auto_tune_latest_min_sold_count,
            1,
            100,
        )
    )
    updates["AUTO_TUNE_PREVIOUS_MIN_SOLD_COUNT"] = str(
        _normalize_int(
            payload.get("auto_tune_previous_min_sold_count"),
            settings.auto_tune_previous_min_sold_count,
            1,
            100,
        )
    )

    new_password = str(payload.get("ui_auth_password") or "").strip()
    if new_password:
        if len(new_password) < 6:
            raise ValueError("admin password must be at least 6 characters")
        updates["UI_AUTH_PASSWORD"] = new_password
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE users
                SET password_hash = ?, nickname = ?, updated_at = CURRENT_TIMESTAMP
                WHERE lower(username) = lower(?)
                """,
                (hash_password(new_password), nickname or settings.ui_auth_nickname, settings.ui_auth_username),
            )

    env_path = _write_env_updates(updates)
    for key in _CONFIG_KEY_ORDER:
        if key in updates:
            _set_runtime_value(key, updates[key])

    if nickname and not new_password:
        with get_conn() as conn:
            conn.execute(
                """
                UPDATE users
                SET nickname = ?, updated_at = CURRENT_TIMESTAMP
                WHERE lower(username) = lower(?)
                """,
                (nickname, settings.ui_auth_username),
            )

    next_values = _settings_snapshot()
    changed_keys = [key for key in _CONFIG_KEY_ORDER if key in updates]
    audit_entry = (
        _create_setting_audit_log(
            actor=actor,
            source=source,
            changed_keys=changed_keys,
            previous_values=previous_values,
            next_values=next_values,
        )
        if changed_keys
        else None
    )

    return {
        "saved": True,
        "config_path": str(env_path),
        "applied_keys": changed_keys,
        "audit": audit_entry,
        "status": get_first_run_setup_status(),
    }


def rollback_setting_audit(
    audit_id: int,
    *,
    actor: str = "operator",
    source: str = "system_settings_rollback",
) -> dict[str, Any]:
    audit = get_setting_audit_log(audit_id)
    if not audit:
        raise ValueError("setting audit log not found")

    previous_values = audit.get("details", {}).get("previous", {})
    changed_keys = list(audit.get("changed_keys") or [])
    payload: dict[str, Any] = {}
    skipped_secret_keys: list[str] = []

    for key in changed_keys:
        if key in _SECRET_KEYS:
            skipped_secret_keys.append(key)
            continue
        payload_key = _ENV_TO_PAYLOAD_KEY.get(key)
        if not payload_key:
            continue
        payload[payload_key] = previous_values.get(key)

    if not payload:
        raise ValueError("selected audit entry only contains non-revertible secret changes")

    result = apply_first_run_setup(payload, actor=actor, source=source)
    result["rollback_of_audit_id"] = audit_id
    result["skipped_secret_keys"] = skipped_secret_keys
    return result
