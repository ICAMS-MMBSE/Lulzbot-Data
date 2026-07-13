"""Driver registry: maps config strings (e.g. "mpu6050") to driver classes.

Real and mock drivers register under the same key in separate tables; the
``use_mock_drivers`` config flag selects the table. Adding a sensor type is:

    @register("bno055")
    class BNO055Driver(Sensor): ...
"""
from __future__ import annotations

from typing import Callable, Dict, Type

from sensor_service.drivers.base import Sensor

_REAL: Dict[str, Type[Sensor]] = {}
_MOCK: Dict[str, Type[Sensor]] = {}


class UnknownDriverError(KeyError):
    pass


def register(name: str, mock: bool = False) -> Callable[[Type[Sensor]], Type[Sensor]]:
    """Class decorator registering a driver under ``name``."""
    table = _MOCK if mock else _REAL
    key = name.lower()

    def deco(cls: Type[Sensor]) -> Type[Sensor]:
        if key in table:
            raise ValueError(f"Driver {key!r} already registered ({'mock' if mock else 'real'})")
        cls.driver_name = key
        table[key] = cls
        return cls

    return deco


def resolve(name: str, use_mock: bool = False) -> Type[Sensor]:
    table = _MOCK if use_mock else _REAL
    key = name.lower()
    if key not in table:
        kind = "mock" if use_mock else "real"
        raise UnknownDriverError(
            f"No {kind} driver registered for {key!r}. Known: {sorted(table)}")
    return table[key]


def known_drivers(use_mock: bool = False) -> list:
    return sorted(_MOCK if use_mock else _REAL)
