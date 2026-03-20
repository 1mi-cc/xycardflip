from __future__ import annotations

import random
import threading
from datetime import datetime, timezone
from typing import Any

from .. import repositories as repo
from ..config import settings
from ..errors import BusyStateError
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
        self._run_lock = threading.Lock()
        self._running = False
        self._last_run_at = ""
        self._last_error = ""
        self._last_busy_at = ""
        self._last_busy_reason = ""
        self._total_runs = 0
        self._total_approved = 0
        self._interval_sec = max(5, int(settings.auto_approve_interval_sec))
        self._batch_size = max(1, int(settings.auto_approve_batch_size))
        self._min_score = float(settings.auto_approve_min_score)
        self._min_roi = float(settings.auto_approve_min_roi)
        self._max_risk_score = float(settings.auto_approve_max_risk_score)
        self._require_risk_score = bool(settings.auto_approve_require_risk_score)
        self._auto_execute_buy_on_approve = bool(settings.auto_execute_buy_on_approve)
        self._auto_execute_buy_dry_run = bool(settings.auto_execute_buy_dry_run)
        self._auto_execute_list_on_buy_success = bool(settings.auto_execute_list_on_buy_success)
        self._auto_execute_list_dry_run = bool(settings.auto_execute_list_dry_run)
        self._auto_execute_list_discount_min_pct = float(settings.auto_execute_list_discount_min_pct)
        self._auto_execute_list_discount_max_pct = float(settings.auto_execute_list_discount_max_pct)
        if self._auto_execute_list_discount_min_pct > self._auto_execute_list_discount_max_pct:
            self._auto_execute_list_discount_min_pct, self._auto_execute_list_discount_max_pct = (
                self._auto_execute_list_discount_max_pct,
                self._auto_execute_list_discount_min_pct,
            )
        self._auto_execute_sell_on_list_success = bool(settings.auto_execute_sell_on_list_success)
        self._auto_execute_sell_dry_run = bool(settings.auto_execute_sell_dry_run)
        self._auto_execute_sell_price_multiplier = float(settings.auto_execute_sell_price_multiplier)

    def update_config(
        self,
        *,
        interval_sec: int | None = None,
        batch_size: int | None = None,
        min_score: float | None = None,
        min_roi: float | None = None,
        max_risk_score: float | None = None,
        require_risk_score: bool | None = None,
        auto_execute_buy_on_approve: bool | None = None,
        auto_execute_buy_dry_run: bool | None = None,
        auto_execute_list_on_buy_success: bool | None = None,
        auto_execute_list_dry_run: bool | None = None,
        auto_execute_list_discount_min_pct: float | None = None,
        auto_execute_list_discount_max_pct: float | None = None,
        auto_execute_sell_on_list_success: bool | None = None,
        auto_execute_sell_dry_run: bool | None = None,
        auto_execute_sell_price_multiplier: float | None = None,
    ) -> dict[str, Any]:
        with self._lock:
            if interval_sec is not None:
                self._interval_sec = max(5, min(3600, int(interval_sec)))
            if batch_size is not None:
                self._batch_size = max(1, min(500, int(batch_size)))
            if min_score is not None:
                self._min_score = max(0.0, min(100.0, float(min_score)))
            if min_roi is not None:
                self._min_roi = max(0.0, min(10.0, float(min_roi)))
            if max_risk_score is not None:
                self._max_risk_score = max(0.0, min(100.0, float(max_risk_score)))
            if require_risk_score is not None:
                self._require_risk_score = bool(require_risk_score)
            if auto_execute_buy_on_approve is not None:
                self._auto_execute_buy_on_approve = bool(auto_execute_buy_on_approve)
            if auto_execute_buy_dry_run is not None:
                self._auto_execute_buy_dry_run = bool(auto_execute_buy_dry_run)
            if auto_execute_list_on_buy_success is not None:
                self._auto_execute_list_on_buy_success = bool(auto_execute_list_on_buy_success)
            if auto_execute_list_dry_run is not None:
                self._auto_execute_list_dry_run = bool(auto_execute_list_dry_run)
            if auto_execute_list_discount_min_pct is not None:
                self._auto_execute_list_discount_min_pct = max(
                    0.0,
                    min(99.0, float(auto_execute_list_discount_min_pct)),
                )
            if auto_execute_list_discount_max_pct is not None:
                self._auto_execute_list_discount_max_pct = max(
                    0.0,
                    min(99.0, float(auto_execute_list_discount_max_pct)),
                )
            if auto_execute_sell_on_list_success is not None:
                self._auto_execute_sell_on_list_success = bool(auto_execute_sell_on_list_success)
            if auto_execute_sell_dry_run is not None:
                self._auto_execute_sell_dry_run = bool(auto_execute_sell_dry_run)
            if auto_execute_sell_price_multiplier is not None:
                self._auto_execute_sell_price_multiplier = max(
                    0.0,
                    min(5.0, float(auto_execute_sell_price_multiplier)),
                )
            if self._auto_execute_list_discount_min_pct > self._auto_execute_list_discount_max_pct:
                self._auto_execute_list_discount_min_pct, self._auto_execute_list_discount_max_pct = (
                    self._auto_execute_list_discount_max_pct,
                    self._auto_execute_list_discount_min_pct,
                )
        return self.status()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "enabled": settings.auto_approve_enabled,
                "running": self._running,
                "busy": self._run_lock.locked(),
                "interval_sec": self._interval_sec,
                "batch_size": self._batch_size,
                "min_score": self._min_score,
                "min_roi": self._min_roi,
                "max_risk_score": self._max_risk_score,
                "require_risk_score": self._require_risk_score,
                "approved_by": settings.auto_approve_approved_by,
                "auto_execute_buy_on_approve": self._auto_execute_buy_on_approve,
                "auto_execute_buy_dry_run": self._auto_execute_buy_dry_run,
                "auto_execute_list_on_buy_success": self._auto_execute_list_on_buy_success,
                "auto_execute_list_dry_run": self._auto_execute_list_dry_run,
                "auto_execute_list_discount_min_pct": self._auto_execute_list_discount_min_pct,
                "auto_execute_list_discount_max_pct": self._auto_execute_list_discount_max_pct,
                "auto_execute_sell_on_list_success": self._auto_execute_sell_on_list_success,
                "auto_execute_sell_dry_run": self._auto_execute_sell_dry_run,
                "auto_execute_sell_price_multiplier": self._auto_execute_sell_price_multiplier,
                "last_run_at": self._last_run_at,
                "last_error": self._last_error,
                "last_busy_at": self._last_busy_at,
                "last_busy_reason": self._last_busy_reason,
                "total_runs": self._total_runs,
                "total_approved": self._total_approved,
            }

    def guard_status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "service": "autotrade",
                "busy": self._run_lock.locked(),
                "last_busy_at": self._last_busy_at,
                "last_busy_reason": self._last_busy_reason,
            }

    def _mark_busy(self, reason: str) -> None:
        with self._lock:
            self._last_busy_at = datetime.now(timezone.utc).isoformat()
            self._last_busy_reason = reason

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
        if not self._run_lock.acquire(blocking=False):
            self._mark_busy("run_once_in_progress")
            raise BusyStateError(
                service="autotrade",
                reason="run_once_in_progress",
                message="autotrade run is already in progress",
            )

        try:
            with self._lock:
                configured_batch_size = self._batch_size
                min_score = self._min_score
                min_roi = self._min_roi
                max_risk_score = self._max_risk_score
                require_risk_score = self._require_risk_score
                auto_execute_buy_on_approve = self._auto_execute_buy_on_approve
                auto_execute_buy_dry_run = self._auto_execute_buy_dry_run
                auto_execute_list_on_buy_success = self._auto_execute_list_on_buy_success
                auto_execute_list_dry_run = self._auto_execute_list_dry_run
                auto_execute_list_discount_min_pct = self._auto_execute_list_discount_min_pct
                auto_execute_list_discount_max_pct = self._auto_execute_list_discount_max_pct
                auto_execute_sell_on_list_success = self._auto_execute_sell_on_list_success
                auto_execute_sell_dry_run = self._auto_execute_sell_dry_run
                auto_execute_sell_price_multiplier = self._auto_execute_sell_price_multiplier

            batch_limit = configured_batch_size
            if limit is not None:
                batch_limit = max(1, min(500, int(limit)))

            rows = repo.list_opportunities(status="pending_review", limit=max(50, batch_limit * 5))
            approved = 0
            skipped_score = 0
            skipped_risk = 0
            skipped_roi = 0
            skipped_missing_risk = 0
            skipped_not_pending = 0
            idempotent_hits = 0
            errors = 0
            picked_ids: list[int] = []
            buy_exec_attempted = 0
            buy_exec_succeeded = 0
            buy_exec_failed = 0
            list_exec_attempted = 0
            list_exec_succeeded = 0
            list_exec_failed = 0
            sell_exec_attempted = 0
            sell_exec_succeeded = 0
            sell_exec_failed = 0

            for row in rows:
                if approved >= batch_limit:
                    break
                opportunity_id = int(row["id"])
                score = float(row["score"])
                roi = float(row["roi"])
                list_price = float(row["list_price"])
                risk_score = _parse_risk_score(str(row["review_note"] or ""))

                if score < min_score:
                    skipped_score += 1
                    continue
                if roi < min_roi:
                    skipped_roi += 1
                    continue
                if risk_score is None and require_risk_score:
                    skipped_missing_risk += 1
                    continue
                if risk_score is not None and risk_score > max_risk_score:
                    skipped_risk += 1
                    continue

                approved_buy_price = round(max(0.01, list_price), 2)
                note = (
                    f"{settings.auto_approve_note}; score={score:.2f}; roi={roi:.4f}; "
                    f"risk_score={risk_score if risk_score is not None else 'na'}"
                )
                if settings.monitor_include_virtual_goods_channels:
                    channels = [ch.strip() for ch in settings.monitor_virtual_goods_channels if ch and ch.strip()]
                    if channels:
                        note = f"{note}; monitored_channels={','.join(channels)}"

                try:
                    approval = repo.approve_opportunity_idempotent(
                        opportunity_id=opportunity_id,
                        approved_buy_price=approved_buy_price,
                        approved_by=settings.auto_approve_approved_by,
                        note=note,
                    )
                    if approval.get("idempotent"):
                        idempotent_hits += 1
                        continue
                    if not approval.get("created"):
                        skipped_not_pending += 1
                        continue

                    trade_id = int(approval["trade_id"])
                    approved += 1
                    picked_ids.append(opportunity_id)
                    if auto_execute_buy_on_approve:
                        buy_exec_attempted += 1
                        exec_res = execution_service.execute_buy(
                            trade_id=trade_id,
                            dry_run=auto_execute_buy_dry_run,
                        )
                        if exec_res.get("success"):
                            buy_exec_succeeded += 1
                            if auto_execute_list_on_buy_success:
                                current_trade = repo.get_trade(trade_id)
                                target_sell_price = float(
                                    current_trade["target_sell_price"] if current_trade else approved_buy_price
                                )
                                discount_pct = random.uniform(
                                    auto_execute_list_discount_min_pct,
                                    auto_execute_list_discount_max_pct,
                                )
                                discounted_target_price = round(
                                    max(
                                        approved_buy_price + 0.01,
                                        target_sell_price * (1 - discount_pct / 100.0),
                                    ),
                                    2,
                                )
                                repo.update_trade_target_price(
                                    trade_id=trade_id,
                                    target_sell_price=discounted_target_price,
                                    note=(
                                        "auto-applied "
                                        f"{discount_pct:.2f}% discount for fast sale"
                                    ),
                                )
                                list_exec_attempted += 1
                                list_res = execution_service.execute_list(
                                    trade_id=trade_id,
                                    dry_run=auto_execute_list_dry_run,
                                    note=(
                                        "auto listed after buy execution; "
                                        f"discount={discount_pct:.2f}%"
                                    ),
                                )
                                if list_res.get("success"):
                                    list_exec_succeeded += 1
                                    if auto_execute_sell_on_list_success:
                                        sell_exec_attempted += 1
                                        sell_price = round(
                                            max(
                                                approved_buy_price + 0.01,
                                                discounted_target_price * auto_execute_sell_price_multiplier,
                                            ),
                                            2,
                                        )
                                        sell_res = execution_service.execute_sell(
                                            trade_id=trade_id,
                                            dry_run=auto_execute_sell_dry_run,
                                            sold_price=sell_price,
                                            note=(
                                                "auto sell after list success; "
                                                f"sell_multiplier={auto_execute_sell_price_multiplier:.4f}"
                                            ),
                                        )
                                        if sell_res.get("success"):
                                            sell_exec_succeeded += 1
                                        else:
                                            sell_exec_failed += 1
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
                "skipped_not_pending": skipped_not_pending,
                "idempotent_hits": idempotent_hits,
                "opportunity_ids": picked_ids,
                "buy_exec_attempted": buy_exec_attempted,
                "buy_exec_succeeded": buy_exec_succeeded,
                "buy_exec_failed": buy_exec_failed,
                "buy_exec_dry_run": auto_execute_buy_dry_run,
                "list_exec_attempted": list_exec_attempted,
                "list_exec_succeeded": list_exec_succeeded,
                "list_exec_failed": list_exec_failed,
                "list_exec_dry_run": auto_execute_list_dry_run,
                "sell_exec_attempted": sell_exec_attempted,
                "sell_exec_succeeded": sell_exec_succeeded,
                "sell_exec_failed": sell_exec_failed,
                "sell_exec_dry_run": auto_execute_sell_dry_run,
            }
        finally:
            self._run_lock.release()

    def _loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.run_once()
            except BusyStateError:
                pass
            except Exception as exc:  # pragma: no cover
                with self._lock:
                    self._last_error = str(exc)
            with self._lock:
                interval_sec = self._interval_sec
            if self._stop_event.wait(timeout=max(5, int(interval_sec))):
                break
        with self._lock:
            self._running = False


auto_trade_service = AutoTradeService()
