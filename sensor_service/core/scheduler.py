"""Acquisition scheduling.

One worker thread per enabled sensor, paced by ``time.monotonic`` so slow
sensors never block fast ones -- but every I2C transaction happens while
holding the shared mux ``bus_lock``, so reads across mux channels are
strictly serialized (no channel races). MQTT publishing happens outside
the lock.

Failure isolation: a sensor that fails to initialize or read is logged,
reported on ``<base>/status/<name>``, and retried with exponential
backoff. Other sensors, and the printer, are unaffected.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Callable, Iterable, List, Optional

from sensor_service.core.config import HealthConfig
from sensor_service.core.mqtt_client import MqttClient
from sensor_service.core.payload import build_payload
from sensor_service.drivers.base import Sensor

log = logging.getLogger("scheduler")

ReadingHook = Callable[[Sensor, dict, float], None]  # (sensor, values, unix_ts)


class HealthState:
    """Per-sensor health bookkeeping + status topic publishing."""

    def __init__(self, sensor: Sensor, mqtt: MqttClient, cfg: HealthConfig):
        self.sensor = sensor
        self.mqtt = mqtt
        self.cfg = cfg
        self.status = "init"
        self.consecutive_failures = 0
        self.last_error: Optional[str] = None
        self._last_publish = 0.0

    def backoff(self) -> float:
        n = max(self.consecutive_failures - 1, 0)
        return min(self.cfg.backoff_initial_s * (2 ** n), self.cfg.backoff_max_s)

    def record_success(self) -> None:
        transition = self.status != "ok"
        self.status = "ok"
        self.consecutive_failures = 0
        self.last_error = None
        if transition:
            self.publish()

    def record_failure(self, exc: Exception, phase: str) -> None:
        self.consecutive_failures += 1
        self.last_error = f"{phase}: {type(exc).__name__}: {exc}"
        new_status = "failed" if self.consecutive_failures >= self.cfg.reinit_after_failures else "degraded"
        transition = new_status != self.status
        self.status = new_status
        log.warning("Sensor %s %s (failure #%d): %s",
                    self.sensor.name, new_status, self.consecutive_failures, self.last_error)
        if transition:
            self.publish()

    def heartbeat(self) -> None:
        if time.monotonic() - self._last_publish >= self.cfg.heartbeat_interval_s:
            self.publish()

    def publish(self) -> None:
        self._last_publish = time.monotonic()
        payload = build_payload(
            sensor_id=self.sensor.name,
            role="status",
            values={
                "status": self.status,
                "consecutive_failures": self.consecutive_failures,
                "last_error": self.last_error,
            },
            units={},
            seq=self.mqtt.seq.next(f"status/{self.sensor.name}"),
            quality="ok" if self.status == "ok" else "bad",
        )
        self.mqtt.status(self.sensor.name, payload)


class SensorWorker(threading.Thread):
    def __init__(
        self,
        sensor: Sensor,
        bus_lock: threading.RLock,
        mqtt: MqttClient,
        health_cfg: HealthConfig,
        stop_event: threading.Event,
        on_reading: Optional[ReadingHook] = None,
    ):
        super().__init__(name=f"sensor-{sensor.name}", daemon=True)
        self.sensor = sensor
        self.bus_lock = bus_lock
        self.mqtt = mqtt
        self.stop_event = stop_event
        self.on_reading = on_reading
        self.health = HealthState(sensor, mqtt, health_cfg)
        self.period = 1.0 / sensor.sample_rate_hz

    # -- init with retry ----------------------------------------------------
    def _initialize(self) -> bool:
        """Try to init until success or shutdown. Never raises."""
        while not self.stop_event.is_set():
            try:
                with self.bus_lock:
                    self.sensor.initialize()
                log.info("Sensor %s initialized (channel %d, addr 0x%02x)",
                         self.sensor.name, self.sensor.config.mux_channel,
                         self.sensor.config.address)
                self.health.record_success()
                return True
            except Exception as exc:  # noqa: BLE001
                self.health.record_failure(exc, "initialize")
                self.stop_event.wait(self.health.backoff())
        return False

    def run(self) -> None:
        if not self._initialize():
            return
        next_due = time.monotonic()
        while not self.stop_event.is_set():
            now = time.monotonic()
            if now < next_due:
                self.stop_event.wait(min(next_due - now, 0.5))
                continue
            # Catch up without bursting if we fell behind.
            next_due = max(next_due + self.period, now - self.period)
            try:
                with self.bus_lock:
                    values = self.sensor.read()
            except Exception as exc:  # noqa: BLE001
                self.health.record_failure(exc, "read")
                if self.health.consecutive_failures >= self.health.cfg.reinit_after_failures:
                    self.stop_event.wait(self.health.backoff())
                    try:
                        with self.bus_lock:
                            self.sensor.close()
                    except Exception:  # noqa: BLE001
                        pass
                    self._initialize()
                    next_due = time.monotonic()
                continue

            ts_unix = time.time()
            payload = build_payload(
                sensor_id=self.sensor.name,
                role=self.sensor.role,
                values=values,
                units=self.sensor.units,
                seq=self.mqtt.seq.next(self.sensor.config.topic_suffix),
            )
            self.mqtt.telemetry(self.sensor.config.topic_suffix, payload)
            self.health.record_success()
            self.health.heartbeat()
            if self.on_reading is not None:
                try:
                    self.on_reading(self.sensor, values, ts_unix)
                except Exception:  # noqa: BLE001
                    log.exception("on_reading hook failed for %s", self.sensor.name)


class Scheduler:
    def __init__(
        self,
        sensors: Iterable[Sensor],
        bus_lock: threading.RLock,
        mqtt: MqttClient,
        health_cfg: HealthConfig,
        on_reading: Optional[ReadingHook] = None,
    ):
        self.stop_event = threading.Event()
        self.workers: List[SensorWorker] = [
            SensorWorker(s, bus_lock, mqtt, health_cfg, self.stop_event, on_reading)
            for s in sensors
        ]

    def start(self) -> None:
        for w in self.workers:
            w.start()

    def stop(self, timeout: float = 5.0) -> None:
        self.stop_event.set()
        for w in self.workers:
            w.join(timeout)
