"""Environment-driven configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _truthy(name: str, default: bool = False) -> bool:
    v = os.environ.get(name)
    if v is None:
        return default
    return v.strip().lower() in ("1", "true", "yes", "on")


def _float(name: str, default: float) -> float:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return float(v)


def _int(name: str, default: int) -> int:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return default
    return int(v)


def _opt_float(name: str) -> float | None:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return None
    return float(v)


def _opt_int(name: str) -> int | None:
    v = os.environ.get(name)
    if v is None or v.strip() == "":
        return None
    return int(v)


@dataclass(frozen=True)
class Config:
    meter_id: str | None
    metric: bool
    poll_interval_sec: float
    rtl_tcp_startup_sec: float
    watchdog_minutes: int
    curl_api: str | None
    # MQTT
    mqtt_host: str | None
    mqtt_port: int
    mqtt_topic: str | None
    mqtt_topic_prefix: str | None
    mqtt_user: str | None
    mqtt_password: str | None
    mqtt_tls: bool
    mqtt_retain_readings: bool
    mqtt_topic_radio: str | None
    mqtt_publish_radio: bool
    mqtt_disable_discovery: bool
    mqtt_discovery_prefix: str
    mqtt_device_name: str
    mqtt_sw_version: str
    mqtt_publish_on_change: bool
    mqtt_heartbeat_sec: float | None
    mqtt_availability_topic: str | None
    # healthcheck helper
    healthcheck_max_age_sec: int

    @property
    def unit_divisor(self) -> float:
        return 1000.0 if self.metric else 10000.0

    @property
    def unit_label(self) -> str:
        return "Cubic Meters" if self.metric else "CCF"

    @classmethod
    def from_environ(cls) -> Config:
        mid = os.environ.get("METERID")
        meter_id = mid.strip() if mid and mid.strip() else None
        return cls(
            meter_id=meter_id,
            metric=_truthy("METRIC"),
            poll_interval_sec=_float("POLL_INTERVAL_SEC", 60.0),
            rtl_tcp_startup_sec=_float("RTL_TCP_STARTUP_SEC", 10.0),
            watchdog_minutes=_int("WATCHDOG_MINUTES", 30),
            curl_api=os.environ.get("CURL_API") or None,
            mqtt_host=os.environ.get("MQTT_HOST") or None,
            mqtt_port=_int("MQTT_PORT", 1883),
            mqtt_topic=os.environ.get("MQTT_TOPIC") or None,
            mqtt_topic_prefix=os.environ.get("MQTT_TOPIC_PREFIX") or None,
            mqtt_user=os.environ.get("MQTT_USER") or None,
            mqtt_password=os.environ.get("MQTT_PASSWORD") or None,
            mqtt_tls=_truthy("MQTT_TLS"),
            mqtt_retain_readings=_truthy("MQTT_RETAIN"),
            mqtt_topic_radio=os.environ.get("MQTT_TOPIC_RADIO") or None,
            mqtt_publish_radio=_truthy("MQTT_PUBLISH_RADIO"),
            mqtt_disable_discovery=_truthy("MQTT_DISABLE_DISCOVERY"),
            mqtt_discovery_prefix=os.environ.get("MQTT_DISCOVERY_PREFIX", "homeassistant"),
            mqtt_device_name=os.environ.get("MQTT_DEVICE_NAME", "Water meter"),
            mqtt_sw_version=os.environ.get("MQTT_SW_VERSION", "1.0"),
            mqtt_publish_on_change=_truthy("MQTT_PUBLISH_ON_CHANGE"),
            mqtt_heartbeat_sec=_opt_float("MQTT_HEARTBEAT_SEC"),
            mqtt_availability_topic=os.environ.get("MQTT_AVAILABILITY_TOPIC") or None,
            healthcheck_max_age_sec=_int("HEALTHCHECK_MAX_AGE_SEC", 2400),
        )
