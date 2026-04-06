"""Paho MQTT client: discovery, LWT, TLS, retained readings."""

from __future__ import annotations

import json
import ssl
import threading
from typing import TYPE_CHECKING

import paho.mqtt.client as mqtt

from meter import ha_discovery
from meter.logutil import log_event
from meter.topics import resolve_availability_topic

if TYPE_CHECKING:
    from meter.config import Config


class MqttPublisher:
    def __init__(
        self,
        cfg: Config,
        *,
        reading_topic: str,
        radio_topic: str | None,
        meter_id: str,
        unit_label: str,
    ) -> None:
        self._cfg = cfg
        self._reading_topic = reading_topic
        self._radio_topic = radio_topic
        self._meter_id = meter_id
        self._unit_label = unit_label
        self._availability_topic = (
            cfg.mqtt_availability_topic or resolve_availability_topic(reading_topic)
        )
        cid = f"atlanta-water-meter-{meter_id}"[:64]
        self._connected_evt = threading.Event()
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=cid,
            protocol=mqtt.MQTTv311,
        )
        if cfg.mqtt_user is not None:
            self._client.username_pw_set(cfg.mqtt_user, cfg.mqtt_password or "")
        if cfg.mqtt_tls:
            ctx = ssl.create_default_context()
            self._client.tls_set_context(ctx)
        self._client.will_set(
            self._availability_topic,
            payload="offline",
            qos=1,
            retain=True,
        )

    @property
    def availability_topic(self) -> str:
        return self._availability_topic

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: object,
        flags: object,
        reason_code: object,
        properties: object | None,
    ) -> None:
        if getattr(reason_code, "is_failure", False):
            log_event("error", "mqtt_connect_failed", reason=str(reason_code))
            return
        log_event("info", "mqtt_connected", host=self._cfg.mqtt_host)
        client.publish(self._availability_topic, "online", qos=1, retain=True)
        self._connected_evt.set()

    def connect(self) -> None:
        self._client.on_connect = self._on_connect
        host = self._cfg.mqtt_host or ""
        self._client.connect(host, self._cfg.mqtt_port, keepalive=60)
        self._client.loop_start()
        if not self._connected_evt.wait(20.0):
            raise RuntimeError("MQTT connect timeout")

    def publish_discovery(self) -> None:
        if self._cfg.mqtt_disable_discovery:
            return
        topic = ha_discovery.discovery_topic(self._meter_id, self._cfg.mqtt_discovery_prefix)
        cfg = ha_discovery.build_discovery_config(
            state_topic=self._reading_topic,
            unit=self._unit_label,
            meter_id=self._meter_id,
            device_name=self._cfg.mqtt_device_name,
            sw_version=self._cfg.mqtt_sw_version,
            availability_topic=self._availability_topic,
        )
        payload = json.dumps(cfg, separators=(",", ":"))
        self._client.publish(topic, payload, qos=1, retain=True)
        log_event("info", "mqtt_discovery_published", topic=topic)

    def publish_reading(self, payload_obj: dict, radio_raw: str) -> None:
        body = json.dumps(payload_obj, separators=(",", ":"))
        retain = self._cfg.mqtt_retain_readings
        self._client.publish(self._reading_topic, body, qos=0, retain=retain)
        if self._radio_topic:
            self._client.publish(self._radio_topic, radio_raw, qos=0, retain=retain)

    def disconnect_graceful(self) -> None:
        try:
            self._client.publish(self._availability_topic, "offline", qos=1, retain=True)
        except Exception:
            pass
        self._client.loop_stop()
        self._client.disconnect()

    def close(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()
