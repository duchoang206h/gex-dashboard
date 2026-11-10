"""Core contracts for the rewrite pipeline.

This package is additive: existing modules remain the runtime default while
new components can depend on stable schemas/interfaces.
"""
from .schemas import (
    SCHEMA_VERSION,
    QualityFlags,
    Provenance,
    RawChainSnapshot,
    EnrichedSnapshotMeta,
    MarketSummaryMeta,
)
from .events import Event, EventBus, topics
from .interfaces import ChainProvider, SnapshotStore
from .validation import ValidationError, require_non_empty, validate_provenance

__all__ = [
    "SCHEMA_VERSION",
    "QualityFlags",
    "Provenance",
    "RawChainSnapshot",
    "EnrichedSnapshotMeta",
    "MarketSummaryMeta",
    "Event",
    "EventBus",
    "topics",
    "ChainProvider",
    "SnapshotStore",
    "ValidationError",
    "require_non_empty",
    "validate_provenance",
]
