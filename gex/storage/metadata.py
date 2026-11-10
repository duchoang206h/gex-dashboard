"""Storage metadata helpers (phase 4, additive).

These utilities add schema/provenance side information without altering existing
Parquet dataset formats.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from gex.config import SETTINGS
from gex.core import SCHEMA_VERSION


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def manifests_dir(base: Path | None = None) -> Path:
    return _ensure_dir((base or SETTINGS.data_dir) / "manifests")


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
        f.write("\n")
    os.replace(tmp, path)


def read_json(path: Path) -> dict[str, Any] | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None


def snapshot_manifest_path(symbol: str, base: Path | None = None) -> Path:
    safe = symbol.replace("/", "_")
    return manifests_dir(base) / f"{safe}.snapshot.json"


def write_snapshot_manifest(symbol: str, provenance: Mapping[str, Any] | None,
                            *, rows: int | None = None, extra: Mapping[str, Any] | None = None,
                            base: Path | None = None) -> Path:
    payload = {
        "symbol": symbol,
        "schema_version": SCHEMA_VERSION,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "rows": rows,
        "provenance": dict(provenance or {}),
    }
    if extra:
        payload.update(dict(extra))
    path = snapshot_manifest_path(symbol, base=base)
    write_json_atomic(path, payload)
    return path
