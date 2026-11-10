"""Pure compute-layer wrappers for Black-Scholes Greeks.

Phase 1 delegates to `gex.greeks` to guarantee numerical parity while
establishing a stable import path for the rewrite pipeline.
"""
from __future__ import annotations

from gex.greeks import *  # noqa: F401,F403
from gex import greeks as _legacy

__all__ = [name for name in dir(_legacy) if not name.startswith("_")]
