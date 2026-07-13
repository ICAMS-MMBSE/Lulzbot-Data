"""Compare OctoPrint's commanded/reported position against external ToF
measurements and publish residuals to ``<base>/validation/<axis>``.

Reference sources (OctoPrint MQTT plugin, base topic ``octoPrint/`` by
default):

* ``octoPrint/event/ZChange``       -> {"new": <z_mm>, "old": ...}
  Fires on layer change. Reliable and always available -> primary Z source.
* ``octoPrint/event/PositionUpdate`` -> {"x":..,"y":..,"z":..,"e":..}
  Fires after M114. Enables X/Y comparison when M114 is polled or present
  in gcode.

Timestamp note: the plugin's ``_timestamp`` is whole seconds, too coarse
for alignment. Since the broker is local, we use message *arrival* time
(time.time() at receipt), which is accurate to a few ms.
"""
from __future__ import annotations

import json
import logging
import time
from typing import Dict

from sensor_service.core.config import ValidationConfig
from sensor_service.core.mqtt_client import MqttClient, build_topic
from sensor_service.core.payload import build_payload
from sensor_service.validation.alignment import Sample, SampleBuffer, align
from sensor_service.validation.csv_logger import ResidualCsvLogger

log = logging.getLogger("validation")

AXES = ("x", "y", "z")


class OctoPrintComparator:
    def __init__(self, cfg: ValidationConfig, mqtt: MqttClient):
        self.cfg = cfg
        self.mqtt = mqtt
        self.buffers: Dict[str, SampleBuffer] = {
            axis: SampleBuffer(horizon_s=cfg.buffer_seconds) for axis in AXES
        }
        self.csv = ResidualCsvLogger(cfg.csv_dir)
        self.stats = {"aligned": 0, "rejected_gap": 0, "no_data": 0}

    def start(self) -> None:
        base = self.mqtt.cfg.base_topic
        op = self.cfg.octoprint_base_topic
        for axis in AXES:
            self.mqtt.subscribe(build_topic(base, "position", axis), self._on_sensor_msg)
        self.mqtt.subscribe(build_topic(op, "event", "ZChange"), self._on_zchange)
        self.mqtt.subscribe(build_topic(op, "event", "PositionUpdate"), self._on_position_update)
        log.info("Validation comparator subscribed (OctoPrint base %r)", op)

    # -- our own telemetry -> ring buffers ----------------------------------
    def _on_sensor_msg(self, topic: str, raw: bytes) -> None:
        axis = topic.rsplit("/", 1)[-1].lower()
        if axis not in AXES:
            return
        try:
            payload = json.loads(raw)
            pos = float(payload["values"]["position_mm"])
        except (ValueError, KeyError, TypeError) as exc:
            log.debug("Unparseable sensor payload on %s: %s", topic, exc)
            return
        self.buffers[axis].append(Sample(t=time.time(), value=pos))

    # -- OctoPrint references -----------------------------------------------
    def _on_zchange(self, topic: str, raw: bytes) -> None:
        try:
            payload = json.loads(raw)
            z = float(payload["new"])
        except (ValueError, KeyError, TypeError) as exc:
            log.debug("Unparseable ZChange payload: %s", exc)
            return
        self._compare("zchange", "z", z, time.time())

    def _on_position_update(self, topic: str, raw: bytes) -> None:
        try:
            payload = json.loads(raw)
        except ValueError as exc:
            log.debug("Unparseable PositionUpdate payload: %s", exc)
            return
        now = time.time()
        for axis in AXES:
            if axis in payload and payload[axis] is not None:
                try:
                    self._compare("position_update", axis, float(payload[axis]), now)
                except (TypeError, ValueError):
                    continue

    # -- residual computation + publish --------------------------------------
    def _compare(self, source: str, axis: str, commanded_mm: float, ref_t: float) -> None:
        buf = self.buffers[axis]
        if len(buf) == 0:
            self.stats["no_data"] += 1
            return
        pair = align(buf, ref_t, commanded_mm, self.cfg.max_alignment_gap_s)
        if pair is None:
            self.stats["rejected_gap"] += 1
            log.debug("No %s sample within %.2fs of %s reference",
                      axis, self.cfg.max_alignment_gap_s, source)
            return
        self.stats["aligned"] += 1
        payload = build_payload(
            sensor_id=f"validation_{axis}",
            role="validation",
            values={
                "commanded_mm": pair.ref_value,
                "measured_mm": pair.measured_value,
                "residual_mm": pair.residual,
                "alignment_gap_s": pair.gap_s,
            },
            units={"commanded_mm": "mm", "measured_mm": "mm",
                   "residual_mm": "mm", "alignment_gap_s": "s"},
            seq=self.mqtt.seq.next(f"validation/{axis}"),
            extra={"source": source},
        )
        self.mqtt.telemetry(f"validation/{axis}", payload)
        self.csv.log(source, axis, pair)

    def stop(self) -> None:
        log.info("Validation stats: %s", self.stats)
        self.csv.close()
