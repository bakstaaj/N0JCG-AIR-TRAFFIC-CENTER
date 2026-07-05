#!/usr/bin/env bash
# Validate that the Pi can see the dedicated 978 MHz UAT RTL-SDR receiver by serial.
# This compatibility validator is intentionally safe to run while the app service is up:
# it proves the hardware/role contract without stealing the receiver from dump978-fa.
set -u

PROJECT_ROOT="$(pwd)"
REPORT_DIR="runtime/preflight"
STAMP="$(date +%Y%m%d_%H%M%S)"
WORK_DIR="${REPORT_DIR}/uat_978_capability_${STAMP}"
REPORT_PATH="${REPORT_DIR}/pi5_uat_978_capability_${STAMP}.txt"
BASE_URL="${PI_AIR_TRAFFIC_BASE_URL:-http://${PI_AIR_TRAFFIC_HOST:-127.0.0.1}:${PI_AIR_TRAFFIC_PORT:-8090}}"
UAT_SERIAL="${PI_AIR_TRAFFIC_UAT_SERIAL:-00000978}"
PASS_COUNT=0
WARN_COUNT=0
FAIL_COUNT=0

mkdir -p "$REPORT_DIR" "$WORK_DIR"
log(){ printf '%s\n' "$*" | tee -a "$REPORT_PATH"; }
section(){ log ""; log "===== $* ====="; }
pass(){ PASS_COUNT=$((PASS_COUNT+1)); log "PASS: $*"; }
warn(){ WARN_COUNT=$((WARN_COUNT+1)); log "WARN: $*"; }
fail(){ FAIL_COUNT=$((FAIL_COUNT+1)); log "FAIL: $*"; }

json_get(){
  local file="$1" expr="$2"
  python3 - "$file" "$expr" <<'PY_JSON_GET_UAT978_CAPABILITY'
import json, sys
path, expr = sys.argv[1], sys.argv[2]
try:
    value = json.load(open(path, encoding='utf-8'))
except Exception:
    print('')
    raise SystemExit(0)
for part in expr.split('.'):
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break
if isinstance(value, bool): print('true' if value else 'false')
elif value is None: print('')
else: print(value)
PY_JSON_GET_UAT978_CAPABILITY
}

section "Environment"
log "PROJECT_ROOT=$PROJECT_ROOT"
log "BASE_URL=$BASE_URL"
log "UAT_SERIAL=$UAT_SERIAL"
if [[ -f README.md && -d src/backend && -d tools ]]; then pass "repository root appears valid"; else fail "run from repository root"; fi
for cmd in python3 rtl_test timeout grep; do
  if command -v "$cmd" >/dev/null 2>&1; then pass "$cmd available at $(command -v "$cmd")"; else fail "$cmd is required"; fi
done
if command -v curl >/dev/null 2>&1; then pass "curl available at $(command -v curl)"; else warn "curl not available; service role check will be skipped"; fi

section "Static UAT role contract"
ROLE_JSON="runtime/settings/pi_air_traffic_hardware_roles.pi5-flycatcher-serials.json"
if [[ -f "$ROLE_JSON" ]] && python3 -m json.tool "$ROLE_JSON" >/dev/null 2>&1; then
  pass "hardware roles JSON validates"
  if grep -q "$UAT_SERIAL" "$ROLE_JSON"; then pass "hardware roles JSON includes UAT serial $UAT_SERIAL"; else fail "hardware roles JSON does not include UAT serial $UAT_SERIAL"; fi
else
  warn "hardware roles JSON is not present or not valid at $ROLE_JSON"
fi
if grep -q "UAT_SERIAL.*$UAT_SERIAL\|PI_AIR_TRAFFIC_UAT_SERIAL" src/backend/pi_air_traffic_backend.py; then
  pass "backend declares UAT serial contract"
else
  fail "backend UAT serial contract marker missing"
fi

section "RTL-SDR enumeration"
RTL_TEST_OUTPUT="$WORK_DIR/rtl_test_t.txt"
if timeout 20 rtl_test -t > "$RTL_TEST_OUTPUT" 2>&1 || true; then
  if grep -q "SN: *$UAT_SERIAL" "$RTL_TEST_OUTPUT"; then
    pass "rtl_test enumerates UAT RTL-SDR serial $UAT_SERIAL"
  else
    fail "rtl_test did not enumerate UAT serial $UAT_SERIAL"
  fi
else
  fail "rtl_test command failed unexpectedly"
fi
DEVICE_ROWS="$(grep -c 'SN:' "$RTL_TEST_OUTPUT" 2>/dev/null || echo 0)"
log "RTL_DEVICE_ROWS=$DEVICE_ROWS"

section "Service role visibility"
if command -v curl >/dev/null 2>&1; then
  STATUS_JSON="$WORK_DIR/api_status.json"
  if curl -sS --max-time 8 "$BASE_URL/api/status" -o "$STATUS_JSON" && python3 -m json.tool "$STATUS_JSON" >/dev/null 2>&1; then
    pass "/api/status returned JSON"
    if grep -q "$UAT_SERIAL" "$STATUS_JSON"; then pass "/api/status reports UAT serial $UAT_SERIAL"; else warn "/api/status did not expose UAT serial $UAT_SERIAL"; fi
  else
    warn "/api/status unavailable; hardware enumeration already completed"
  fi
fi

section "Decoder binary visibility"
if [[ -x runtime/bin/dump978-fa || -x bin/dump978-fa ]]; then
  pass "app-owned dump978-fa is available for UAT receiver use"
else
  warn "app-owned dump978-fa not found here; decoder tooling validator will check this separately"
fi

section "Summary"
log "Summary: ${PASS_COUNT} PASS, ${WARN_COUNT} WARN, ${FAIL_COUNT} FAIL"
log "Report path: $REPORT_PATH"
log "Work dir: $WORK_DIR"
if [[ "$FAIL_COUNT" -eq 0 ]]; then log "FINAL: PASS"; exit 0; else log "FINAL: FAIL"; exit 1; fi
