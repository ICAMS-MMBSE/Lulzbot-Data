"""Service entrypoint.

    python -m sensor_service --config config/config.yaml          # run
    python -m sensor_service --config ... --probe                 # scan mux vs config
    python -m sensor_service --config ... --validate-config       # parse + exit
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading

from sensor_service.core.config import AppConfig, ConfigError, load_config
from sensor_service.core.logging_setup import setup_logging
from sensor_service.core.mqtt_client import MqttClient
from sensor_service.core.mux import I2CMux, MockMux, MuxError, NUM_CHANNELS
from sensor_service.core.scheduler import Scheduler
from sensor_service.fusion.position import PositionFuser
from sensor_service.validation.octoprint_compare import OctoPrintComparator
import sensor_service.drivers  # noqa: F401 - registers all drivers
from sensor_service.drivers.registry import resolve

log = logging.getLogger("main")


def build_mux(cfg: AppConfig):
    if cfg.use_mock_drivers:
        scan_map = {s.mux_channel: [s.address] for s in cfg.sensors if s.enabled}
        return MockMux(cfg.mux, scan_map=scan_map)
    return I2CMux(cfg.mux)


def build_sensors(cfg: AppConfig, mux):
    """Instantiate drivers from config. Instantiation errors are isolated."""
    sensors = []
    for sc in cfg.sensors:
        if not sc.enabled:
            log.info("Sensor %s disabled in config; skipping", sc.name)
            continue
        try:
            cls = resolve(sc.driver, use_mock=cfg.use_mock_drivers)
            sensors.append(cls(mux.channel(sc.mux_channel), sc))
        except Exception:  # noqa: BLE001
            log.exception("Could not construct driver for sensor %s; skipping", sc.name)
    return sensors


def cmd_probe(cfg: AppConfig) -> int:
    """Scan all mux channels; report found vs configured."""
    mux = build_mux(cfg)
    expected = {s.mux_channel: s for s in cfg.sensors if s.enabled}
    print(f"Mux @ 0x{cfg.mux.address:02x}"
          f"{' (MOCK: simulated scan)' if cfg.use_mock_drivers else ''}")
    print(f"{'ch':>2}  {'found':<20} {'expected':<28} result")
    ok = True
    for n in range(NUM_CHANNELS):
        found = mux.scan_channel(n)
        found_s = ", ".join(f"0x{a:02x}" for a in found) or "-"
        exp = expected.get(n)
        if exp is None:
            exp_s, result = "-", ("UNEXPECTED" if found else "ok (empty)")
            ok = ok and not found
        else:
            exp_s = f"{exp.name} @ 0x{exp.address:02x}"
            if exp.address in found:
                result = "OK"
            else:
                result, ok = "MISSING", False
        print(f"{n:>2}  {found_s:<20} {exp_s:<28} {result}")
    print("PROBE PASS" if ok else "PROBE FAIL")
    return 0 if ok else 1


def cmd_run(cfg: AppConfig) -> int:
    try:
        mux = build_mux(cfg)
    except MuxError as exc:
        log.error("%s", exc)
        return 1
    sensors = build_sensors(cfg, mux)
    if not sensors:
        log.error("No sensors could be constructed; check config/drivers")
        return 1

    mqtt = MqttClient(cfg.mqtt)
    stop_event = threading.Event()

    fuser = None
    if cfg.fusion.enabled:
        fuser = PositionFuser(cfg.fusion, mqtt, stop_event)

    comparator = None
    if cfg.validation.enabled:
        comparator = OctoPrintComparator(cfg.validation, mqtt)
        comparator.start()  # subscriptions registered; effective on connect

    scheduler = Scheduler(
        sensors, mux.bus_lock, mqtt, cfg.health,
        on_reading=fuser.ingest if fuser else None,
    )

    def _shutdown(signum, frame):  # noqa: ARG001
        log.info("Signal %s received; shutting down", signum)
        stop_event.set()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    mqtt.start()
    if not mqtt.wait_connected(10):
        log.warning("Broker not reachable yet; continuing (paho retries in background)")
    scheduler.start()
    if fuser:
        fuser.start()
    log.info("Service running with %d sensor(s): %s",
             len(sensors), ", ".join(s.name for s in sensors))

    stop_event.wait()

    scheduler.stop()
    scheduler.stop_event.set()
    if comparator:
        comparator.stop()
    mqtt.stop()
    log.info("Shutdown complete")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="sensor_service",
                                     description="Lulzbot multi-sensor MQTT service")
    parser.add_argument("--config", "-c", default="config/config.yaml",
                        help="Path to YAML config")
    parser.add_argument("--probe", action="store_true",
                        help="Scan all mux channels, compare to config, exit")
    parser.add_argument("--validate-config", action="store_true",
                        help="Parse and validate config, then exit")
    args = parser.parse_args(argv)

    try:
        cfg = load_config(args.config)
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2
    setup_logging(cfg.logging)

    if args.validate_config:
        n = sum(1 for s in cfg.sensors if s.enabled)
        print(f"Config OK: {len(cfg.sensors)} sensor(s) defined, {n} enabled, "
              f"broker {cfg.mqtt.host}:{cfg.mqtt.port}, base topic {cfg.mqtt.base_topic!r}")
        return 0
    if args.probe:
        try:
            return cmd_probe(cfg)
        except MuxError as exc:
            print(f"Probe failed: {exc}", file=sys.stderr)
            return 1
    return cmd_run(cfg)


if __name__ == "__main__":
    sys.exit(main())
