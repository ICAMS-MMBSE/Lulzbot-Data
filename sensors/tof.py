"""VL53L0X time-of-flight sensor helpers."""

import adafruit_vl53l0x


def init_sensors(mux, channels, timing_budget_us):
    sensors = {}

    for name, channel in channels.items():
        sensor = adafruit_vl53l0x.VL53L0X(mux[channel])
        sensor.measurement_timing_budget = timing_budget_us
        sensors[name] = sensor

    return sensors


def read_sensors(sensors):
    readings = {}

    for name, sensor in sensors.items():
        try:
            readings[name] = {"distance_mm": sensor.range}
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on bad reads.
            readings[name] = {"error": str(exc)}

    return readings
