# Raspberry Pi tracker for Neptune R900 smart water meters
### Works for City of Atlanta and many other municipalities

[See an example](https://docs.google.com/spreadsheets/d/1XC9UFRQpvzUn7gjXML7KuaprB8APLXgE_EjsmUM8MWI/edit?usp=sharing) (Please don't judge me by my water usage)

## Introduction

Unfortunately this is less elegant and more technically verbose than I would like, but it's still the only way I've found to reliably track my water usage. I've been using this to track my water usage for over a year without any problems (although I've just recently switched for Google Spreadsheets for logging)

The goals of this project are:
- Use a Raspberry Pi and a RTL-SDR to track my smart water meter (Read: cheap, less than $50)
- Docker to simplify the installation and setup of RTLAMR
- Resin.io to deploy this docker container to the Raspberry Pi in my house
- Logging to a Google Spreadsheet so house members can track usage

## Credit

- @besmasher - Built the excellent [RTLAMR](https://github.com/bemasher/rtlamr) library which actually does all the work of reading the meters.
- [Frederik Granna's](https://bitbucket.org/fgranna/) docker base for setting up RTL-SDR on the Raspberry Pi

## Requirements

- **Python 3.14** — The container image is based on the official `python:3.14-slim-trixie` image. Local edits to `daemon.sh` should use `python3` compatible with 3.x (see `.python-version`).
- Raspberry Pi 3 (Might work on others, only tested on the 3)
- [RTL-SDR](https://www.amazon.com/NooElec-NESDR-Mini-Compatible-Packages/dp/B009U7WZCA)
- [Resin.io](https://resin.io) for deployment and installation to the Raspberry pi

### Technical chops

You'll need to be able to do the following to get this to work:

- Clone and push a repository with 'git'
- Write a disk image to an SD card
- Basic script editing

## Installation

1. Signup for [Resin.io](https://resin.io)
1. Create a new Application and download the image for the Raspberry Pi
1. Install the image on the Raspberry Pi
1. Plug in your RTL-SDR into the USB port on the Raspberry Pi
1. `git push` this repository to your Resin application
1. In Resin, view the logs on your device and find your meter ID. This is hardest part. You'll need to know your current reading to match it up to the meter ID. I've not found any correlation between what's written on the meter and the ID being sent out over the air.
1. Once you find your meter ID, enter it as an environment variable in the Resin dashboard under "METERID"
1. At this point it's up to you as to where you want to 'send' the data. You can publish to **MQTT** (recommended for [Home Assistant](https://www.home-assistant.io/integrations/mqtt/)), use a custom HTTP endpoint via `CURL_API`, or log to a Google Spreadsheet (instructions below).

## Repository layout

| Path | Role |
|------|------|
| `scripts/daemon.sh` | RTL TCP + rtlamr loop, MQTT, optional HTTP logging |
| `scripts/watchdog.sh` | Stale-process watchdog (Balena/Resin supervisor reboot) |
| `meter/payload.py` | **Canonical reading JSON** — schema version, timestamp, scaled `consumption`, full rtlamr payload under `radio` |
| `meter/ha_discovery.py` | **Home Assistant MQTT discovery** — retained config on `homeassistant/sensor/.../config` |
| `Dockerfile` | Runtime image: Python 3.14, rtl-sdr, rtlamr, MQTT client |
| `Baseimage/Dockerfile` | Optional: build rtl-sdr from source for custom bases |

Keeping parsing in small Python modules keeps the shell script thin and gives you one place to evolve the data contract (Home Assistant automations, future InfluxDB, etc.).

## MQTT and Home Assistant

When `MQTT_HOST` is set, each successful read publishes a **versioned JSON** reading (see below). Raw rtlamr output is optional on a second topic.

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

### Home Assistant MQTT discovery

When `MQTT_HOST` is set and `MQTT_DISABLE_DISCOVERY` is **not** `1`, the container publishes a **retained** discovery message at startup to:

`{MQTT_DISCOVERY_PREFIX}/sensor/water_meter_{METERID}/config`

(Non-alphanumeric characters in `METERID` are replaced with `_` in the topic `object_id`.)

In Home Assistant, ensure the MQTT integration has **discovery** enabled (it is on by default). The **Water meter** sensor should appear automatically; no manual `configuration.yaml` entry is required for the sensor itself.

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
6. The URL from the last step is now your URL you'll need to setup in Resin
    - Should look like `https://script.google.com/macros/u/1/s/RandomLookingScriptID/exec`
    - In Resin add the environment variable CURL_API with the value of the script from before, but with '?value=' appended
        -  eg. "https://script.google.com/macros/s/RandomLookingScriptID/exec?value="
    - To test it you can send some data with 'curl: `curl -L https://script.google.com/macros/u/1/s/RandomLookingScriptID/exec?value=10`

