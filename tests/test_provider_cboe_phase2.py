from datetime import datetime, timedelta

import pandas as pd

from gex.ingest import ChainSnapshot
from gex.metrics import ET
from gex.providers import CBOEChainProvider, normalize_legacy_snapshot
from gex.config import UNDERLYINGS


def make_legacy(symbol="SPX"):
    now = datetime.now(ET)
    exp = (now + timedelta(days=30)).date()
    opts = pd.DataFrame([
        {"contract": "A", "expiry": exp, "type": "C", "strike": 100.0, "bid": 1, "ask": 1.2,
         "iv": 0.2, "open_interest": 50, "volume": 5, "delta_cboe": 0, "gamma_cboe": 0, "last_trade_price": 0},
    ])
    return ChainSnapshot(symbol=symbol, spot=123.0, feed_timestamp=now.replace(tzinfo=None),
                         fetched_at=now.replace(tzinfo=None), options=opts)


def test_normalize_legacy_snapshot_sets_provenance():
    snap = make_legacy("SPX")
    raw = normalize_legacy_snapshot(snap, source="cboe")
    assert raw.symbol == "SPX"
    assert raw.spot == 123.0
    assert raw.provenance.source == "cboe"
    assert raw.provenance.quality.delayed is True
    assert list(raw.options["contract"]) == ["A"]


def test_cboe_provider_fetch_and_normalize_with_injected_fetcher():
    legacy = make_legacy("SPX")
    calls = {}

    def fake_fetch(symbol, cboe_symbol):
        calls["symbol"] = symbol
        calls["cboe_symbol"] = cboe_symbol
        return legacy

    provider = CBOEChainProvider(fetcher=fake_fetch)
    assert provider.resolve_cboe_symbol("SPX") == UNDERLYINGS["SPX"].cboe_symbol
    raw = provider.fetch_chain("SPX")
    assert calls == {"symbol": "SPX", "cboe_symbol": UNDERLYINGS["SPX"].cboe_symbol}
    assert raw.symbol == "SPX"
    assert raw.provenance.source == "cboe"
    assert raw.provenance.quality.delayed is True
    assert provider.capabilities.has_signed_flow is False


def test_capabilities_metadata():
    provider = CBOEChainProvider(fetcher=lambda s, c: make_legacy(s))
    caps = provider.capabilities
    assert caps.name == "cboe"
    assert caps.delayed is True
    assert caps.realtime is False
    assert caps.has_greeks is True
