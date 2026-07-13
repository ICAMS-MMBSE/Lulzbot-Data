"""Topic construction."""
from sensor_service.core.mqtt_client import build_topic


def test_basic_join():
    assert build_topic("Lulzbot", "position/z") == "Lulzbot/position/z"


def test_multiple_parts():
    assert build_topic("Lulzbot", "status", "tof_z") == "Lulzbot/status/tof_z"


def test_stray_slashes_normalized():
    assert build_topic("Lulzbot/", "/position/z/") == "Lulzbot/position/z"


def test_empty_parts_skipped():
    assert build_topic("Lulzbot", "", "thermal") == "Lulzbot/thermal"


def test_hierarchy_is_separable():
    # each measurement class must sit under its own subtree
    assert build_topic("Lulzbot", "acceleration/buildplate").startswith("Lulzbot/acceleration/")
    assert build_topic("Lulzbot", "validation/z").startswith("Lulzbot/validation/")
