from gex.pipeline.runtime import RewriteRuntime
from gex.serve.health import rewrite_health


def test_rewrite_health_disabled(monkeypatch):
    import gex.pipeline.runtime as rtmod
    monkeypatch.setattr(rtmod, "rewrite_enabled", lambda: False)
    # ensure global runtime not treated as enabled by flag override only; function checks both
    old = rtmod.RUNTIME.enabled
    rtmod.RUNTIME.enabled = False
    try:
        h = rewrite_health(["SPX"])
        assert h["enabled"] is False
        assert h["symbols"] == {}
    finally:
        rtmod.RUNTIME.enabled = old


def test_rewrite_health_enabled_reads_model(monkeypatch):
    import gex.pipeline.runtime as rtmod
    from gex.core import Provenance
    monkeypatch.setattr(rtmod, "rewrite_enabled", lambda: True)
    # use isolated runtime to avoid polluting global
    rt = RewriteRuntime(enabled=True)
    rt.read_model.update_summary("SPX", {"net_gex": 1}, Provenance(symbol="SPX", source="cboe"))
    old = rtmod.RUNTIME
    rtmod.RUNTIME = rt
    try:
        h = rewrite_health(["SPX"])
        assert h["enabled"] is True
        assert "SPX" in h["symbols"]
        assert h["symbols"]["SPX"]["available"] is True
    finally:
        rtmod.RUNTIME = old
