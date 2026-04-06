"""Structured JSON logs on stderr."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log_event(level: str, event: str, **fields: object) -> None:
    record: dict[str, object] = {
        "ts": utc_now(),
        "level": level,
        "event": event,
    }
    record.update({k: v for k, v in fields.items() if v is not None})
    print(json.dumps(record, separators=(",", ":")), file=sys.stderr, flush=True)
