"""Pure compute-layer wrappers for Black-Scholes Greeks.

Phase 1 delegates to `gex.greeks` to guarantee numerical parity while
establishing a stable import path for the rewrite pipeline.

Compatibility shim: retained until deprecation window/parity soak completion.
Set `GEX_REWRITE_DEPRECATION_WARNINGS=1` to emit opt-in deprecation warnings.
"""
from __future__ import annotations

from gex.greeks import *  # noqa: F401,F403
from gex import greeks as _legacy

try:
    from gex.core.deprecation import warn_deprecated
    warn_deprecated("gex.compute.greeks")
except Exception:
    pass

__all__ = [name for name in dir(_legacy) if not name.startswith("_")]

