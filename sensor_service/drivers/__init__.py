"""Importing this package registers all real and mock drivers."""
from sensor_service.drivers import (  # noqa: F401
    adxl345,
    amg8833,
    bme280,
    mpu6050,
    vcnl4010,
    vl53l0x,
    vl53l1x,
)
from sensor_service.drivers import mock  # noqa: F401
