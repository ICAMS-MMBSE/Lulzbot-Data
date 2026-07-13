"""Driver registry behaviour."""
import pytest

import sensor_service.drivers  # noqa: F401 - triggers registration
from sensor_service.drivers.registry import UnknownDriverError, known_drivers, resolve

ALL_DRIVERS = ["adxl345", "amg8833", "bme280", "mpu6050", "vcnl4010", "vl53l0x", "vl53l1x"]


def test_all_real_drivers_registered():
    assert known_drivers(use_mock=False) == ALL_DRIVERS


def test_every_real_driver_has_a_mock():
    assert known_drivers(use_mock=True) == ALL_DRIVERS


def test_real_and_mock_are_distinct_classes():
    for name in ALL_DRIVERS:
        assert resolve(name, use_mock=False) is not resolve(name, use_mock=True)


def test_case_insensitive():
    assert resolve("MPU6050") is resolve("mpu6050")


def test_unknown_driver_raises():
    with pytest.raises(UnknownDriverError, match="bno055"):
        resolve("bno055")
