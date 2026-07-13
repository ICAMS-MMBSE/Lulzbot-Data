"""Configuration loading and validation.

All hardware topology (mux channels, addresses), MQTT settings, and sample
rates live in YAML config -- never in code. ``load_config`` parses and
validates the file into frozen dataclasses; any structural problem raises
``ConfigError`` with a human-readable message before the service starts.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import yaml


class ConfigError(Exception):
    """Raised when the config file is missing, malformed, or inconsistent."""


_ENV_RE = re.compile(r"\$\{([A-Za-z0-9_]+)\}")


def _expand_env(obj: Any) -> Any:
    """Recursively expand ``${VAR}`` references from the environment."""
    if isinstance(obj, dict):
        return {k: _expand_env(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand_env(v) for v in obj]
    if isinstance(obj, str):
        def repl(m: "re.Match[str]") -> str:
            var = m.group(1)
            if var not in os.environ:
                raise ConfigError(f"Environment variable {var!r} referenced in config is not set")
            return os.environ[var]
        return _ENV_RE.sub(repl, obj)
    return obj


@dataclass(frozen=True)
class MqttConfig:
    host: str
    port: int = 1883
    username: Optional[str] = None
    password: Optional[str] = None
    base_topic: str = "Lulzbot"
    client_id: str = "lulzbot-sensor-service"
    keepalive: int = 30
    qos_telemetry: int = 0
    qos_status: int = 1
    retain_telemetry: bool = False
    retain_status: bool = True


@dataclass(frozen=True)
class MuxConfig:
    driver: str = "tca9548a"
    address: int = 0x70


@dataclass(frozen=True)
class LoggingConfig:
    level: str = "INFO"
    format: str = "plain"  # "plain" | "json"


@dataclass(frozen=True)
class SensorConfig:
    name: str
    driver: str
    mux_channel: int
    address: int
    sample_rate_hz: float
    topic_suffix: str
    role: str
    enabled: bool = True
    params: dict = field(default_factory=dict)


@dataclass(frozen=True)
class FusionConfig:
    enabled: bool = True
    publish_rate_hz: float = 10.0
    max_age_s: float = 1.0


@dataclass(frozen=True)
class ValidationConfig:
    enabled: bool = False
    octoprint_base_topic: str = "octoPrint"
    max_alignment_gap_s: float = 0.5
    buffer_seconds: float = 15.0
    csv_dir: Optional[str] = None


@dataclass(frozen=True)
class HealthConfig:
    reinit_after_failures: int = 3
    backoff_initial_s: float = 1.0
    backoff_max_s: float = 60.0
    heartbeat_interval_s: float = 30.0


@dataclass(frozen=True)
class AppConfig:
    mqtt: MqttConfig
    mux: MuxConfig
    logging: LoggingConfig
    sensors: tuple
    fusion: FusionConfig
    validation: ValidationConfig
    health: HealthConfig
    use_mock_drivers: bool = False


_TOPIC_FORBIDDEN = ("+", "#")


def _require(raw: dict, key: str, ctx: str) -> Any:
    if key not in raw:
        raise ConfigError(f"Missing required key {key!r} in {ctx}")
    return raw[key]


def _build_sensor(raw: dict, index: int) -> SensorConfig:
    ctx = f"sensors[{index}]"
    name = _require(raw, "name", ctx)
    ctx = f"sensor {name!r}"
    suffix = str(_require(raw, "topic_suffix", ctx)).strip("/")
    if not suffix:
        raise ConfigError(f"{ctx}: topic_suffix must be non-empty")
    for ch in _TOPIC_FORBIDDEN:
        if ch in suffix:
            raise ConfigError(f"{ctx}: topic_suffix may not contain {ch!r}")
    mux_channel = int(_require(raw, "mux_channel", ctx))
    if not 0 <= mux_channel <= 7:
        raise ConfigError(f"{ctx}: mux_channel must be 0-7, got {mux_channel}")
    rate = float(_require(raw, "sample_rate_hz", ctx))
    if rate <= 0:
        raise ConfigError(f"{ctx}: sample_rate_hz must be > 0, got {rate}")
    address = int(_require(raw, "address", ctx))
    if not 0x03 <= address <= 0x77:
        raise ConfigError(f"{ctx}: I2C address 0x{address:02x} outside valid 7-bit range")
    params = raw.get("params") or {}
    if not isinstance(params, dict):
        raise ConfigError(f"{ctx}: params must be a mapping")
    return SensorConfig(
        name=str(name),
        driver=str(_require(raw, "driver", ctx)).lower(),
        mux_channel=mux_channel,
        address=address,
        sample_rate_hz=rate,
        topic_suffix=suffix,
        role=str(raw.get("role", suffix.replace("/", "_"))),
        enabled=bool(raw.get("enabled", True)),
        params=params,
    )


def load_config(path: "str | Path") -> AppConfig:
    path = Path(path)
    if not path.exists():
        raise ConfigError(f"Config file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise ConfigError(f"Invalid YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Top level of {path} must be a mapping")
    raw = _expand_env(raw)

    mqtt_raw = _require(raw, "mqtt", "config")
    mqtt = MqttConfig(
        host=str(_require(mqtt_raw, "host", "mqtt")),
        port=int(mqtt_raw.get("port", 1883)),
        username=mqtt_raw.get("username") or None,
        password=mqtt_raw.get("password") or None,
        base_topic=str(mqtt_raw.get("base_topic", "Lulzbot")).strip("/"),
        client_id=str(mqtt_raw.get("client_id", "lulzbot-sensor-service")),
        keepalive=int(mqtt_raw.get("keepalive", 30)),
        qos_telemetry=int((mqtt_raw.get("qos") or {}).get("telemetry", 0)),
        qos_status=int((mqtt_raw.get("qos") or {}).get("status", 1)),
        retain_telemetry=bool((mqtt_raw.get("retain") or {}).get("telemetry", False)),
        retain_status=bool((mqtt_raw.get("retain") or {}).get("status", True)),
    )
    if not mqtt.base_topic:
        raise ConfigError("mqtt.base_topic must be non-empty")

    mux_raw = (raw.get("i2c") or {}).get("mux") or {}
    mux = MuxConfig(driver=str(mux_raw.get("driver", "tca9548a")).lower(),
                    address=int(mux_raw.get("address", 0x70)))

    log_raw = raw.get("logging") or {}
    logging_cfg = LoggingConfig(level=str(log_raw.get("level", "INFO")).upper(),
                                format=str(log_raw.get("format", "plain")).lower())

    sensors_raw = _require(raw, "sensors", "config")
    if not isinstance(sensors_raw, list) or not sensors_raw:
        raise ConfigError("'sensors' must be a non-empty list")
    sensors = tuple(_build_sensor(s, i) for i, s in enumerate(sensors_raw))

    names = [s.name for s in sensors]
    if len(names) != len(set(names)):
        dupes = sorted({n for n in names if names.count(n) > 1})
        raise ConfigError(f"Duplicate sensor names: {dupes}")
    enabled_channels = [s.mux_channel for s in sensors if s.enabled]
    if len(enabled_channels) != len(set(enabled_channels)):
        dupes = sorted({c for c in enabled_channels if enabled_channels.count(c) > 1})
        raise ConfigError(f"Multiple enabled sensors share mux channel(s): {dupes}")

    fusion_raw = (raw.get("fusion") or {}).get("position") or {}
    fusion = FusionConfig(
        enabled=bool(fusion_raw.get("enabled", True)),
        publish_rate_hz=float(fusion_raw.get("publish_rate_hz", 10.0)),
        max_age_s=float(fusion_raw.get("max_age_s", 1.0)),
    )

    val_raw = raw.get("validation") or {}
    validation = ValidationConfig(
        enabled=bool(val_raw.get("enabled", False)),
        octoprint_base_topic=str(val_raw.get("octoprint_base_topic", "octoPrint")).strip("/"),
        max_alignment_gap_s=float(val_raw.get("max_alignment_gap_s", 0.5)),
        buffer_seconds=float(val_raw.get("buffer_seconds", 15.0)),
        csv_dir=val_raw.get("csv_dir") or None,
    )

    health_raw = raw.get("health") or {}
    health = HealthConfig(
        reinit_after_failures=int(health_raw.get("reinit_after_failures", 3)),
        backoff_initial_s=float(health_raw.get("backoff_initial_s", 1.0)),
        backoff_max_s=float(health_raw.get("backoff_max_s", 60.0)),
        heartbeat_interval_s=float(health_raw.get("heartbeat_interval_s", 30.0)),
    )

    return AppConfig(
        mqtt=mqtt,
        mux=mux,
        logging=logging_cfg,
        sensors=sensors,
        fusion=fusion,
        validation=validation,
        health=health,
        use_mock_drivers=bool(raw.get("use_mock_drivers", False)),
    )
