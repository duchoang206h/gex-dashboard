from datetime import datetime

import pandas as pd

from gex.core import EnrichedSnapshotMeta, Provenance, QualityFlags
from gex.state import ReadModel


def test_readmodel_update_and_health():
    rm = ReadModel()
    prov = Provenance(symbol="SPX", source="cboe", provider_timestamp=datetime(2026, 1, 1, 12, 0, 0),
                      quality=QualityFlags(delayed=True))
    df = pd.DataFrame([{"strike": 100, "gex": 1.0}])
    meta = EnrichedSnapshotMeta(provenance=prov, row_count=1)

    rm.update_enriched("SPX", df, meta)
    st = rm.get("SPX")
    assert st is not None and st.enriched is not None
    assert st.provenance.source == "cboe"

    health = rm.health("SPX")
    assert health["available"] is True
    assert health["source"] == "cboe"
    assert health["quality"]["delayed"] is True
    assert health["last_error"] is None


def test_readmodel_summary_and_error():
    rm = ReadModel()
    prov = Provenance(symbol="NDX", source="cboe")
    rm.update_summary("NDX", {"net_gex": 10}, prov, extras={"k": "v"})
    st = rm.get("NDX")
    assert st.summary == {"net_gex": 10}
    assert st.summary_meta is not None
    assert st.summary_meta.extras["k"] == "v"

    rm.record_error("NDX", "boom")
    st2 = rm.get("NDX")
    assert st2.last_error == "boom"
    assert st2.summary == {"net_gex": 10}
    assert rm.health("NDX")["last_error"] == "boom"


def test_readmodel_missing_symbol_health():
    rm = ReadModel()
    h = rm.health("MISSING")
    assert h["available"] is False
    assert h["symbol"] == "MISSING"
