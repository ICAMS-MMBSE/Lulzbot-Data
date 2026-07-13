"""Config parsing and validation."""
import textwrap

import pytest

from sensor_service.core.config import ConfigError, load_config

MINIMAL = """
mqtt:
  host: localhost
sensors:
  - name: tof_z
    driver: vl53l0x
    mux_channel: 0
    address: 0x29
    sample_rate_hz: 20
    topic_suffix: position/z
"""


def write(tmp_path, text):
    p = tmp_path / "config.yaml"
    p.write_text(textwrap.dedent(text), encoding="utf-8")
    return p


def test_minimal_config_parses(tmp_path):
    cfg = load_config(write(tmp_path, MINIMAL))
    assert cfg.mqtt.host == "localhost"
    assert cfg.mqtt.base_topic == "Lulzbot"
    s = cfg.sensors[0]
    assert s.name == "tof_z"
    assert s.address == 0x29
    assert s.role == "position_z"  # derived from topic_suffix
    assert s.enabled is True


def test_example_configs_parse():
    for path in ("config/config.example.yaml", "config/config.mock.yaml"):
        cfg = load_config(path)
        assert len(cfg.sensors) == 8
        channels = sorted(s.mux_channel for s in cfg.sensors if s.enabled)
        assert channels == list(range(8))


def test_missing_file():
    with pytest.raises(ConfigError, match="not found"):
        load_config("/nonexistent/config.yaml")


def test_duplicate_mux_channel_rejected(tmp_path):
    text = MINIMAL + """
  - name: tof_x
    driver: vl53l1x
    mux_channel: 0
    address: 0x29
    sample_rate_hz: 20
    topic_suffix: position/x
"""
    with pytest.raises(ConfigError, match="share mux channel"):
        load_config(write(tmp_path, text))


def test_disabled_sensor_may_share_channel(tmp_path):
    text = MINIMAL + """
  - name: tof_x
    driver: vl53l1x
    enabled: false
    mux_channel: 0
    address: 0x29
    sample_rate_hz: 20
    topic_suffix: position/x
"""
    cfg = load_config(write(tmp_path, text))
    assert [s for s in cfg.sensors if s.enabled][0].name == "tof_z"


def test_duplicate_names_rejected(tmp_path):
    text = MINIMAL + """
  - name: tof_z
    driver: vl53l1x
    mux_channel: 1
    address: 0x29
    sample_rate_hz: 20
    topic_suffix: position/x
"""
    with pytest.raises(ConfigError, match="Duplicate sensor names"):
        load_config(write(tmp_path, text))


def test_bad_channel_rejected(tmp_path):
    with pytest.raises(ConfigError, match="mux_channel must be 0-7"):
        load_config(write(tmp_path, MINIMAL.replace("mux_channel: 0", "mux_channel: 8")))


def test_bad_rate_rejected(tmp_path):
    with pytest.raises(ConfigError, match="sample_rate_hz"):
        load_config(write(tmp_path, MINIMAL.replace("sample_rate_hz: 20", "sample_rate_hz: 0")))


def test_wildcards_in_suffix_rejected(tmp_path):
    with pytest.raises(ConfigError, match="topic_suffix"):
        load_config(write(tmp_path, MINIMAL.replace("position/z", "position/#")))


def test_env_expansion(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_MQTT_HOST", "broker.example")
    cfg = load_config(write(tmp_path, MINIMAL.replace("localhost", "${TEST_MQTT_HOST}")))
    assert cfg.mqtt.host == "broker.example"


def test_env_expansion_missing_var(tmp_path, monkeypatch):
    monkeypatch.delenv("NOPE_VAR", raising=False)
    with pytest.raises(ConfigError, match="NOPE_VAR"):
        load_config(write(tmp_path, MINIMAL.replace("localhost", "${NOPE_VAR}")))
