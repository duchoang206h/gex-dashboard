"""Health/read helpers for rewrite runtime (phase 5, additive)."""
from __future__ import annotations

from typing import Any


def rewrite_health(symbols: list[str] | None = None) -> dict[str, Any]:
    from gex.pipeline import runtime as rt
    enabled = rt.rewrite_enabled() or rt.RUNTIME.enabled
    out: dict[str, Any] = {"enabled": enabled, "symbols": {}}
    if not enabled:
        return out
    rm = rt.RUNTIME.read_model
    # expose requested symbols, or all known in read model
    if symbols is None:
        try:
            symbols = list(getattr(rm, "_symbols", {}).keys())  # noqa: SLF001
        except Exception:
            symbols = []
    for sym in symbols:
        out["symbols"][sym] = rm.health(sym)
    return out
