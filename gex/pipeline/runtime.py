"""Optional rewrite runtime (flagged, side-channel).

Enabled with env var `GEX_REWRITE_PIPELINE=1`. When enabled, ingestion paths
can publish normalized/enriched outputs to the rewrite read model and event bus
without changing legacy STATE/storage behavior.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from gex.core import EventBus, topics
from gex.state import ReadModel
from gex.compute import pipeline as compute_pipeline


def rewrite_enabled() -> bool:
    v = os.environ.get("GEX_REWRITE_PIPELINE", "")
    return v.strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class RewriteRuntime:
    enabled: bool = field(default_factory=rewrite_enabled)
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
            raw = compute_pipeline.wrap_raw_snapshot(legacy_snapshot, source=source, delayed=(source == "cboe"))
            self.events.publish(topics.SNAPSHOT_RECEIVED, raw)
            prov = compute_pipeline.provenance_from_chain_snapshot(legacy_snapshot, source=source,
                                                                     delayed=(source == "cboe"))
            rows = None
            if enriched is not None:
                _, meta = compute_pipeline.enrich_chain_snapshot(legacy_snapshot, source=source,
                                                                  delayed=(source == "cboe"))
                meta.row_count = len(enriched)
                rows = len(enriched)
                self.read_model.update_enriched(symbol, enriched, meta)
                self.events.publish(topics.SNAPSHOT_ENRICHED, {"symbol": symbol, "rows": rows})
            if summary is not None:
                self.read_model.update_summary(symbol, summary, prov)
                self.events.publish(topics.SUMMARY_UPDATED, {"symbol": symbol})
            # additive sidecar manifest (phase 4) - must not affect legacy persistence
            try:
                from gex.storage.metadata import write_snapshot_manifest
                write_snapshot_manifest(symbol, prov.as_dict(), rows=rows)
            except Exception:
                pass
        except Exception:
            # must never impact legacy path
            try:
                self.read_model.record_error(symbol, "rewrite side-channel update failed")
            except Exception:
                pass


RUNTIME = RewriteRuntime() if rewrite_enabled() else RewriteRuntime(enabled=False)
