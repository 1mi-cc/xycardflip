from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from .proxy_resolver import rotate_proxy
from .execution import execution_service


def _normalize_action(value: str | None) -> str:
    text = (value or "").strip().lower()
    if text in {"buy", "list", "sell", "all"}:
        return text
    return "all"


def _contains_business_ban(result: dict[str, Any]) -> bool:
    items = result.get("items")
    if not isinstance(items, list):
        return False
    for item in items:
        if not isinstance(item, dict):
            continue
        code = str(item.get("business_ban_code") or "").strip()
        if code:
            return True
        error_text = str(item.get("error") or "").lower()
        if "business ban" in error_text:
            return True
    return False


class ExecutionRetryService:
    """Background retry service for latest failed execution logs."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False
        self._last_run_at = ""
        self._last_error = ""
        self._total_runs = 0
        self._total_retried = 0
        self._total_succeeded = 0
        self._total_failed = 0

    def status(self) -> dict[str, Any]:
        configured_action = _normalize_action(settings.execution_retry_action)
        with self._lock:
            return {
                "enabled": settings.execution_retry_enabled,
                "running": self._running,
                "interval_sec": settings.execution_retry_interval_sec,
                "batch_size": settings.execution_retry_batch_size,
                "action": configured_action,
                "dry_run": settings.execution_retry_dry_run,
                "force": settings.execution_retry_force,
                "confirm_token_configured": bool(
                    settings.execution_retry_confirm_token.strip()
                    or settings.execution_live_confirm_token.strip()
                ),
                "last_run_at": self._last_run_at,
                "last_error": self._last_error,
                "total_runs": self._total_runs,
                "total_retried": self._total_retried,
                "total_succeeded": self._total_succeeded,
                "total_failed": self._total_failed,
            }

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._running:
                return {"started": False, "reason": "already running"}
            if not settings.execution_retry_enabled:
                return {"started": False, "reason": "EXECUTION_RETRY_ENABLED=false"}
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop,
                daemon=True,
                name="execution-retry-service",
            )
            self._running = True
            self._thread.start()
            return {"started": True}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            if not self._running:
                return {"stopped": False, "reason": "not running"}
            self._stop_event.set()
            thread = self._thread
        if thread:
            thread.join(timeout=5)
        with self._lock:
            self._running = False
        return {"stopped": True}

    def run_once(
        self,
        *,
        limit: int | None = None,
        service_force: bool = False,
        action: str | None = None,
        dry_run: bool | None = None,
        execution_force: bool | None = None,
        confirm_token: str | None = None,
    ) -> dict[str, Any]:
        if not service_force and not settings.execution_retry_enabled:
            return {
                "enabled": False,
                "retried": 0,
                "reason": "EXECUTION_RETRY_ENABLED=false",
            }

        selected_action = _normalize_action(action or settings.execution_retry_action)
        selected_limit = settings.execution_retry_batch_size
        if limit is not None:
            selected_limit = max(1, min(200, int(limit)))
        selected_dry_run = settings.execution_retry_dry_run if dry_run is None else bool(dry_run)
        selected_force = (
            settings.execution_retry_force if execution_force is None else bool(execution_force)
        )
        effective_confirm_token = (confirm_token or "").strip() or (
            settings.execution_retry_confirm_token.strip()
            or settings.execution_live_confirm_token.strip()
        )

        result = execution_service.retry_failed(
            action=None if selected_action == "all" else selected_action,
            limit=selected_limit,
            dry_run=selected_dry_run,
            force=selected_force,
            confirm_token=effective_confirm_token or None,
        )
        retried = int(result.get("retried") or 0)
        succeeded = int(result.get("succeeded") or 0)
        failed = int(result.get("failed") or 0)

        with self._lock:
            self._last_run_at = datetime.now(timezone.utc).isoformat()
            self._last_error = ""
            self._total_runs += 1
            self._total_retried += retried
            self._total_succeeded += succeeded
            self._total_failed += failed

        if _contains_business_ban(result) and settings.execution_auto_rotate_proxy_on_ban:
            rotate_proxy(reason="execution_retry_business_ban", required=False)

        return {
            **result,
            "enabled": settings.execution_retry_enabled,
            "service_force": service_force,
            "configured_action": _normalize_action(settings.execution_retry_action),
            "configured_dry_run": settings.execution_retry_dry_run,
            "configured_force": settings.execution_retry_force,
            "effective_action": selected_action,
            "effective_limit": selected_limit,
            "effective_dry_run": selected_dry_run,
            "effective_force": selected_force,
            "confirm_token_used": bool(effective_confirm_token),
        }

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:  # pragma: no cover
                with self._lock:
                    self._last_run_at = datetime.now(timezone.utc).isoformat()
                    self._last_error = str(exc)
                    self._total_runs += 1
                if settings.execution_auto_rotate_proxy_on_ban:
                    text = str(exc).lower()
                    if "business ban" in text or "http_403" in text or "http_429" in text:
                        rotate_proxy(reason=f"execution_retry_exception:{str(exc)[:120]}", required=False)
            if self._stop_event.wait(timeout=max(5, settings.execution_retry_interval_sec)):
                break
        with self._lock:
            self._running = False


execution_retry_service = ExecutionRetryService()
