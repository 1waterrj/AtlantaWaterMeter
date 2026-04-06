# Raspberry Pi tracker for Neptune R900 smart water meters
### Works for City of Atlanta and many other municipalities

[See an example](https://docs.google.com/spreadsheets/d/1XC9UFRQpvzUn7gjXML7KuaprB8APLXgE_EjsmUM8MWI/edit?usp=sharing) (Please don't judge me by my water usage)

## Introduction

Unfortunately this is less elegant and more technically verbose than I would like, but it's still the only way I've found to reliably track my water usage. I've been using this to track my water usage for over a year without any problems (although I've just recently switched for Google Spreadsheets for logging)

The goals of this project are:
- Use a Raspberry Pi and a RTL-SDR to track my smart water meter (Read: cheap, less than $50)
- Docker to simplify the installation and setup of RTLAMR
- **Docker Compose** on the Pi (or any Linux host with USB access to the RTL-SDR) to run the container
- Logging via **MQTT / Home Assistant**, optional HTTP (`CURL_API`), or a Google Spreadsheet

## Credit

- @besmasher - Built the excellent [RTLAMR](https://github.com/bemasher/rtlamr) library which actually does all the work of reading the meters.
- Early RTL-SDR-on-Pi writeups (including community Docker examples) informed older iterations of this project

## Requirements

- **Python 3.14** — The container image is based on the official `python:3.14-slim-trixie` image. Application code lives under `meter/` (see `.python-version`).
- Raspberry Pi 3 (Might work on others, only tested on the 3)
- [RTL-SDR](https://www.amazon.com/NooElec-NESDR-Mini-Compatible-Packages/dp/B009U7WZCA)
- [Docker](https://docs.docker.com/engine/install/debian/) and [Docker Compose](https://docs.docker.com/compose/) on the Pi (or another Linux machine next to the meter)

### Technical chops

You'll need to be able to do the following to get this to work:

- Clone a repository with `git` and run `docker compose`
- Flash Raspberry Pi OS if you use a Pi, or install Docker on your Linux host
- Basic editing of a `.env` file

## Installation (Docker Compose on Raspberry Pi)

1. Install **Raspberry Pi OS** (64-bit recommended) or another Linux distribution on your Pi, or use an existing host with Docker.
1. Install **Docker Engine** and the **Docker Compose plugin** (see Docker’s docs for your OS).
1. Plug the **RTL-SDR** into USB.
1. Clone this repository on the Pi and enter the directory.
1. Copy the environment template and edit it: `cp env.example .env` — set at least `MQTT_HOST` / MQTT credentials if you use Home Assistant, and leave `METERID` empty for the first run if you still need to discover your meter ID.
1. Build and start: `docker compose up -d --build`
1. Follow logs: `docker compose logs -f`. With **`METERID` unset**, the container runs in **debug mode** and prints nearby meters; match readings to your physical meter to find your ID. This is the hardest step — there is usually no simple correlation between the ID and what is printed on the meter housing.
1. Add **`METERID=...`** to `.env`, then `docker compose up -d` again.
1. Point outputs at **MQTT** (recommended), **`CURL_API`**, or Google Sheets (below).

USB access for the SDR uses `privileged: true` and `/dev/bus/usb` in `docker-compose.yml`. If your setup needs different device nodes, adjust that file.

### Watchdog (optional)

The main loop touches `updated.log` on each successful read. A background **watchdog** thread detects if that file goes stale (workaround for long-running `rtl_tcp` issues). To run a command when that happens (e.g. reboot the host), set **`WATCHDOG_REBOOT_CMD`** in `.env` to a shell one-liner. If unset, the watchdog only logs structured messages to stderr — no reboot. Many people rely on `restart: unless-stopped`, **Docker health checks**, and periodic `docker compose restart` instead of rebooting the whole Pi.

### Health check

The image defines a **HEALTHCHECK** that fails if `updated.log` is older than **`HEALTHCHECK_MAX_AGE_SEC`** (default **2400** seconds, 40 minutes — above the default 30‑minute watchdog window). Override **`HEALTHCHECK_LOG`** if you change the file path. Compose repeats the same check in `docker-compose.yml`.

## Repository layout

| Path | Role |
|------|------|
| `meter/daemon.py` | Main process: `rtl_tcp` + `rtlamr`, MQTT (**Paho**), optional `curl`, watchdog thread |
| `meter/mqtt_publisher.py` | MQTT client: TLS, LWT + **availability** topic, discovery + readings |
| `meter/payload.py` | **Canonical reading JSON** — schema version, timestamp, `consumption`, `radio` |
| `meter/ha_discovery.py` | Home Assistant MQTT discovery (includes `availability_topic`) |
| `meter/healthcheck.py` | Docker `HEALTHCHECK` helper |
| `meter/config.py` | Environment configuration |
| `Dockerfile` | Python 3.14, **pinned** `rtlamr@v0.9.4`, rtl-sdr, **no** `mosquitto-clients` (MQTT is in-process) |
| `docker-compose.yml` | Build, USB, `.env`, health check |
| `requirements.txt` | `paho-mqtt` |
| `env.example` | Copy to `.env` |

**Logs:** informational and error events are written to **stderr** as **single-line JSON** (`ts`, `level`, `event`, and fields) for easy scraping by Loki or journald.

## MQTT and Home Assistant

When `MQTT_HOST` is set, the app uses **Paho MQTT** with a persistent connection: **Last Will** publishes `offline` to the **availability** topic (default: sibling of the reading topic, e.g. `water_meter/availability` or `home/water_meter/{id}/availability`). On connect it publishes **`online`** (retained). Home Assistant discovery includes `availability_topic` / `payload_available` / `payload_not_available`.

Each successful read publishes a **versioned JSON** reading (see below). Raw rtlamr output is optional on a second topic.

### Topic layout

- **Flat (default):** if you set neither `MQTT_TOPIC` nor `MQTT_TOPIC_PREFIX`, the reading is published to topic `water_meter`.
- **Hierarchical (recommended for multiple devices or clearer ACLs):** set `MQTT_TOPIC_PREFIX` (e.g. `home/water_meter`) and **omit** `MQTT_TOPIC`. The reading goes to `{MQTT_TOPIC_PREFIX}/{METERID}/reading`.
- **Explicit:** set `MQTT_TOPIC` to the full topic string (wins over `MQTT_TOPIC_PREFIX`).

Raw rtlamr JSON on a second topic:

- Set `MQTT_TOPIC_RADIO` to a full topic, **or**
- Set `MQTT_PUBLISH_RADIO=1` together with `MQTT_TOPIC_PREFIX` to publish to `{MQTT_TOPIC_PREFIX}/{METERID}/radio`.

### Environment variables

| Variable | Required | Description |
|----------|----------|-------------|
| `MQTT_HOST` | Yes, to enable MQTT | Broker hostname or IP |
| `MQTT_PORT` | No | Broker port (default `1883`) |
| `MQTT_TOPIC` | No | Full topic for the reading JSON (overrides prefix-based topic) |
| `MQTT_TOPIC_PREFIX` | No | Prefix for `{prefix}/{METERID}/reading` (and optional `.../radio`) |
| `MQTT_USER` | No | Username |
| `MQTT_PASSWORD` | No | Password |
| `MQTT_TLS` | No | Set to `1` to use TLS (`--tls-use-os-certs`; typical with port `8883`) |
| `MQTT_RETAIN` | No | Set to `1` to retain the last message on the broker |
| `MQTT_TOPIC_RADIO` | No | Full topic for raw rtlamr JSON only |
| `MQTT_PUBLISH_RADIO` | No | Set to `1` with `MQTT_TOPIC_PREFIX` to also publish raw JSON to `{prefix}/{METERID}/radio` |
| `MQTT_DISABLE_DISCOVERY` | No | Set to `1` to skip [MQTT discovery](https://www.home-assistant.io/integrations/mqtt/#mqtt-discovery) (manual YAML only) |
| `MQTT_DISCOVERY_PREFIX` | No | Discovery prefix (default `homeassistant`) |
| `MQTT_DEVICE_NAME` | No | Friendly name for the sensor/device (default `Water meter`) |
| `MQTT_SW_VERSION` | No | Reported firmware/software version (default `1.0`) |
| `MQTT_AVAILABILITY_TOPIC` | No | Override the default `{reading_topic}/availability` sibling topic |
| `MQTT_PUBLISH_ON_CHANGE` | No | Set to `1` to publish MQTT only when `consumption` changes (health log still updates every cycle) |
| `MQTT_HEARTBEAT_SEC` | No | With `MQTT_PUBLISH_ON_CHANGE=1`, force a publish at least this often (seconds) even if unchanged |

### Timing and behavior

| Variable | Default | Description |
|----------|---------|-------------|
| `POLL_INTERVAL_SEC` | `60` | Sleep between read cycles after killing `rtl_tcp` |
| `RTL_TCP_STARTUP_SEC` | `10` | Wait after starting `rtl_tcp` before `rtlamr` |
| `WATCHDOG_MINUTES` | `30` | Staleness window for `updated.log` (same semantics as the original shell watchdog) |

### Home Assistant MQTT discovery

When `MQTT_HOST` is set and `MQTT_DISABLE_DISCOVERY` is **not** `1`, the container publishes a **retained** discovery message at startup to:

`{MQTT_DISCOVERY_PREFIX}/sensor/water_meter_{METERID}/config`

(Non-alphanumeric characters in `METERID` are replaced with `_` in the topic `object_id`.)

In Home Assistant, ensure the MQTT integration has **discovery** enabled (it is on by default). The **Water meter** sensor should appear automatically; no manual `configuration.yaml` entry is required for the sensor itself. The entity respects **availability** (online/offline) from MQTT.

### Reading payload (`meter/payload.py`)

Consumers should check `schema_version` when you change fields. Current version is **1**.

| Field | Meaning |
|-------|---------|
| `schema_version` | Integer; bump when you change shape or semantics |
| `timestamp` | UTC time of this reading (`YYYY-MM-DDTHH:MM:SSZ`) |
| `consumption` | Scaled reading (same units as container logs: CCF or cubic meters) |
| `unit` | `CCF`, `Cubic Meters`, etc. |
| `meter_id` | Your `METERID` |
| `radio` | Full rtlamr JSON object (time, offset, message fields, etc.) |

### Home Assistant manual configuration (optional)

If you disabled discovery (`MQTT_DISABLE_DISCOVERY=1`), define the sensor manually:

```yaml
mqtt:
  sensor:
    - name: "Water meter"
      state_topic: "water_meter"
      value_template: "{{ value_json.consumption }}"
      unit_of_measurement: "CCF"
      json_attributes_topic: "water_meter"
      json_attributes_template: "{{ value_json.radio }}"

```

With `MQTT_TOPIC_PREFIX=home/water_meter` and `METERID=12345678`, use `state_topic` / `json_attributes_topic`: `home/water_meter/12345678/reading`. Change `unit_of_measurement` if you use `METRIC`.

## Logging to Google Spreadsheet

I'd love to find a better alternative to this, but at the moment, it's the easiest way to track my water usage.

Quick overview: Google Docs have the option of adding scripts to their spreadsheets, similar to how Visual Basic was integrated into Excel. These scripts can not only modify the spreadsheet, but they can also be called via HTTP. In this case, we deploy a script that allows us to call it from the Raspberry Pi and pass along the current meter reading as a parameter.

Couple of problems needed to be addressed with this script:
- At some point we'll run out of space on the spreadsheet. I solved this by setting a maximum number of rows (5000 right now). After the maximum row is reached, we add a row and at the same time delete the oldest row the top. This keep several months of history for most household users.
- We should ignore updates that are the same meter reading. For my use, it doesn't make just sense to have 50 updates overnight with the same reading. Therefore, the script will only update when the meter reading differs from the previous reading.

Here's the full breakdown:

1. Open my [template spreadsheet](https://docs.google.com/spreadsheets/d/1XC9UFRQpvzUn7gjXML7KuaprB8APLXgE_EjsmUM8MWI/edit?usp=sharing) and make a copy - 'File' > 'Make a copy...'
2. Your new copy will open. Click 'Tools' > 'Script editor'
3. In the script editor page, Change the 'SheetID' to your version of the spreadsheet
    - eg. https://docs.google.com/spreadsheets/d/158hDszrPBudHZkFik2AvQDFTDfzV8mYHq80PyHb4dDo/edit#gid=0 - the SheetId would be '158hDszrPBudHZkFik2AvQDFTDfzV8mYHq80PyHb4dDo'
4. 'File' > 'Save'
5. 'Publish' > 'Deploy as web app...' - Deploy with the following settings
    - Version: 'New'
    - Execute the app as: 'Me'
    - Who has access to the app: 'Anyone, even anonymous'
    - Click 'Deploy'
    - Authoration required prompt will display
    - Click 'Review Permissions'
    - Choose your account and allow access to your Drive
      - There might be some scary messaging here from Google about allowing an unverified script to have access to your account, but the only script that has access is the version you're currently editing.
    - ** Copy the 'Current web app URL:' on the final step after clicking deploy **
6. The URL from the last step is the endpoint for **`CURL_API`**
    - Should look like `https://script.google.com/macros/u/1/s/RandomLookingScriptID/exec`
    - In your `.env` (or `docker-compose` environment), set `CURL_API` to that URL with `?value=` appended
        -  eg. "https://script.google.com/macros/s/RandomLookingScriptID/exec?value="
    - To test it you can send some data with 'curl: `curl -L https://script.google.com/macros/u/1/s/RandomLookingScriptID/exec?value=10`

## Development and CI

- **Tests:** `pip install -r requirements-dev.txt` then `pytest`.
- **Image build:** `docker build -t atlanta-water-meter .`
- **GitHub Actions** (`.github/workflows/ci.yml`) runs **pytest** on Python 3.12 and **`docker build`** on every push/PR.

