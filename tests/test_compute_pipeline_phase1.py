from datetime import datetime, timedelta

import pandas as pd

from gex.compute import pipeline
from gex.ingest import ChainSnapshot
from gex.metrics import ET


def make_chain():
    now = datetime.now(ET)
    exp = (now + timedelta(days=30)).date()
    opts = pd.DataFrame([
        {"contract": "T1", "expiry": exp, "type": "C", "strike": 100.0, "bid": 1, "ask": 1.2,
         "iv": 0.2, "open_interest": 100, "volume": 10, "delta_cboe": 0, "gamma_cboe": 0, "last_trade_price": 0},
        {"contract": "T2", "expiry": exp, "type": "P", "strike": 100.0, "bid": 1, "ask": 1.2,
         "iv": 0.2, "open_interest": 100, "volume": 10, "delta_cboe": 0, "gamma_cboe": 0, "last_trade_price": 0},
    ])
    return ChainSnapshot(symbol="SPX", spot=5000.0, feed_timestamp=now.replace(tzinfo=None),
                         fetched_at=now.replace(tzinfo=None), options=opts)


def test_wrap_raw_snapshot_builds_provenance(monkeypatch):
    import gex.rates
    monkeypatch.setattr(gex.rates, "current_rate", lambda: 0.045)
    snap = make_chain()
    raw = pipeline.wrap_raw_snapshot(snap, source="cboe", delayed=True, partial=False)
    assert raw.symbol == "SPX"
    assert raw.spot == 5000.0
    assert raw.provenance.source == "cboe"
    assert raw.provenance.quality.delayed is True
    assert raw.provenance.quality.partial is False
    assert len(raw.options) == 2


def test_enrich_chain_snapshot_returns_metadata(monkeypatch):
    import gex.rates
    monkeypatch.setattr(gex.rates, "current_rate", lambda: 0.045)
    snap = make_chain()
    now = datetime.now(ET)
    enriched, meta = pipeline.enrich_chain_snapshot(snap, now_et=now, source="cboe", delayed=True)
    assert not enriched.empty
    assert meta.row_count == len(enriched)
    assert meta.provenance.symbol == "SPX"
    assert meta.provenance.quality.delayed is True

    summary = pipeline.summarize_chain_snapshot(snap, enriched, with_basis=False)
    assert hasattr(summary, "as_row")
    assert summary.as_row()["symbol"] == "SPX"
