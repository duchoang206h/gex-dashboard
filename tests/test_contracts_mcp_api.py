import json
import os
from datetime import datetime, timedelta

import pandas as pd


def test_mcp_get_gex_summary_contract(tmp_path, monkeypatch):
    import gex.config
    import gex.mcp_server as mcp

    monkeypatch.setattr(gex.config.SETTINGS, "data_dir", tmp_path)
    hist_dir = tmp_path / "history"
    hist_dir.mkdir(parents=True)
    df = pd.DataFrame([
        {"timestamp": "2026-01-01T10:00:00", "symbol": "SPX", "net_gex": 1.0, "spot": 5000.0},
        {"timestamp": "2026-01-01T10:01:00", "symbol": "SPX", "net_gex": 2.0, "spot": 5001.0},
    ])
    df.to_parquet(hist_dir / "metrics.parquet", index=False)

    out = json.loads(mcp.get_gex_summary("SPX"))
    assert "dernier" in out
    assert out["dernier"]["symbol"] == "SPX"
    assert "nb_snapshots" in out and out["nb_snapshots"] == 2
    assert "variation_du_jour" in out
    assert "net_gex" in out["variation_du_jour"]


def test_mcp_get_gex_by_strike_contract(tmp_path, monkeypatch):
    import gex.config
    import gex.mcp_server as mcp

    monkeypatch.setattr(gex.config.SETTINGS, "data_dir", tmp_path)
    snap = tmp_path / "snapshots" / "SPX" / "2026-01-01"
    snap.mkdir(parents=True)
    df = pd.DataFrame([
        {"strike": 5000.0, "gex": 100.0, "open_interest": 10},
        {"strike": 5000.0, "gex": 50.0, "open_interest": 5},
        {"strike": 5010.0, "gex": -200.0, "open_interest": 8},
    ])
    p = snap / "x.parquet"
    df.to_parquet(p, index=False)

    out = json.loads(mcp.get_gex_by_strike("SPX", top_n=2))
    assert "snapshot" in out
    assert "murs_de_gamma" in out
    assert len(out["murs_de_gamma"]) <= 2
    row = out["murs_de_gamma"][0]
    assert {"strike", "gex_net_dollars", "cote", "open_interest"}.issubset(row.keys())


def test_api_rewrite_health_contract():
    from flask import Flask
    from gex.api import register_api

    app = Flask(__name__)
    register_api(app)
    client = app.test_client()
    res = client.get("/api/v1/rewrite/health")
    assert res.status_code == 200
    data = res.get_json()
    assert "enabled" in data
    assert "symbols" in data
