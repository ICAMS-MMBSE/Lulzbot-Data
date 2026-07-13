"""Mock drivers: full pipeline on a dev machine with no hardware.

Each mock registers under the same key as its real counterpart (in the
mock table) and produces plausible, smoothly varying synthetic data so
downstream consumers (MQTT dashboards, the validation module, plots) see
realistic streams.
"""
from sensor_service.drivers.mock import mock_drivers  # noqa: F401
