from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from .. import repositories as repo
from ..config import settings
from .execution import execution_service


def _parse_risk_score(note: str) -> float | None:
    text = (note or "").strip()
    if not text:
        return None
    for part in text.split(";"):
        seg = part.strip()
        if not seg.startswith("risk_score="):
            continue
        _, value = seg.split("=", 1)
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


class AutoTradeService:
    """Background auto-approval service for pending opportunities."""

    def __init__(self) -> None:
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._running = False
        self._last_run_at = ""
        self._last_error = ""
        self._total_runs = 0
        self._total_approved = 0

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": settings.auto_approve_enabled,
                "running": self._running,
                "interval_sec": settings.auto_approve_interval_sec,
                "batch_size": settings.auto_approve_batch_size,
                "min_score": settings.auto_approve_min_score,
                "min_roi": settings.auto_approve_min_roi,
                "max_risk_score": settings.auto_approve_max_risk_score,
                "require_risk_score": settings.auto_approve_require_risk_score,
                "approved_by": settings.auto_approve_approved_by,
                "auto_execute_buy_on_approve": settings.auto_execute_buy_on_approve,
                "auto_execute_buy_dry_run": settings.auto_execute_buy_dry_run,
                "auto_execute_list_on_buy_success": settings.auto_execute_list_on_buy_success,
                "auto_execute_list_dry_run": settings.auto_execute_list_dry_run,
                "last_run_at": self._last_run_at,
                "last_error": self._last_error,
                "total_runs": self._total_runs,
                "total_approved": self._total_approved,
            }

    def start(self) -> dict[str, Any]:
        with self._lock:
            if self._running:
                return {"started": False, "reason": "already running"}
            if not settings.auto_approve_enabled:
                return {"started": False, "reason": "AUTO_APPROVE_ENABLED=false"}
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True, name="auto-trade-service")
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

    def run_once(self, limit: int | None = None, force: bool = False) -> dict[str, Any]:
        if not force and not settings.auto_approve_enabled:
            return {
                "enabled": False,
                "approved": 0,
                "reason": "AUTO_APPROVE_ENABLED=false",
            }

        batch_limit = settings.auto_approve_batch_size
        if limit is not None:
            batch_limit = max(1, min(500, int(limit)))

        rows = repo.list_opportunities(status="pending_review", limit=max(50, batch_limit * 5))
        approved = 0
        skipped_score = 0
        skipped_risk = 0
        skipped_roi = 0
        skipped_missing_risk = 0
        errors = 0
        picked_ids: list[int] = []
        buy_exec_attempted = 0
        buy_exec_succeeded = 0
        buy_exec_failed = 0
        list_exec_attempted = 0
        list_exec_succeeded = 0
        list_exec_failed = 0

        for row in rows:
            if approved >= batch_limit:
                break
            opportunity_id = int(row["id"])
            score = float(row["score"])
            roi = float(row["roi"])
            list_price = float(row["list_price"])
            risk_score = _parse_risk_score(str(row["review_note"] or ""))

            if score < settings.auto_approve_min_score:
                skipped_score += 1
                continue
            if roi < settings.auto_approve_min_roi:
                skipped_roi += 1
                continue
            if risk_score is None and settings.auto_approve_require_risk_score:
                skipped_missing_risk += 1
                continue
            if risk_score is not None and risk_score > settings.auto_approve_max_risk_score:
                skipped_risk += 1
                continue

            approved_buy_price = round(max(0.01, list_price), 2)
            note = (
                f"{settings.auto_approve_note}; score={score:.2f}; roi={roi:.4f}; "
                f"risk_score={risk_score if risk_score is not None else 'na'}"
            )

            try:
                trade_id = repo.create_trade(
                    opportunity_id=opportunity_id,
                    approved_buy_price=approved_buy_price,
                    target_sell_price=float(row["suggested_list_price"]),
                    approved_by=settings.auto_approve_approved_by,
                    note=note,
                )
                repo.update_opportunity_status(opportunity_id, "approved_for_buy", note)
                approved += 1
                picked_ids.append(opportunity_id)
                if settings.auto_execute_buy_on_approve:
                    buy_exec_attempted += 1
                    exec_res = execution_service.execute_buy(
                        trade_id=trade_id,
                        dry_run=settings.auto_execute_buy_dry_run,
                    )
                    if exec_res.get("success"):
                        buy_exec_succeeded += 1
                        if settings.auto_execute_list_on_buy_success:
                            list_exec_attempted += 1
                            list_res = execution_service.execute_list(
                                trade_id=trade_id,
                                dry_run=settings.auto_execute_list_dry_run,
                                note="auto listed after buy execution",
                            )
                            if list_res.get("success"):
                                list_exec_succeeded += 1
                            else:
                                list_exec_failed += 1
                    else:
                        buy_exec_failed += 1
            except Exception:
                errors += 1

        with self._lock:
            self._last_run_at = datetime.now(timezone.utc).isoformat()
            self._last_error = "" if errors == 0 else f"errors={errors}"
            self._total_runs += 1
            self._total_approved += approved

        return {
            "enabled": settings.auto_approve_enabled,
            "approved": approved,
            "errors": errors,
            "considered": len(rows),
            "batch_limit": batch_limit,
            "skipped_score": skipped_score,
            "skipped_roi": skipped_roi,
            "skipped_risk": skipped_risk,
            "skipped_missing_risk": skipped_missing_risk,
            "opportunity_ids": picked_ids,
            "buy_exec_attempted": buy_exec_attempted,
            "buy_exec_succeeded": buy_exec_succeeded,
            "buy_exec_failed": buy_exec_failed,
            "buy_exec_dry_run": settings.auto_execute_buy_dry_run,
            "list_exec_attempted": list_exec_attempted,
            "list_exec_succeeded": list_exec_succeeded,
            "list_exec_failed": list_exec_failed,
            "list_exec_dry_run": settings.auto_execute_list_dry_run,
        }

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except Exception as exc:  # pragma: no cover
                with self._lock:
                    self._last_error = str(exc)
            if self._stop_event.wait(timeout=max(5, settings.auto_approve_interval_sec)):
                break
        with self._lock:
            self._running = False


auto_trade_service = AutoTradeService()
