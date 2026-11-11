from datetime import datetime, timedelta

import pandas as pd

from gex.compute.pipeline import provenance_from_chain_snapshot
from gex.ingest import ChainSnapshot
from gex.metrics import ET, enrich, summarize
from gex.pipeline.runtime import RewriteRuntime


def make_chain(symbol="SPX"):
    now = datetime.now(ET)
    exp = (now + timedelta(days=30)).date()
    opts = pd.DataFrame([
        {"contract": "A", "expiry": exp, "type": "C", "strike": 100.0, "bid": 1, "ask": 1.2,
         "iv": 0.2, "open_interest": 50, "volume": 5, "delta_cboe": 0, "gamma_cboe": 0, "last_trade_price": 0},
        {"contract": "B", "expiry": exp, "type": "P", "strike": 100.0, "bid": 1, "ask": 1.2,
         "iv": 0.2, "open_interest": 40, "volume": 4, "delta_cboe": 0, "gamma_cboe": 0, "last_trade_price": 0},
    ])
    return ChainSnapshot(symbol=symbol, spot=100.0, feed_timestamp=now.replace(tzinfo=None),
                         fetched_at=now.replace(tzinfo=None), options=opts)


def test_runtime_disabled_is_noop(monkeypatch):
    import gex.rates
    monkeypatch.setattr(gex.rates, "current_rate", lambda: 0.045)
    rt = RewriteRuntime(enabled=False)
    snap = make_chain()
    now = datetime.now(ET)
    df = enrich(snap, now_et=now)
    summary = summarize(snap, df, with_basis=False)
    rt.on_legacy_snapshot(snap, df, summary)
    assert rt.read_model.get("SPX") is None


def test_runtime_enabled_updates_read_model_events_and_manifest(monkeypatch, tmp_path):
    import gex.rates
    import gex.config
    monkeypatch.setattr(gex.rates, "current_rate", lambda: 0.045)
    monkeypatch.setattr(gex.config.SETTINGS, "data_dir", tmp_path)

    rt = RewriteRuntime(enabled=True)
    events = []
    rt.events.subscribe("snapshot.received", lambda e: events.append(e.topic))
    rt.events.subscribe("snapshot.enriched", lambda e: events.append(e.topic))
    rt.events.subscribe("summary.updated", lambda e: events.append(e.topic))

    snap = make_chain("NDX")
    now = datetime.now(ET)
    df = enrich(snap, now_et=now)
    summary = summarize(snap, df, with_basis=False)
    rt.on_legacy_snapshot(snap, df, summary)

    st = rt.read_model.get("NDX")
    assert st is not None
    assert st.enriched is not None and len(st.enriched) == len(df)
    assert st.summary is not None
    assert st.provenance is not None and st.provenance.source == "cboe"
    assert "snapshot.received" in events
    assert "snapshot.enriched" in events
    assert "summary.updated" in events

    manifest = tmp_path / "manifests" / "NDX.snapshot.json"
    assert manifest.exists()


def test_runtime_error_is_captured_without_raising(monkeypatch):
    import gex.compute.pipeline as cp
    import gex.rates
    monkeypatch.setattr(gex.rates, "current_rate", lambda: 0.045)
    rt = RewriteRuntime(enabled=True)

    snap = make_chain("SPX")

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(cp, "wrap_raw_snapshot", boom)
    rt.on_legacy_snapshot(snap, None, None)
    st = rt.read_model.get("SPX")
    assert st is not None
    assert st.last_error == "rewrite side-channel update failed"
