"""MPU6050 accelerometer + gyro (printhead motion)."""
from __future__ import annotations

from typing import Any, Dict

from sensor_service.drivers.base import Sensor, SensorInitError, SensorReadError
from sensor_service.drivers.registry import register


@register("mpu6050")
class MPU6050Driver(Sensor):
    default_units = {
        "ax_ms2": "m/s^2", "ay_ms2": "m/s^2", "az_ms2": "m/s^2",
        "gx_rads": "rad/s", "gy_rads": "rad/s", "gz_rads": "rad/s",
        "temp_c": "degC",
    }

    def initialize(self) -> None:
        try:
            import adafruit_mpu6050  # lazy: hardware lib
            self._dev = adafruit_mpu6050.MPU6050(self.i2c, address=self.config.address)
        except Exception as exc:  # noqa: BLE001
            raise SensorInitError(f"MPU6050 init failed: {exc}") from exc

    def read(self) -> Dict[str, Any]:
        try:
            ax, ay, az = self._dev.acceleration
            gx, gy, gz = self._dev.gyro
            temp = self._dev.temperature
        except Exception as exc:  # noqa: BLE001
            raise SensorReadError(f"MPU6050 read failed: {exc}") from exc
        return {
            "ax_ms2": float(ax), "ay_ms2": float(ay), "az_ms2": float(az),
            "gx_rads": float(gx), "gy_rads": float(gy), "gz_rads": float(gz),
            "temp_c": float(temp),
        }
