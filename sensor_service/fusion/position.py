"""Position fusion: combine the three ToF axis sensors into one
``<base>/position`` message at a fixed rate.

Individual axis telemetry is still published per-sensor on
``position/x|y|z``; this module only merges the latest values. Axes whose
last reading is older than ``max_age_s`` are omitted (and flagged stale).
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Dict, Optional, Tuple

from sensor_service.core.config import FusionConfig
from sensor_service.core.mqtt_client import MqttClient
from sensor_service.core.payload import build_payload
from sensor_service.drivers.base import Sensor

log = logging.getLogger("fusion")

AXES = ("x", "y", "z")


class PositionFuser(threading.Thread):
    def __init__(self, cfg: FusionConfig, mqtt: MqttClient, stop_event: threading.Event):
        super().__init__(name="position-fuser", daemon=True)
        self.cfg = cfg
        self.mqtt = mqtt
        self.stop_event = stop_event
        self._lock = threading.Lock()
        # axis -> (monotonic_ts, position_mm, sensor_name)
        self._latest: Dict[str, Tuple[float, float, str]] = {}

    def ingest(self, sensor: Sensor, values: dict, ts_unix: float) -> None:
        """Reading hook called by the scheduler for every sensor reading."""
        axis = sensor.config.params.get("axis")
        pos = values.get("position_mm")
        if axis in AXES and pos is not None:
            with self._lock:
                self._latest[axis] = (time.monotonic(), float(pos), sensor.name)

    def _snapshot(self) -> Optional[dict]:
        now = time.monotonic()
        values: dict = {}
        sources: dict = {}
        stale: list = []
        with self._lock:
            latest = dict(self._latest)
        if not latest:
            return None
        for axis, (t, pos, name) in latest.items():
            age = now - t
            if age <= self.cfg.max_age_s:
                values[f"{axis}_mm"] = pos
                sources[axis] = name
            else:
                stale.append(axis)
        if not values:
            return None
        return {
            "values": values,
            "sources": sources,
            "stale_axes": stale,
        }

    def run(self) -> None:
        period = 1.0 / self.cfg.publish_rate_hz
        while not self.stop_event.wait(period):
            snap = self._snapshot()
            if snap is None:
                continue
            payload = build_payload(
                sensor_id="position_fusion",
                role="position",
                values=snap["values"],
                units={k: "mm" for k in snap["values"]},
                seq=self.mqtt.seq.next("position"),
                quality="degraded" if snap["stale_axes"] else "ok",
                extra={"sources": snap["sources"], "stale_axes": snap["stale_axes"]},
            )
            self.mqtt.telemetry("position", payload)
