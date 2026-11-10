"""Pure compute-layer wrappers for market metrics.

Phase 1 delegates to `gex.metrics` for behavior parity. Future phases can move
implementations here once callers and contracts are migrated.
"""
from __future__ import annotations

from gex.metrics import *  # noqa: F401,F403
from gex import metrics as _legacy

__all__ = [name for name in dir(_legacy) if not name.startswith("_")]
