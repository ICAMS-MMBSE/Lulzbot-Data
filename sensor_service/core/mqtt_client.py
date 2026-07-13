"""MQTT client wrapper (paho-mqtt v2 API).

Owns topic construction, the JSON envelope hookup, per-topic sequence
numbers, subscriptions, and the Last Will & Testament on
``<base>/status/system`` for offline detection.
"""
from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable, Dict, List, Tuple

import paho.mqtt.client as mqtt

from sensor_service.core.config import MqttConfig
from sensor_service.core.payload import SequenceCounter, utc_now_iso

log = logging.getLogger("mqtt")


def build_topic(base: str, *parts: str) -> str:
    """Join topic segments, normalizing stray slashes. build_topic('Lulzbot',
    'position/z') -> 'Lulzbot/position/z'."""
    segs = [str(base).strip("/")]
    segs += [str(p).strip("/") for p in parts if p is not None]
    return "/".join(s for s in segs if s)


class MqttClient:
    def __init__(self, cfg: MqttConfig):
        self.cfg = cfg
        self.seq = SequenceCounter()
        self.system_topic = build_topic(cfg.base_topic, "status", "system")
        self._subs: List[Tuple[str, Callable]] = []
        self._connected = threading.Event()

        c = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=cfg.client_id,
            protocol=mqtt.MQTTv311,
        )
        if cfg.username:
            c.username_pw_set(cfg.username, cfg.password)
        c.will_set(
            self.system_topic,
            json.dumps({"online": False, "reason": "unexpected-disconnect"}),
            qos=cfg.qos_status,
            retain=cfg.retain_status,
        )
        c.on_connect = self._on_connect
        c.on_disconnect = self._on_disconnect
        self._client = c

    # -- lifecycle ---------------------------------------------------------
    def start(self) -> None:
        self._client.connect_async(self.cfg.host, self.cfg.port, self.cfg.keepalive)
        self._client.loop_start()

    def stop(self) -> None:
        try:
            info = self._client.publish(
                self.system_topic,
                json.dumps({"online": False, "reason": "shutdown", "ts": utc_now_iso()}),
                qos=self.cfg.qos_status,
                retain=self.cfg.retain_status,
            )
            info.wait_for_publish(timeout=3)
        except Exception:  # noqa: BLE001
            log.warning("Could not publish graceful offline message")
        self._client.loop_stop()
        self._client.disconnect()

    def wait_connected(self, timeout: float) -> bool:
        return self._connected.wait(timeout)

    # -- callbacks ---------------------------------------------------------
    def _on_connect(self, client, userdata, flags, reason_code, properties) -> None:
        if reason_code.is_failure:
            log.error("MQTT connect failed: %s", reason_code)
            return
        log.info("Connected to broker %s:%s", self.cfg.host, self.cfg.port)
        self._connected.set()
        client.publish(
            self.system_topic,
            json.dumps({"online": True, "ts": utc_now_iso()}),
            qos=self.cfg.qos_status,
            retain=self.cfg.retain_status,
        )
        for topic, _cb in self._subs:
            client.subscribe(topic, qos=1)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties) -> None:
        self._connected.clear()
        log.warning("Disconnected from broker (%s); paho will auto-reconnect", reason_code)

    # -- publishing --------------------------------------------------------
    def publish_json(self, topic: str, payload: Dict[str, Any], qos: int, retain: bool) -> None:
        self._client.publish(topic, json.dumps(payload, default=float), qos=qos, retain=retain)

    def telemetry(self, topic_suffix: str, payload: Dict[str, Any]) -> None:
        topic = build_topic(self.cfg.base_topic, topic_suffix)
        self.publish_json(topic, payload, self.cfg.qos_telemetry, self.cfg.retain_telemetry)

    def status(self, sensor_name: str, payload: Dict[str, Any]) -> None:
        topic = build_topic(self.cfg.base_topic, "status", sensor_name)
        self.publish_json(topic, payload, self.cfg.qos_status, self.cfg.retain_status)

    # -- subscribing -------------------------------------------------------
    def subscribe(self, topic_filter: str, callback: Callable[[str, bytes], None]) -> None:
        """Register ``callback(topic, raw_payload_bytes)`` for a topic filter."""

        def _wrapped(client, userdata, message) -> None:
            try:
                callback(message.topic, message.payload)
            except Exception:  # noqa: BLE001 - subscriber bug must not kill the loop
                log.exception("Subscriber callback failed for %s", message.topic)

        self._subs.append((topic_filter, _wrapped))
        self._client.message_callback_add(topic_filter, _wrapped)
        if self._connected.is_set():
            self._client.subscribe(topic_filter, qos=1)
