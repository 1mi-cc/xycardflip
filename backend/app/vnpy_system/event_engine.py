from __future__ import annotations

import logging
import queue
import threading
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Dict, List

logger = logging.getLogger(__name__)


class EventType(Enum):
    """Event type enumeration."""

    # Trading events
    TICK_RECEIVED = "tick_received"
    PRICE_UPDATED = "price_updated"
    ORDER_SUBMITTED = "order_submitted"
    ORDER_TRADED = "order_traded"
    ORDER_CANCELLED = "order_cancelled"

    # Item events
    ITEM_FOUND = "item_found"
    ITEM_ANALYZED = "item_analyzed"
    ITEM_UNDERPRICED = "item_underpriced"
    ITEM_LISTED = "item_listed"
    ITEM_SOLD = "item_sold"

    # Strategy events
    SIGNAL_GENERATED = "signal_generated"
    STRATEGY_STARTED = "strategy_started"
    STRATEGY_STOPPED = "strategy_stopped"

    # System events
    MARKET_OPENED = "market_opened"
    MARKET_CLOSED = "market_closed"
    SYSTEM_WARNING = "system_warning"
    SYSTEM_ERROR = "system_error"


@dataclass
class Event:
    """Event payload."""

    event_type: EventType
    data: Dict
    timestamp: str | None = None


class EventEngine:
    """Thread-safe publish/subscribe event engine."""

    def __init__(self) -> None:
        self.handlers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self.queue: queue.Queue[Event] = queue.Queue()
        self.active = False
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()

    def start(self) -> None:
        """Start the event engine."""
        if self.active:
            return
        self.active = True
        self._thread = threading.Thread(target=self._process_loop, daemon=True, name="vnpy-event-engine")
        self._thread.start()
        logger.info("event engine started")

    def stop(self) -> None:
        """Stop the event engine."""
        if not self.active:
            return
        self.active = False
        thread = self._thread
        if thread:
            thread.join(timeout=2)
        logger.info("event engine stopped")

    def register(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Register an event handler."""
        with self._lock:
            if event_type not in self.handlers:
                self.handlers[event_type] = []
            self.handlers[event_type].append(handler)
        logger.debug("registered handler for %s", event_type.value)

    def unregister(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Unregister an event handler."""
        with self._lock:
            if event_type in self.handlers:
                try:
                    self.handlers[event_type].remove(handler)
                except ValueError:
                    pass

    def emit(self, event: Event) -> None:
        """Emit an event (non-blocking)."""
        self.queue.put(event)

    def _process_loop(self) -> None:
        """Event processing loop."""
        while self.active:
            try:
                event = self.queue.get(timeout=1)
                self._handle_event(event)
            except queue.Empty:
                continue
            except Exception as exc:
                logger.error("event processing error: %s", exc)

    def _handle_event(self, event: Event) -> None:
        """Handle one event."""
        with self._lock:
            handlers = list(self.handlers.get(event.event_type, []))

        for handler in handlers:
            try:
                handler(event)
            except Exception as exc:
                logger.error("event handler error: %s", exc, exc_info=True)


event_engine = EventEngine()
