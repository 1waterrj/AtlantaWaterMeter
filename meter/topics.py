"""MQTT topic resolution (matches former shell logic)."""

from __future__ import annotations


def resolve_reading_topic(
    *,
    meter_id: str,
    mqtt_topic: str | None,
    mqtt_topic_prefix: str | None,
) -> str:
    if mqtt_topic:
        return mqtt_topic
    if mqtt_topic_prefix:
        return f"{mqtt_topic_prefix}/{meter_id}/reading"
    return "water_meter"


def resolve_radio_topic(
    *,
    meter_id: str,
    mqtt_topic_radio: str | None,
    mqtt_publish_radio: bool,
    mqtt_topic_prefix: str | None,
) -> str | None:
    if mqtt_topic_radio:
        return mqtt_topic_radio
    if mqtt_publish_radio and mqtt_topic_prefix:
        return f"{mqtt_topic_prefix}/{meter_id}/radio"
    return None


def resolve_availability_topic(state_topic: str) -> str:
    """Sibling topic used for HA availability + MQTT LWT."""
    if "/" in state_topic:
        base = state_topic.rsplit("/", 1)[0]
        return f"{base}/availability"
    return f"{state_topic}/availability"
