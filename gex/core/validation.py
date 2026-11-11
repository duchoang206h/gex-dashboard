"""Validation helpers for core contracts."""
from __future__ import annotations

from .schemas import Provenance


class ValidationError(ValueError):
    """Raised when a core contract is invalid."""


def require_non_empty(value: str, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{field} must be a non-empty string")
    return value


def validate_provenance(prov: Provenance) -> Provenance:
    require_non_empty(prov.symbol, "symbol")
    require_non_empty(prov.source, "source")
    require_non_empty(prov.schema_version, "schema_version")
    return prov
