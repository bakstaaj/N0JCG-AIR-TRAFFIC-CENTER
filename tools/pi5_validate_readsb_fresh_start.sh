#!/usr/bin/env bash
set -u -o pipefail

SCRIPT_NAME="pi5_validate_readsb_fresh_start"
SERVICE_NAME="${PI_AIR_TRAFFIC_SERVICE:-pi-air-traffic-tracker.service}"
HOST="${PI_AIR_TRAFFIC_HOST:-127.0.0.1}"
PORT="${PI_AIR_TRAFFIC_PORT:-8090}"
BASE_URL="http://${HOST}:${PORT}"
EXPECTED_SERIAL="${PI_AIR_TRAFFIC_ADSB_SERIAL:-00001090}"
RUNTIME_ROOT="${RTL_ADSB_TRACKER_RUNTIME:-runtime}"
JSON_DIR="${RUNTIME_ROOT}/settings/readsb-json"
AIRCRAFT_JSON="${JSON_DIR}/aircraft.json"
REPORT_DIR="runtime/preflight"
STAMP="$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="${REPORT_DIR}/pi5_readsb_fresh_start_${STAMP}.txt"
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0
VALIDATION_OK=1
SERVICE_WAS_ACTIVE=0
SENTINEL_TIME=0

mkdir -p "$REPORT_DIR"
exec > >(tee "$REPORT_PATH") 2>&1

pass() { echo "PASS: $*"; PASS_COUNT=$((PASS_COUNT + 1)); }
warn() { echo "WARN: $*"; WARN_COUNT=$((WARN_COUNT + 1)); }
fail() { echo "FAIL: $*"; FAIL_COUNT=$((FAIL_COUNT + 1)); VALIDATION_OK=0; }
section() { echo; echo "===== $* ====="; }

json_get() {
  local expr="$1"
  python3 - "$expr" <<'PY'
import json, sys
expr = sys.argv[1]
payload = json.load(sys.stdin)
cur = payload
for part in expr.split('.'):
    if isinstance(cur, dict):
        cur = cur.get(part)
    else:
        cur = None
        break
if isinstance(cur, (dict, list)):
    print(json.dumps(cur, sort_keys=True))
elif cur is None:
    print('')
else:
    print(cur)
PY
}

cleanup() {
  if [[ "$VALIDATION_OK" -eq 0 ]]; then
    warn "leaving service state unchanged after failed validation attempt"
  fi
}
trap cleanup EXIT

section "Environment"
if [[ -d .git && -f src/backend/pi_air_traffic_backend.py ]]; then
  pass "repository root appears valid"
else
  fail "run from PI-AIR-TRAFFIC-TRACKER repo root"
fi

echo "SERVICE_NAME=$SERVICE_NAME"
echo "BASE_URL=$BASE_URL"
echo "AIRCRAFT_JSON=$AIRCRAFT_JSON"

if command -v systemctl >/dev/null 2>&1; then
  pass "systemctl available"
else
  fail "systemctl is required"
fi
if command -v curl >/dev/null 2>&1; then
  pass "curl available"
else
  fail "curl is required"
fi
if command -v python3 >/dev/null 2>&1; then
  pass "python3 available"
else
  fail "python3 is required"
fi

if [[ "$VALIDATION_OK" -eq 0 ]]; then
  section "Summary"
  echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
  echo "Report path: $REPORT_PATH"
  echo "FINAL: FAIL"
  exit 1
fi

section "Stop service and create stale JSON sentinel"
if systemctl is-active --quiet "$SERVICE_NAME"; then
  SERVICE_WAS_ACTIVE=1
  pass "$SERVICE_NAME was active before test"
else
  warn "$SERVICE_NAME was not active before test; validator will still start it"
fi

if sudo systemctl stop "$SERVICE_NAME"; then
  pass "stopped $SERVICE_NAME"
else
  fail "failed to stop $SERVICE_NAME"
fi

mkdir -p "$JSON_DIR"
SENTINEL_TIME="$(date +%s)"
cat > "$AIRCRAFT_JSON" <<JSON
{"now": ${SENTINEL_TIME}, "messages": 3, "aircraft": [], "stale_startup_sentinel": true}
JSON
pass "wrote stale aircraft.json sentinel with messages=3"
sleep 1

section "Start service"
if sudo systemctl start "$SERVICE_NAME"; then
  pass "started $SERVICE_NAME"
else
  fail "failed to start $SERVICE_NAME"
fi

section "Wait for /api/status"
STATUS_JSON=""
for _ in $(seq 1 30); do
  STATUS_JSON="$(curl -fsS --max-time 2 "${BASE_URL}/api/status" 2>/dev/null || true)"
  if [[ -n "$STATUS_JSON" ]] && printf '%s' "$STATUS_JSON" | python3 -m json.tool >/dev/null 2>&1; then
    pass "/api/status returned JSON"
    break
  fi
  sleep 1
done
if [[ -z "$STATUS_JSON" ]]; then
  fail "/api/status did not become available"
fi

if [[ -n "$STATUS_JSON" ]]; then
  ROLE_SERIAL="$(printf '%s' "$STATUS_JSON" | json_get 'receiver_roles.adsb.serial')"
  if [[ "$ROLE_SERIAL" == "$EXPECTED_SERIAL" ]]; then
    pass "status receiver_roles.adsb.serial=$EXPECTED_SERIAL"
  else
    fail "status receiver_roles.adsb.serial expected $EXPECTED_SERIAL, got ${ROLE_SERIAL:-<empty>}"
  fi

  READSB_CMD="$(printf '%s' "$STATUS_JSON" | json_get 'pi_backend.readsb_command')"
  DECODER_RUNNING="$(printf '%s' "$STATUS_JSON" | json_get 'decoder.running')"
  echo "READSB_CMD=${READSB_CMD:-<empty>}"
  echo "DECODER_RUNNING=${DECODER_RUNNING:-<empty>}"
  if [[ "$READSB_CMD" == *"runtime/bin/readsb"* ]]; then
    pass "status reports app-owned readsb command: $READSB_CMD"
  else
    fail "status did not report app-owned runtime/bin/readsb command: ${READSB_CMD:-<empty>}"
  fi
  if [[ "$DECODER_RUNNING" == "True" || "$DECODER_RUNNING" == "true" ]]; then
    pass "status reports decoder running"
  else
    fail "status decoder.running was not true: ${DECODER_RUNNING:-<empty>}"
  fi
fi

section "Process and JSON freshness"
REPO_ROOT="$(pwd -P)"
READSB_PATTERN="${REPO_ROOT}/runtime/bin/readsb.*--device[ =]${EXPECTED_SERIAL}|${REPO_ROOT}/runtime/bin/readsb.*${EXPECTED_SERIAL}"
if pgrep -af "runtime/bin/readsb" | grep -E -- "$EXPECTED_SERIAL" >/dev/null 2>&1; then
  pass "app-owned readsb process is running for serial $EXPECTED_SERIAL"
  pgrep -af "runtime/bin/readsb" | grep -E -- "$EXPECTED_SERIAL" || true
else
  fail "no app-owned readsb process found for serial $EXPECTED_SERIAL"
  pgrep -af "readsb" || true
fi

FRESH=0
for _ in $(seq 1 30); do
  if [[ -f "$AIRCRAFT_JSON" ]]; then
    if python3 - "$AIRCRAFT_JSON" "$SENTINEL_TIME" <<'PY'
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
sentinel = int(sys.argv[2])
payload = json.loads(p.read_text(encoding='utf-8'))
if payload.get('stale_startup_sentinel'):
    raise SystemExit(1)
messages = int(payload.get('messages', 0))
mtime = int(p.stat().st_mtime)
if mtime <= sentinel:
    raise SystemExit(1)
print(messages)
PY
    then
      FRESH=1
      pass "aircraft.json was replaced/refreshed by readsb"
      break
    fi
  fi
  sleep 1
done
if [[ "$FRESH" -ne 1 ]]; then
  fail "aircraft.json still appears stale or was not refreshed"
  [[ -f "$AIRCRAFT_JSON" ]] && cat "$AIRCRAFT_JSON" || true
fi

section "ADS-B observation"
START_MESSAGES="$(python3 - "$AIRCRAFT_JSON" <<'PY'
import json, sys
try:
    print(int(json.load(open(sys.argv[1], encoding='utf-8')).get('messages', 0)))
except Exception:
    print(0)
PY
)"
echo "START_MESSAGES=$START_MESSAGES"
sleep 20
END_MESSAGES="$(python3 - "$AIRCRAFT_JSON" <<'PY'
import json, sys
try:
    payload = json.load(open(sys.argv[1], encoding='utf-8'))
    print(int(payload.get('messages', 0)))
except Exception:
    print(0)
PY
)"
echo "END_MESSAGES=$END_MESSAGES"
if [[ "$END_MESSAGES" -gt "$START_MESSAGES" ]]; then
  pass "ADS-B messages increased after service fresh start: $START_MESSAGES -> $END_MESSAGES"
elif [[ "$END_MESSAGES" -gt 3 ]]; then
  warn "ADS-B messages are above stale sentinel but did not increase during short observation: $START_MESSAGES -> $END_MESSAGES"
else
  fail "ADS-B messages did not move beyond stale sentinel: $START_MESSAGES -> $END_MESSAGES"
fi

section "Summary"
echo "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
echo "Report path: $REPORT_PATH"
if [[ "$VALIDATION_OK" -eq 1 ]]; then
  echo "FINAL: PASS"
  exit 0
else
  echo "FINAL: FAIL"
  exit 1
fi
