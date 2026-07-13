"""Sensor abstract base class.

Every physical (or mock) sensor implements this interface. The acquisition
loop and MQTT layer interact with sensors *only* through this ABC, so
swapping hardware (e.g. MPU6050 -> BNO055) means writing one new driver
class and editing config -- nothing else.

Drivers receive an I2C bus object in the constructor. In production this is
a ``TCA9548A[channel]`` object, so simply using ``self.i2c`` performs mux
channel selection structurally -- drivers never touch the mux directly.

Hardware libraries (Blinka / adafruit-circuitpython-*) must be imported
lazily inside ``initialize()`` so the package imports cleanly on dev
machines without hardware support.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from sensor_service.core.config import SensorConfig


class SensorError(Exception):
    """Base class for driver errors."""


class SensorInitError(SensorError):
    """Sensor failed to initialize."""


class SensorReadError(SensorError):
    """Sensor failed to produce a reading."""


class Sensor(ABC):
    """Abstract sensor.

    Class attributes:
        driver_name:   registry key (matches the config ``driver`` string).
        default_units: mapping of value key -> unit string, used to build
                       the ``units`` field of every MQTT payload.
    """

    driver_name: str = "abstract"
    default_units: Dict[str, str] = {}

    def __init__(self, i2c: Any, config: SensorConfig):
        self.i2c = i2c
        self.config = config
        self.name = config.name
        self.role = config.role
        self.sample_rate_hz = config.sample_rate_hz
        self.units: Dict[str, str] = dict(self.default_units)
        self._dev: Any = None

    @abstractmethod
    def initialize(self) -> None:
        """Set up the hardware. Raise ``SensorInitError`` on failure."""

    @abstractmethod
    def read(self) -> Dict[str, Any]:
        """Return one reading as a flat dict of value key -> value.

        Keys should match ``self.units``. Raise ``SensorReadError`` on
        failure -- the scheduler handles retry/backoff and status topics.
        """

    def health_check(self) -> Dict[str, Any]:
        """Cheap liveness probe. Default: attempt a read."""
        try:
            self.read()
            return {"healthy": True}
        except Exception as exc:  # noqa: BLE001 - report, don't crash
            return {"healthy": False, "error": f"{type(exc).__name__}: {exc}"}

    def close(self) -> None:
        """Release resources before re-initialization. Optional."""
        self._dev = None


def apply_axis_transform(distance_mm: float, params: dict) -> float:
    """Map a raw ToF distance to a machine-axis position.

    position_mm = sign * distance_mm + offset_mm

    ``sign`` and ``offset_mm`` come from config params so frame-mounted
    (position = offset - reading, sign=-1) and toolhead-mounted (position =
    reading + offset, sign=+1) sensors both work without code changes.
    """
    sign = float(params.get("sign", 1.0))
    offset = float(params.get("offset_mm", 0.0))
    return sign * distance_mm + offset
