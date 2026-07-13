"""End-to-end sanity of mock drivers against the Sensor contract."""
import pytest

import sensor_service.drivers  # noqa: F401
from sensor_service.core.config import SensorConfig
from sensor_service.drivers.registry import known_drivers, resolve


def make_cfg(driver, **params):
    return SensorConfig(
        name=f"test_{driver}", driver=driver, mux_channel=0, address=0x29,
        sample_rate_hz=10, topic_suffix=f"test/{driver}", role="test", params=params,
    )


@pytest.mark.parametrize("driver", known_drivers(use_mock=True))
def test_mock_driver_contract(driver):
    cls = resolve(driver, use_mock=True)
    sensor = cls("mock-i2c", make_cfg(driver))
    sensor.initialize()
    values = sensor.read()
    assert isinstance(values, dict) and values
    # every declared unit key appears in the reading
    assert set(sensor.units) == set(values)
    assert sensor.health_check()["healthy"] is True


def test_tof_transform_applied():
    cls = resolve("vl53l1x", use_mock=True)
    sensor = cls("mock-i2c", make_cfg("vl53l1x", axis="x", sign=-1.0, offset_mm=300.0))
    sensor.initialize()
    v = sensor.read()
    assert abs(v["position_mm"] - (300.0 - v["distance_mm"])) < 1e-6


def test_vcnl_presence_is_bool():
    cls = resolve("vcnl4010", use_mock=True)
    sensor = cls("mock-i2c", make_cfg("vcnl4010", present_threshold=2200, hysteresis=200))
    sensor.initialize()
    assert isinstance(sensor.read()["person_present"], bool)
