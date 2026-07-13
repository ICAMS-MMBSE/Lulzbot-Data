"""ADXL345 3-axis accelerometer (buildplate vibration)."""
from __future__ import annotations

from typing import Any, Dict

from sensor_service.drivers.base import Sensor, SensorInitError, SensorReadError
from sensor_service.drivers.registry import register


@register("adxl345")
class ADXL345Driver(Sensor):
    default_units = {"ax_ms2": "m/s^2", "ay_ms2": "m/s^2", "az_ms2": "m/s^2"}

    def initialize(self) -> None:
        try:
            import adafruit_adxl34x  # lazy: hardware lib
            self._dev = adafruit_adxl34x.ADXL345(self.i2c, address=self.config.address)
            rng = self.config.params.get("range_g")
            if rng:
                self._dev.range = {
                    2: adafruit_adxl34x.Range.RANGE_2_G,
                    4: adafruit_adxl34x.Range.RANGE_4_G,
                    8: adafruit_adxl34x.Range.RANGE_8_G,
                    16: adafruit_adxl34x.Range.RANGE_16_G,
                }[int(rng)]
        except Exception as exc:  # noqa: BLE001
            raise SensorInitError(f"ADXL345 init failed: {exc}") from exc

    def read(self) -> Dict[str, Any]:
        try:
            ax, ay, az = self._dev.acceleration
        except Exception as exc:  # noqa: BLE001
            raise SensorReadError(f"ADXL345 read failed: {exc}") from exc
        return {"ax_ms2": float(ax), "ay_ms2": float(ay), "az_ms2": float(az)}
