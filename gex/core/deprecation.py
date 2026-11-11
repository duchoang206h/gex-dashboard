"""Deprecation helpers for rewrite migration.

Legacy compatibility shims must remain until parity soak and deprecation window
are complete. This module provides explicit markers and opt-in warnings.
"""
from __future__ import annotations

import os
import warnings

_EMITTED: set[str] = set()

DEPRECATED_SHIMS = {
    "gex.compute.greeks": "compat wrapper over gex.greeks; slated for removal after deprecation window",
    "gex.compute.metrics": "compat wrapper over gex.metrics; slated for removal after deprecation window",
}


def warn_deprecated(key: str, message: str | None = None, *, force: bool = False) -> None:
    """Emit DeprecationWarning once per key when opt-in or forced.

    Opt-in via `GEX_REWRITE_DEPRECATION_WARNINGS=1` to avoid noisy defaults.
    """
    if key in _EMITTED and not force:
        return
    if not force and os.environ.get("GEX_REWRITE_DEPRECATION_WARNINGS", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return
    _EMITTED.add(key)
    warnings.warn(message or DEPRECATED_SHIMS.get(key, f"deprecated: {key}"), DeprecationWarning, stacklevel=2)


def reset_deprecation_state() -> None:
    _EMITTED.clear()
