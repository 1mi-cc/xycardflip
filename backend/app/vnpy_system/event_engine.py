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


@dataclass
class HandlerStats:
    """Per-handler runtime status and fault isolation metrics."""

    name: str
    handled_events: int = 0
    total_errors: int = 0
    consecutive_errors: int = 0
    last_error: str = ""
    quarantined: bool = False
    max_consecutive_errors: int = 3


class EventEngine:
    """Thread-safe publish/subscribe event engine."""

    def __init__(self) -> None:
        self.handlers: Dict[EventType, List[Callable[[Event], None]]] = {}
        self._handler_stats: Dict[int, HandlerStats] = {}
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

    def register(
        self,
        event_type: EventType,
        handler: Callable[[Event], None],
        *,
        handler_name: str | None = None,
        max_consecutive_errors: int = 3,
    ) -> None:
        """Register an event handler."""
        stats = HandlerStats(
            name=handler_name or getattr(handler, "__name__", "anonymous_handler"),
            max_consecutive_errors=max(1, int(max_consecutive_errors)),
        )
        with self._lock:
            if event_type not in self.handlers:
                self.handlers[event_type] = []
            self.handlers[event_type].append(handler)
            self._handler_stats[id(handler)] = stats
        logger.debug("registered handler for %s", event_type.value)

    def unregister(self, event_type: EventType, handler: Callable[[Event], None]) -> None:
        """Unregister an event handler."""
        with self._lock:
            if event_type in self.handlers:
                try:
                    self.handlers[event_type].remove(handler)
                except ValueError:
                    pass
            self._handler_stats.pop(id(handler), None)

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
            stats = self._handler_stats.get(id(handler))
            if stats and stats.quarantined:
                continue
            try:
                handler(event)
                if stats:
                    stats.handled_events += 1
                    stats.consecutive_errors = 0
            except Exception as exc:
                if stats:
                    stats.total_errors += 1
                    stats.consecutive_errors += 1
                    stats.last_error = str(exc)
                    if stats.consecutive_errors >= stats.max_consecutive_errors:
                        stats.quarantined = True
                        logger.error(
                            "event handler quarantined: %s (event=%s, consecutive_errors=%s)",
                            stats.name,
                            event.event_type.value,
                            stats.consecutive_errors,
                            exc_info=True,
                        )
                        continue
                logger.error("event handler error: %s", exc, exc_info=True)

    def handler_status(self) -> dict[str, dict]:
        """Return handler runtime metrics for observability."""
        with self._lock:
            result: dict[str, dict] = {}
            for stats in self._handler_stats.values():
                result[stats.name] = {
                    "handled_events": stats.handled_events,
                    "total_errors": stats.total_errors,
                    "consecutive_errors": stats.consecutive_errors,
                    "last_error": stats.last_error,
                    "quarantined": stats.quarantined,
                    "max_consecutive_errors": stats.max_consecutive_errors,
                }
            return result


event_engine = EventEngine()
