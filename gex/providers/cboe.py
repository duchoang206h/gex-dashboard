"""CBOE provider adapter (phase 2).

Wraps legacy ingestion and normalizes output to core contracts without changing
fetch behavior.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Any

from gex import ingest
from gex.compute.pipeline import wrap_raw_snapshot
from gex.config import UNDERLYINGS
from gex.core import RawChainSnapshot


@dataclass(frozen=True)
class ProviderCapabilities:
    name: str = "cboe"
    delayed: bool = True
    realtime: bool = False
    has_signed_flow: bool = False
    has_greeks: bool = True


class CBOEChainProvider:
    """Fetches and normalizes CBOE delayed option chains."""

    name = "cboe"
    capabilities = ProviderCapabilities()

    def __init__(self, fetcher: Callable[[str, str], Any] | None = None):
        self._fetcher = fetcher or ingest.fetch_chain

    def resolve_cboe_symbol(self, symbol: str) -> str:
        u = UNDERLYINGS.get(symbol)
        if u is None:
            raise KeyError(f"unknown symbol: {symbol}")
        return u.cboe_symbol

    def fetch_legacy(self, symbol: str):
        cboe_symbol = self.resolve_cboe_symbol(symbol)
        return self._fetcher(symbol, cboe_symbol)

    def normalize(self, legacy_snapshot: Any) -> RawChainSnapshot:
        return wrap_raw_snapshot(
            legacy_snapshot,
            source=self.name,
            delayed=self.capabilities.delayed,
            partial=False,
        )

    def fetch_chain(self, symbol: str) -> RawChainSnapshot:
        return self.normalize(self.fetch_legacy(symbol))


def normalize_legacy_snapshot(legacy_snapshot: Any, source: str = "cboe") -> RawChainSnapshot:
    """Convenience normalizer for already-fetched legacy snapshots."""
    delayed = source == "cboe"
    return wrap_raw_snapshot(legacy_snapshot, source=source, delayed=delayed, partial=False)
