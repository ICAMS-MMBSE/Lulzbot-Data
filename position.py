#!/usr/bin/env python3
"""
Current phase (working):
  - 3x VL53L0X ToF        -> mux channels 0-2  (shared 0x29 address, must be muxed)
  - 3x MB1010 ultrasonic  -> ADS1115 A0-A2     (analog, on main bus)

Scaffolded for later (uncomment when the hardware arrives):
  - 2x AMG8833 thermal    -> mux channels 3-4
  - 2x MPU6050 accel/gyro -> mux channels 5-6

Setup:
  sudo raspi-config           # Interface Options -> I2C -> enable
  pip install adafruit-blinka adafruit-circuitpython-vl53l0x \
              adafruit-circuitpython-tca9548a adafruit-circuitpython-ads1x15 \
              adafruit-circuitpython-amg88xx adafruit-circuitpython-mpu6050
  i2cdetect -y 1              # sanity check: mux at 0x70, ADS1115 at 0x48
"""

import time
import json
from datetime import datetime, timezone

import board
import busio
import adafruit_tca9548a
import adafruit_vl53l0x

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

# import adafruit_amg88xx          # later
# import adafruit_mpu6050          # later

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

MUX_ADDRESS = 0x70  # SparkFun Qwiic Mux (TCA9548A) default

# One device per channel keeps addressing trivial — no address pins to juggle.
VL53_CHANNELS = {"tof_0": 0, "tof_1": 1, "tof_2": 2}
# AMG_CHANNELS   = {"thermal_0": 3, "thermal_1": 4}   # later
# ACCEL_CHANNELS = {"accel_0": 5, "accel_1": 6}       # later

READ_PERIOD_S = 0.2
TIMING_BUDGET_US = 50000  # VL53L0X: 50 ms. Raise for accuracy, lower for speed.

# ---------------------------------------------------------------------------
# Init
# ---------------------------------------------------------------------------

i2c = busio.I2C(board.SCL, board.SDA)
mux = adafruit_tca9548a.TCA9548A(i2c, address=MUX_ADDRESS)

# Each VL53L0X lives on its own mux channel, so the shared 0x29 address never
# collides. The TCA9548A wrapper selects the channel on every transaction,
# so there is no manual channel-switching step to get wrong.
tof_sensors = {}
for name, ch in VL53_CHANNELS.items():
    sensor = adafruit_vl53l0x.VL53L0X(mux[ch])
    sensor.measurement_timing_budget = TIMING_BUDGET_US
    tof_sensors[name] = sensor

# ADS1115 has a unique address (0x48), so it lives on the MAIN bus — no mux
# channel consumed.
ads = ADS.ADS1115(i2c)
ads.gain = 1  # +/-4.096V range; comfortably covers a 3.3V-referenced signal

# thermal_sensors = {n: adafruit_amg88xx.AMG88XX(mux[c]) for n, c in AMG_CHANNELS.items()}
# accel_sensors   = {n: adafruit_mpu6050.MPU6050(mux[c]) for n, c in ACCEL_CHANNELS.items()}

# ---------------------------------------------------------------------------
# Readers  (each returns a dict; errors are captured per-sensor, never fatal)
# ---------------------------------------------------------------------------

def read_tof():
    out = {}
    for name, sensor in tof_sensors.items():
        try:
            out[name] = {"distance_mm": sensor.range}
        except Exception as e:  # noqa: BLE001 - keep the loop alive on a bad read
            out[name] = {"error": str(e)}
    return out

# def read_thermal():
#     out = {}
#     for name, sensor in thermal_sensors.items():
#         try:
#             out[name] = {"pixels_c": [round(t, 2) for row in sensor.pixels for t in row]}
#         except Exception as e:
#             out[name] = {"error": str(e)}
#     return out


# def read_accel():
#     out = {}
#     for name, sensor in accel_sensors.items():
#         try:
#             ax, ay, az = sensor.acceleration
#             gx, gy, gz = sensor.gyro
#             out[name] = {"accel_ms2": [ax, ay, az], "gyro_rads": [gx, gy, gz]}
#         except Exception as e:
#             out[name] = {"error": str(e)}
#     return out


def build_payload():
    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tof": read_tof(),
        # "thermal": read_thermal(),
        # "accel": read_accel(),
    }

# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

def main():
    print("Starting ICAMS acquisition. Ctrl-C to stop.")
    try:
        while True:
            payload = build_payload()
            print(json.dumps(payload))
            # Later: mqtt_client.publish("icams/rig1/sensors", json.dumps(payload))
            time.sleep(READ_PERIOD_S)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()