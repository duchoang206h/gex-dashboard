"""Optional SQLite hot-query index for summaries/history (phase 4).

Default off. Enabled via `GEX_REWRITE_INDEX=1` (and rewrite runtime enabled) or
by calling functions explicitly. Additive and does not replace Parquet storage.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from gex.config import SETTINGS
from gex.core import SCHEMA_VERSION


def index_db_path(base: Path | None = None) -> Path:
    d = (base or SETTINGS.data_dir) / "index"
    d.mkdir(parents=True, exist_ok=True)
    return d / "rewrite.sqlite"


def _connect(base: Path | None = None) -> sqlite3.Connection:
    conn = sqlite3.connect(index_db_path(base))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS summary_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL,
            timestamp TEXT,
            spot REAL,
            net_gex REAL,
            net_gex_0dte REAL,
            zero_gamma REAL,
            net_dex REAL,
            pc_oi REAL,
            pc_volume REAL,
            basis REAL,
            source TEXT,
            schema_version TEXT,
            provenance_json TEXT,
            inserted_at TEXT NOT NULL
        )
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_summary_symbol_ts ON summary_history(symbol, timestamp)")
    conn.commit()


def _summary_row(summary: Any) -> dict[str, Any]:
    if hasattr(summary, "as_row"):
        row = dict(summary.as_row())
    elif isinstance(summary, dict):
        row = dict(summary)
    else:
        row = {k: getattr(summary, k) for k in dir(summary) if not k.startswith("_")}
    # normalize timestamp
    ts = row.get("timestamp")
    if hasattr(ts, "isoformat"):
        row["timestamp"] = ts.isoformat()
    return row


def index_summary(symbol: str, summary: Any, provenance: dict[str, Any] | None = None,
                  *, base: Path | None = None) -> None:
    row = _summary_row(summary)
    prov = provenance or {}
    with _connect(base) as conn:
        ensure_schema(conn)
        conn.execute(
            """
            INSERT INTO summary_history
            (symbol, timestamp, spot, net_gex, net_gex_0dte, zero_gamma, net_dex, pc_oi, pc_volume, basis, source, schema_version, provenance_json, inserted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                symbol,
                row.get("timestamp"),
                row.get("spot"),
                row.get("net_gex"),
                row.get("net_gex_0dte"),
                row.get("zero_gamma"),
                row.get("net_dex"),
                row.get("pc_oi"),
                row.get("pc_volume"),
                row.get("basis"),
                row.get("source") or prov.get("source"),
                prov.get("schema_version") or SCHEMA_VERSION,
                json.dumps(prov, default=str),
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        conn.commit()


def get_latest_summary(symbol: str, *, base: Path | None = None) -> dict[str, Any] | None:
    with _connect(base) as conn:
        ensure_schema(conn)
        cur = conn.execute(
            "SELECT symbol,timestamp,spot,net_gex,net_gex_0dte,zero_gamma,net_dex,pc_oi,pc_volume,basis,source,schema_version,provenance_json FROM summary_history WHERE symbol=? ORDER BY id DESC LIMIT 1",
            (symbol,),
        )
        r = cur.fetchone()
    if not r:
        return None
    cols = ["symbol","timestamp","spot","net_gex","net_gex_0dte","zero_gamma","net_dex","pc_oi","pc_volume","basis","source","schema_version","provenance_json"]
    d = dict(zip(cols, r))
    try:
        d["provenance"] = json.loads(d.pop("provenance_json") or "{}")
    except Exception:
        d["provenance"] = {}
    return d


def get_history(symbol: str, last_n: int = 50, *, base: Path | None = None) -> list[dict[str, Any]]:
    with _connect(base) as conn:
        ensure_schema(conn)
        cur = conn.execute(
            "SELECT symbol,timestamp,spot,net_gex,net_gex_0dte,zero_gamma,net_dex,pc_oi,pc_volume,basis,source,schema_version FROM summary_history WHERE symbol=? ORDER BY id DESC LIMIT ?",
            (symbol, int(last_n)),
        )
        rows = cur.fetchall()
    cols = ["symbol","timestamp","spot","net_gex","net_gex_0dte","zero_gamma","net_dex","pc_oi","pc_volume","basis","source","schema_version"]
    out = [dict(zip(cols, r)) for r in rows]
    out.reverse()  # chronological
    return out
