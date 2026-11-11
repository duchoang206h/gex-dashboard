"""Storage metadata helpers (phase 4, additive).

These utilities add schema/provenance side information without altering existing
Parquet dataset formats.
"""
from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from gex.config import SETTINGS
from gex.core import SCHEMA_VERSION


def list_snapshot_manifests(base: Path | None = None) -> list[dict[str, Any]]:
    """Versioned dataset manifest reader (additive): lists per-symbol snapshot manifests."""
    d = manifests_dir(base)
    out = []
    for p in sorted(d.glob("*.snapshot.json")):
        data = read_json(p)
        if data:
            data["_path"] = str(p)
            out.append(data)
    return out


def dataset_manifest(base: Path | None = None) -> dict[str, Any]:
    """Dataset-level manifest/index with schema version and known snapshot manifests."""
    snaps = list_snapshot_manifests(base)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "snapshots": snaps,
        "count": len(snaps),
    }


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def manifests_dir(base: Path | None = None) -> Path:
    return _ensure_dir((base or SETTINGS.data_dir) / "manifests")


def write_json_atomic(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
    try:
        with tmp.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, default=str)
            f.write("\n")
        os.replace(tmp, path)
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except Exception:
            pass


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
