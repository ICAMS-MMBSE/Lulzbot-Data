"""VL53L1X time-of-flight distance sensor (X / Y axes, frame-mounted)."""
from __future__ import annotations

from typing import Any, Dict

from sensor_service.drivers.base import (
    Sensor, SensorInitError, SensorReadError, apply_axis_transform,
)
from sensor_service.drivers.registry import register


@register("vl53l1x")
class VL53L1XDriver(Sensor):
    default_units = {"distance_mm": "mm", "position_mm": "mm"}

    def initialize(self) -> None:
        try:
            import adafruit_vl53l1x  # lazy: hardware lib
            self._dev = adafruit_vl53l1x.VL53L1X(self.i2c, address=self.config.address)
            # distance_mode: 1 = short (better ambient immunity, <=1.3 m),
            # 2 = long (up to 4 m). Printer axes are short-range.
            self._dev.distance_mode = int(self.config.params.get("distance_mode", 1))
            self._dev.timing_budget = int(self.config.params.get("timing_budget_ms", 50))
            self._dev.start_ranging()
        except Exception as exc:  # noqa: BLE001
            raise SensorInitError(f"VL53L1X init failed: {exc}") from exc

    def read(self) -> Dict[str, Any]:
        try:
            distance_cm = self._dev.distance  # cm, or None if no target/no data
            self._dev.clear_interrupt()
        except Exception as exc:  # noqa: BLE001
            raise SensorReadError(f"VL53L1X read failed: {exc}") from exc
        if distance_cm is None:
            raise SensorReadError("VL53L1X returned no ranging data (target out of range?)")
        distance_mm = float(distance_cm) * 10.0
        return {
            "distance_mm": distance_mm,
            "position_mm": apply_axis_transform(distance_mm, self.config.params),
        }

    def close(self) -> None:
        try:
            if self._dev is not None:
                self._dev.stop_ranging()
        except Exception:  # noqa: BLE001
            pass
        super().close()
