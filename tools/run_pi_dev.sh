#!/usr/bin/env bash
# Development runner placeholder for the Pi port.
# This will be tightened once the Pi backend entry point is created.

set -Eeuo pipefail

if [[ ! -d web || ! -d src ]]; then
  echo "FAIL: run from PI-AIR-TRAFFIC-TRACKER repository root"
  exit 1
fi

if [[ -f src/backend/pi_air_traffic_backend.py ]]; then
  exec python3 src/backend/pi_air_traffic_backend.py --host 0.0.0.0 --port 8090
elif [[ -f src/backend/rtl_windows_pi_port_backend.py ]]; then
  echo "WARN: using Windows baseline backend name; Pi backend refactor is not complete yet"
  exec python3 src/backend/rtl_windows_pi_port_backend.py --host 0.0.0.0 --port 8090
else
  echo "FAIL: no known backend entry point found"
  exit 1
fi
