"""Optional rewrite runtime (flagged).

Modes (env):
- `GEX_REWRITE_PIPELINE=1|true|on`  -> side-channel updates (default off)
- `GEX_REWRITE_PRIMARY=1|true|on`   -> primary compute path in ingestion (also enables runtime)
- `GEX_REWRITE_INDEX=1|true|on`     -> optional SQLite hot-query index updates when runtime enabled

All modes preserve legacy STATE/storage/API behavior.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

import logging

from gex.core import EnrichedSnapshotMeta, EventBus, topics
from gex.state import ReadModel
from gex.compute import pipeline as compute_pipeline

log = logging.getLogger(__name__)


def _env_on(name: str) -> bool:
    v = os.environ.get(name, "")
    return v.strip().lower() in {"1", "true", "yes", "on"}


def rewrite_enabled() -> bool:
    return _env_on("GEX_REWRITE_PIPELINE") or primary_enabled()


def primary_enabled() -> bool:
    return _env_on("GEX_REWRITE_PRIMARY")


def index_enabled() -> bool:
    return _env_on("GEX_REWRITE_INDEX")


@dataclass
class RewriteRuntime:
    enabled: bool = field(default_factory=rewrite_enabled)
    primary: bool = field(default_factory=primary_enabled)
    index: bool = field(default_factory=index_enabled)
    events: EventBus = field(default_factory=EventBus)
    read_model: ReadModel = field(default_factory=ReadModel)

    def on_legacy_snapshot(self, legacy_snapshot: Any, enriched: Any = None,
                           summary: Any = None, *, source: str = "cboe",
                           with_basis: bool = True) -> None:
        """Side-channel update from legacy pipeline artifacts (best-effort)."""
        if not self.enabled:
            return
        symbol = getattr(legacy_snapshot, "symbol", None)
        if not symbol:
            return
        try:
            delayed = (source == "cboe")
            raw = compute_pipeline.wrap_raw_snapshot(legacy_snapshot, source=source, delayed=delayed)
            self.events.publish(topics.SNAPSHOT_RECEIVED, raw)
            prov = compute_pipeline.provenance_from_chain_snapshot(
                legacy_snapshot, source=source, delayed=delayed)
            rows = None
            if enriched is not None:
                # avoid recomputing enrichment: build metadata from provided artifact
                meta = EnrichedSnapshotMeta(provenance=prov, row_count=len(enriched))
                rows = len(enriched)
                self.read_model.update_enriched(symbol, enriched, meta)
                self.events.publish(topics.SNAPSHOT_ENRICHED, {"symbol": symbol, "rows": rows})
            if summary is not None:
                self.read_model.update_summary(symbol, summary, prov)
                payload = {"symbol": symbol}
                self.events.publish(topics.SUMMARY_UPDATED, payload)
                try:
                    from gex.serve.stream import STREAM_BUS
                    STREAM_BUS.publish({"topic": topics.SUMMARY_UPDATED, **payload}, topic=topics.SUMMARY_UPDATED)
                except Exception:
                    pass
            # additive sidecar manifest (phase 4) - must not affect legacy persistence
            try:
                from gex.storage.metadata import write_snapshot_manifest
                write_snapshot_manifest(symbol, prov.as_dict(), rows=rows)
            except Exception:
                log.debug("rewrite manifest write failed for %s", symbol, exc_info=True)
            # optional indexed hot-query backend (phase 4) - default off
            if self.index or index_enabled():
                try:
                    from gex.storage.indexed import index_summary
                    if summary is not None:
                        index_summary(symbol, summary, prov.as_dict())
                except Exception:
                    log.debug("rewrite index update failed for %s", symbol, exc_info=True)
        except Exception:
            # must never impact legacy path
            try:
                self.read_model.record_error(symbol, "rewrite side-channel update failed")
            except Exception:
                pass


RUNTIME = RewriteRuntime() if rewrite_enabled() else RewriteRuntime(enabled=False)
