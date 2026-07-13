"""Payload schema: every message carries the required envelope."""
import re

from sensor_service.core.payload import (
    REQUIRED_FIELDS, SequenceCounter, build_payload, utc_now_iso,
)

ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$")


def test_timestamp_format():
    assert ISO_RE.match(utc_now_iso())


def test_required_fields_present():
    p = build_payload("tof_z", "z_position", {"distance_mm": 12.3},
                      {"distance_mm": "mm"}, seq=7)
    for f in REQUIRED_FIELDS:
        assert f in p
    assert p["seq"] == 7
    assert p["sensor_id"] == "tof_z"
    assert p["quality"] == "ok"
    assert ISO_RE.match(p["ts"])


def test_extra_fields_merged():
    p = build_payload("f", "r", {}, {}, seq=1, extra={"source": "zchange"})
    assert p["source"] == "zchange"


def test_sequence_counter_monotonic_per_key():
    c = SequenceCounter()
    assert [c.next("a"), c.next("a"), c.next("a")] == [1, 2, 3]
    assert c.next("b") == 1  # independent counter per topic
