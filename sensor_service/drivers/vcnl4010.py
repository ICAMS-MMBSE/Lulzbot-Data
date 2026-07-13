"""VCNL4010 proximity sensor (person-in-front-of-printer detection).

Publishes raw proximity counts plus a derived ``person_present`` boolean
with hysteresis: enter "present" above ``present_threshold + hysteresis``,
leave below ``present_threshold - hysteresis``. Both come from config.
"""
from __future__ import annotations

from typing import Any, Dict

from sensor_service.drivers.base import Sensor, SensorInitError, SensorReadError
from sensor_service.drivers.registry import register


@register("vcnl4010")
class VCNL4010Driver(Sensor):
    default_units = {"proximity_counts": "counts", "ambient_lux": "lux", "person_present": "bool"}

    def __init__(self, i2c, config):
        super().__init__(i2c, config)
        self._present = False

    def initialize(self) -> None:
        try:
            import adafruit_vcnl4010  # lazy: hardware lib
            try:
                self._dev = adafruit_vcnl4010.VCNL4010(self.i2c, address=self.config.address)
            except TypeError:
                # older lib versions have no address kwarg (fixed 0x13)
                self._dev = adafruit_vcnl4010.VCNL4010(self.i2c)
        except Exception as exc:  # noqa: BLE001
            raise SensorInitError(f"VCNL4010 init failed: {exc}") from exc
        self._present = False

    def _update_presence(self, proximity: float) -> bool:
        thr = float(self.config.params.get("present_threshold", 2200))
        hyst = float(self.config.params.get("hysteresis", 200))
        if self._present:
            self._present = proximity > (thr - hyst)
        else:
            self._present = proximity > (thr + hyst)
        return self._present

    def read(self) -> Dict[str, Any]:
        try:
            proximity = float(self._dev.proximity)
            ambient = float(self._dev.ambient_lux)
        except Exception as exc:  # noqa: BLE001
            raise SensorReadError(f"VCNL4010 read failed: {exc}") from exc
        return {
            "proximity_counts": proximity,
            "ambient_lux": ambient,
            "person_present": self._update_presence(proximity),
        }
