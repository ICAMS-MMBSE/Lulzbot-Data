"""VL53L0X time-of-flight distance sensor (Z axis, toolhead-mounted)."""
from __future__ import annotations

from typing import Any, Dict

from sensor_service.drivers.base import (
    Sensor, SensorInitError, SensorReadError, apply_axis_transform,
)
from sensor_service.drivers.registry import register


@register("vl53l0x")
class VL53L0XDriver(Sensor):
    default_units = {"distance_mm": "mm", "position_mm": "mm"}

    def initialize(self) -> None:
        try:
            import adafruit_vl53l0x  # lazy: hardware lib
            self._dev = adafruit_vl53l0x.VL53L0X(self.i2c, address=self.config.address)
            budget_us = self.config.params.get("timing_budget_us")
            if budget_us:
                self._dev.measurement_timing_budget = int(budget_us)
        except Exception as exc:  # noqa: BLE001
            raise SensorInitError(f"VL53L0X init failed: {exc}") from exc

    def read(self) -> Dict[str, Any]:
        try:
            distance_mm = float(self._dev.range)
        except Exception as exc:  # noqa: BLE001
            raise SensorReadError(f"VL53L0X read failed: {exc}") from exc
        return {
            "distance_mm": distance_mm,
            "position_mm": apply_axis_transform(distance_mm, self.config.params),
        }
