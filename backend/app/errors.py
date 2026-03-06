from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class BusyStateError(RuntimeError):
    service: str
    reason: str
    message: str = ""

    def __post_init__(self) -> None:
        text = self.message or f"{self.service} is busy"
        RuntimeError.__init__(self, text)

    def to_payload(self) -> dict[str, object]:
        return {
            "busy": True,
            "service": self.service,
            "reason": self.reason,
            "message": self.message or f"{self.service} is busy",
        }
