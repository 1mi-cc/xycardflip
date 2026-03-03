from __future__ import annotations

from app.vnpy_system.event_engine import Event
from app.vnpy_system.event_engine import EventEngine
from app.vnpy_system.event_engine import EventType


def test_event_engine_quarantines_bad_handler_after_threshold() -> None:
    engine = EventEngine()
    calls = {"good": 0, "bad": 0}

    def good_handler(event: Event) -> None:
        assert event.event_type == EventType.ITEM_FOUND
        calls["good"] += 1

    def bad_handler(_: Event) -> None:
        calls["bad"] += 1
        raise RuntimeError("boom")

    engine.register(EventType.ITEM_FOUND, good_handler, handler_name="good", max_consecutive_errors=3)
    engine.register(EventType.ITEM_FOUND, bad_handler, handler_name="bad", max_consecutive_errors=2)

    event = Event(event_type=EventType.ITEM_FOUND, data={"id": 1})
    engine._handle_event(event)
    engine._handle_event(event)
    engine._handle_event(event)

    status = engine.handler_status()
    assert calls["good"] == 3
    assert calls["bad"] == 2
    assert status["bad"]["quarantined"] is True
    assert status["bad"]["consecutive_errors"] >= 2
    assert status["good"]["quarantined"] is False
