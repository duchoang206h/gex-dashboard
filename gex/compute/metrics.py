"""Pure compute-layer wrappers for market metrics.

Phase 1 delegates to `gex.metrics` for behavior parity. Future phases can move
implementations here once callers and contracts are migrated.

Compatibility shim: retained until deprecation window/parity soak completion.
Set `GEX_REWRITE_DEPRECATION_WARNINGS=1` to emit opt-in deprecation warnings.
"""
from __future__ import annotations

from gex.metrics import *  # noqa: F401,F403
from gex import metrics as _legacy

try:
    from gex.core.deprecation import warn_deprecated
    warn_deprecated("gex.compute.metrics")
except Exception:
    pass

__all__ = [name for name in dir(_legacy) if not name.startswith("_")]

