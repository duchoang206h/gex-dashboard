"""Canonical schemas and metadata for the rewrite pipeline.

These structures are intentionally lightweight and DataFrame-friendly so they
can wrap current pandas-based flows without forcing an immediate rewrite.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Mapping

import pandas as pd

SCHEMA_VERSION = "1.0"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class QualityFlags:
    """Data quality/freshness indicators carried with snapshots and summaries."""

    delayed: bool = False
    stale: bool = False
    partial: bool = False
    estimated: bool = False
    notes: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class Provenance:
    """Where a piece of data came from and when it was observed."""

    symbol: str
    source: str
    provider_timestamp: datetime | None = None
    fetched_at: datetime | None = None
    schema_version: str = SCHEMA_VERSION
    quality: QualityFlags = field(default_factory=QualityFlags)

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # datetimes are kept as objects for in-memory use; callers may serialize
        q = self.quality.as_dict()
        d["quality"] = q
        return d


@dataclass
class RawChainSnapshot:
    """Normalized container for a raw options chain snapshot.

    `options` keeps the current pandas representation to stay compatible with
    existing metrics/ingestion code during migration.
    """

    symbol: str
    spot: float
    options: pd.DataFrame
    provenance: Provenance

    @property
    def provider_timestamp(self) -> datetime | None:
        return self.provenance.provider_timestamp

    @property
    def fetched_at(self) -> datetime | None:
        return self.provenance.fetched_at

    def with_quality(self, **flags: bool) -> "RawChainSnapshot":
        q = self.provenance.quality
        new_q = QualityFlags(
            delayed=flags.get("delayed", q.delayed),
            stale=flags.get("stale", q.stale),
            partial=flags.get("partial", q.partial),
            estimated=flags.get("estimated", q.estimated),
            notes=q.notes,
        )
        new_p = Provenance(
            symbol=self.provenance.symbol,
            source=self.provenance.source,
            provider_timestamp=self.provenance.provider_timestamp,
            fetched_at=self.provenance.fetched_at,
            schema_version=self.provenance.schema_version,
            quality=new_q,
        )
        return RawChainSnapshot(
            symbol=self.symbol, spot=self.spot, options=self.options.copy(), provenance=new_p
        )


@dataclass
class EnrichedSnapshotMeta:
    """Metadata for an enriched snapshot emitted by compute."""

    provenance: Provenance
    row_count: int
    generated_at: datetime = field(default_factory=_utcnow)


@dataclass
class MarketSummaryMeta:
    """Metadata for a computed market summary/read model."""

    provenance: Provenance
    generated_at: datetime = field(default_factory=_utcnow)
    extras: Mapping[str, Any] = field(default_factory=dict)
