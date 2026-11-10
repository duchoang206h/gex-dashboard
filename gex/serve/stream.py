"""Dedicated backpressured publish/subscribe utilities for streaming (phase 5).

Thread-safe, in-process component with bounded per-subscriber queues. Intended
as a bridge toward async/backpressured streaming without forcing a server rewrite.
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Iterator


@dataclass
class Subscriber:
    id: int
    q: "queue.Queue[Any]"
    topic: str | None = None


class BackpressuredPublisher:
    """Bounded pub/sub with drop-oldest backpressure policy."""

    def __init__(self, maxsize: int = 100):
        self.maxsize = maxsize
        self._lock = threading.RLock()
        self._subs: dict[int, Subscriber] = {}
        self._next_id = 1

    def subscribe(self, topic: str | None = None, maxsize: int | None = None) -> Subscriber:
        with self._lock:
            sid = self._next_id
            self._next_id += 1
            sub = Subscriber(id=sid, q=queue.Queue(maxsize=maxsize or self.maxsize), topic=topic)
            self._subs[sid] = sub
            return sub

    def unsubscribe(self, sub: Subscriber | int) -> None:
        sid = sub.id if isinstance(sub, Subscriber) else sub
        with self._lock:
            self._subs.pop(sid, None)

    def _targets(self, topic: str | None) -> list[Subscriber]:
        with self._lock:
            subs = list(self._subs.values())
        if topic is None:
            return subs
        return [s for s in subs if s.topic in (None, topic)]

    def publish(self, message: Any, topic: str | None = None) -> int:
        """Publish to subscribers, dropping oldest on full queues. Returns delivered count."""
        delivered = 0
        for sub in self._targets(topic):
            try:
                sub.q.put_nowait(message)
                delivered += 1
            except queue.Full:
                try:
                    sub.q.get_nowait()
                except queue.Empty:
                    pass
                try:
                    sub.q.put_nowait(message)
                    delivered += 1
                except queue.Full:
                    pass
        return delivered

    def get(self, sub: Subscriber, timeout: float | None = None) -> Any | None:
        try:
            return sub.q.get(timeout=timeout)
        except queue.Empty:
            return None

    def iter_messages(self, sub: Subscriber, *, heartbeat_s: float = 15.0,
                      stop: Callable[[], bool] | None = None) -> Iterator[Any | None]:
        """Yield messages; yields None on heartbeat timeout (no message)."""
        while True:
            if stop and stop():
                return
            msg = self.get(sub, timeout=heartbeat_s)
            yield msg


STREAM_BUS = BackpressuredPublisher(maxsize=128)
