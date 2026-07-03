"""Build JSON-ready sensor payloads."""

from datetime import datetime, timezone

from config import ULTRASONIC_REFERENCE_V
from sensors.tof import read_sensors as read_tof_sensors
from sensors.ultrasonic import read_sensors as read_ultrasonic_sensors


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def build_payload(tof_sensors=None, ultrasonic_sensors=None):
    payload = {"timestamp": utc_timestamp()}

    if tof_sensors is not None:
        payload["tof"] = read_tof_sensors(tof_sensors)

    if ultrasonic_sensors is not None:
        payload["ultrasonic"] = read_ultrasonic_sensors(
            ultrasonic_sensors,
            reference_voltage=ULTRASONIC_REFERENCE_V,
        )

    return payload
