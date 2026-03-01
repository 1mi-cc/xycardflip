from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, Optional

from .event_engine import Event, EventType, event_engine
from .main_engine import MainEngine

logger = logging.getLogger(__name__)


@dataclass
class StrategyOrder:
    order_id: str
    strategy_name: str
    listing_row_id: int
    buy_price: float
    sell_price: float
    quantity: int
    status: str
    created_time: str


class Strategy(ABC):
    """Base strategy class."""

    def __init__(self, name: str, main_engine: MainEngine) -> None:
        self.name = name
        self.main_engine = main_engine
        self.event_engine = event_engine
        self.active = False
        self.orders: Dict[str, StrategyOrder] = {}
        self._register_events()

    def _register_events(self) -> None:
        self.event_engine.register(EventType.ITEM_ANALYZED, self.on_item_analyzed)
        self.event_engine.register(EventType.ORDER_TRADED, self.on_order_traded)

    def start(self) -> None:
        self.active = True
        self.on_start()
        logger.info("strategy started: %s", self.name)
        self.main_engine.emit_event(EventType.STRATEGY_STARTED, {"strategy_name": self.name})

    def stop(self) -> None:
        self.active = False
        self.on_stop()
        logger.info("strategy stopped: %s", self.name)
        self.main_engine.emit_event(EventType.STRATEGY_STOPPED, {"strategy_name": self.name})

    @abstractmethod
    def on_start(self) -> None:
        pass

    @abstractmethod
    def on_stop(self) -> None:
        pass

    @abstractmethod
    def on_item_analyzed(self, event: Event) -> None:
        pass

    @abstractmethod
    def on_order_traded(self, event: Event) -> None:
        pass

    def send_order(self, listing_row_id: int, buy_price: float, sell_price: float, quantity: int = 1) -> str:
        order_id = f"{self.name}_{listing_row_id}_{len(self.orders)}"
        order = StrategyOrder(
            order_id=order_id,
            strategy_name=self.name,
            listing_row_id=listing_row_id,
            buy_price=buy_price,
            sell_price=sell_price,
            quantity=quantity,
            status="submitted",
            created_time=datetime.now(timezone.utc).isoformat(),
        )
        self.orders[order_id] = order
        self.main_engine.emit_event(EventType.ORDER_SUBMITTED, {"order": order.__dict__})
        logger.info("[%s] order submitted: %s", self.name, order_id)
        return order_id

    def get_order(self, order_id: str) -> Optional[StrategyOrder]:
        return self.orders.get(order_id)


class StrategyEngine:
    """Strategy manager."""

    def __init__(self, main_engine: MainEngine) -> None:
        self.main_engine = main_engine
        self.strategies: Dict[str, Strategy] = {}

    def add_strategy(self, strategy: Strategy) -> None:
        self.strategies[strategy.name] = strategy
        logger.info("strategy registered: %s", strategy.name)

    def start_strategy(self, name: str) -> None:
        strategy = self.strategies.get(name)
        if strategy:
            strategy.start()
        else:
            logger.error("strategy not found: %s", name)

    def stop_strategy(self, name: str) -> None:
        strategy = self.strategies.get(name)
        if strategy:
            strategy.stop()

    def start_all(self) -> None:
        for strategy in self.strategies.values():
            strategy.start()

    def stop_all(self) -> None:
        for strategy in self.strategies.values():
            strategy.stop()
