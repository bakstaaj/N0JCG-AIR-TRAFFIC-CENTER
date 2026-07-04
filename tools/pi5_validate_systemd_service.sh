#!/usr/bin/env bash
# Validate installed PI Air Traffic Tracker systemd service and LAN UI/API endpoints.

set -Eeuo pipefail

PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
REPORT_DIR="runtime/preflight"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="$REPORT_DIR/pi5_systemd_service_validation_${STAMP}.txt"
PORT="${PI_AIR_TRAFFIC_WEB_PORT:-8090}"
SERVICE_NAME="${PI_AIR_TRAFFIC_SERVICE_NAME:-pi-air-traffic-tracker.service}"

pass() { echo "PASS: $*" | tee -a "$REPORT_PATH"; PASS_COUNT=$((PASS_COUNT + 1)); }
warn() { echo "WARN: $*" | tee -a "$REPORT_PATH"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { echo "FAIL: $*" | tee -a "$REPORT_PATH"; FAIL_COUNT=$((FAIL_COUNT + 1)); }
section() { echo "" | tee -a "$REPORT_PATH"; echo "===== $* =====" | tee -a "$REPORT_PATH"; }

mkdir -p "$REPORT_DIR" runtime/logs
: > "$REPORT_PATH"

if [[ ! -d .git || ! -f src/backend/pi_air_traffic_backend.py || ! -f web/index.html ]]; then
  echo "FAIL: run from PI-AIR-TRAFFIC-TRACKER repository root" | tee -a "$REPORT_PATH"
  exit 1
fi
pass "repo root validated"

section "Systemd state"
if command -v systemctl >/dev/null 2>&1; then
  pass "systemctl available"
else
  fail "systemctl missing"
fi

if systemctl is-enabled "$SERVICE_NAME" >/dev/null 2>&1; then
  pass "$SERVICE_NAME is enabled"
else
  warn "$SERVICE_NAME is not enabled"
fi

if systemctl is-active --quiet "$SERVICE_NAME"; then
  pass "$SERVICE_NAME is active"
else
  fail "$SERVICE_NAME is not active"
  systemctl status "$SERVICE_NAME" --no-pager 2>&1 | tail -n 80 | tee -a "$REPORT_PATH" || true
fi

section "HTTP validation"
if python3 - <<PY
import json
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
    raise RuntimeError(f"/api/status did not report expected status: {last_error}")

for path, marker in [("/", "text/html"), ("/app.js", "javascript"), ("/app.css", "text/css")]:
    status, content_type, body = get(path)
    if status != 200 or marker not in content_type or len(body) < 50:
        raise RuntimeError(f"unexpected {path}: status={status} content_type={content_type} len={len(body)}")

status, content_type, body = get("/api/aircraft.json")
aircraft = json.loads(body.decode("utf-8"))
if not isinstance(aircraft, dict) or not isinstance(aircraft.get("aircraft"), list):
    raise RuntimeError("/api/aircraft.json did not return expected aircraft object")

print(json.dumps({
    "service": payload.get("service"),
    "messages": payload.get("messages"),
    "aircraft_count": payload.get("aircraft_count"),
    "decoder_running": (payload.get("decoder") or {}).get("running"),
    "readsb_json_available": payload.get("readsb_json_available"),
    "audio_receiver_serial": payload.get("audio_receiver_serial"),
}, indent=2, sort_keys=True))
PY
then
  pass "service UI/API endpoints validated"
else
  fail "service UI/API endpoint validation failed"
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

section "Recent service log"
journalctl -u "$SERVICE_NAME" -n 80 --no-pager 2>&1 | tee -a "$REPORT_PATH" || warn "could not read journal for $SERVICE_NAME"

if [[ "$FAIL_COUNT" -eq 0 ]]; then FINAL="PASS"; else FINAL="FAIL"; fi

echo "" | tee -a "$REPORT_PATH"
echo "Report path: $REPORT_PATH" | tee -a "$REPORT_PATH"
echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL" | tee -a "$REPORT_PATH"
echo "FINAL: $FINAL" | tee -a "$REPORT_PATH"
[[ "$FINAL" == "PASS" ]]
