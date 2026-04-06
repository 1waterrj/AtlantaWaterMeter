import json

from meter.payload import READING_SCHEMA_VERSION, build_reading


def test_build_reading_ccf():
    rtl = {"Message": {"Consumption": 10000}, "Time": "t"}
    out = build_reading(rtl, unit_divisor=10000.0, unit="CCF", meter_id="m1")
    assert out["schema_version"] == READING_SCHEMA_VERSION
    assert out["consumption"] == 1.0
    assert out["unit"] == "CCF"
    assert out["meter_id"] == "m1"
    assert out["radio"] == rtl
    assert "timestamp" in out


def test_build_reading_metric():
    rtl = {"Message": {"Consumption": 5000}}
    out = build_reading(rtl, unit_divisor=1000.0, unit="Cubic Meters", meter_id="x")
    assert out["consumption"] == 5.0
