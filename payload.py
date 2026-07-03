"""Build JSON-ready sensor payloads."""

from datetime import datetime, timezone

from config import ULTRASONIC_REFERENCE_V
from sensors.tof import read_sensors as read_tof_sensors


def utc_timestamp():
    return datetime.now(timezone.utc).isoformat()


def build_payload(tof_sensors=None): # when adding a new sensor, add it as a parameter here
    """Build a JSON-ready payload from the current sensor readings."""
    payload = {"timestamp": utc_timestamp()}

    if tof_sensors is not None:
        payload["tof"] = read_tof_sensors(tof_sensors)
    
    # then if you add a new sensor, add it here as well, e.g.:
    # if ultrasonic_sensors is not None:
    #     payload["ultrasonic"] = read_ultrasonic_sensors(ultrasonic_sensors, ULTRASONIC_REFERENCE_V)
    

    return payload
