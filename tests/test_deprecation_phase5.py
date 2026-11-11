import warnings

from gex.core.deprecation import DEPRECATED_SHIMS, reset_deprecation_state, warn_deprecated


def test_warn_deprecated_opt_in(monkeypatch):
    reset_deprecation_state()
    monkeypatch.delenv("GEX_REWRITE_DEPRECATION_WARNINGS", raising=False)
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        warn_deprecated("gex.compute.metrics")
        assert len(w) == 0

    monkeypatch.setenv("GEX_REWRITE_DEPRECATION_WARNINGS", "1")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        warn_deprecated("gex.compute.metrics")
        warn_deprecated("gex.compute.metrics")  # once
        assert len(w) == 1
        assert issubclass(w[0].category, DeprecationWarning)
    reset_deprecation_state()


def test_deprecated_shims_registry():
    assert "gex.compute.greeks" in DEPRECATED_SHIMS
    assert "gex.compute.metrics" in DEPRECATED_SHIMS
