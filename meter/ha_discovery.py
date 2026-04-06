"""Home Assistant MQTT discovery config for the water meter sensor."""

from __future__ import annotations

import json
import os
import re
import sys

from meter.topics import resolve_availability_topic


def object_id(meter_id: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9_-]", "_", meter_id)
    return f"water_meter_{s}" if s else "water_meter"


def unique_id(meter_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9_]", "_", f"atlanta_wm_{meter_id}")


def discovery_topic(meter_id: str, prefix: str) -> str:
    return f"{prefix}/sensor/{object_id(meter_id)}/config"


def build_discovery_config(
    *,
    state_topic: str,
    unit: str,
    meter_id: str,
    device_name: str,
    sw_version: str,
    availability_topic: str | None = None,
) -> dict:
    uid = unique_id(meter_id)
    cfg: dict = {
        "name": device_name,
        "unique_id": uid,
        "state_topic": state_topic,
        "value_template": "{{ value_json.consumption }}",
        "unit_of_measurement": unit,
        "json_attributes_topic": state_topic,
        "json_attributes_template": "{{ value_json.radio }}",
        "state_class": "total_increasing",
        "device": {
            "identifiers": [uid],
            "name": device_name,
            "manufacturer": "AtlantaWaterMeter",
            "model": "Neptune R900 (RTL-SDR)",
            "sw_version": sw_version,
        },
    }
    if availability_topic:
        cfg["availability_topic"] = availability_topic
        cfg["payload_available"] = "online"
        cfg["payload_not_available"] = "offline"
    return cfg


def main() -> None:
    prefix = os.environ.get("MQTT_DISCOVERY_PREFIX", "homeassistant")
    state_topic = os.environ["MQTT_READING_TOPIC"]
    unit = os.environ.get("UNIT", "CCF")
    meter_id = os.environ["METERID"]
    device_name = os.environ.get("MQTT_DEVICE_NAME", "Water meter")
    sw_version = os.environ.get("MQTT_SW_VERSION", "1.0")
    avail = os.environ.get("MQTT_AVAILABILITY_TOPIC") or resolve_availability_topic(state_topic)
    topic = discovery_topic(meter_id, prefix)
    cfg = build_discovery_config(
        state_topic=state_topic,
        unit=unit,
        meter_id=meter_id,
        device_name=device_name,
        sw_version=sw_version,
        availability_topic=avail,
    )
    sys.stdout.write(topic + "\n")
    json.dump(cfg, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
