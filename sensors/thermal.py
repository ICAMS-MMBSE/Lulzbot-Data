"""AMG8833 thermal sensor helpers for future expansion."""

import adafruit_amg88xx


def init_sensors(mux, channels):
    return {
        name: adafruit_amg88xx.AMG88XX(mux[channel])
        for name, channel in channels.items()
    }


def read_sensors(sensors):
    readings = {}

    for name, sensor in sensors.items():
        try:
            readings[name] = {
                "pixels_c": [
                    round(temperature, 2)
                    for row in sensor.pixels
                    for temperature in row
                ],
            }
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on bad reads.
            readings[name] = {"error": str(exc)}

    return readings
