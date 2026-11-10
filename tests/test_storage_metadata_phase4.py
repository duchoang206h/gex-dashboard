from pathlib import Path

from gex.core import Provenance, QualityFlags
from gex.storage.metadata import read_json, snapshot_manifest_path, write_snapshot_manifest


def test_write_and_read_snapshot_manifest(tmp_path: Path):
    prov = Provenance(symbol="SPX", source="cboe", quality=QualityFlags(delayed=True)).as_dict()
    path = write_snapshot_manifest("SPX", prov, rows=123, extra={"note": "ok"}, base=tmp_path)
    assert path == snapshot_manifest_path("SPX", base=tmp_path)
    assert path.exists()
    data = read_json(path)
    assert data["symbol"] == "SPX"
    assert data["rows"] == 123
    assert data["provenance"]["source"] == "cboe"
    assert data["provenance"]["quality"]["delayed"] is True
    assert data["schema_version"]
    assert data["note"] == "ok"
    assert data["updated_at"]


def test_read_json_missing(tmp_path: Path):
    assert read_json(tmp_path / "nope.json") is None
