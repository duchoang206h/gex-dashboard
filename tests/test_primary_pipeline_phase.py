from datetime import datetime, timedelta

import pandas as pd

from gex.ingest import ChainSnapshot
from gex.metrics import ET
from gex.pipeline import runtime as rtmod


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


def test_primary_mode_updates_readmodel(monkeypatch, tmp_path):
    import gex.config
    import gex.rates
    import gex.scheduler as sched

    monkeypatch.setenv("GEX_REWRITE_PRIMARY", "1")
    monkeypatch.setattr(gex.rates, "current_rate", lambda: 0.045)
    monkeypatch.setattr(gex.config.SETTINGS, "data_dir", tmp_path)

    # reset runtime singleton state for test isolation
    old_rt = rtmod.RUNTIME
    rtmod.RUNTIME = rtmod.RewriteRuntime()
    try:
        snap = make_chain("SPX")
        now = datetime.now(ET)
        summary = sched.ingest_snapshot("SPX", snap, persist_snapshot=False, now=now)
        st = rtmod.RUNTIME.read_model.get("SPX")
        assert st is not None
        assert st.summary is not None
        assert st.enriched is not None
        assert summary.as_row()["symbol"] == "SPX"
        # legacy state also updated
        assert sched.STATE.get("SPX").summary is not None
    finally:
        rtmod.RUNTIME = old_rt
        sched.STATE.per_symbol.pop("SPX", None)
