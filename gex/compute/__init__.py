"""Compute layer (pure/deterministic analytics).

Currently delegates to legacy implementations for parity during migration.
"""
from . import greeks, metrics, pipeline

__all__ = ["greeks", "metrics", "pipeline"]

