#!/bin/bash

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$APP_ROOT"

if [ -z "$METERID" ]; then
  echo "METERID not set, launching in debug mode"
  echo "If you don't know your Meter's ID, you'll need to figure it out manually"
  echo "Easiest way is to go outside and read your meter, then match it to a meter id in the logs"
  echo "Note: It may take a several minutes to read all the nearby meters"

  rtl_tcp &> /dev/null &
  sleep 10 #Let rtl_tcp startup and open a port

  rtlamr -msgtype=r900
  exit 0
fi

# Setup for Metric/CCF
UNIT_DIVISOR=10000
UNIT="CCF" # Hundred cubic feet
if [ ! -z "$METRIC" ]; then
  echo "Setting meter to metric readings"
  UNIT_DIVISOR=1000
  UNIT="Cubic Meters"
fi

export UNIT_DIVISOR UNIT METERID

# Publish to MQTT (Home Assistant, etc.). Set MQTT_HOST to enable.
mqtt_resolve_topic() {
  if [ -n "${MQTT_TOPIC:-}" ]; then
    printf '%s' "$MQTT_TOPIC"
  elif [ -n "${MQTT_TOPIC_PREFIX:-}" ]; then
    printf '%s' "${MQTT_TOPIC_PREFIX}/${METERID}/reading"
  else
    printf '%s' "water_meter"
  fi
}

mqtt_resolve_topic_radio() {
  if [ -n "${MQTT_TOPIC_RADIO:-}" ]; then
    printf '%s' "$MQTT_TOPIC_RADIO"
  elif [ "${MQTT_PUBLISH_RADIO:-}" = "1" ] && [ -n "${MQTT_TOPIC_PREFIX:-}" ]; then
    printf '%s' "${MQTT_TOPIC_PREFIX}/${METERID}/radio"
  else
    printf ''
  fi
}

# Optional third arg: "1" = always retain (used for Home Assistant discovery).
mqtt_publish() {
  local f
  f=$(mktemp)
  printf '%s' "$1" > "$f"
  local port="${MQTT_PORT:-1883}"
  local topic="$2"
  local force_retain="${3:-}"
  local -a cmd=(mosquitto_pub -h "$MQTT_HOST" -p "$port" -t "$topic" -f "$f")
  if [ -n "${MQTT_USER:-}" ]; then
    cmd+=(-u "$MQTT_USER" -P "${MQTT_PASSWORD:-}")
  fi
  if [ "${MQTT_TLS:-}" = "1" ]; then
    cmd+=(--tls-use-os-certs)
  fi
  if [ "${force_retain}" = "1" ] || [ "${MQTT_RETAIN:-}" = "1" ]; then
    cmd+=(-r)
  fi
  if ! "${cmd[@]}"; then
    echo "MQTT publish failed" >&2
  fi
  rm -f "$f"
}

if [ -n "${MQTT_HOST:-}" ] && [ "${MQTT_DISABLE_DISCOVERY:-}" != "1" ]; then
  export MQTT_READING_TOPIC="$(mqtt_resolve_topic)"
  discovery_out=$(python3 -m meter.ha_discovery)
  discovery_topic=$(printf '%s\n' "$discovery_out" | head -n 1)
  discovery_json=$(printf '%s\n' "$discovery_out" | tail -n +2)
  mqtt_publish "$discovery_json" "$discovery_topic" "1"
  echo "Published Home Assistant MQTT discovery to ${discovery_topic}"
fi

# Kill this script (and restart the container) if we haven't seen an update in 30 minutes
# Nasty issue probably related to a memory leak, but this works really well, so not changing it
"$SCRIPT_DIR/watchdog.sh" 30 updated.log &

while true; do
  # Suppress the very verbose output of rtl_tcp and background the process
  rtl_tcp &> /dev/null &
  rtl_tcp_pid=$! # Save the pid for murder later
  sleep 10 #Let rtl_tcp startup and open a port

  json=$(rtlamr -msgtype=r900 -filterid=$METERID -single=true -format=json)
  echo "Meter info: $json"

  payload=$(echo "$json" | python3 -m meter.payload)
  consumption=$(echo "$payload" | python3 -c "import json,sys; print(json.load(sys.stdin)['consumption'])")
  echo "Current consumption: $consumption $UNIT"

  if [ -n "${MQTT_HOST:-}" ]; then
    echo "Publishing to MQTT"
    mqtt_publish "$payload" "$(mqtt_resolve_topic)"
    radio_topic=$(mqtt_resolve_topic_radio)
    if [ -n "$radio_topic" ]; then
      mqtt_publish "$json" "$radio_topic"
    fi
  fi

  # Replace with your custom logging code
  if [ ! -z "$CURL_API" ]; then
    echo "Logging to custom API"
    # For example, CURL_API would be "https://mylogger.herokuapp.com?value="
    # Currently uses a GET request
    curl -L "$CURL_API$consumption"
  fi

  kill $rtl_tcp_pid # rtl_tcp has a memory leak and hangs after frequent use, restarts required - https://github.com/bemasher/rtlamr/issues/49
  sleep 60 # I don't need THAT many updates

  # Let the watchdog know we've done another cycle
  touch updated.log
done
