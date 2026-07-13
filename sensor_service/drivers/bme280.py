"""BME280 ambient environment sensor (temp / humidity / pressure)."""
from __future__ import annotations

from typing import Any, Dict

from sensor_service.drivers.base import Sensor, SensorInitError, SensorReadError
from sensor_service.drivers.registry import register


@register("bme280")
class BME280Driver(Sensor):
    default_units = {"temp_c": "degC", "humidity_pct": "%RH", "pressure_hpa": "hPa"}

    def initialize(self) -> None:
        try:
            from adafruit_bme280 import basic as adafruit_bme280  # lazy: hardware lib
            self._dev = adafruit_bme280.Adafruit_BME280_I2C(
                self.i2c, address=self.config.address)
        except Exception as exc:  # noqa: BLE001
            raise SensorInitError(f"BME280 init failed: {exc}") from exc

    def read(self) -> Dict[str, Any]:
        try:
            return {
                "temp_c": float(self._dev.temperature),
                "humidity_pct": float(self._dev.relative_humidity),
                "pressure_hpa": float(self._dev.pressure),
            }
        except Exception as exc:  # noqa: BLE001
            raise SensorReadError(f"BME280 read failed: {exc}") from exc
