"""Compatibility helpers that bridge legacy snapshots to core contracts.

Phase 1/early Phase 2: produce canonical provenance/metadata while delegating
all math to the legacy compute path for parity.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import pandas as pd

from gex.core import (
    EnrichedSnapshotMeta,
    Provenance,
    QualityFlags,
    RawChainSnapshot,
    validate_provenance,
)

from . import metrics as compute_metrics


def provenance_from_chain_snapshot(snapshot: Any, source: str = "cboe",
                                   *, delayed: bool = True,
                                   stale: bool = False,
                                   partial: bool = False) -> Provenance:
    prov = Provenance(
        symbol=getattr(snapshot, "symbol", ""),
        source=source,
        provider_timestamp=getattr(snapshot, "feed_timestamp", None),
        fetched_at=getattr(snapshot, "fetched_at", None),
        quality=QualityFlags(delayed=delayed, stale=stale, partial=partial),
    )
    return validate_provenance(prov)


def wrap_raw_snapshot(snapshot: Any, source: str = "cboe", **quality: bool) -> RawChainSnapshot:
    prov = provenance_from_chain_snapshot(snapshot, source=source, **quality)
    opts = getattr(snapshot, "options", None)
    if opts is None:
        opts = pd.DataFrame()
    else:
        opts = opts.copy()
    return RawChainSnapshot(
        symbol=prov.symbol,
        spot=float(getattr(snapshot, "spot", 0.0) or 0.0),
        options=opts,
        provenance=prov,
    )


def enrich_chain_snapshot(snapshot: Any, *, now_et: datetime | None = None,
                          source: str = "cboe", **quality: bool) -> tuple[pd.DataFrame, EnrichedSnapshotMeta]:
    """Enrich a legacy ChainSnapshot and return (enriched_df, metadata)."""
    enriched = compute_metrics.enrich(snapshot, now_et=now_et)
    prov = provenance_from_chain_snapshot(snapshot, source=source, **quality)
    meta = EnrichedSnapshotMeta(provenance=prov, row_count=len(enriched))
    return enriched, meta


def summarize_chain_snapshot(snapshot: Any, enriched: pd.DataFrame, *, with_basis: bool = True):
    """Parity wrapper for legacy summarize."""
    return compute_metrics.summarize(snapshot, enriched, with_basis=with_basis)
