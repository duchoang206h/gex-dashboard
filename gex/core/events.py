"""Minimal in-process event primitives for pipeline decoupling.

Kept dependency-free and synchronous so it can be used in current threaded
runtime; can be swapped for an async/bus implementation later.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, DefaultDict
from collections import defaultdict
import logging

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class topics:
    SNAPSHOT_RECEIVED = "snapshot.received"
    SNAPSHOT_ENRICHED = "snapshot.enriched"
    SUMMARY_UPDATED = "summary.updated"
    FLOW_COMPUTED = "flow.computed"
    REGIME_CHANGED = "regime.changed"


@dataclass
class Event:
    topic: str
    payload: Any
    occurred_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


Handler = Callable[[Event], None]


class EventBus:
    """Simple publish/subscribe bus with per-topic handlers."""

    def __init__(self) -> None:
        self._handlers: DefaultDict[str, list[Handler]] = defaultdict(list)

    def subscribe(self, topic: str, handler: Handler) -> None:
        self._handlers[topic].append(handler)

    def publish(self, topic: str, payload: Any) -> Event:
        event = Event(topic=topic, payload=payload)
        for handler in list(self._handlers.get(topic, [])):
            try:
                handler(event)
            except Exception:  # noqa: BLE001 - handlers must not break publishers
                log.exception("event handler failed for topic=%s", topic)
        return event

    def clear(self, topic: str | None = None) -> None:
        if topic is None:
            self._handlers.clear()
        else:
            self._handlers.pop(topic, None)
