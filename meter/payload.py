"""Canonical JSON shape for MQTT and downstream consumers (Home Assistant, etc.)."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone

# Bump when adding/removing/renaming top-level keys (consumers may branch on this).
READING_SCHEMA_VERSION = 1


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_reading(
    rtlamr: dict,
    *,
    unit_divisor: float,
    unit: str,
    meter_id: str,
) -> dict:
    """Merge rtlamr output with scaled consumption and metadata."""
    consumption = float(rtlamr["Message"]["Consumption"]) / unit_divisor
    return {
        "schema_version": READING_SCHEMA_VERSION,
        "timestamp": utc_timestamp(),
        "meter_id": meter_id,
        "unit": unit,
        "consumption": consumption,
        "radio": rtlamr,
    }


def main() -> None:
    unit_divisor = float(os.environ["UNIT_DIVISOR"])
    unit = os.environ.get("UNIT", "CCF")
    meter_id = os.environ.get("METERID", "")
    obj = json.load(sys.stdin)
    out = build_reading(obj, unit_divisor=unit_divisor, unit=unit, meter_id=meter_id)
    json.dump(out, sys.stdout, separators=(",", ":"))


if __name__ == "__main__":
    main()
