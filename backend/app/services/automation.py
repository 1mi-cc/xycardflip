from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from typing import Any

from .. import repositories as repo
from ..config import settings
from ..errors import BusyStateError
from ..schemas import ListingIn, ValuationOut
from .autotrade import auto_trade_service
from .execution_retry import execution_retry_service
from .market_monitor import monitor_service
from .opportunity_scan import scan_open_listings
from .supabase_sync import supabase_sync_service


class AutomationService:
    """Orchestrates monitor + scan + autotrade + execution retry + supabase sync."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._run_lock = threading.Lock()
        self._last_run_at = ""
        self._last_run_result: dict[str, Any] = {}
        self._last_busy_at = ""
        self._last_busy_reason = ""

    def status(self) -> dict[str, Any]:
        monitor = monitor_service.status()
        autotrade = auto_trade_service.status()
        execution_retry = execution_retry_service.status()
        supabase_sync = supabase_sync_service.status()
        autotrade_enabled = bool(autotrade.get("enabled"))
        execution_retry_enabled = bool(execution_retry.get("enabled"))
        supabase_enabled = bool(supabase_sync.get("enabled"))
        monitor_required = bool(settings.automation_default_include_monitor)
        autotrade_required = bool(settings.automation_default_include_autotrade and autotrade_enabled)
        execution_retry_required = bool(
            settings.automation_default_include_execution_retry and execution_retry_enabled
        )
        supabase_required = bool(
            settings.automation_default_include_supabase_sync and supabase_enabled
        )
        with self._lock:
            last_run_at = self._last_run_at
            last_run_result = {**self._last_run_result}
            last_busy_at = self._last_busy_at
            last_busy_reason = self._last_busy_reason
        return {
            "monitor": monitor,
            "autotrade": autotrade,
            "execution_retry": execution_retry,
            "supabase_sync": supabase_sync,
            "busy": self._run_lock.locked(),
            "all_running": bool(
                (not monitor_required or monitor.get("is_running"))
                and (not autotrade_required or autotrade.get("running"))
                and (not execution_retry_required or execution_retry.get("running"))
                and (not supabase_required or supabase_sync.get("is_running"))
            ),
            "default_include_monitor": monitor_required,
            "default_include_scan": settings.automation_default_include_scan,
            "default_include_autotrade": autotrade_required,
            "default_include_execution_retry": execution_retry_required,
            "default_include_supabase_sync": supabase_required,
            "default_scan_limit": settings.automation_default_scan_limit,
            "auto_start_monitor": settings.auto_start_monitor,
            "auto_start_autotrade": settings.auto_start_autotrade,
            "auto_start_execution_retry": settings.auto_start_execution_retry,
            "auto_start_supabase_sync": settings.auto_start_supabase_sync,
            "last_run_at": last_run_at,
            "last_run_result": last_run_result,
            "last_busy_at": last_busy_at,
            "last_busy_reason": last_busy_reason,
        }

    def guard_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "service": "automation",
                "busy": self._run_lock.locked(),
                "last_busy_at": self._last_busy_at,
                "last_busy_reason": self._last_busy_reason,
            }

    def _mark_busy(self, reason: str) -> None:
        with self._lock:
            self._last_busy_at = datetime.now(timezone.utc).isoformat()
            self._last_busy_reason = reason

    def start(
        self,
        *,
        include_monitor: bool = True,
        include_autotrade: bool = True,
        include_execution_retry: bool = True,
        include_supabase_sync: bool = False,
    ) -> dict[str, Any]:
        result = {
            "include_monitor": include_monitor,
            "include_autotrade": include_autotrade,
            "include_execution_retry": include_execution_retry,
            "include_supabase_sync": include_supabase_sync,
            "monitor": {"skipped": not include_monitor},
            "autotrade": {"skipped": not include_autotrade},
            "execution_retry": {"skipped": not include_execution_retry},
            "supabase_sync": {"skipped": not include_supabase_sync},
        }
        if include_monitor:
            result["monitor"] = monitor_service.start()
        if include_autotrade:
            result["autotrade"] = auto_trade_service.start()
        if include_execution_retry:
            result["execution_retry"] = execution_retry_service.start()
        if include_supabase_sync:
            result["supabase_sync"] = supabase_sync_service.start()
        result["started_any"] = bool(
            result["monitor"].get("started")
            or result["autotrade"].get("started")
            or result["execution_retry"].get("started")
            or result["supabase_sync"].get("started")
        )
        return result

    def stop(
        self,
        *,
        include_monitor: bool = True,
        include_autotrade: bool = True,
        include_execution_retry: bool = True,
        include_supabase_sync: bool = False,
    ) -> dict[str, Any]:
        result = {
            "include_monitor": include_monitor,
            "include_autotrade": include_autotrade,
            "include_execution_retry": include_execution_retry,
            "include_supabase_sync": include_supabase_sync,
            "monitor": {"skipped": not include_monitor},
            "autotrade": {"skipped": not include_autotrade},
            "execution_retry": {"skipped": not include_execution_retry},
            "supabase_sync": {"skipped": not include_supabase_sync},
        }
        if include_monitor:
            result["monitor"] = monitor_service.stop()
        if include_autotrade:
            result["autotrade"] = auto_trade_service.stop()
        if include_execution_retry:
            result["execution_retry"] = execution_retry_service.stop()
        if include_supabase_sync:
            result["supabase_sync"] = supabase_sync_service.stop()
        result["stopped_any"] = bool(
            result["monitor"].get("stopped")
            or result["autotrade"].get("stopped")
            or result["execution_retry"].get("stopped")
            or result["supabase_sync"].get("stopped")
        )
        return result

    def run_once(
        self,
        *,
        include_monitor: bool = True,
        include_scan: bool = True,
        include_autotrade: bool = True,
        include_execution_retry: bool = True,
        include_supabase_sync: bool = False,
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
            except BusyStateError as exc:
                return {
                    "success": False,
                    "busy": True,
                    "reason": exc.reason,
                    "service": exc.service,
                    "status_code": 409,
                    "error": exc.message or str(exc),
                    "stage": name,
                }
            except Exception as exc:
                return {"success": False, "busy": False, "error": str(exc), "stage": name, "status_code": 500}

        if not self._run_lock.acquire(blocking=False):
            self._mark_busy("run_once_in_progress")
            raise BusyStateError(
                service="automation",
                reason="run_once_in_progress",
                message="automation run is already in progress",
            )

        try:
            normalized_scan_limit = max(
                1,
                min(500, int(scan_limit or settings.automation_default_scan_limit)),
            )
            result: dict[str, Any] = {
                "include_monitor": include_monitor,
                "include_scan": include_scan,
                "include_autotrade": include_autotrade,
                "include_execution_retry": include_execution_retry,
                "include_supabase_sync": include_supabase_sync,
                "force": force,
                "monitor": {"skipped": not include_monitor},
                "scan": {"skipped": not include_scan},
                "autotrade": {"skipped": not include_autotrade},
                "execution_retry": {"skipped": not include_execution_retry},
                "supabase_sync": {"skipped": not include_supabase_sync},
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
            if include_supabase_sync:
                result["supabase_sync"] = _run_stage(
                    "supabase_sync",
                    lambda: supabase_sync_service.run_once(force=force),
                )

            result["success"] = all(
                part.get("success", True) or part.get("skipped", False)
                for part in (
                    result["monitor"],
                    result["scan"],
                    result["autotrade"],
                    result["execution_retry"],
                    result["supabase_sync"],
                )
            )
            result["had_busy"] = any(
                bool(part.get("busy"))
                for part in (
                    result["monitor"],
                    result["scan"],
                    result["autotrade"],
                    result["execution_retry"],
                    result["supabase_sync"],
                )
            )
            ran_at = datetime.now(timezone.utc).isoformat()
            with self._lock:
                self._last_run_at = ran_at
                self._last_run_result = {**result}
            result["ran_at"] = ran_at
            return result
        finally:
            self._run_lock.release()

    def bootstrap_simulation_data(self, count: int = 6) -> dict[str, Any]:
        normalized_count = max(1, min(30, int(count or 6)))
        timestamp = datetime.now(timezone.utc)
        seed_batch_id = timestamp.strftime("%Y%m%d%H%M%S%f")
        seeded = 0

        for index in range(normalized_count):
            list_price = round(88 + (index * 18.0), 2)
            expected_sale_price = round(list_price * 1.38, 2)
            suggested_list_price = round(expected_sale_price * 1.03, 2)
            buy_limit = round(list_price * 1.14, 2)
            if buy_limit <= list_price:
                buy_limit = round(list_price + 8, 2)

            listing = ListingIn(
                source="simulation_seed",
                listing_id=f"sim-{seed_batch_id}-{index}",
                seller_id=f"sim-seller-{(index % 3) + 1}",
                title=f"模拟训练卡片 #{index + 1}",
                description="自动生成的模拟样本，用于验证审批与执行链路。",
                list_price=list_price,
                listed_at=timestamp,
                status="open",
                raw={
                    "seed": True,
                    "seed_at": timestamp.isoformat(),
                    "seed_index": index + 1,
                },
            )
            listing_row_id, created = repo.upsert_listing(listing)
            if not listing_row_id:
                continue

            valuation_id = repo.save_valuation(
                ValuationOut(
                    listing_row_id=listing_row_id,
                    expected_sale_price=expected_sale_price,
                    buy_limit=buy_limit,
                    suggested_list_price=suggested_list_price,
                    ci_low=round(expected_sale_price * 0.93, 2),
                    ci_high=round(expected_sale_price * 1.08, 2),
                    model_confidence=0.91,
                    comparables_count=18,
                    reasoning="simulation seed valuation",
                )
            )

            fee = settings.platform_fee_rate * expected_sale_price
            net_profit = expected_sale_price - list_price - settings.default_shipping_cost - fee
            roi = (net_profit / list_price) if list_price > 0 else 0.0
            score = round(max(80.0, min(99.0, 88.0 - (index * 0.8))), 2)

            repo.upsert_opportunity(
                listing_row_id=listing_row_id,
                valuation_id=valuation_id,
                expected_profit=round(net_profit, 2),
                roi=round(roi, 4),
                score=score,
                status="pending_review",
                note="simulation_seed;risk_score=0;risk_level=low;reasons=none",
            )
            if created:
                seeded += 1

        pending_review = len(repo.list_opportunities(status="pending_review", limit=200))
        return {
            "seeded": seeded,
            "requested": normalized_count,
            "pending_review": pending_review,
        }


automation_service = AutomationService()
