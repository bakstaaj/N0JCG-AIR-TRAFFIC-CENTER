#!/usr/bin/env bash
# Validate Pi web/UI/API operation in foreground/dev mode.

set -Eeuo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
BACKEND_PID=""
REPORT_DIR="runtime/preflight"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="$REPORT_DIR/pi5_ui_api_smoke_${STAMP}.txt"
LOG_PATH="runtime/logs/pi_ui_api_smoke_${STAMP}.log"
STDOUT_PATH="runtime/logs/pi_ui_api_smoke_${STAMP}.stdout"
PORT="${PI_AIR_TRAFFIC_WEB_PORT:-8090}"
HOST="${PI_AIR_TRAFFIC_WEB_HOST:-0.0.0.0}"

pass() { echo "PASS: $*" | tee -a "$REPORT_PATH"; PASS_COUNT=$((PASS_COUNT + 1)); }
warn() { echo "WARN: $*" | tee -a "$REPORT_PATH"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { echo "FAIL: $*" | tee -a "$REPORT_PATH"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
section() { echo "" | tee -a "$REPORT_PATH"; echo "===== $* =====" | tee -a "$REPORT_PATH"; }

cleanup() {
  if [[ -n "${BACKEND_PID:-}" ]] && kill -0 "$BACKEND_PID" >/dev/null 2>&1; then
    kill "$BACKEND_PID" >/dev/null 2>&1 || true
    wait "$BACKEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT

mkdir -p "$REPORT_DIR" runtime/logs runtime/settings runtime/bin
: > "$REPORT_PATH"

if [[ ! -d .git || ! -f src/backend/pi_air_traffic_backend.py || ! -f web/index.html ]]; then
  echo "FAIL: run from PI-AIR-TRAFFIC-TRACKER repository root" | tee -a "$REPORT_PATH"
  exit 1
fi
pass "repo root validated"

section "Prerequisites"
if command -v python3 >/dev/null 2>&1; then pass "python3 available"; else fail "python3 missing"; fi
if command -v rtl_test >/dev/null 2>&1; then pass "rtl_test available"; else fail "rtl_test missing"; fi
if [[ -x runtime/bin/readsb ]]; then pass "app-owned readsb executable exists: runtime/bin/readsb"; else fail "app-owned readsb missing; run ./tools/pi5_install_app_owned_readsb.sh"; fi

if rtl_test -t > "runtime/preflight/pi5_ui_api_smoke_rtl_test_${STAMP}.txt" 2>&1; then
  if grep -q 'SN: 00001090' "runtime/preflight/pi5_ui_api_smoke_rtl_test_${STAMP}.txt" && \
     grep -q 'SN: 00000162' "runtime/preflight/pi5_ui_api_smoke_rtl_test_${STAMP}.txt" && \
     grep -q 'SN: 00000978' "runtime/preflight/pi5_ui_api_smoke_rtl_test_${STAMP}.txt"; then
    pass "expected receiver serials visible to rtl_test"
  else
    fail "expected receiver serials not all visible; see runtime/preflight/pi5_ui_api_smoke_rtl_test_${STAMP}.txt"
  fi
else
  fail "rtl_test -t failed; see runtime/preflight/pi5_ui_api_smoke_rtl_test_${STAMP}.txt"
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
  fail "TCP port $PORT is already in use; stop the service or choose PI_AIR_TRAFFIC_WEB_PORT"
fi

if [[ "$FAIL_COUNT" -ne 0 ]]; then
  echo "" | tee -a "$REPORT_PATH"
  echo "Report path: $REPORT_PATH" | tee -a "$REPORT_PATH"
  echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL" | tee -a "$REPORT_PATH"
  echo "FINAL: FAIL" | tee -a "$REPORT_PATH"
  exit 1
fi

section "Starting backend"
PYTHONUNBUFFERED=1 python3 src/backend/pi_air_traffic_backend.py \
  --host "$HOST" \
  --port "$PORT" \
  --autostart \
  --foreground-log \
  --log-file "$LOG_PATH" \
  --log-level INFO \
  > "$STDOUT_PATH" 2>&1 &
BACKEND_PID="$!"
pass "started Pi backend pid=$BACKEND_PID on ${HOST}:${PORT}"

section "HTTP validation"
if python3 - <<PY
import json
import sys
import time
import urllib.request
port = int("$PORT")
base = f"http://127.0.0.1:{port}"

def get(path, timeout=2.0):
    with urllib.request.urlopen(base + path, timeout=timeout) as response:
        body = response.read()
        return response.status, response.headers.get("Content-Type", ""), body

last_error = None
payload = None
for _ in range(60):
    try:
        status, content_type, body = get("/api/status")
        payload = json.loads(body.decode("utf-8"))
        roles = payload.get("receiver_roles") or {}
        expected = {"adsb": "00001090", "audio": "00000162", "uat": "00000978"}
        for key, serial in expected.items():
            role = roles.get(key) or {}
            if str(role.get("serial")) != serial:
                raise RuntimeError(f"role {key} serial mismatch: expected {serial}, got {role}")
        decoder = payload.get("decoder") or {}
        if not decoder.get("running"):
            raise RuntimeError(f"decoder not running: {decoder}")
        break
    except Exception as exc:
        last_error = exc
        time.sleep(0.5)
else:
    raise RuntimeError(f"/api/status did not report expected Pi status: {last_error}")

checks = [
    ("/", "text/html"),
    ("/app.js", "javascript"),
    ("/app.css", "text/css"),
]
for path, expected_content in checks:
    status, content_type, body = get(path)
    if status != 200 or expected_content not in content_type or len(body) < 50:
        raise RuntimeError(f"unexpected response for {path}: status={status} content_type={content_type} length={len(body)}")

status, content_type, body = get("/api/aircraft.json")
aircraft = json.loads(body.decode("utf-8"))
if not isinstance(aircraft, dict) or not isinstance(aircraft.get("aircraft"), list):
    raise RuntimeError("/api/aircraft.json did not return a readsb-style aircraft object")

print(json.dumps({
    "service": payload.get("service"),
    "messages": payload.get("messages"),
    "aircraft_count": payload.get("aircraft_count"),
    "decoder": payload.get("decoder"),
    "receiver_roles": payload.get("receiver_roles"),
}, indent=2, sort_keys=True))
PY
then
  pass "web root, assets, /api/status, and /api/aircraft.json validated"
else
  fail "HTTP UI/API smoke validation failed"
fi

section "LAN URLs"
ips="$(hostname -I 2>/dev/null | tr ' ' '\n' | grep -E '^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$' | grep -v '^127\.' | sort -u || true)"
if [[ -z "$ips" ]]; then
  warn "could not determine non-loopback IPv4 address"
  echo "Open locally: http://127.0.0.1:${PORT}" | tee -a "$REPORT_PATH"
else
  pass "detected LAN IPv4 address(es)"
  for ip in $ips; do
    echo "URL: http://${ip}:${PORT}" | tee -a "$REPORT_PATH"
  done
fi

cleanup
BACKEND_PID=""

if [[ -s "$STDOUT_PATH" ]]; then pass "backend stdout captured: $STDOUT_PATH"; else warn "backend stdout empty: $STDOUT_PATH"; fi
if [[ -s "$LOG_PATH" ]]; then pass "backend log captured: $LOG_PATH"; else warn "backend log empty: $LOG_PATH"; fi

if [[ "$FAIL_COUNT" -eq 0 ]]; then FINAL="PASS"; else FINAL="FAIL"; fi

echo "" | tee -a "$REPORT_PATH"
echo "Report path: $REPORT_PATH" | tee -a "$REPORT_PATH"
echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL" | tee -a "$REPORT_PATH"
echo "FINAL: $FINAL" | tee -a "$REPORT_PATH"
[[ "$FINAL" == "PASS" ]]
