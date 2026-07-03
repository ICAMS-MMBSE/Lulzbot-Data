"""Hardware setup helpers."""

from dataclasses import dataclass
from typing import Any

import board
import busio
import adafruit_tca9548a
import adafruit_ads1x15.ads1115 as ADS

from config import ADS_GAIN, MUX_ADDRESS


@dataclass
class Hardware:
    i2c: Any
    mux: Any
    ads: Any


def init_i2c():
    return busio.I2C(board.SCL, board.SDA)


def init_mux(i2c, address=MUX_ADDRESS):
    return adafruit_tca9548a.TCA9548A(i2c, address=address)


def init_ads(i2c, gain=ADS_GAIN):
    ads = ADS.ADS1115(i2c)
    ads.gain = gain
    return ads


def init_hardware():
    i2c = init_i2c()
    return Hardware(
        i2c=i2c,
        mux=init_mux(i2c),
        ads=init_ads(i2c),
    )
