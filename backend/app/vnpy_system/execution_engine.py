from __future__ import annotations

import logging
from enum import Enum
from typing import Dict

from .event_engine import Event, EventType, event_engine
from .main_engine import MainEngine

logger = logging.getLogger(__name__)


class OrderStatus(Enum):
    SUBMITTED = "submitted"
    FILLED = "filled"
    PARTIAL = "partial"
    CANCELLED = "cancelled"
    FAILED = "failed"


class ExecutionEngine:
    """Execute orders (simulation only)."""

    def __init__(self, main_engine: MainEngine) -> None:
        self.main_engine = main_engine
        self.orders: Dict[str, Dict] = {}
        event_engine.register(EventType.ORDER_SUBMITTED, self.on_order_submitted)

    def on_order_submitted(self, event: Event) -> None:
        order = event.data.get("order")
        if not order:
            return
        try:
            self._simulate_order_execution(order)
        except Exception as exc:
            logger.error("order execution error: %s", exc)
            self._emit_order_failed(order, str(exc))

    def _simulate_order_execution(self, order: Dict) -> None:
        order_id = order.get("order_id")
        self.orders[order_id] = {
            **order,
            "status": OrderStatus.FILLED.value,
            "filled_time": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        }
        self.main_engine.emit_event(EventType.ORDER_TRADED, {"order": self.orders[order_id]})
        logger.info("order filled: %s", order_id)

    def _emit_order_failed(self, order: Dict, reason: str) -> None:
        order_id = order.get("order_id")
        self.orders[order_id] = {**order, "status": OrderStatus.FAILED.value, "failure_reason": reason}
        logger.error("order failed: %s - %s", order_id, reason)


class PortfolioManager:
    """Track simulated positions."""

    def __init__(self) -> None:
        self.positions: Dict[str, Dict] = {}
        event_engine.register(EventType.ORDER_TRADED, self.on_order_traded)

    def on_order_traded(self, event: Event) -> None:
        order = event.data.get("order")
        if not order or order.get("status") != OrderStatus.FILLED.value:
            return
        self._update_position(order)

    def _update_position(self, order: Dict) -> None:
        listing_row_id = str(order.get("listing_row_id"))
        buy_price = float(order.get("buy_price", 0))
        if listing_row_id not in self.positions:
            self.positions[listing_row_id] = {"quantity": 0, "avg_cost": 0.0}
        pos = self.positions[listing_row_id]
        total_cost = pos["avg_cost"] * pos["quantity"] + buy_price
        pos["quantity"] += 1
        pos["avg_cost"] = total_cost / max(1, pos["quantity"])
        logger.info(
            "position updated: %s qty=%s avg_cost=%.2f",
            listing_row_id,
            pos["quantity"],
            pos["avg_cost"],
        )
