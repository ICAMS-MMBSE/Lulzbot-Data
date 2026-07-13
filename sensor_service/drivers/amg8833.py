"""AMG8833 8x8 thermal camera (print/bed thermal view)."""
from __future__ import annotations

from typing import Any, Dict

from sensor_service.drivers.base import Sensor, SensorInitError, SensorReadError
from sensor_service.drivers.registry import register


@register("amg8833")
class AMG8833Driver(Sensor):
    default_units = {"grid_c": "degC[8x8]", "min_c": "degC", "max_c": "degC", "mean_c": "degC"}

    def initialize(self) -> None:
        try:
            import adafruit_amg88xx  # lazy: hardware lib
            self._dev = adafruit_amg88xx.AMG88XX(self.i2c, addr=self.config.address)
        except Exception as exc:  # noqa: BLE001
            raise SensorInitError(f"AMG8833 init failed: {exc}") from exc

    def read(self) -> Dict[str, Any]:
        try:
            grid = [[float(px) for px in row] for row in self._dev.pixels]
        except Exception as exc:  # noqa: BLE001
            raise SensorReadError(f"AMG8833 read failed: {exc}") from exc
        flat = [px for row in grid for px in row]
        return {
            "grid_c": grid,
            "min_c": min(flat),
            "max_c": max(flat),
            "mean_c": sum(flat) / len(flat),
        }
