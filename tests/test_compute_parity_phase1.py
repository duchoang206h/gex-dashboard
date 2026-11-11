from datetime import date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from gex import greeks as legacy_greeks
from gex import metrics as legacy_metrics
from gex.compute import greeks as compute_greeks
from gex.compute import metrics as compute_metrics
from gex.ingest import ChainSnapshot
from gex.metrics import ET


def make_chain(spot: float, rows: list[dict]) -> ChainSnapshot:
    defaults = {
        "bid": 1.0,
        "ask": 1.2,
        "iv": 0.20,
        "open_interest": 100.0,
        "volume": 10.0,
        "delta_cboe": 0.0,
        "gamma_cboe": 0.0,
        "last_trade_price": 0.0,
    }
    full = []
    for i, r in enumerate(rows):
        d = {**defaults, **r}
        d.setdefault("contract", f"TST{i:06d}")
        full.append(d)
    now = datetime.now(ET)
    return ChainSnapshot(
        symbol="TST",
        spot=spot,
        feed_timestamp=now.replace(tzinfo=None),
        fetched_at=now.replace(tzinfo=None),
        options=pd.DataFrame(full),
    )


def far_expiry() -> date:
    return (datetime.now(ET) + timedelta(days=30)).date()


def test_greeks_parity_scalar_and_vector():
    S, K, T, R, SIG = 100.0, 100.0, 1.0, 0.05, 0.20
    strikes = np.array([90.0, 100.0, 110.0])
    funcs = [
        "call_price", "put_price", "call_delta", "put_delta", "gamma",
        "vega", "call_theta", "vanna", "charm", "charm_per_day",
    ]
    for name in funcs:
        lfn = getattr(legacy_greeks, name)
        cfn = getattr(compute_greeks, name)
        assert cfn(S, K, T, R, SIG) == pytest.approx(lfn(S, K, T, R, SIG), rel=1e-12, abs=1e-12)
        np.testing.assert_allclose(cfn(S, strikes, 0.1, R, SIG), lfn(S, strikes, 0.1, R, SIG))


def test_metrics_enrich_and_summary_parity(monkeypatch):
    import gex.rates
    monkeypatch.setattr(gex.rates, "current_rate", lambda: 0.045)

    exp = far_expiry()
    now = datetime.now(ET)
    snap = make_chain(
        100.0,
        [
            {"expiry": exp, "type": "C", "strike": 95.0, "open_interest": 120.0, "iv": 0.22},
            {"expiry": exp, "type": "C", "strike": 100.0, "open_interest": 200.0, "iv": 0.20},
            {"expiry": exp, "type": "P", "strike": 100.0, "open_interest": 180.0, "iv": 0.21},
            {"expiry": exp, "type": "P", "strike": 105.0, "open_interest": 150.0, "iv": 0.23},
        ],
    )
    df_l = legacy_metrics.enrich(snap, now_et=now)
    df_c = compute_metrics.enrich(snap, now_et=now)
    pd.testing.assert_frame_equal(df_c.reset_index(drop=True), df_l.reset_index(drop=True))

    s_l = legacy_metrics.summarize(snap, df_l)
    s_c = compute_metrics.summarize(snap, df_c)
    assert s_c.as_row() == s_l.as_row()


def test_metrics_flow_delta_parity(monkeypatch):
    import gex.rates
    monkeypatch.setattr(gex.rates, "current_rate", lambda: 0.045)
    exp = far_expiry()
    now = datetime.now(ET)
    prev = legacy_metrics.enrich(make_chain(100.0, [
        {"expiry": exp, "type": "C", "strike": 100.0, "open_interest": 100.0, "volume": 10.0},
        {"expiry": exp, "type": "P", "strike": 100.0, "open_interest": 100.0, "volume": 8.0},
    ]), now_et=now)
    cur = legacy_metrics.enrich(make_chain(101.0, [
        {"expiry": exp, "type": "C", "strike": 100.0, "open_interest": 100.0, "volume": 25.0},
        {"expiry": exp, "type": "P", "strike": 100.0, "open_interest": 100.0, "volume": 20.0},
    ]), now_et=now)
    l = legacy_metrics.flow_delta(prev, cur, 101.0)
    c = compute_metrics.flow_delta(prev, cur, 101.0)
    assert c == l
