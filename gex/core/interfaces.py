"""Protocols for pluggable pipeline components.

These define the seams for incremental migration; implementations may wrap
existing modules initially.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable, Any

from .schemas import RawChainSnapshot


@runtime_checkable
class ChainProvider(Protocol):
    """Source adapter capable of producing normalized chain snapshots."""

    name: str

    def fetch_chain(self, symbol: str) -> RawChainSnapshot: ...


@runtime_checkable
class SnapshotStore(Protocol):
    """Persistence boundary for snapshots/summaries (minimal for phase 0)."""

    def save_raw_snapshot(self, snapshot: RawChainSnapshot) -> Any: ...

    def save_enriched_snapshot(self, symbol: str, enriched: Any, when: Any = None) -> Any: ...
