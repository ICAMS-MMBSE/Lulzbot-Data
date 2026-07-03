#!/usr/bin/env python3
"""
Current phase (working):
  - 3x VL53L0X ToF        -> mux channels 0-2  (shared 0x29 address, must be muxed)
  - 3x MB1010 ultrasonic  -> ADS1115 A0-A2     (analog, on main bus)

Scaffolded for later:
  - 2x AMG8833 thermal    -> mux channels 3-4
  - 2x MPU6050 accel/gyro -> mux channels 5-6

Setup:
  sudo raspi-config           # Interface Options -> I2C -> enable
  pip install -r requirements.txt
  i2cdetect -y 1              # sanity check: mux at 0x70, ADS1115 at 0x48
"""

import time

from config import (
    READ_PERIOD_S,
    TIMING_BUDGET_US,
    ULTRASONIC_CHANNELS,
    VL53_CHANNELS,
)
from hardware import init_hardware
from outputs.console import write_payload
from payload import build_payload
from sensors.tof import init_sensors as init_tof_sensors


def init_sensor_stack():
    hardware = init_hardware()
    return {
        "tof": init_tof_sensors(
            hardware.mux,
            VL53_CHANNELS,
            TIMING_BUDGET_US,
        ),
        
    }


def main():
    print("Starting ICAMS acquisition. Ctrl-C to stop.")
    sensors = init_sensor_stack()

    try:
        while True:
            payload = build_payload(
                tof_sensors=sensors["tof"],
                ultrasonic_sensors=sensors["ultrasonic"],
            )
            write_payload(payload)
            time.sleep(READ_PERIOD_S)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
