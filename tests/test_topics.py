from meter.topics import (
    resolve_availability_topic,
    resolve_radio_topic,
    resolve_reading_topic,
)


def test_resolve_reading_flat():
    assert resolve_reading_topic(meter_id="1", mqtt_topic=None, mqtt_topic_prefix=None) == "water_meter"


def test_resolve_reading_prefix():
    assert (
        resolve_reading_topic(meter_id="99", mqtt_topic=None, mqtt_topic_prefix="home/wm")
        == "home/wm/99/reading"
    )


def test_resolve_reading_explicit():
    assert (
        resolve_reading_topic(meter_id="99", mqtt_topic="custom/t", mqtt_topic_prefix="ignored")
        == "custom/t"
    )


def test_resolve_radio():
    assert resolve_radio_topic(
        meter_id="1",
        mqtt_topic_radio=None,
        mqtt_publish_radio=False,
        mqtt_topic_prefix=None,
    ) is None
    assert (
        resolve_radio_topic(
            meter_id="1",
            mqtt_topic_radio="r/t",
            mqtt_publish_radio=False,
            mqtt_topic_prefix="p",
        )
        == "r/t"
    )
    assert (
        resolve_radio_topic(
            meter_id="1",
            mqtt_topic_radio=None,
            mqtt_publish_radio=True,
            mqtt_topic_prefix="p",
        )
        == "p/1/radio"
    )


def test_availability():
    assert resolve_availability_topic("water_meter") == "water_meter/availability"
    assert resolve_availability_topic("home/wm/1/reading") == "home/wm/1/availability"
