#!/usr/bin/env bash
# Validate manual UAT 978 backend API controls without enabling autostart.
set -u

PROJECT_ROOT="$(pwd)"
REPORT_DIR="runtime/preflight"
WORK_DIR="${REPORT_DIR}/uat_backend_api_$(date +%Y%m%d_%H%M%S)"
REPORT_PATH="${REPORT_DIR}/pi5_uat_backend_api_$(date +%Y%m%d_%H%M%S).txt"
BASE_URL="${PI_AIR_TRAFFIC_BASE_URL:-http://${PI_AIR_TRAFFIC_HOST:-127.0.0.1}:${PI_AIR_TRAFFIC_PORT:-8090}}"
UAT_SERIAL="${PI_AIR_TRAFFIC_UAT_SERIAL:-00000978}"
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

mkdir -p "$REPORT_DIR" "$WORK_DIR"
log() { printf '%s\n' "$*" | tee -a "$REPORT_PATH"; }
section() { log ""; log "===== $* ====="; }
pass() { PASS_COUNT=$((PASS_COUNT+1)); log "PASS: $*"; }
warn() { WARN_COUNT=$((WARN_COUNT+1)); log "WARN: $*"; }
fail() { FAIL_COUNT=$((FAIL_COUNT+1)); log "FAIL: $*"; }

json_get() {
  local file="$1"
  local expr="$2"
  python3 - "$file" "$expr" <<'PY'
import json, sys
path, expr = sys.argv[1], sys.argv[2]
try:
    value = json.load(open(path, encoding='utf-8'))
except Exception:
    print('')
    raise SystemExit(0)
for part in expr.split('.'):
    if not part:
        continue
    value = value.get(part) if isinstance(value, dict) else None
if isinstance(value, bool):
    print('true' if value else 'false')
elif value is None:
    print('')
else:
    print(value)
PY
}

post_empty() {
  local path="$1"
  local out="$2"
  curl -sS --max-time 15 -X POST -H 'Content-Type: application/json' -d '{}' "$BASE_URL$path" -o "$out"
}

section "Environment"
log "PROJECT_ROOT=$PROJECT_ROOT"
log "BASE_URL=$BASE_URL"
log "UAT_SERIAL=$UAT_SERIAL"
if [[ -f README.md && -d src/backend && -d tools ]]; then
  pass "repository root appears valid"
else
  fail "run from the PI-AIR-TRAFFIC-TRACKER repository root"
fi
for cmd in python3 curl pgrep sed awk; do
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$cmd available at $(command -v "$cmd")"
  else
    fail "$cmd is required"
  fi
done

section "Service readiness"
if command -v systemctl >/dev/null 2>&1; then
  if systemctl is-active --quiet pi-air-traffic-tracker.service; then
    pass "pi-air-traffic-tracker.service is active"
  else
    fail "pi-air-traffic-tracker.service is not active"
  fi
else
  warn "systemctl unavailable; skipping service active check"
fi
STATUS_READY=0
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  if curl -sS --max-time 5 "$BASE_URL/api/status" -o "$WORK_DIR/status_ready.json" \
      && python3 -m json.tool "$WORK_DIR/status_ready.json" >/dev/null 2>&1; then
    STATUS_READY=1
    break
  fi
  sleep 1
 done
if [[ "$STATUS_READY" -eq 1 ]]; then
  pass "/api/status returned JSON"
else
  fail "/api/status did not become ready"
fi

section "Initial UAT status"
STOP_CLEANUP_JSON="$WORK_DIR/uat_stop_cleanup.json"
post_empty "/api/uat/stop" "$STOP_CLEANUP_JSON" >/dev/null 2>&1 || true
UAT_STATUS_JSON="$WORK_DIR/uat_status_initial.json"
if curl -sS --max-time 10 "$BASE_URL/api/uat/status" -o "$UAT_STATUS_JSON" \
    && python3 -m json.tool "$UAT_STATUS_JSON" >/dev/null 2>&1; then
  pass "/api/uat/status returned JSON"
else
  fail "/api/uat/status did not return parseable JSON"
fi
cat "$UAT_STATUS_JSON" | tee -a "$REPORT_PATH" >/dev/null 2>&1 || true
status_serial="$(json_get "$UAT_STATUS_JSON" serial)"
status_available="$(json_get "$UAT_STATUS_JSON" available)"
status_manual="$(json_get "$UAT_STATUS_JSON" manual_control_enabled)"
status_persistent="$(json_get "$UAT_STATUS_JSON" persistent_enabled)"
status_running="$(json_get "$UAT_STATUS_JSON" running)"
log "INITIAL_UAT_SERIAL=$status_serial"
log "INITIAL_UAT_AVAILABLE=$status_available"
log "INITIAL_UAT_MANUAL_CONTROL=$status_manual"
log "INITIAL_UAT_PERSISTENT_ENABLED=$status_persistent"
log "INITIAL_UAT_RUNNING=$status_running"
[[ "$status_serial" == "$UAT_SERIAL" ]] && pass "UAT status reports expected serial" || fail "UAT status serial mismatch"
[[ "$status_available" == "true" ]] && pass "app-owned dump978-fa is available to backend" || fail "backend does not report app-owned dump978-fa available"
[[ "$status_manual" == "true" ]] && pass "manual UAT control is enabled" || fail "manual UAT control not enabled"
[[ "$status_persistent" == "false" ]] && pass "persistent UAT autostart remains disabled" || fail "persistent UAT autostart should remain disabled"
[[ "$status_running" == "false" ]] && pass "UAT decoder starts stopped" || warn "UAT decoder was already running before start test"

section "Start UAT decoder"
START_JSON="$WORK_DIR/uat_start.json"
if post_empty "/api/uat/start" "$START_JSON" && python3 -m json.tool "$START_JSON" >/dev/null 2>&1; then
  pass "/api/uat/start returned JSON"
else
  cat "$START_JSON" 2>/dev/null | tee -a "$REPORT_PATH" >/dev/null || true
  fail "/api/uat/start did not return parseable JSON"
fi
cat "$START_JSON" | tee -a "$REPORT_PATH" >/dev/null 2>&1 || true
started="$(json_get "$START_JSON" started)"
running="$(json_get "$START_JSON" running)"
verified="$(json_get "$START_JSON" startup_verified)"
log "UAT_START_STARTED=$started"
log "UAT_START_RUNNING=$running"
log "UAT_START_VERIFIED=$verified"
if [[ "$started" == "true" || "$(json_get "$START_JSON" already_running)" == "true" ]]; then
  pass "UAT start accepted"
else
  fail "UAT start was not accepted"
fi
[[ "$running" == "true" ]] && pass "UAT decoder reports running after start" || fail "UAT decoder did not report running after start"

section "Running UAT status poll"
RUNNING_OK=0
PORT_OK=0
for attempt in 1 2 3 4 5 6 7 8 9 10; do
  POLL_JSON="$WORK_DIR/uat_status_running_${attempt}.json"
  if curl -sS --max-time 10 "$BASE_URL/api/uat/status" -o "$POLL_JSON" \
      && python3 -m json.tool "$POLL_JSON" >/dev/null 2>&1; then
    poll_running="$(json_get "$POLL_JSON" running)"
    poll_json_open="$(json_get "$POLL_JSON" json_port_open)"
    poll_raw_open="$(json_get "$POLL_JSON" raw_port_open)"
    log "UAT_STATUS_ATTEMPT=$attempt RUNNING=$poll_running JSON_PORT_OPEN=$poll_json_open RAW_PORT_OPEN=$poll_raw_open"
    if [[ "$poll_running" == "true" ]]; then
      RUNNING_OK=1
    fi
    if [[ "$poll_json_open" == "true" ]]; then
      PORT_OK=1
      break
    fi
  fi
  sleep 1
 done
[[ "$RUNNING_OK" -eq 1 ]] && pass "UAT decoder remained running during poll" || fail "UAT decoder did not remain running"
[[ "$PORT_OK" -eq 1 ]] && pass "UAT JSON port opened while decoder running" || fail "UAT JSON port did not open"

PROCESS_LIST="$WORK_DIR/processes_running.txt"
pgrep -af 'dump978-fa|dump978|uat' > "$PROCESS_LIST" 2>/dev/null || true
cat "$PROCESS_LIST" | tee -a "$REPORT_PATH" >/dev/null
if grep -q -- "$UAT_SERIAL" "$PROCESS_LIST"; then
  pass "running dump978-fa process mentions UAT serial $UAT_SERIAL"
else
  fail "no running dump978-fa process mentions UAT serial $UAT_SERIAL"
fi

section "Status enrichment"
STATUS_JSON="$WORK_DIR/status_with_uat.json"
if curl -sS --max-time 10 "$BASE_URL/api/status" -o "$STATUS_JSON" \
    && python3 -m json.tool "$STATUS_JSON" >/dev/null 2>&1; then
  pass "/api/status returned JSON with UAT running"
  status_uat_running="$(json_get "$STATUS_JSON" uat_978.running)"
  status_uat_serial="$(json_get "$STATUS_JSON" uat_978.serial)"
  log "STATUS_UAT_RUNNING=$status_uat_running"
  log "STATUS_UAT_SERIAL=$status_uat_serial"
  [[ "$status_uat_running" == "true" ]] && pass "/api/status reports UAT running" || fail "/api/status did not report UAT running"
  [[ "$status_uat_serial" == "$UAT_SERIAL" ]] && pass "/api/status reports expected UAT serial" || fail "/api/status UAT serial mismatch"
else
  fail "/api/status failed while UAT running"
fi

section "Stop UAT decoder"
STOP_JSON="$WORK_DIR/uat_stop.json"
if post_empty "/api/uat/stop" "$STOP_JSON" && python3 -m json.tool "$STOP_JSON" >/dev/null 2>&1; then
  pass "/api/uat/stop returned JSON"
else
  cat "$STOP_JSON" 2>/dev/null | tee -a "$REPORT_PATH" >/dev/null || true
  fail "/api/uat/stop did not return parseable JSON"
fi
cat "$STOP_JSON" | tee -a "$REPORT_PATH" >/dev/null 2>&1 || true
stopped="$(json_get "$STOP_JSON" stopped)"
final_running="$(json_get "$STOP_JSON" running)"
log "UAT_STOP_STOPPED=$stopped"
log "UAT_STOP_RUNNING=$final_running"
[[ "$stopped" == "true" || "$(json_get "$STOP_JSON" already_stopped)" == "true" ]] && pass "UAT stop accepted" || fail "UAT stop was not accepted"
[[ "$final_running" == "false" ]] && pass "UAT decoder reports stopped" || fail "UAT decoder still reports running after stop"

sleep 1
FINAL_STATUS_JSON="$WORK_DIR/uat_status_final.json"
curl -sS --max-time 10 "$BASE_URL/api/uat/status" -o "$FINAL_STATUS_JSON" || true
if python3 -m json.tool "$FINAL_STATUS_JSON" >/dev/null 2>&1; then
  final_status_running="$(json_get "$FINAL_STATUS_JSON" running)"
  log "FINAL_UAT_RUNNING=$final_status_running"
  [[ "$final_status_running" == "false" ]] && pass "final UAT status is stopped" || fail "final UAT status is still running"
else
  fail "final /api/uat/status did not return JSON"
fi
PROCESS_FINAL="$WORK_DIR/processes_final.txt"
pgrep -af 'dump978-fa.*00000978|dump978-fa.*serial=00000978' > "$PROCESS_FINAL" 2>/dev/null || true
if [[ -s "$PROCESS_FINAL" ]]; then
  cat "$PROCESS_FINAL" | tee -a "$REPORT_PATH" >/dev/null
  fail "UAT dump978-fa process still appears to be running after stop"
else
  pass "no UAT dump978-fa process remains after stop"
fi

section "Summary"
log "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
log "Report path: $REPORT_PATH"
log "Work dir: $WORK_DIR"
if [[ "$FAIL_COUNT" -eq 0 ]]; then
  log "FINAL: PASS"
  exit 0
else
  log "FINAL: FAIL"
  exit 1
fi
