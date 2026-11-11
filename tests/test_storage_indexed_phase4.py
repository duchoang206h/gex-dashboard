from datetime import datetime

import pandas as pd

from gex.core import Provenance
from gex.storage.indexed import get_history, get_latest_summary, index_db_path, index_summary
from gex.storage.metadata import dataset_manifest, write_snapshot_manifest


class _Summary:
    def __init__(self, ts, net_gex):
        self._row = {
            "timestamp": ts, "symbol": "SPX", "spot": 100.0, "net_gex": net_gex,
            "net_gex_0dte": net_gex, "zero_gamma": 99.0, "net_dex": 1.0,
            "pc_oi": 1.1, "pc_volume": 1.2, "basis": None, "source": "cboe",
        }

    def as_row(self):
        return dict(self._row)


def test_indexed_summary_roundtrip(tmp_path):
    prov = Provenance(symbol="SPX", source="cboe").as_dict()
    index_summary("SPX", _Summary("2026-01-01T10:00:00", 1.0), prov, base=tmp_path)
    index_summary("SPX", _Summary("2026-01-01T10:01:00", 2.0), prov, base=tmp_path)
    assert index_db_path(tmp_path).exists()

    latest = get_latest_summary("SPX", base=tmp_path)
    assert latest is not None
    assert latest["net_gex"] == 2.0
    assert latest["schema_version"]
    assert latest["provenance"]["source"] == "cboe"

    hist = get_history("SPX", last_n=10, base=tmp_path)
    assert [h["net_gex"] for h in hist] == [1.0, 2.0]


def test_dataset_manifest_reader(tmp_path):
    prov = Provenance(symbol="NDX", source="cboe").as_dict()
    write_snapshot_manifest("NDX", prov, rows=5, base=tmp_path)
    m = dataset_manifest(base=tmp_path)
    assert m["schema_version"]
    assert m["count"] == 1
    assert m["snapshots"][0]["symbol"] == "NDX"
