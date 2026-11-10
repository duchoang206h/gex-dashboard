import pandas as pd
from datetime import datetime, timezone

from gex.core import (
    SCHEMA_VERSION,
    EventBus,
    Provenance,
    QualityFlags,
    RawChainSnapshot,
    topics,
    validate_provenance,
)
from gex.core.validation import ValidationError


def test_provenance_defaults_and_dict():
    p = Provenance(symbol="SPX", source="cboe")
    assert p.schema_version == SCHEMA_VERSION
    assert p.quality.delayed is False
    d = p.as_dict()
    assert d["symbol"] == "SPX"
    assert d["source"] == "cboe"
    assert d["quality"]["partial"] is False


def test_raw_chain_snapshot_with_quality_is_non_mutating():
    opts = pd.DataFrame([{"strike": 100, "type": "C"}])
    prov = Provenance(symbol="NDX", source="cboe", quality=QualityFlags(delayed=True))
    snap = RawChainSnapshot(symbol="NDX", spot=200.0, options=opts, provenance=prov)
    snap2 = snap.with_quality(partial=True)

    assert snap.provenance.quality.partial is False
    assert snap.provenance.quality.delayed is True
    assert snap2.provenance.quality.partial is True
    assert snap2.provenance.quality.delayed is True
    # options copied
    snap2.options.loc[0, "strike"] = 999
    assert snap.options.loc[0, "strike"] == 100


def test_event_bus_publish_subscribe_and_handler_isolation():
    bus = EventBus()
    seen = []

    def ok(ev):
        seen.append((ev.topic, ev.payload))

    def bad(_ev):
        raise RuntimeError("boom")

    bus.subscribe(topics.SUMMARY_UPDATED, bad)
    bus.subscribe(topics.SUMMARY_UPDATED, ok)
    ev = bus.publish(topics.SUMMARY_UPDATED, {"net_gex": 1})

    assert ev.topic == topics.SUMMARY_UPDATED
    assert seen == [(topics.SUMMARY_UPDATED, {"net_gex": 1})]


def test_validate_provenance_rejects_empty_fields():
    try:
        validate_provenance(Provenance(symbol="", source="cboe"))
        assert False, "expected ValidationError"
    except ValidationError:
        pass
    try:
        validate_provenance(Provenance(symbol="SPX", source=""))
        assert False, "expected ValidationError"
    except ValidationError:
        pass
    assert validate_provenance(Provenance(symbol="SPX", source="cboe")).source == "cboe"


def test_quality_flags_as_dict():
    q = QualityFlags(delayed=True, notes=("late",))
    d = q.as_dict()
    assert d["delayed"] is True
    assert d["notes"] == ("late",)
