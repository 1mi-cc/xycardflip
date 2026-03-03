from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from ..config import settings
from .autotrade import auto_trade_service
from .execution_retry import execution_retry_service
from .market_monitor import monitor_service
from .opportunity_scan import scan_open_listings


class AutomationService:
    """Orchestrates monitor + scan + autotrade + execution retry."""

    def __init__(self) -> None:
        self._last_run_at = ""
        self._last_run_result: dict[str, Any] = {}

    def status(self) -> dict[str, Any]:
        monitor = monitor_service.status()
        autotrade = auto_trade_service.status()
        execution_retry = execution_retry_service.status()
        return {
            "monitor": monitor,
            "autotrade": autotrade,
            "execution_retry": execution_retry,
            "all_running": bool(
                monitor.get("is_running")
                and autotrade.get("running")
                and execution_retry.get("running")
            ),
            "default_include_monitor": settings.automation_default_include_monitor,
            "default_include_scan": settings.automation_default_include_scan,
            "default_include_autotrade": settings.automation_default_include_autotrade,
            "default_include_execution_retry": settings.automation_default_include_execution_retry,
            "default_scan_limit": settings.automation_default_scan_limit,
            "auto_start_monitor": settings.auto_start_monitor,
            "auto_start_autotrade": settings.auto_start_autotrade,
            "auto_start_execution_retry": settings.auto_start_execution_retry,
            "last_run_at": self._last_run_at,
            "last_run_result": self._last_run_result,
        }

    def start(
        self,
        *,
        include_monitor: bool = True,
        include_autotrade: bool = True,
        include_execution_retry: bool = True,
    ) -> dict[str, Any]:
        result = {
            "include_monitor": include_monitor,
            "include_autotrade": include_autotrade,
            "include_execution_retry": include_execution_retry,
            "monitor": {"skipped": not include_monitor},
            "autotrade": {"skipped": not include_autotrade},
            "execution_retry": {"skipped": not include_execution_retry},
        }
        if include_monitor:
            result["monitor"] = monitor_service.start()
        if include_autotrade:
            result["autotrade"] = auto_trade_service.start()
        if include_execution_retry:
            result["execution_retry"] = execution_retry_service.start()
        result["started_any"] = bool(
            result["monitor"].get("started")
            or result["autotrade"].get("started")
            or result["execution_retry"].get("started")
        )
        return result

    def stop(
        self,
        *,
        include_monitor: bool = True,
        include_autotrade: bool = True,
        include_execution_retry: bool = True,
    ) -> dict[str, Any]:
        result = {
            "include_monitor": include_monitor,
            "include_autotrade": include_autotrade,
            "include_execution_retry": include_execution_retry,
            "monitor": {"skipped": not include_monitor},
            "autotrade": {"skipped": not include_autotrade},
            "execution_retry": {"skipped": not include_execution_retry},
        }
        if include_monitor:
            result["monitor"] = monitor_service.stop()
        if include_autotrade:
            result["autotrade"] = auto_trade_service.stop()
        if include_execution_retry:
            result["execution_retry"] = execution_retry_service.stop()
        result["stopped_any"] = bool(
            result["monitor"].get("stopped")
            or result["autotrade"].get("stopped")
            or result["execution_retry"].get("stopped")
        )
        return result

    def run_once(
        self,
        *,
        include_monitor: bool = True,
        include_scan: bool = True,
        include_autotrade: bool = True,
        include_execution_retry: bool = True,
        scan_limit: int | None = None,
        autotrade_limit: int | None = None,
        execution_retry_limit: int | None = None,
        force: bool = False,
        confirm_token: str | None = None,
    ) -> dict[str, Any]:
        def _run_stage(name: str, func: Any) -> dict[str, Any]:
            try:
                payload = func()
                if isinstance(payload, dict):
                    return {"success": True, **payload}
                return {"success": True, "result": payload}
            except Exception as exc:
                return {"success": False, "error": str(exc), "stage": name}

        normalized_scan_limit = max(
            1,
            min(500, int(scan_limit or settings.automation_default_scan_limit)),
        )
        result: dict[str, Any] = {
            "include_monitor": include_monitor,
            "include_scan": include_scan,
            "include_autotrade": include_autotrade,
            "include_execution_retry": include_execution_retry,
            "force": force,
            "monitor": {"skipped": not include_monitor},
            "scan": {"skipped": not include_scan},
            "autotrade": {"skipped": not include_autotrade},
            "execution_retry": {"skipped": not include_execution_retry},
        }

        if include_monitor:
            result["monitor"] = _run_stage("monitor", monitor_service.run_once)
        if include_scan:
            result["scan"] = _run_stage(
                "scan",
                lambda: asyncio.run(scan_open_listings(limit=normalized_scan_limit)),
            )
        if include_autotrade:
            result["autotrade"] = _run_stage(
                "autotrade",
                lambda: auto_trade_service.run_once(
                    limit=autotrade_limit,
                    force=force,
                ),
            )
        if include_execution_retry:
            result["execution_retry"] = _run_stage(
                "execution_retry",
                lambda: execution_retry_service.run_once(
                    limit=execution_retry_limit,
                    service_force=force,
                    confirm_token=confirm_token,
                ),
            )

        self._last_run_at = datetime.now(timezone.utc).isoformat()
        self._last_run_result = result
        result["ran_at"] = self._last_run_at
        return result


automation_service = AutomationService()
