"""MQTT payload schema.

Every message published by this service -- telemetry, status, fusion,
validation -- goes through ``build_payload`` so the JSON envelope is
uniform: ISO 8601 UTC timestamp, monotonic per-topic sequence number,
sensor ID, role, values, units, quality.
"""
from __future__ import annotations

import threading
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Dict, Optional

REQUIRED_FIELDS = ("ts", "seq", "sensor_id", "role", "values", "units", "quality")


def utc_now_iso() -> str:
    """Current UTC time, ISO 8601 with milliseconds and 'Z' suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


class SequenceCounter:
    """Thread-safe monotonic sequence numbers, one counter per key."""

    def __init__(self) -> None:
        self._counts: Dict[str, int] = defaultdict(int)
        self._lock = threading.Lock()

    def next(self, key: str) -> int:
        with self._lock:
            self._counts[key] += 1
            return self._counts[key]


def build_payload(
    sensor_id: str,
    role: str,
    values: Dict[str, Any],
    units: Dict[str, str],
    seq: int,
    quality: str = "ok",
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "ts": utc_now_iso(),
        "seq": seq,
        "sensor_id": sensor_id,
        "role": role,
        "values": values,
        "units": units,
        "quality": quality,
    }
    if extra:
        payload.update(extra)
    return payload
