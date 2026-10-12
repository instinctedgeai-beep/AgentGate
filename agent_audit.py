
"""Structured audit events for AgentGate agent execution."""

import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class AuditEvent:
    request_id: str
    event_type: str
    status: str
    detail: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        ).isoformat()
    )


class AgentAudit:
    def __init__(self):
        self.request_id = str(uuid.uuid4())
        self.events = []
        self.started = time.perf_counter()

    def record(self, event_type, status, detail=""):
        """Record an observed execution event."""
        event = AuditEvent(
            request_id=self.request_id,
            event_type=event_type,
            status=status,
            detail=detail,
        )

        self.events.append(event)
        return event

    def summary(self):
        """Return basic metrics for the current request."""
        return {
            "request_id": self.request_id,
            "event_count": len(self.events),
            "duration_ms": round(
                (time.perf_counter() - self.started) * 1000,
                2,
            ),
            "events": [
                {
                    "event_type": event.event_type,
                    "status": event.status,
                    "detail": event.detail,
                    "timestamp": event.timestamp,
                }
                for event in self.events
            ],
        }
