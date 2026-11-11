"""In-memory read model for latest per-symbol analytics (phase 3 scaffold).

Designed to be fed by pipeline events/jobs and read by serving layers without
coupling them to ingestion internals.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any

import pandas as pd

from gex.core import EnrichedSnapshotMeta, MarketSummaryMeta, Provenance


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class SymbolReadState:
    symbol: str
    provenance: Provenance | None = None
    enriched: pd.DataFrame | None = None
    enriched_meta: EnrichedSnapshotMeta | None = None
    summary: Any = None
    summary_meta: MarketSummaryMeta | None = None
    last_updated_at: datetime | None = None
    last_error: str | None = None


@dataclass
class ReadModel:
    _lock: RLock = field(default_factory=RLock, repr=False)
    _symbols: dict[str, SymbolReadState] = field(default_factory=dict, repr=False)

    def _get(self, symbol: str) -> SymbolReadState:
        st = self._symbols.get(symbol)
        if st is None:
            st = SymbolReadState(symbol=symbol)
            self._symbols[symbol] = st
        return st

    def update_enriched(self, symbol: str, enriched: pd.DataFrame, meta: EnrichedSnapshotMeta) -> SymbolReadState:
        with self._lock:
            st = self._get(symbol)
            st.provenance = meta.provenance
            st.enriched = enriched
            st.enriched_meta = meta
            st.last_updated_at = _utcnow()
            st.last_error = None
            return st

    def update_summary(self, symbol: str, summary: Any, provenance: Provenance,
                       extras: dict | None = None) -> SymbolReadState:
        with self._lock:
            st = self._get(symbol)
            st.provenance = provenance
            st.summary = summary
            st.summary_meta = MarketSummaryMeta(provenance=provenance, extras=extras or {})
            st.last_updated_at = _utcnow()
            st.last_error = None
            return st

    def record_error(self, symbol: str, message: str) -> SymbolReadState:
        with self._lock:
            st = self._get(symbol)
            st.last_error = message
            st.last_updated_at = _utcnow()
            return st

    def get(self, symbol: str) -> SymbolReadState | None:
        with self._lock:
            st = self._symbols.get(symbol)
            if st is None:
                return None
            # return a shallow snapshot object (DataFrame/objects are references)
            return SymbolReadState(
                symbol=st.symbol,
                provenance=st.provenance,
                enriched=st.enriched,
                enriched_meta=st.enriched_meta,
                summary=st.summary,
                summary_meta=st.summary_meta,
                last_updated_at=st.last_updated_at,
                last_error=st.last_error,
            )

    def health(self, symbol: str) -> dict[str, Any]:
        st = self.get(symbol)
        if st is None:
            return {"symbol": symbol, "available": False}
        prov = st.provenance
        quality = prov.quality.as_dict() if prov else None
        # derive staleness hint from provider timestamp age (best-effort)
        if quality is not None and prov and prov.provider_timestamp:
            try:
                pts = prov.provider_timestamp
                if pts.tzinfo is None:
                    # naive feed timestamps are stored in ET historically; compare conservatively in UTC-ish by assuming local ET is not critical here
                    # fallback: treat as not stale if parsing ambiguous
                    now = datetime.now()
                    age_s = (now.replace(tzinfo=None) - pts.replace(tzinfo=None)).total_seconds()
                else:
                    age_s = (_utcnow() - pts.astimezone(timezone.utc)).total_seconds()
                # delayed sources can legitimately lag ~15 min; mark stale only when clearly stuck
                if age_s > 45 * 60:
                    quality = {**quality, "stale": True, "feed_age_s": int(age_s)}
                else:
                    quality = {**quality, "feed_age_s": max(0, int(age_s))}
            except Exception:
                pass
        return {
            "symbol": symbol,
            "available": st.enriched is not None or st.summary is not None,
            "last_updated_at": st.last_updated_at.isoformat() if st.last_updated_at else None,
            "source": prov.source if prov else None,
            "provider_timestamp": prov.provider_timestamp.isoformat() if prov and prov.provider_timestamp else None,
            "schema_version": prov.schema_version if prov else None,
            "quality": quality,
            "last_error": st.last_error,
        }
