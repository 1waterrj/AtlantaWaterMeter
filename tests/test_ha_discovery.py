from meter import ha_discovery


def test_discovery_has_availability():
    cfg = ha_discovery.build_discovery_config(
        state_topic="water_meter",
        unit="CCF",
        meter_id="123",
        device_name="WM",
        sw_version="1",
        availability_topic="water_meter/availability",
    )
    assert cfg["availability_topic"] == "water_meter/availability"
    assert cfg["payload_available"] == "online"
    assert cfg["payload_not_available"] == "offline"
    assert "state_topic" in cfg


def test_discovery_topic_slug():
    assert "water_meter_12_3" in ha_discovery.discovery_topic("12.3", "homeassistant")
