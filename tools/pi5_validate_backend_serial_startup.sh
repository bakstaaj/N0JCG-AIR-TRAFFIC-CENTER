#!/usr/bin/env bash
# Validate the Pi serial backend can resolve receivers and keep readsb alive.

set -Eeuo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
BACKEND_PID=""
REPORT_DIR="runtime/preflight"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="$REPORT_DIR/pi5_backend_serial_startup_${STAMP}.txt"
LOG_PATH="runtime/logs/pi_backend_serial_startup_test.log"
PORT="${PI_AIR_TRAFFIC_TEST_PORT:-8091}"

pass() { echo "PASS: $*" | tee -a "$REPORT_PATH"; PASS_COUNT=$((PASS_COUNT + 1)); }
warn() { echo "WARN: $*" | tee -a "$REPORT_PATH"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { echo "FAIL: $*" | tee -a "$REPORT_PATH"; FAIL_COUNT=$((FAIL_COUNT + 1)); }

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

mkdir -p "$REPORT_DIR" runtime/logs runtime/settings
: > "$REPORT_PATH"

if [[ ! -d .git || ! -f src/backend/pi_air_traffic_backend.py || ! -d web ]]; then
  echo "FAIL: run from PI-AIR-TRAFFIC-TRACKER repository root" | tee -a "$REPORT_PATH"
  exit 1
fi
pass "repo root validated"

if command -v python3 >/dev/null 2>&1; then pass "python3 available"; else fail "python3 missing"; fi
if command -v rtl_test >/dev/null 2>&1; then pass "rtl_test available"; else fail "rtl_test missing"; fi
if command -v readsb >/dev/null 2>&1 || command -v dump1090 >/dev/null 2>&1; then pass "ADS-B decoder command available"; else fail "readsb/dump1090 missing"; fi

if [[ "$FAIL_COUNT" -ne 0 ]]; then
  echo "" | tee -a "$REPORT_PATH"
  echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL" | tee -a "$REPORT_PATH"
  echo "FINAL: FAIL" | tee -a "$REPORT_PATH"
  exit 1
fi

if python3 - <<PY
import socket
port = int("$PORT")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.settimeout(0.5)
try:
    rc = s.connect_ex(("127.0.0.1", port))
finally:
    s.close()
raise SystemExit(1 if rc == 0 else 0)
PY
then
  pass "TCP port $PORT appears free"
else
  fail "TCP port $PORT is already in use"
fi

python3 src/backend/pi_air_traffic_backend.py \
  --host 127.0.0.1 \
  --port "$PORT" \
  --autostart \
  --foreground-log \
  --log-file "$LOG_PATH" \
  --log-level DEBUG \
  > "runtime/logs/pi_backend_serial_startup_test.stdout" 2>&1 &
BACKEND_PID="$!"
pass "started Pi backend test process pid=$BACKEND_PID"

if python3 - <<PY
import json
import sys
import time
import urllib.request
port = int("$PORT")
url = f"http://127.0.0.1:{port}/api/status"
deadline = time.time() + 60.0
last_error = None
while time.time() < deadline:
    try:
        with urllib.request.urlopen(url, timeout=1.5) as response:
            payload = json.loads(response.read().decode("utf-8"))
        print(json.dumps(payload, indent=2, sort_keys=True))
        roles = payload.get("receiver_roles") or {}
        expected = {
            "adsb": "00001090",
            "audio": "00000162",
            "uat": "00000978",
        }
        for key, serial in expected.items():
            role = roles.get(key) or {}
            if str(role.get("serial")) != serial:
                raise RuntimeError(f"role {key} serial mismatch: expected {serial}, got {role}")
        decoder = payload.get("decoder") or {}
        if not decoder.get("running"):
            raise RuntimeError(f"decoder not running: {decoder}")
        sys.exit(0)
    except Exception as exc:
        last_error = exc
        time.sleep(0.5)
print(f"LAST_ERROR: {last_error}", file=sys.stderr)
sys.exit(1)
PY
then
  pass "backend status reports expected serial roles and running ADS-B decoder"
else
  fail "backend did not report expected serial roles/running decoder"
fi

if [[ -f runtime/settings/readsb-json/aircraft.json ]]; then
  pass "readsb aircraft JSON file exists"
else
  warn "readsb aircraft JSON file not present yet; decoder may need live RF messages before writing JSON"
fi

if [[ -s "$LOG_PATH" ]]; then
  pass "backend/readsb log captured: $LOG_PATH"
else
  warn "backend/readsb log is empty: $LOG_PATH"
fi

cleanup
BACKEND_PID=""

if [[ "$FAIL_COUNT" -eq 0 ]]; then
  FINAL="PASS"
else
  FINAL="FAIL"
fi

echo "" | tee -a "$REPORT_PATH"
echo "Report path: $REPORT_PATH" | tee -a "$REPORT_PATH"
echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL" | tee -a "$REPORT_PATH"
echo "FINAL: $FINAL" | tee -a "$REPORT_PATH"

[[ "$FINAL" == "PASS" ]]
