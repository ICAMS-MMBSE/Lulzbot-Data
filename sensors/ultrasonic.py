"""ADS1115/MB1010 ultrasonic sensor helpers."""

import adafruit_ads1x15.ads1115 as ADS
from adafruit_ads1x15.analog_in import AnalogIn

MM_PER_INCH = 25.4
MB1010_STEPS_PER_INCH = 512

ADS_PINS = {
    0: ADS.P0,
    1: ADS.P1,
    2: ADS.P2,
    3: ADS.P3,
}


def init_sensors(ads, channels):
    sensors = {}

    for name, channel in channels.items():
        sensors[name] = AnalogIn(ads, _pin_for_channel(channel))

    return sensors


def read_sensors(sensors, reference_voltage):
    readings = {}

    for name, sensor in sensors.items():
        try:
            voltage = sensor.voltage
            readings[name] = {
                "voltage": round(voltage, 4),
                "raw": sensor.value,
                "distance_mm_estimate": round(
                    voltage_to_distance_mm(voltage, reference_voltage),
                    1,
                ),
            }
        except Exception as exc:  # noqa: BLE001 - keep the loop alive on bad reads.
            readings[name] = {"error": str(exc)}

    return readings


def voltage_to_distance_mm(voltage, reference_voltage):
    inches = voltage * MB1010_STEPS_PER_INCH / reference_voltage
    return inches * MM_PER_INCH


def _pin_for_channel(channel):
    try:
        return ADS_PINS[channel]
    except KeyError as exc:
        raise ValueError(f"ADS1115 channel must be 0-3, got {channel}") from exc
