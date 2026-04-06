"""Main process: rtl_tcp + rtlamr, MQTT (Paho), optional HTTP, watchdog thread."""

from __future__ import annotations

import atexit
import json
import os
import signal
import subprocess
import threading
import time
from pathlib import Path

from meter.config import Config
from meter.logutil import log_event
from meter.mqtt_publisher import MqttPublisher
from meter.payload import build_reading
from meter.topics import resolve_radio_topic, resolve_reading_topic

UPDATED_LOG = Path("updated.log")


def _run_watchdog(cfg: Config) -> None:
    timeout_sec = cfg.watchdog_minutes * 60
    time.sleep(timeout_sec)
    while True:
        if not UPDATED_LOG.exists():
            break
        age_sec = time.time() - UPDATED_LOG.stat().st_mtime
        if age_sec >= timeout_sec:
            break
        time.sleep(60)
    log_event("error", "watchdog_stale", path=str(UPDATED_LOG))
    cmd = os.environ.get("WATCHDOG_REBOOT_CMD")
    if cmd:
        log_event("warning", "watchdog_running_reboot_cmd")
        os.system(cmd)
    else:
        log_event(
            "warning",
            "watchdog_no_reboot_cmd",
            hint="set WATCHDOG_REBOOT_CMD or rely on compose restart",
        )


def _start_rtl_tcp() -> subprocess.Popen[bytes]:
    return subprocess.Popen(
        ["rtl_tcp"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _run_rtlamr(meter_id: str) -> str:
    r = subprocess.run(
        [
            "rtlamr",
            "-msgtype=r900",
            f"-filterid={meter_id}",
            "-single=true",
            "-format=json",
        ],
        capture_output=True,
        text=True,
        timeout=300,
        check=False,
    )
    if r.returncode != 0:
        err = (r.stderr or r.stdout or "").strip()
        raise RuntimeError(f"rtlamr failed ({r.returncode}): {err}")
    return r.stdout.strip()


def _debug_mode(cfg: Config) -> None:
    log_event("info", "debug_mode_no_meter_id")
    p = _start_rtl_tcp()
    try:
        time.sleep(cfg.rtl_tcp_startup_sec)
        subprocess.run(["rtlamr", "-msgtype=r900"], check=False)
    finally:
        p.terminate()
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()


def main() -> None:
    cfg = Config.from_environ()
    publisher: MqttPublisher | None = None

    if not cfg.meter_id:
        _debug_mode(cfg)
        return

    reading_topic = resolve_reading_topic(
        meter_id=cfg.meter_id,
        mqtt_topic=cfg.mqtt_topic,
        mqtt_topic_prefix=cfg.mqtt_topic_prefix,
    )
    radio_topic = resolve_radio_topic(
        meter_id=cfg.meter_id,
        mqtt_topic_radio=cfg.mqtt_topic_radio,
        mqtt_publish_radio=cfg.mqtt_publish_radio,
        mqtt_topic_prefix=cfg.mqtt_topic_prefix,
    )

    if cfg.mqtt_host:
        publisher = MqttPublisher(
            cfg,
            reading_topic=reading_topic,
            radio_topic=radio_topic,
            meter_id=cfg.meter_id,
            unit_label=cfg.unit_label,
        )
        publisher.connect()
        publisher.publish_discovery()

        def _graceful() -> None:
            if publisher:
                publisher.disconnect_graceful()

        atexit.register(_graceful)

        def _sig(_s: int, _f: object) -> None:
            _graceful()
            raise SystemExit(0)

        signal.signal(signal.SIGTERM, _sig)
        signal.signal(signal.SIGINT, _sig)

    t = threading.Thread(target=_run_watchdog, args=(cfg,), daemon=True)
    t.start()

    last_pub_consumption: float | None = None
    last_mqtt_mono: float | None = None

    while True:
        rtl_tcp = _start_rtl_tcp()
        try:
            time.sleep(cfg.rtl_tcp_startup_sec)
            raw = _run_rtlamr(cfg.meter_id)
            rtlamr_obj = json.loads(raw)
            reading = build_reading(
                rtlamr_obj,
                unit_divisor=cfg.unit_divisor,
                unit=cfg.unit_label,
                meter_id=cfg.meter_id,
            )
            consumption = float(reading["consumption"])
            log_event(
                "info",
                "reading",
                consumption=consumption,
                unit=cfg.unit_label,
                meter_id=cfg.meter_id,
            )

            should_mqtt = True
            if publisher and cfg.mqtt_publish_on_change:
                should_mqtt = False
                if last_pub_consumption is None or consumption != last_pub_consumption:
                    should_mqtt = True
                elif cfg.mqtt_heartbeat_sec is not None and last_mqtt_mono is not None:
                    if time.monotonic() - last_mqtt_mono >= cfg.mqtt_heartbeat_sec:
                        should_mqtt = True
                        log_event("info", "mqtt_heartbeat_publish")

            if publisher and should_mqtt:
                publisher.publish_reading(reading, raw)
                last_pub_consumption = consumption
                last_mqtt_mono = time.monotonic()

            if cfg.curl_api:
                subprocess.run(
                    ["curl", "-fSL", f"{cfg.curl_api}{consumption}"],
                    check=False,
                    timeout=120,
                )

            UPDATED_LOG.touch()
        except (json.JSONDecodeError, KeyError, RuntimeError) as e:
            log_event("error", "read_cycle_failed", error=str(e))
        finally:
            rtl_tcp.terminate()
            try:
                rtl_tcp.wait(timeout=5)
            except subprocess.TimeoutExpired:
                rtl_tcp.kill()

        time.sleep(cfg.poll_interval_sec)


if __name__ == "__main__":
    main()
